# NebulaGraph (graphe de connaissances)

## Rôle

Base de données graphe qui stocke la hiérarchie structurelle des documents. Modèle de données et fonctionnement : [graphe_connaissances.md](../graphe_connaissances.md). Contrat avec l'agent (tags, propriétés, types, arêtes) : [llm_integration_plan.md §4.2](../llm_integration_plan.md#42-nebulagraph--space-rag_space).

Écrit par `docling-service` seul. Lu par `rag-agent-chat` (autre dépôt) et par les instruments `verify_data`, `verify_contract`, `index_report` ; vidé par `wipe_stores`.

## Conteneurs

Quatre services de `docker-compose.yml`, tous sur le réseau `rag_network`, tous en `restart: unless-stopped`.

| Service | Image | Conteneur | Ports d'écoute | Publié sur l'hôte |
|---|---|---|---|---|
| `metad` | `vesoft/nebula-metad:v3.6.0` | `metad` | 9559, 19559 (HTTP) | non |
| `storaged` | `vesoft/nebula-storaged:v3.6.0` | `storaged` | 9779, 19779 (HTTP) | non |
| `graphd` | `vesoft/nebula-graphd:v3.6.0` | `graphd` | 9669 (nGQL), 19669 (HTTP) | non |
| `nebula-studio` | `vesoft/nebula-graph-studio:v3.8.0` | nom attribué par Compose | 7001 | **7001** |

Les ports viennent des options `--port` et `--ws_http_port` de chaque service. Seul `graphd` déclare `expose` ; seul `nebula-studio` publie un port.

## Volumes

- `metad` : `./Datas/database/nebula/meta:/data/meta`
- `storaged` : `./Datas/database/nebula/storage:/data/storage`

`graphd` et `nebula-studio` ne persistent rien.

## Variables consommées

Les conteneurs Nebula n'en lisent aucune : leur configuration tient dans leur `command`. Les variables sont celles des **clients** (`docling-service` et les instruments), lues par `src/docling_service/settings.py` :

| Variable | Défaut du code |
|---|---|
| `NEBULA_HOST` | `graphd` |
| `NEBULA_PORT` | `9669` |
| `NEBULA_USER` | `root` |
| `NEBULA_PASSWORD` | `nebula` (identifiant public d'un graphd de développement) |
| `NEBULA_MAX_ATTEMPTS` / `NEBULA_RETRY_SECONDS` | `15` / `10` : ouverture du pool |
| `NEBULA_SPACE_ATTEMPTS` | `12` : tentatives de `CREATE SPACE` |

Rôle des quatre premières : [livraison.md §2.2](../livraison.md#22-le-env--toutes-les-variables).

## Dépendances

`storaged` dépend de `metad`, `graphd` de `storaged`. Ces `depends_on` sans condition fixent l'ordre de démarrage, pas l'attente de disponibilité. `docling-service` ne déclare aucun `depends_on` : il attend le graphd par ses propres tentatives (`NebulaWriter._connect`, puis `_create_space`).

## Schéma nGQL

`nebula.init_schema()` pose le schéma au démarrage de `docling-service`, dans un fil d'arrière-plan : `ADD HOSTS "storaged":9779` (échec toléré), `CREATE SPACE`, tags, arêtes, index `doc_index`, puis vérification des colonnes par `DESCRIBE TAG`. Un échec n'arrête pas le service : `/health` rend `graph_ready: false` et 503. Le site unique du schéma est `src/docling_service/ngql.py`.

```ngql
CREATE SPACE IF NOT EXISTS rag_space(partition_num=10, replica_factor=1, vid_type=FIXED_STRING(256));
```

**`vid_type` vaut 256 octets.** Les identifiants de document du corpus vont de **38** à **111** octets (mesure du 2 septembre 2026 sur le graphe en service, `MATCH (v:Document) RETURN id(v)` : 23 identifiants, dont **16** au-dessus de 64). Un space créé à 64 refuse ces documents. Nebula ne sait pas modifier un `vid_type` : le changer impose une purge complète des stores. Motif : [graphe_connaissances.md](../graphe_connaissances.md#longueur-des-identifiants--vid_type-à-256-octets).

Contraintes d'exploitation :

- `init_schema()` n'est joué qu'au démarrage du service. Après une purge (`wipe_stores`), redémarrer `docling-service` avant toute réingestion, sinon les `INSERT` visent un space ou des tags absents : [livraison.md §3.3](../livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit).
- Une colonne supprimée ne revient jamais (« Schema exisited before! », mesuré le 31 août 2026) : `ALTER TAG … DROP` n'est pas un moyen de retour arrière. Détail : [graphe_connaissances.md](../graphe_connaissances.md#le-schéma-migre-en-place-pas-les-données).
- `src/init_nebula.py` fait l'amorçage à la main sur une pile neuve (enregistrement du storaged, `CREATE SPACE`, `SHOW HOSTS`, `SHOW SPACES`), sans créer les tags. Forme de lancement : celle des instruments de [livraison.md §4](../livraison.md#4-vérifier), avec `python -m src.init_nebula`.

## Sonde de santé

Aucune : `docker-compose.yml` ne déclare de `healthcheck` sur aucun des quatre services, qui n'affichent que `running`. L'état utile est celui de `docling-service` (`graph_ready` dans `/health`, voir [livraison.md §2.4](../livraison.md#24-la-santé-des-services)).

## Diagnostic

Les images de la pile n'embarquent pas `curl` (`Dockerfile.docling`, `Dockerfile.dagster`). Interroger le port HTTP de `graphd` depuis `docling-service` :

```bash
docker compose exec -T docling-service python -c \
  "import urllib.request; print(urllib.request.urlopen('http://graphd:19669/status', timeout=10).read().decode())"
```

Dans Nebula Studio, `SHOW HOSTS;` doit montrer `storaged:9779` en ligne. Journaux :

```bash
docker compose logs graphd --tail 50
```

## Interface

Nebula Studio : `http://localhost:7001`. Se connecter à `graphd:9669` avec `NEBULA_USER` / `NEBULA_PASSWORD`. Sélectionner `rag_space` dans la liste déroulante plutôt que par `USE` ; requêtes types : [graphe_connaissances.md](../graphe_connaissances.md#lire-le-graphe--requêtes-types).
