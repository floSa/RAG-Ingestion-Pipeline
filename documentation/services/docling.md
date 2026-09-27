# Docling Service (extraction documentaire)

## Rôle

Microservice FastAPI qui convertit un document (PDF, HTML, Markdown) en éléments
structurés et les écrit dans les stores. Docling (IBM) fait l'analyse de mise en
page, PyMuPDF le crop des images des PDF. **Seul service à écrire dans
NebulaGraph et ChromaDB.** Dans le stockage objet, il écrit les crops des PDF et
les images des notes Markdown ; les images des captures HTML y sont déposées en
amont par l'asset de nettoyage Dagster (`src/pipeline/media.py`, préfixe
`images/html/`).

Ce que le service fait des documents (conversion, identité, hiérarchie,
découpage, médias) est décrit dans
[`extraction_donnees.md`](../extraction_donnees.md).

## Conteneur

| | |
|---|---|
| Service compose | `docling-service` |
| Conteneur | `rag_assistant-docling-service-1` |
| Image | construite depuis `Dockerfile.docling` (base `python:3.12-slim`), utilisateur `docling` (uid 1000) |
| Commande | `uvicorn src.docling_service.main:app --host 0.0.0.0 --port 8000` |
| Port | 8000, interne à `rag_network` (`expose`), non publié sur l'hôte |
| Redémarrage | `restart: always` |
| Réseau | `rag_network` |

L'image embarque les wheels `torch==2.5.1`, `torchvision==0.20.1` et
`torchaudio==2.5.1` de l'index CUDA 12.1 : les wheels `+cu121` n'existent pas
sur PyPI. Elle **n'exige pas de GPU** : sans runtime nvidia, `torch` retombe sur
le processeur. Les autres versions sont épinglées dans
`src/docling_service/requirements.txt` (`docling==2.117.0`,
`chromadb==0.6.3`, `minio==7.2.20`, `pymupdf==1.28.0`,
`sentence-transformers==5.6.1`…).

## Ressources

| Ressource | Valeur | Source |
|---|---|---|
| Mémoire | limite 10 Go | `deploy.resources.limits.memory: 10G` |
| Mémoire partagée | 2 Go | `shm_size: 2gb` |
| GPU | aucun par défaut | superposer `docker-compose.gpu.yml` (un GPU nvidia réservé) |
| Poids de l'image | 10,4 Go | registre §6.12, ouvert |

Le compose principal ne réserve aucun GPU : une réservation écrite en dur
empêcherait de créer le conteneur sur une machine sans runtime nvidia
(« could not select device driver "nvidia" »). Pour rendre un GPU au service :

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --no-deps docling-service
```

Le poids de l'image vient des bibliothèques CUDA embarquées par `torch`, alors
que la chaîne tourne sur processeur. Passer aux wheels CPU allégerait l'image
de plusieurs gigaoctets ; ce changement demande une reconstruction et une
réingestion de contrôle (mêmes éléments, mêmes vecteurs).

## Volumes

| Montage | Cible | Rôle |
|---|---|---|
| `./Datas` | `/opt/dagster/app/Datas` | le corpus, au même chemin que dans les conteneurs Dagster |
| `./src` | `/app/src` | le code, monté par-dessus celui de l'image |
| volume nommé `docling_models` | `/tmp/.cache` | cache des modèles Docling et d'embedding (`HOME=/tmp`), conservé entre deux recréations |

Le code monté par `./src` prime sur celui copié dans l'image : une modification
de `src/` prend effet au redémarrage du service, sans reconstruction. Une
modification de `requirements.txt` ou de `Dockerfile.docling` demande une
reconstruction.

## API

| Méthode | Endpoint | Corps | Réponse |
|---|---|---|---|
| POST | `/extract` | `{"filepath": "/opt/.../fichier.pdf", "source_path": "pdfs/fichier.pdf"}` | `{"job_id": "a1b2c3d4e5f6", "status": "pending"}` |
| GET | `/jobs/{job_id}` | — | état, avancement, erreur éventuelle, durée |
| GET | `/health` | — | état de la file et disponibilité des stores |

`source_path` (chemin relatif à `Datas/`, clé de partition Dagster) porte
l'identité du document ; absent, le service le déduit du chemin
(`extraction._deduce_source_path`). Schéma : `ExtractRequest` dans
`src/pipeline/schemas.py`.

| Code | Endpoint | Signification |
|---|---|---|
| 404 | `/extract` | fichier introuvable |
| 415 | `/extract` | extension non prise en charge (`.pdf`, `.html`, `.htm`, `.md`, `.markdown` acceptées) |
| 404 | `/jobs/{id}` | job inconnu (service redémarré, ou job sorti de l'historique) |
| 503 | `/health` | worker arrêté, ou graphe, bucket ou modèles pas encore prêts |

Exemple de réponse `/jobs/{job_id}` :

```json
{
  "job_id": "a1b2c3d4e5f6",
  "filepath": "/opt/dagster/app/Datas/pdfs/statisticsfordatascience.pdf",
  "status": "running",
  "error": null,
  "progress": {
    "source_path": "pdfs/statisticsfordatascience.pdf",
    "pages_total": 412,
    "pages_done": 145,
    "elements": 3820,
    "chunks": 4611,
    "failed_batches": []
  },
  "elapsed_seconds": 1832.4
}
```

`status` vaut `pending`, `running`, `success` ou `failed`.

## Modèle d'exécution

L'extraction d'un livre de plusieurs centaines de pages dure des heures : elle
ne se fait pas dans la requête HTTP.

1. `POST /extract` valide le fichier, le met en file et rend un `job_id`. Un
   fichier déjà en attente ou en cours rend le job existant (`JobQueue.submit`).
2. Un **worker unique** déroule les jobs un par un. La conversion sature déjà la
   machine ; le débit global est cadencé en amont par la file Dagster
   (`max_concurrent_runs: 2` dans `dagster.yaml`).
3. L'asset Dagster interroge `GET /jobs/{job_id}` : premier sondage immédiat,
   puis intervalle doublé jusqu'à `extraction_poll_seconds` (15 s,
   `src/pipeline/settings.py`).

`/health` et `/jobs` répondent pendant une conversion. La file vit **en
mémoire** : un redémarrage perd les jobs en cours, et le sondage suivant reçoit
un 404. L'asset lève alors une erreur transitoire que sa politique de reprise
(`EXTRACTION_RETRY_POLICY`, deux reprises, `src/pipeline/factory.py`) rattrape
sans intervention. Les `JOB_HISTORY_SIZE` (500) derniers jobs terminés restent
consultables.

## Modules

| Module | Responsabilité |
|---|---|
| `main.py` | application FastAPI, endpoints, initialisation au démarrage |
| `jobs.py` | file de jobs et worker unique |
| `extraction.py` | conversion Docling, pagination des PDF, orchestration d'un document |
| `elements.py` | taxonomie des labels, identité, hiérarchie et positions des éléments |
| `markdown.py` | Markdown : extraction des images, normalisation des paragraphes |
| `storage.py` | persistance d'un lot (graphe puis vecteurs), purge d'un document |
| `nebula.py` | pool partagé, sessions, écritures groupées, schéma |
| `ngql.py` | échappement et construction des requêtes nGQL |
| `vectors.py` | découpage, embeddings par lots et upsert ChromaDB |
| `chunking.py` | ce que le modèle d'embedding reçoit, la forme de l'id de chunk, le filtre du bruit |
| `images.py` | crop PyMuPDF, envoi d'objets ; seul endroit où le client S3 est construit |
| `anchoring.py` | rattachement des chunks Docling aux éléments du contrat |
| `hierarchy.py` | rattachement de chaque titre à son titre parent |
| `ranking.py` | rang d'un titre, quelle que soit la source |
| `matter.py` | repérage des parties d'un ouvrage qui ne sont pas du contenu (index, table des matières…) |
| `language.py` | détection de la langue d'un document |
| `embedding.py` | chargement et verrouillage du modèle d'embedding |
| `settings.py` | configuration du service (pydantic-settings) |

**Quatorze modules ne dépendent que de la bibliothèque standard**, et leur
logique est donc testée sans Docling, sans torch et sans GPU.

**Le critère.** Le périmètre est les **18 modules** de `src/docling_service/` :
les `*.py` du répertoire, moins le marqueur de paquet `__init__.py`, qui est
vide. Un module porte une dépendance externe quand une instruction `import` ou
`from ... import` du **corps du module** (donc ni dans une fonction, ni dans une
méthode, ni derrière un `if`) nomme un paquet racine qui n'est ni un import
relatif, ni `src` ou `docling_service`, ni membre de `sys.stdlib_module_names`.
Le balayage se fait à l'AST et est rejoué par
`tests/unit/test_dependances_de_niveau_module.py`.

Les quatorze : `anchoring.py`, `chunking.py`, `elements.py`, `embedding.py`,
`hierarchy.py`, `jobs.py`, `language.py`, `markdown.py`, `matter.py`,
`nebula.py`, `ngql.py`, `ranking.py`, `storage.py`, `vectors.py`.

**Les quatre autres** : `extraction.py` (`bs4`),
`images.py` (`minio`, la bibliothèque cliente S3), `main.py` (`fastapi`),
`settings.py` (`pydantic_settings`).

`embedding.py`, `nebula.py` et `vectors.py` figurent parmi les quatorze parce
que leurs imports lourds (`sentence_transformers`, `nebula3`, `chromadb`) sont
**différés** dans la fonction qui en a besoin. C'est ce qui permet à
`tests/unit/test_vectors.py` et `tests/unit/test_nebula.py` de s'exécuter sans
ces paquets, absents du venv du dépôt (registre §3.4, §4.4, §4.28.d).

Ce compte n'est pas celui des modules **inimportables** côté hôte. `bs4`,
`minio` et `pydantic_settings` sont dans le venv du dépôt : trois des quatre
s'importent donc quand même. Seul `main.py` ne s'importe pas (`fastapi` est
absent du venv). Cette propriété est vérifiée par
`tests/unit/test_importabilite_cote_hote.py`.

## Variables d'environnement

Le service reçoit tout le `.env` (`env_file: .env`) ; `docker-compose.yml`
fixe en plus, dans `environment`, les variables des stores. Le rôle des
variables partagées avec le reste de la pile est détaillé dans
[livraison.md §2.2](../livraison.md#22-le-env--toutes-les-variables).

**Stores** (lus par `DoclingSettings` et `ReglagesDuStockageObjet`,
`src/reglages_s3.py`) :

| Variable | Défaut dans le code | Remarque |
|---|---|---|
| `S3_ENDPOINT` | aucun, exigée | [livraison.md §6.2](../livraison.md#62-ladresse-du-stockage-na-aucune-valeur-par-défaut) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | aucun, exigées | dérivées par `docker-compose.yml` de `SEAWEEDFS_RW_ACCESS_KEY` / `SEAWEEDFS_RW_SECRET_KEY` ; ne pas les écrire dans le `.env` |
| `S3_BUCKET` | `documents` | |
| `NEBULA_HOST` / `NEBULA_PORT` | `graphd` / `9669` | |
| `NEBULA_USER` / `NEBULA_PASSWORD` | `root` / `nebula` | |
| `CHROMA_HOST` / `CHROMA_PORT` | `chromadb` / `8000` | |
| `EMBEDDING_MODEL_NAME` | `paraphrase-multilingual-MiniLM-L12-v2` | verrouillé : le service refuse de démarrer sur un autre modèle ([base_vectorielle.md](../base_vectorielle.md#le-service-refuse-de-démarrer-sur-un-autre-modèle)) |

**Réglages d'extraction** (`src/docling_service/settings.py`, absents de
`.env.example`) :

| Variable | Défaut | Effet |
|---|---|---|
| `PDF_BATCH_PAGES` | 5 | pages converties par passe |
| `IMAGE_CROP_ZOOM` | 2.0 | facteur d'agrandissement des crops PDF |
| `MIN_CHUNK_CHARS` | 24 | plancher d'indexation d'un chunk autonome (caractères) |
| `EMBED_SECTION_CONTEXT` | `true` | titre de section préposé au texte encodé |
| `EMBEDDING_BATCH_SIZE` | 32 | textes encodés par appel au modèle |
| `CHROMA_UPSERT_BATCH` | 500 | chunks par upsert ChromaDB |
| `GRAPH_TEXT_MAX_CHARS` | 2000 | aperçu du texte stocké dans le graphe |
| `JOB_HISTORY_SIZE` | 500 | jobs terminés conservés en mémoire |
| `NEBULA_MAX_ATTEMPTS` / `NEBULA_RETRY_SECONDS` | 15 / 10.0 | connexion au graphd au démarrage |
| `NEBULA_SPACE_ATTEMPTS` | 12 | tentatives de `CREATE SPACE` |

Aucune variable `CHUNK_SIZE` ni `CHUNK_OVERLAP` n'est lue : le découpage suit la
structure du document et la fenêtre du tokenizer (registre 5.1,
[extraction_donnees.md](../extraction_donnees.md#ce-qui-part-dans-lindex-vectoriel)).

Un `docker compose restart` ne relit pas le `.env` : recréer le service
([livraison.md §6.4](../livraison.md#64-restart-ne-relit-pas-le-env)).

## Dépendances

`docker-compose.yml` ne déclare aucun `depends_on` pour ce service : il attend
ses stores par nouvelles tentatives au démarrage.

- `graphd` : écriture des nœuds et arêtes NebulaGraph — fiche
  [`nebulagraph.md`](nebulagraph.md)
- `chromadb` : upsert des chunks — fiche [`chromadb.md`](chromadb.md)
- `seaweedfs` (passerelle S3, `S3_ENDPOINT`) : crops et images — fiche
  [`stockage_objet.md`](stockage_objet.md)

Consommateur : l'asset d'extraction Dagster, par `DOCLING_SERVICE_URL`
(`http://docling-service:8000`).

## Sonde de santé

Au démarrage, le service vérifie d'abord `EMBEDDING_MODEL_NAME` (un autre modèle
fait échouer le démarrage), démarre le worker, puis lance en parallèle
l'initialisation du schéma NebulaGraph, la création du bucket et le
préchargement des modèles. `/health` rend 503 tant que l'une des trois n'a pas
abouti ou que le worker est arrêté.

La sonde compose interroge `http://localhost:8000/health` dans le conteneur :
`interval` 30 s, `timeout` 15 s, `retries` 5, `start_period` 600 s (premier
téléchargement des modèles). État attendu et commandes :
[livraison.md §2.4](../livraison.md#24-la-santé-des-services).

## Diagnostic

Le port n'étant pas publié, les appels se font dans le conteneur.

```bash
# Journal
docker compose logs docling-service --tail 100 -f

# État détaillé (queue, graph_ready, objects_ready, models_ready)
docker compose exec docling-service python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"

# Extraction manuelle, sans Dagster
docker compose exec docling-service python -c "
import json, urllib.request
corps = json.dumps({'filepath': '/opt/dagster/app/Datas/pdfs/mon_livre.pdf',
                    'source_path': 'pdfs/mon_livre.pdf'}).encode()
requete = urllib.request.Request('http://localhost:8000/extract', data=corps,
                                 headers={'Content-Type': 'application/json'})
print(urllib.request.urlopen(requete).read().decode())"

# Suivi du job retourné
docker compose exec docling-service python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/jobs/a1b2c3d4e5f6').read().decode())"
```

Une extraction manuelle écrit dans les trois stores, comme une ingestion
Dagster : sauf doublon exact d'un document déjà ingéré, elle purge d'abord le
document de même `source_path`.

| Symptôme | Cause probable |
|---|---|
| `/health` en 503 avec `models_ready: false` durablement | échec du préchargement, journalisé (« Prechargement des modeles echoue ») ; il n'est pas retenté : redémarrer le service |
| `/health` en 503 avec `objects_ready: false` | passerelle S3 injoignable ou identifiants refusés (15 tentatives espacées de 5 s) |
| `/health` en 503 avec `graph_ready: false` | graphd ou storaged pas prêts |
| conteneur qui redémarre en boucle | `EMBEDDING_MODEL_NAME` hors contrat, ou `S3_ENDPOINT` / identifiants S3 absents |
| job `failed` avec « batch(s) non convertis » | un lot de pages a échoué ; le document partiel a été retiré des stores |

Après une purge des stores, redémarrer ce service pour recréer le schéma
([livraison.md §3.3](../livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit)).
Les instruments (`verify_contract`, `index_report`…) se lancent dans l'image de
ce service : [livraison.md §4](../livraison.md#4-vérifier).
