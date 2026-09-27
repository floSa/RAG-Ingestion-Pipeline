# Retrait de MinIO — la procédure, et son compte rendu

> **Archive datée, non réécrite.** Procédure et compte rendu du 25 septembre 2026. L'état en service est décrit par [`livraison.md`](../livraison.md).

> **Ce document est une PROCÉDURE, puis un COMPTE RENDU.** Les §1 à §10 sont la
> procédure, écrite le 25 septembre 2026 avant tout déploiement. **Elle a été
> exécutée le même jour, entre 13:36 et 13:55 UTC** : le compte rendu, avec
> chaque mesure réellement relevée et chaque suppression, est au
> [§11](#11-compte-rendu-dexécution--25-septembre-2026). **MinIO ne tourne plus,
> son conteneur, ses données et ses images sont supprimés.**
>
> C'est un fichier daté de `campagnes/` : il nomme MinIO, et il doit le faire —
> une procédure de retrait qui ne nommerait pas ce qu'elle retire ne serait pas
> exécutable. Le reste de la documentation vivante, elle, n'en porte plus
> qu'**une ligne d'historique**, à
> [`../services/stockage_objet.md`](../services/stockage_objet.md).

---

## 0. Ce que la branche a changé, en une phrase

Les variables du stockage objet sont devenues génériques (`S3_*`), l'adresse n'a
plus de valeur par défaut, le contrat publie `media_url` et `object_key` à la
place de `minio_url`, le service `minio` a quitté `docker-compose.yml`, et le
client S3 n'est plus construit qu'à un seul endroit.

---

## 1. L'ORDRE EST IMPÉRATIF — l'agent d'abord

**L'étape 1 se fait dans `rag-agent-chat`, et rien de ce qui suit ne commence
avant qu'elle soit servie.**

`rag-agent-chat` doit tourner avec une version qui lit **`media_url`**, et
**`minio_url` à défaut** — les deux, dans cet ordre, sur la même lecture de
sommet. C'est la fenêtre de compatibilité, et elle est nécessaire :

- **avant** la réingestion, le graphe ne porte que `minio_url` ;
- **après**, il ne porte plus que `media_url` ;
- entre les deux, il y a une purge, pendant laquelle il ne porte **rien**.

Un agent qui ne lirait que l'ancien champ servirait un corpus sans figures dès
la fin de la réingestion, **sans une seule erreur** : son proxy rend un 404
silencieux, et l'écran dit simplement « image absente ». Un agent qui ne lirait
que le nouveau ferait la même chose, plus tôt — dès sa propre mise en service et
jusqu'à la fin de la réingestion.

Il peut, dans le même geste, prendre `object_key` : la clé nue de l'objet, qui
lui évite de défaire l'adresse pour retrouver ce qu'il veut lire. Ce n'est pas
un prérequis.

**Son `.env` prend aussi les nouveaux noms** — `S3_ENDPOINT=seaweedfs:8333`,
`S3_ACCESS_KEY` / `S3_SECRET_KEY` portant le jeu **lecture seule**, et
`S3_BUCKET=documents`. Les anciens noms sont retirés du même geste.

**Ce dépôt ne peut ni faire ni vérifier cette étape.** Elle se constate chez
l'agent : son journal doit montrer la connexion au store, et son proxy `/media`
doit rendre **200** sur une image du corpus *avant* la purge — c'est-à-dire en
lisant encore `minio_url`.

---

## 2. La fusion

```bash
git checkout main && git pull
git merge --no-ff claude/remove-minio-seaweedfs-b89e35
```

Rien n'est poussé ni fusionné par la conversation qui a préparé la branche.

---

## 3. Le `.env` du clone principal

**Trois lignes à ajouter, quatre à retirer.** Le fichier n'est pas versionné ;
il se modifie à la main, sur le poste.

À **ajouter** :

```
S3_ENDPOINT=seaweedfs:8333
S3_BUCKET=documents
```

À **retirer** :

```
MINIO_ENDPOINT=…
MINIO_ROOT_USER=…
MINIO_ROOT_PASSWORD=…
MINIO_BUCKET=…
```

**`S3_ACCESS_KEY` et `S3_SECRET_KEY` ne s'écrivent PAS dans le `.env`.**
`docker-compose.yml` les dérive de `SEAWEEDFS_RW_ACCESS_KEY` et
`SEAWEEDFS_RW_SECRET_KEY`, qui restent tels quels : ce sont les identités du
**serveur**, et le client présente les mêmes valeurs sous d'autres noms. Une
seule valeur, deux noms, un seul endroit qui la porte.

**Les quatre `SEAWEEDFS_*` ne bougent pas.**

> **Vérification avant de continuer** : `S3_ENDPOINT` doit être présente et non
> vide. Sans elle, **rien ne démarre** — c'est voulu, et c'est ce qui ferme le
> risque de purger le mauvais stockage.

---

## 4. Recréer les services, nommément

```bash
docker compose up -d --force-recreate --no-deps dagster-daemon dagster-webserver
docker compose up -d --force-recreate --no-deps docling-service
```

**Les trois services reçoivent `S3_ACCESS_KEY` et `S3_SECRET_KEY`, et pas le
seul `docling-service`.** Dagster téléverse lui-même les images HTML
(`src/pipeline/media.py`) ; dans la première version de cette branche, seul le
service d'extraction recevait la dérivation, et les deux services Dagster
seraient partis aux identifiants vides — 403 à chaque téléversement, 199 images
absentes, et aucune erreur au démarrage (§4.28.b). Les réglages refusent
désormais un identifiant absent ou vide, comme l'adresse.

- **`--force-recreate` et non `restart`** : un `restart` ne relit pas le `.env`.
- **`--no-deps`** : sans lui, `docker compose up -d <service>` redémarre aussi
  ce dont il dépend — `postgres-dagster`, qui porte **les curseurs des capteurs
  et l'historique des runs**. Un Postgres qui repartirait vierge ferait
  réingérer le corpus entier, sans un mot (registre §4.26).
- **On nomme les services.** Un `docker compose up -d` nu recrée tout ce dont la
  configuration a changé, et la configuration vient de changer partout.

`seaweedfs` n'est pas dans la liste : sa configuration n'a pas bougé.

Le journal de `docling-service` doit porter :

```
INFO [src.docling_service.images] Bucket 'documents' pret sur seaweedfs:8333.
```

---

## 5. La purge

```bash
docker compose run --rm --no-deps -T -e PYTHONPATH=/app -w /app \
  docling-service python -m src.wipe_stores
```

Par `docker compose run`, et non par `docker run --env-file .env` : le `.env`
ne porte pas les deux identifiants, que seul `docker-compose.yml` dérive.

**Elle doit annoncer, dans cet ordre :**

```
--- Stockage objet (seaweedfs:8333) ---
212 objets supprimes du bucket documents
```

**L'adresse se lit AVANT le compte, et les deux sont des signaux d'arrêt.** Une
autre adresse, ou un autre compte, arrête la procédure : on ne réingère pas
par-dessus un doute. *(Avant cette branche, ce bloc affichait le nom d'un
produit écrit dans le code : il l'aurait affiché à l'identique en vidant un tout
autre serveur.)*

La purge joue aussi `DROP SPACE`, et c'est ce qui rend le renommage des colonnes
du graphe possible : Nebula n'autorise jamais une colonne supprimée à revenir
sous le même nom, donc `minio_url` ne peut pas être *renommée* — elle disparaît
avec le space.

---

## 6. Les deux redémarrages

```bash
docker compose restart docling-service
```

`init_schema()` **ne tourne qu'au démarrage**. C'est lui qui recrée le space et
les onze tags d'élément, désormais avec `media_url` **et** `object_key`. Sans ce
redémarrage, la réingestion écrit contre un schéma qui n'existe pas.

```bash
docker compose restart agent-api    # dans le depot rag-agent-chat
```

`agent-api` ouvre sa session NebulaGraph à son démarrage et la garde. Après un
`DROP SPACE` suivi d'une recréation, cette session répond
`SemanticError: Unknown tag`, et **son proxy `/media` rend 404 sur toutes les
images pendant que `/health` reste VERT**. C'est un défaut de l'autre dépôt ;
jusqu'à sa correction, ce redémarrage fait partie de la purge (§6.6 de
[`../livraison.md`](../livraison.md)).

---

## 7. La réingestion

```bash
docker compose exec -T -w /opt/dagster/app -e PYTHONPATH=/opt/dagster/app \
  dagster-webserver dagster sensor cursor livres_html_sensor \
    --set 'reingerer:2026-09-25-sans-minio' -w src/workspace.yaml
```

**Le marqueur est `reingerer:2026-09-25-sans-minio`**, et il doit être posé sur
**chacun** des capteurs de source. L'étiquette doit être **neuve** : avec une
étiquette déjà consommée, la clé de run est identique et il ne se passe rien,
sans un mot.

Attendre que les runs retombent — 23 documents, et le service ne convertit qu'un
document à la fois.

---

## 8. Les mesures

Toutes en lecture seule, toutes décrites au §4 de
[`../livraison.md`](../livraison.md). **Les attendus :**

| Mesure | Attendu |
|---|---|
| les huit comptes | 15 196 / 23 / 7 251 / 1 748 / 4 963 / 15 173 / 4 367 / 212 |
| l'empreinte des 212 clés | `c91f5be6…7ed0b994` |
| `media_url` sur les sommets visuels | **212 sur 212**, sous `http://seaweedfs:8333/documents/` |
| `object_key` sur les mêmes sommets | **212 sur 212** |
| la propriété `minio_url` dans le graphe | **zéro** — le space a été recréé sans elle |
| `comparer` contre l'instantané | **23 / 23**, `DEPLACES 0`, `rc=0` |

**L'empreinte des clés est le témoin qui compte.** Elle est calculée sur les
clés d'objet, que ce lot **n'a pas touchées** : un renommage de champ ne déplace
aucune clé, et un écart ici voudrait dire que la chaîne d'images a changé sans
qu'on l'ait voulu.

**`comparer` à `DEPLACES 0` est le second.** Les `element_id` dérivent de
`compute_id(filename, page_no, position_in_page, text)` — et d'aucun champ de
média. Le renommage ne peut donc pas les déplacer, et cette mesure l'établit au
lieu de l'affirmer.

**`verify_contract` rend `rc=1`**, sur la seule anomalie connue : 52 sommets
visuels sur 264 sans média (§4.32.b). Il affiche désormais **deux** lignes, une
par champ, et **les deux comptes doivent être égaux** — un écart dirait qu'un
des trois chemins d'image a posé l'adresse sans la clé.

---

## 9. La suppression, et seulement après les mesures

**Rien de ce qui suit ne se fait avant que le §8 soit vert.** Chacun de ces
gestes est irréversible.

```bash
docker compose stop minio
docker compose rm -f minio
```

```bash
sudo rm -rf Datas/database/minio
```

Le bucket témoin de la bascule, sur SeaweedFS :

```
temoin-bascule
```

Il se supprime avec le jeu **RW**, par un client S3 — son objet
`bascule-2026-09-25.txt` d'abord, le bucket ensuite. Il n'a servi qu'à prouver
que la passerelle servait l'agent, et cette preuve est faite.

Enfin, la sauvegarde de l'ancien `.env` :

```bash
shred -u ~/.env.avant-seaweedfs-2026-09-25
```

Elle porte les anciens identifiants MinIO en clair. Elle ne sert plus à rien —
il n'y a plus de serveur vers lequel revenir — et un fichier d'identifiants qui
survit à son usage est un fichier d'identifiants qui traîne.

> **Le retour arrière n'est plus un serveur gardé debout : c'est le CORPUS.**
> `Datas/` porte les 25 fichiers sources, et une purge suivie d'une réingestion
> régénère les trois stores à l'identique — `DEPLACES 0` l'établit à chaque
> campagne. Un serveur maintenu en vie sans être mesuré est un serveur dont la
> configuration dérive en silence, et c'est exactement ce qui était en train
> d'arriver : le `.env` en service ne portait plus ses identifiants.

---

## 10. NON VÉRIFIÉ

1. **~~Aucune étape de ce document n'a été exécutée.~~** Écrit avant le
   déploiement ; **toutes l'ont été** le 25 septembre 2026 après-midi (§11).
2. **Les attendus du §8 sont ceux de la campagne du 25 septembre 2026 au matin.**
   Ils ont été **remesurés après ce lot**, et ils concordent tous (§11.4).
3. **La fenêtre de compatibilité de l'agent n'est pas vérifiable d'ici.** Que
   `rag-agent-chat` lise bien `media_url` puis `minio_url` à défaut se constate
   chez lui, avant tout le reste.
4. **La suppression du bucket témoin n'a pas de commande écrite ici** : elle
   demande un client S3 et le jeu RW, dont ce document ne cite aucune valeur.

---

## 11. Compte rendu d'exécution — 25 septembre 2026

Exécuté depuis le clone principal, heures UTC. Toutes les commandes ont été
lancées **sans tube derrière le processus mesuré** : chaque `rc` est celui du
processus.

### 11.1 Le correctif préalable, sur la branche — `54c5968`

**Un défaut trouvé à la relecture, avant toute fusion.** Dagster téléverse
lui-même les images HTML (`src/pipeline/media.py`), mais la branche ne dérivait
`S3_ACCESS_KEY` / `S3_SECRET_KEY` que pour `docling-service`, et les réglages
leur donnaient `""` par défaut. Déployée telle quelle, elle aurait téléversé les
199 images HTML **aux identifiants vides** : 403 à chaque image, et aucune
erreur au démarrage (§4.28.b).

- `dagster-webserver` et `dagster-daemon` reçoivent désormais les quatre `S3_*`,
  dérivés du même jeu RW. Vérifié par `docker compose config` sur un `.env`
  témoin aux valeurs factices, supprimé aussitôt.
- `s3_access_key` / `s3_secret_key` n'ont plus de défaut vide : même garde que
  `s3_endpoint`, dix tests **rouges avant**, verts après.
- **Même défaut hors du compose** : les instruments lancés par
  `docker run --env-file .env` (purge, `verify_contract`, `index_report`,
  `comparer`, jeu de questions) ne recevaient pas les identifiants — la purge
  aurait rendu 403 sur le stockage objet. Ils se lancent désormais par
  `docker compose run --rm --no-deps`, qui reçoit la même dérivation.
- `make all` dans un worktree : **rc=0**, 1 136 tests, mypy 44 fichiers,
  35 mutations rouges, 87 fichiers formatés.

### 11.2 L'état avant, la fusion, la bascule des noms

| Relevé avant, 13:35 | Valeur |
|---|---|
| les huit comptes | 15 196 / 23 / 7 251 / 1 748 / 4 963 / 15 173 / 4 367 / 212 |
| empreinte des clés | `c91f5be6e24fbcba5f4a744119bf8da65fed44b7ecac79cce0ae1b027ed0b994` |
| runs Dagster | 1 006, **0** en cours |
| corpus (`htms/`, `pdfs/` ; `.cleaned` exclu) | 25 fichiers, contenu `f279af8b…ea431` |

1. 13:37 — les quatre capteurs `dagster sensor stop`, rc=0, lus `STOPPED`.
2. `.env` sauvegardé hors du dépôt, mode 600.
3. `git merge --no-ff claude/remove-minio-seaweedfs-b89e35` → `b170ed8`.
4. `.env` : `S3_ENDPOINT` et `S3_BUCKET` ajoutées, les quatre `MINIO_*` retirées.
5. `docker compose up -d --force-recreate --no-deps dagster-webserver
   dagster-daemon docling-service`, rc=0.
6. Dans les trois conteneurs : **0** variable `MINIO_*`, `S3_ENDPOINT=seaweedfs:8333`,
   `S3_BUCKET=documents`, `S3_ACCESS_KEY` et `S3_SECRET_KEY` **non vides**
   (longueurs 32 et 56). Code location `LOADED`, aucune erreur au journal du
   démon ni du webserver ; `docling-service` : `Bucket 'documents' pret sur
   seaweedfs:8333.` **Aucun retour arrière nécessaire.**

### 11.3 Purge et réingestion

- 13:38 — `docker compose run --rm --no-deps -T … docling-service python -m
  src.wipe_stores`, **rc=0** : `--- Stockage objet (seaweedfs:8333) ---`,
  **`212 objets supprimes du bucket documents`**, collection et space supprimés,
  22 fichiers retirés de `.cleaned`.
- `docker compose restart docling-service`, `healthy`. `DESCRIBE TAG Picture` et
  `DESCRIBE TAG Table` : `media_url` **et** `object_key` ; **aucun** des
  12 tags ne porte `minio_url`.
- 13:39 — les quatre capteurs relancés, marqueur `reingerer:2026-09-25-sans-minio`
  posé sur `livres_html_sensor` et `pdfs_sensor`.
- `docker restart rag-agent-api` (le second redémarrage, `livraison.md` §6.6) —
  un redémarrage, pas une recréation.
- **23 runs créés** (1 006 → 1 029) : 22 `livres_html_job` + 1 `pdfs_job`, **tous
  `SUCCESS`** à 13:46 ; puis `agent_reindex_job` **`SUCCESS`**, journal
  « rag-agent-chat reindexe : 4367 chunks ». 1 030 runs au total.

### 11.4 Les mesures — attendu / mesuré, 13:47 → 13:50

| Mesure | Attendu | Mesuré |
|---|---|---|
| les huit comptes | 15 196 / 23 / 7 251 / 1 748 / 4 963 / 15 173 / 4 367 / 212 | **identiques** |
| empreinte des clés | `c91f5be6…7ed0b994` | **`c91f5be6…7ed0b994`** |
| `media_url` | 212, sous `http://seaweedfs:8333/documents/` | **212 / 212**, 0 sous `minio:9000` |
| `object_key` | 212, ensemble = clés du bucket | **212 distinctes, ensemble ÉGAL** |
| `minio_url` dans le graphe | 0 | **0** — ni dans le schéma (12 tags), ni dans les données |
| ChromaDB | `media_url` là où était `minio_url` | **4** chunks portent `media_url` et `object_key` — autant que de `minio_url` avant ; **0** `minio_url` |
| `Datas/.cleaned/` | 22 fichiers, 199 images toutes au bucket | **22**, **199** URL, **0** absente, **0** vers `minio:9000` |
| `comparer` | 23 / 23, `DEPLACES 0`, rc=0 | **`DOCUMENTS COMPARES 23 / 23`**, **`DEPLACES 0, DECLARES 0`**, **rc=0** |
| `verify_contract` | rc=1, seule l'anomalie connue | **rc=1** — 52/264 sans `media_url`, **52/264** sans `object_key` : les deux comptes égaux |
| corpus | identique à l'octet | **identique** : 25 fichiers, mêmes contenus, tailles et `mtime` |

Et chez l'agent : `GET /media/<clé>` sur une image HTML réingérée → **200**,
49 572 octets.

### 11.5 Les suppressions — après les mesures, toutes vertes

| Geste | Résultat |
|---|---|
| conteneur `rag-ingestion-pipeline-minio-1` (image `minio/minio:latest`) | `docker stop` puis `docker rm`, rc=0 |
| son montage, lu dans `docker inspect` : `Datas/database/minio` → `/data` | supprimé par son **chemin exact** (294 fichiers, 31 Mo, dont une partie à root) ; corpus identique avant **et** après |
| image `minio/minio:latest` | supprimée — aucun conteneur ne l'utilisait |
| image `minio/mc:latest` | supprimée — aucun conteneur ne l'utilisait, aucune référence sur la machine |
| bucket `temoin-bascule` sur SeaweedFS | son objet `bascule-2026-09-25.txt`, puis le bucket ; `documents` garde ses 212 objets |
| `~/.env.avant-seaweedfs-2026-09-25`, `~/.env.avant-sans-minio-2026-09-25` | `shred -u` |

`docker ps -a`, `docker images`, `docker volume ls` : **plus rien** de MinIO.
`git grep -i minio` hors des pièces datées : la bibliothèque cliente `minio`
(dépendances, `images.py`), les gardes et leurs tests
(`equivalence_des_identifiants.py`, tests, table des mutations), les deux
scripts de campagne, et la ligne d'historique de `services/stockage_objet.md`.

### 11.6 NON VÉRIFIÉ

1. **Le `.env` de `rag-agent-chat` porte encore les noms `MINIO_*`** (vu dans
   son conteneur, noms seulement ; `MINIO_ENDPOINT` vaut `seaweedfs:8333`). Il
   sert bien les images ; son renommage est l'affaire de l'autre dépôt.
2. **Les scripts de campagne documentent encore la forme `docker run
   --env-file .env`** dans leur docstring (`mesurer-le-rappel-vectoriel.py`,
   `verifier-le-jeu-de-questions.py`, `verifier-l-equivalence-des-identifiants.py`,
   `capturer-larbre-docling.py`) : elle ne démarre plus. La forme juste est au
   §4 de `livraison.md`.
3. **Ni le jeu de questions ni le rappel vectoriel n'ont été rejoués** après ce
   déploiement ; `comparer` et les huit comptes tiennent le même index.
4. **Aucune question n'a été posée à l'agent** : un seul `GET /media` a été
   essayé.
