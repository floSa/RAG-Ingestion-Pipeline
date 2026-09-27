# Configuration minimale — relevés du 27 septembre 2026

Archive datée, non réécrite. Elle porte les mesures qui fondent
[`configuration_requise.md`](../configuration_requise.md).

Tout est en lecture seule : aucun store écrit, aucun service démarré, arrêté ni
recréé. Les essais tournent dans des conteneurs éphémères, retirés après
lecture de leur journal.

## 1. Conversion sous contrainte

**Ce qui tourne.** Le harnais `comparer`
(`scripts/campagne/verifier-l-equivalence-des-identifiants.py`,
[`livraison.md` §4.3](../livraison.md#43-comparer-contre-linstantané)) : il
reconvertit les 23 documents en service par le chemin de production et
confronte les `element_id` à l'instantané du 24 septembre. Il arme ses barrières
d'écriture avant toute conversion (`9 portes, 11 sites`).

**Comment.** `docker run` équivalent au `docker compose run --rm --no-deps` du
§4.3, avec les bornes en plus :

- image `rag-ingestion-pipeline-docling-service`, réseau `rag_network`,
  environnement recopié du conteneur `docling-service` en service (fichier
  temporaire, supprimé après) ;
- `--cpus=<N> --memory=<M> --memory-swap=<M> --shm-size=2g` ;
- `src` de production monté en lecture seule sur `/app/src`, corpus en lecture
  seule sur `/corpus`, copies HTML nettoyées en lecture seule sur `/sp/cleaned`,
  volume `docling_models` sur `/tmp/.cache` ;
- `COMMIT_MESURE` = `3f27d93` (le `src` en service).

**Mémoire au pic** : `memory.peak` du cgroup du conteneur, lu chaque seconde
depuis l'hôte (le compteur est monotone, la dernière lecture avant la sortie
est le pic). **Durée** : du `docker run -d` à la sortie du processus, modèles
compris.

| Essai | Début (UTC) | vCPU | Mémoire | Durée | Pic mémoire | rc | Verdict |
|---|---|---|---|---|---|---|---|
| c4m8 | 06:28:45 | 4 | 8 Gio | 87 s | 2 115 Mio | 0 | `DOCUMENTS COMPARES 23 / 23`, `DEPLACES 0` |
| c2m4 | 06:30:17 | 2 | 4 Gio | 176 s | 1 850 Mio | 0 | `DOCUMENTS COMPARES 23 / 23`, `DEPLACES 0` |
| c1m2 | 06:33:14 | 1 | 2 Gio | 564 s | 1 638 Mio | 0 | `DOCUMENTS COMPARES 23 / 23`, `DEPLACES 0` |
| c2m1 | 06:42:55 | 2 | 1 Gio | 21 s | 1 024 Mio (la borne) | 137 | **OOM** (`OOMKilled=true`) au chargement des poids, premier document |
| c1m4 | 06:43:24 | 1 | 4 Gio | 561 s | 1 811 Mio | 0 | `DOCUMENTS COMPARES 23 / 23`, `DEPLACES 0` |

Lecture :

- **processeur** : de 4 à 2 vCPU, la durée double (87 → 176 s) ; de 2 à 1 vCPU,
  elle est multipliée par 3,2 (176 → 561 s). c1m4 et c1m2 rendent la même
  durée à 3 s près : à 1 vCPU, c'est le processeur qui borne, pas la mémoire.
  `make all` a tourné sur l'hôte pendant une partie de c1m4, hors de ses bornes ;
- **mémoire** : la conversion passe à 2 Gio et casse à 1 Gio. Le pic suit la
  borne (1,6 à 2,1 Gio) : le noyau récupère le cache de fichiers sous
  contrainte ;
- **ce que la mesure ne couvre pas** : le harnais ne charge pas le modèle
  d'encodage et n'écrit rien. En ingestion réelle, `docling-service` garde les
  deux jeux de modèles chargés ; sa mémoire en ingestion continue a été relevée
  à 6,08 Gio en médiane et 6,43 Gio au pic
  ([`guide_du_depot.md`](../guide_du_depot.md), « Débit et ressources »). C'est
  ce chiffre-là qui fonde le minimum de mémoire.

## 2. Les autres services au repos

`docker stats --no-stream`, 27 septembre 2026, vers 06:45 UTC :

| Conteneur | CPU | Mémoire |
|---|---|---|
| `docling-service` (modèles chargés) | 0,17 % | 2,368 Gio (limite 10 Gio) |
| `dagster-daemon` | 3,28 % | 300,5 Mio |
| `dagster-webserver` | 2,14 % | 277,3 Mio |
| `chromadb` | 0,16 % | 264,7 Mio |
| `seaweedfs` | 0,22 % | 222,4 Mio |
| `storaged` | 0,27 % | 101,8 Mio |
| `metad` | 0,46 % | 89,4 Mio |
| `graphd` | 0,03 % | 73,1 Mio |
| `postgres-dagster` | 0,02 % | 64,3 Mio |
| `nebula-studio` | 0,31 % | 56,5 Mio |

Les neuf services autres que `docling-service` : **1 450 Mio** (`calculé`). Le
`memory.peak` de `dagster-daemon` depuis son démarrage, une heure plus tôt :
449 Mio. Un relevé antérieur (27 septembre, 05:57 UTC) donnait jusqu'à 8 % pour
`dagster-daemon` et 12,9 % pour `postgres-dagster` : les capteurs scrutent le
corpus toutes les 30 s, et l'activité au repos varie d'un instant à l'autre ;
elle reste sous 0,3 vCPU au total.

## 3. Disque

| Élément | Taille | Commande |
|---|---|---|
| image `docling-service` | 10,4 Go | `docker images` |
| images `dagster-webserver` et `dagster-daemon` | 879 Mo chacune | `docker images` |
| autres images (`chromadb`, `postgres`, `seaweedfs`, NebulaGraph × 3, Studio) | 2,6 Go | `docker images` |
| **images, total** | **14,8 Go** au plus (couches partagées comptées deux fois) | `calculé` |
| cache des modèles (volume `docling_models`) | 652 Mo | `docker system df -v` |
| NebulaGraph (`Datas/database/nebula/`) | 293 Mo | `du -sh` |
| Postgres Dagster | 145 Mo | `du -sh` dans le conteneur |
| ChromaDB (`Datas/database/chromadb/`) | 143 Mo | `du -sh` |
| SeaweedFS | 31 Mo | `du -sh` dans le conteneur |
| HTML nettoyé (`Datas/.cleaned/`) | 2,4 Mo | `du -sh` |
| corpus en service (`Datas/pdfs/`, `Datas/htms/`) | 56 Mo | `du -sh` |
| **total** | **16,1 Go** | `calculé` |

Le corpus versionné sur `main` depuis `4ed61af` pèse 159 Mo (`du -sh Datas/`
dans un arbre de travail à `a24b3b0`) ; il n'est pas encore ingéré.

Non mesurés, couverts par la marge : le cache de construction de
`docker compose up --build` et la place prise par une réingestion (la purge
vide les stores, la réingestion les réécrit à taille comparable).

## 4. GPU

`docling-service` n'a aucune réservation de périphérique dans
`docker-compose.yml` ; la réservation vit dans `docker-compose.gpu.yml`. L'image
embarque `torch 2.5.1+cu121` (`python -c "import torch; …"` dans le conteneur).
Le mode GPU n'a pas été essayé.

## 5. Logiciels

`docker version` : Engine 29.5.3. `docker compose version` : 5.1.4. Images
`linux/amd64` (`docker image inspect … .Architecture`).
