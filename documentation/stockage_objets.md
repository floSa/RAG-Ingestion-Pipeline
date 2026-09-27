# Stockage d'objets

## Rôle

Le stockage d'objets conserve les médias récupérés pendant l'ingestion : crops
PNG des images et tableaux des PDF, images des captures HTML et des notes
Markdown dans leur format d'origine. Il permet à un RAG multimodal de rendre des
réponses qui incluent les images de la source, sans alourdir le graphe ni
l'index vectoriel.

Le serveur est SeaweedFS, seul stockage d'objets de la pile depuis le
25 septembre 2026 ; MinIO, qui le précédait, a été retiré ce jour-là. Le code ne
nomme pas le serveur : le pipeline et l'agent parlent à une **passerelle S3** par
un client générique, et seule la variable `S3_ENDPOINT` désigne le serveur.
Changer de serveur ne touche donc à aucune ligne de téléversement.

Exploitation (conteneur, variables, identités, sonde, diagnostic) :
[`services/stockage_objet.md`](services/stockage_objet.md).

## Le client S3

La bibliothèque cliente Python est `minio` (minio-py), un client S3 générique
dont le nom ne dit rien du serveur en face. Le client est construit à un seul
endroit, `images.build_client` (`src/docling_service/images.py`), sans TLS : la
passerelle n'est jointe que sur le réseau Docker interne. `src/pipeline/media.py`
passe par cette fonction.

Les deux classes de réglages qui construisent un client (pipeline Dagster et
service d'extraction) héritent de `ReglagesDuStockageObjet`
(`src/reglages_s3.py`) : bucket et adresse ne peuvent pas diverger d'un côté à
l'autre. `S3_ENDPOINT`, `S3_ACCESS_KEY` et `S3_SECRET_KEY` n'y ont aucune
valeur par défaut ; `S3_BUCKET` vaut `documents` par défaut. Pourquoi, et d'où
viennent les identifiants : [livraison.md §6.2](livraison.md#62-ladresse-du-stockage-na-aucune-valeur-par-défaut).

## Qui écrit quoi

| Média | Écrit par | Clé d'objet |
|---|---|---|
| crops des PDF (`picture`, `table`…) | `docling-service`, `images.crop_and_upload` | `images/{nom_du_pdf}/{element_id}_{label}.png` |
| images référencées par une note Markdown | `docling-service`, `images.upload_file` | `images/md/{doc_key}/{rang:04d}_{nom}` |
| images base64 des captures HTML | Dagster, pendant le nettoyage, `media.ExportateurDImages` | `images/html/{doc_key}/img_{rang:04d}.{ext}` |

`{nom_du_pdf}` est le nom du fichier sans extension, `{element_id}` l'identifiant
de l'élément (10 caractères hexadécimaux), `{doc_key}` le chemin du document
assaini. Exemple : `images/statisticsfordatascience/<element_id>_picture.png`.

Une table HTML est du texte : elle ne produit aucun objet.

Le bucket **`documents`** est vérifié au démarrage du service d'extraction, et
créé s'il manque (`images.ensure_bucket`).

## L'adresse et la clé

Le graphe et les métadonnées ChromaDB publient, pour un élément visuel qui a un
objet, deux champs : `media_url`, l'adresse en style chemin
`http://<S3_ENDPOINT>/<bucket>/<clé>` (`images.object_url`), et `object_key`, la
clé nue passée à `put_object` (`images.object_key`, inverse exact de
`object_url`). Définition du contrat :
[`llm_integration_plan.md` §4.3](llm_integration_plan.md#43-stockage-objet--bucket-documents).

**L'adresse est interne et authentifiée, jamais publique.** Un `GET` anonyme y
rend 403, y compris depuis un conteneur de `rag_network`, et l'hôte est un nom
de service Docker qui ne se résout pas hors de ce réseau. `rag-agent-chat` sert
de proxy : il lit l'objet avec son jeu d'identifiants en lecture seule et le
re-sert, sans jamais transmettre l'adresse à un navigateur. Deux alternatives
sont écartées dans la docstring de `images.object_url` : un bucket public en
lecture, et des URL présignées, qui expireraient alors que le graphe est
durable.

**La clé survit à l'adresse.** L'adresse porte l'hôte et devient fausse quand il
change, comme au changement de serveur du 25 septembre 2026. La clé est
l'identité de l'objet : un consommateur qui veut relire, compter ou rapprocher
un objet d'un listing utilise `object_key` sans décomposer l'adresse.

## Deux jeux d'identifiants

Le pipeline écrit, avec le jeu RW (`make_bucket` exige `Admin`) ; l'agent ne
fait que lire et lister, avec le jeu RO. Avec un seul jeu partagé, tout lecteur
pourrait effacer le corpus d'images. Droits et secrets :
[`SECURITY.md`](SECURITY.md#stockage-objet--deux-jeux-didentifiants).

## Problèmes résolus

- **Défaillance silencieuse au démarrage (images fantômes).** Le stockage
  pouvait être injoignable pendant les premières secondes, ou son nom de service
  Docker pas encore résolu, et le service d'extraction échouait sans réessayer.
  `images.ensure_bucket()` réessaie désormais 15 fois, à 5 secondes
  d'intervalle, et journalise l'adresse visée à chaque tentative.
- **Une adresse par défaut qui survivait au serveur qu'elle désignait.**
  `python -m src.wipe_stores` vide le bucket que désignent les réglages ; une
  adresse par défaut lui aurait fait purger un autre serveur que celui de la
  pile. Les réglages refusent désormais de se construire sans `S3_ENDPOINT`
  ([livraison.md §6.2](livraison.md#62-ladresse-du-stockage-na-aucune-valeur-par-défaut)).
- **Identifiants vides côté Dagster.** Le `.env` ne porte que `SEAWEEDFS_RW_*` ;
  sans la dérivation de `S3_ACCESS_KEY` / `S3_SECRET_KEY` dans
  `docker-compose.yml` pour `dagster-webserver` et `dagster-daemon`, le client
  partait aux identifiants vides : 403 à chaque téléversement d'image HTML,
  aucune erreur au démarrage (registre §4.28.b). Les réglages refusent désormais
  un identifiant vide.
