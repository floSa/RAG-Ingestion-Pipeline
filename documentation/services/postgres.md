# PostgreSQL (métadonnées Dagster)

## Rôle

Base relationnelle de Dagster : `dagster.yaml` y place les trois stockages de
l'instance (`PostgresRunStorage`, `PostgresEventLogStorage`,
`PostgresScheduleStorage`), soit l'historique des runs, les événements et
matérialisations d'assets, et l'état et les curseurs des capteurs. Les données
métier (documents, éléments) sont dans NebulaGraph et ChromaDB.

## Conteneur

- Service `postgres-dagster`, image `postgres:15-alpine`, port interne 5432
  (`expose`, non publié sur l'hôte). Aucun `container_name` : nom attribué par
  Compose.
- Politique de redémarrage : `unless-stopped`.

## Variables consommées

`docker-compose.yml` passe au conteneur `POSTGRES_USER`, `POSTGRES_PASSWORD` et
`POSTGRES_DB`, lues dans `DAGSTER_POSTGRES_USER`, `DAGSTER_POSTGRES_PASSWORD` et
`DAGSTER_POSTGRES_DB`. `DAGSTER_POSTGRES_HOST` ne sert qu'aux clients Dagster.
Aucune n'a de valeur par défaut dans `docker-compose.yml` ni dans
`dagster.yaml`. Rôle : [livraison.md §2.2](../livraison.md#22-le-env--toutes-les-variables).

## Dépendances

Aucune. `dagster-webserver` et `dagster-daemon` en dépendent (`depends_on`).

## Persistance

Volume : `./Datas/database/postgres:/var/lib/postgresql/data`

Curseurs des capteurs et historique des runs vivent dans cette même base : les
perdre ensemble fait réingérer tout le corpus sans message. `docker compose up`
sur un service Dagster sans `--no-deps` redémarre ce conteneur
([livraison.md §6.3](../livraison.md#63-docker-compose-up-sans---no-deps-redémarre-les-dépendances)).

## Sonde de santé

Aucune sonde n'est déclarée dans `docker-compose.yml`. Contrôle manuel :

```bash
docker compose exec postgres-dagster pg_isready
```
