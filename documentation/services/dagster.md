# Dagster (orchestrateur ETL)

## Rôle

Orchestre l'ingestion : détection des fichiers, nettoyage HTML, soumission au
service Docling, suivi des jobs, puis réindexation de `rag-agent-chat`.
Fonctionnement (capteurs, curseurs, file, run monitoring, durées) :
[`orchestration.md`](../orchestration.md).

## Image

`dagster-webserver` et `dagster-daemon` sont construits depuis
`Dockerfile.dagster` : base `python:3.12-slim`, dépendances de
`requirements.txt` (`dagster==1.13.16`, `dagster-postgres==0.29.16`, nettoyage
HTML, client S3 `minio`), utilisateur `dagster` (uid 1000),
`DAGSTER_HOME=/opt/dagster/dagster_home`.

## Conteneurs

Aucun `container_name` : les noms sont attribués par Compose.

| Service             | Port interne | Port hôte | Commande |
|---------------------|--------------|-----------|----------|
| `dagster-webserver` | 3000         | 3002      | `dagster-webserver -h 0.0.0.0 -p 3000 -w /opt/dagster/app/src/workspace.yaml` |
| `dagster-daemon`    | —            | —         | `dagster-daemon run -w /opt/dagster/app/src/workspace.yaml` |

`src/workspace.yaml` charge le module `src.pipeline.definitions`. Les runs
s'exécutent dans le conteneur `dagster-daemon` (`DefaultRunLauncher`, lanceur
par défaut, aucun `run_launcher` déclaré dans `dagster.yaml`).

Politique de redémarrage : `unless-stopped`.

## Volumes

- `./src` monté sur `/opt/dagster/app/src`
- `./Datas` monté sur `/opt/dagster/app/Datas` (même chemin que dans
  `docling-service`)
- `./dagster.yaml` monté sur `/opt/dagster/dagster_home/dagster.yaml`

## Variables consommées

Rôle de chacune : [livraison.md §2.2](../livraison.md#22-le-env--toutes-les-variables).

- `DAGSTER_POSTGRES_USER`, `DAGSTER_POSTGRES_PASSWORD`, `DAGSTER_POSTGRES_DB`,
  `DAGSTER_POSTGRES_HOST` : lues par `dagster.yaml` (stockages des runs, des
  événements et des capteurs).
- `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` : les deux
  dernières dérivées par `docker-compose.yml` de `SEAWEEDFS_RW_ACCESS_KEY` et
  `SEAWEEDFS_RW_SECRET_KEY`. Sans elles, les réglages du pipeline refusent de se
  construire ([livraison.md §6.2](../livraison.md#62-ladresse-du-stockage-na-aucune-valeur-par-défaut)).
- `DOCLING_SERVICE_URL`, `AGENT_SERVICE_URL`, `AGENT_API_KEY`, `SOURCE_DIR` :
  lues par `src/pipeline/settings.py` depuis `env_file: .env`.
- `DAGSTER_TELEMETRY_DISABLED=1` et `HOME=/tmp`, fixées dans
  `docker-compose.yml`.

## Dépendances

- `postgres-dagster` : seul `depends_on` déclaré (métadonnées, curseurs des
  capteurs, historique des runs).
- `docling-service` : extraction et écriture dans NebulaGraph et ChromaDB, par
  HTTP.
- `seaweedfs` : Dagster y téléverse lui-même les images inline des captures HTML
  pendant le nettoyage (`src/pipeline/media.py`). Fiche :
  [`stockage_objet.md`](stockage_objet.md).
- `rag-agent-chat` (autre dépôt, service `agent-api`) : destinataire de
  `POST /reindex`. Une `AGENT_SERVICE_URL` vide désactive l'appel.

Dagster n'écrit ni dans ChromaDB ni dans NebulaGraph.

## Objets Dagster

Générés par la fabrique pour chaque source de `src/pipeline/sources.yaml`
(`pdfs`, `livres_html`, `markdown`) :

- assets `{source}/cleaned_html` (sources `html` seulement) et
  `{source}/extracted_document` ;
- job `{source}_job`, partitions dynamiques `{source}_files` ;
- capteur `{source}_sensor` : `pdfs_sensor`, `livres_html_sensor`,
  `markdown_sensor`.

S'y ajoutent l'asset `agent/lexical_index`, le job `agent_reindex_job` et le
capteur `agent_reindex_sensor`.

Les quatre capteurs sont évalués toutes les 30 s et déclarés
`DefaultSensorStatus.RUNNING` ; un état enregistré en base prime sur le code
([livraison.md §6](../livraison.md#6-à-savoir-avant-de-toucher)). Réingérer :
[livraison.md §3.2](../livraison.md#32-réingérer--le-marqueur-sur-le-curseur).

## Sonde de santé

Aucune sonde n'est déclarée dans `docker-compose.yml` : `docker compose ps`
n'affiche que `running`. Contrôle manuel depuis l'hôte :

```bash
curl -s http://localhost:3002/server_info | python3 -m json.tool
```

## Diagnostic

```bash
docker compose logs dagster-daemon --tail 50
docker compose logs dagster-webserver --tail 50
```

Les runs en attente sont dans **Runs > Queued** ; un run `QUEUED` pendant que le
démon est arrêté repart au `docker compose start dagster-daemon`
([`orchestration.md`](../orchestration.md#un-run-bloqué-ne-gèle-pas-la-réindexation)).
Recréer ces services sans `--no-deps` redémarre `postgres-dagster`
([livraison.md §6.3](../livraison.md#63-docker-compose-up-sans---no-deps-redémarre-les-dépendances)).
