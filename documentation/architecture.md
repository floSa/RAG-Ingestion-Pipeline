# Architecture du RAG Ingestion Pipeline

Pipeline d'ingestion documentaire qui transforme des PDF, HTML et Markdown en
trois stores : une base vectorielle (ChromaDB), un graphe de connaissances
(NebulaGraph) et un stockage d'objets (SeaweedFS, par sa passerelle S3). La
couche LLM/agent vit dans un projet séparé,
[rag-agent-chat](https://github.com/floSa/rag-agent-chat), qui lit ces stores
par le réseau Docker `rag_network`.

Le schéma d'ensemble est dans le [README](../README.md#architecture).

## Services Docker

Dix services, déclarés dans `docker-compose.yml` :

| Service           | Image / build                        | Port interne | Port hôte | Rôle                                  |
|-------------------|--------------------------------------|--------------|-----------|---------------------------------------|
| chromadb          | `chromadb/chroma:0.6.3`              | 8000         | —         | Base vectorielle                      |
| metad             | `vesoft/nebula-metad:v3.6.0`         | 9559         | —         | NebulaGraph : métadonnées             |
| storaged          | `vesoft/nebula-storaged:v3.6.0`      | 9779         | —         | NebulaGraph : stockage                |
| graphd            | `vesoft/nebula-graphd:v3.6.0`        | 9669         | —         | NebulaGraph : moteur de requête       |
| nebula-studio     | `vesoft/nebula-graph-studio:v3.8.0`  | 7001         | 7001      | Interface de visualisation du graphe  |
| seaweedfs         | `chrislusf/seaweedfs:3.80`           | 8333         | —         | Stockage d'objets, passerelle S3      |
| postgres-dagster  | `postgres:15-alpine`                 | 5432         | —         | Métadonnées Dagster                   |
| dagster-webserver | `Dockerfile.dagster`                 | 3000         | 3002      | Interface Dagster                     |
| dagster-daemon    | `Dockerfile.dagster`                 | —            | —         | Capteurs, file et exécution des runs  |
| docling-service   | `Dockerfile.docling`                 | 8000         | —         | Extraction documentaire (FastAPI)     |

Fiches d'exploitation par conteneur : [`services/`](services/).

## Réseau

Tous les services sont sur le réseau bridge `rag_network`. Son nom est fixé
(`name: rag_network`, sans préfixe de projet) parce que `rag-agent-chat` le
déclare `external: true` et s'y attache. Seuls Dagster (3002) et Nebula Studio
(7001) sont publiés sur l'hôte ; les autres services ne se joignent que depuis
un conteneur du réseau. Isolation et secrets : [`SECURITY.md`](SECURITY.md).

## Chemin de bout en bout

1. **Dépôt** d'un fichier dans `Datas/pdfs/`, `Datas/htms/` ou `Datas/mds/`.
2. **Capteur Dagster** (un par source déclarée dans `src/pipeline/sources.yaml`) :
   il voit le fichier nouveau ou modifié et crée une partition et un run. La
   file Dagster en exécute deux à la fois.
3. **Nettoyage** (HTML uniquement) : pré-passe d'hygiène, puis profil par site
   s'il en existe un, sinon comparaison de candidats (conteneurs sémantiques,
   trafilatura, readability-lxml). Dagster téléverse lui-même les images base64
   volumineuses vers le stockage d'objets et réécrit leur `src`.
4. **Soumission** : l'asset poste le chemin au service Docling, qui met le
   document en file et rend un `job_id` ; l'asset suit l'avancement jusqu'au
   terme.
5. **Extraction** : Docling analyse la mise en page, les PDF par lots de pages,
   HTML et Markdown d'un seul tenant. PyMuPDF découpe les images et tableaux des
   PDF en PNG ; les images référencées par une note Markdown sont téléversées
   telles quelles. Les deux vont au stockage d'objets.
6. **Écriture NebulaGraph** : nœuds et hiérarchie `Document → titres → éléments`
   (chaque titre rattaché au titre qui le domine, chaque élément au dernier
   titre rencontré), par INSERT groupés. Tout échec nGQL fait échouer le job :
   pas de perte silencieuse.
7. **Écriture ChromaDB** : le découpage est confié à `HybridChunker` de Docling,
   qui respecte la structure du document et la fenêtre du modèle d'embedding.
   Une part des chunks dépasse malgré tout la fenêtre et est tronquée par le
   modèle, pour deux causes structurelles : une table sérialisée en Markdown est
   indivisible pour le découpeur, et le titre de section est préposé **après**
   le découpage. Le chiffre et ses deux causes sont documentés à un seul
   endroit, `vectors.get_chunker` (registre §3.4 bis). Les chunks sont encodés
   par lots avec `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions), puis
   écrits par upsert avec les **19** métadonnées du contrat d'interface,
   définies par `ChunkMetadata` dans `src/pipeline/schemas.py` (liste :
   [`llm_integration_plan.md` §4](llm_integration_plan.md)).
8. **Réindexation de l'agent** : quand plus aucun run d'ingestion n'est en vol,
   `agent_reindex_sensor` appelle `POST /reindex` sur `rag-agent-chat`
   ([`orchestration.md`](orchestration.md#cadencer-le-débit)).

`docling-service` est le seul service à écrire dans NebulaGraph et ChromaDB. Le
stockage d'objets reçoit les images PDF et Markdown de `docling-service`, et les
images HTML de Dagster (`src/pipeline/media.py`).

## Décisions d'architecture

- **ChromaDB** plutôt que Weaviate : plus simple, sans besoin d'interface
  intégrée pour le vectoriel.
- **NebulaGraph** pour le graphe de connaissances : distribué
  (metad/storaged/graphd), avec Studio pour la visualisation.
- **Dossier partagé** : `./Datas` est monté sur le même chemin,
  `/opt/dagster/app/Datas`, dans Dagster et dans `docling-service`. Le chemin
  que Dagster poste est lu tel quel par le service, sans transfert réseau des
  fichiers.
- **Docling, seul service à pouvoir prendre le GPU** : la charge lourde y est
  isolée. La réservation `nvidia` vit dans `docker-compose.gpu.yml` et n'est pas
  appliquée par défaut : écrite en dur, elle empêcherait de créer le service
  sans runtime nvidia. Le cas nominal est le processeur.
- **Embeddings locaux et multilingues** : `paraphrase-multilingual-MiniLM-L12-v2`
  via SentenceTransformers, sans appel à une API externe. Une question française
  retrouve les passages anglais, et réciproquement.
- **Un capteur par source** : découplage des pipelines, chacun avec son job
  Dagster.
- **Extraction asynchrone** : une conversion de livre dure des heures, ce qui ne
  tient pas dans une requête HTTP. Le service met en file et rend un `job_id` ;
  Dagster suit l'avancement. La boucle d'événements reste libre, et une coupure
  réseau ne condamne pas un run.
- **Un seul worker d'extraction** : la conversion sature déjà la machine (le GPU
  s'il y en a un, les cœurs sinon). La file Dagster en amont cadence le débit,
  et le fait visiblement dans l'interface.
- **Écriture par lots** : INSERT nGQL groupés, pool NebulaGraph partagé et
  embeddings encodés par lot. Un aller-retour par élément rendrait l'ingestion
  d'un livre impraticable.
- **Le graphe garde tout, l'index vectoriel garde ce qui a du sens** : l'analyse
  de mise en page produit quantité de fragments isolés (`x`, `and`, `Note`,
  `-`). `HybridChunker` les regroupe avec leurs voisins selon la structure, et
  un chunk sans contenu exploitable, seul pour son élément, est écarté de la
  recherche sémantique tout en restant dans NebulaGraph.
- **Contextualisation des vecteurs** : le titre de section est préposé au texte
  envoyé au modèle d'embedding, pas au texte stocké. Le passage s'affiche tel
  quel côté agent, mais son vecteur porte le contexte qui lui manquait.
- **Découpage plutôt que troncature** : les textes longs sont découpés en
  plusieurs chunks avant vectorisation, plutôt que tronqués.
- **Identifiants déterministes** :
  `sha256(clé|page|position_dans_la_page|texte[:50])` tronqué à 10 caractères
  hexadécimaux (`elements.compute_id`), où la clé est le chemin relatif à
  `Datas/`, sans extension (`DocumentIdentity.key`). La réingestion est
  idempotente (upsert, pas de doublon), et deux chapitres homonymes de deux
  ouvrages ne se confondent pas.
- **Stockage d'objets derrière une passerelle S3** : le code parle S3 par un
  client générique, et seule `S3_ENDPOINT` désigne le serveur
  ([`stockage_objets.md`](stockage_objets.md)).

## Dossiers de données

| Dossier                          | Contenu                                      |
|----------------------------------|----------------------------------------------|
| `Datas/pdfs/`                    | Documents PDF sources                        |
| `Datas/htms/`                    | Documents HTML sources                       |
| `Datas/mds/`                     | Documents Markdown sources                   |
| `Datas/.cleaned/`                | HTML nettoyés, générés par le pipeline       |
| `Datas/database/chromadb/`       | Persistance ChromaDB                         |
| `Datas/database/nebula/meta/`    | Persistance NebulaGraph (`metad`)            |
| `Datas/database/nebula/storage/` | Persistance NebulaGraph (`storaged`)         |
| `Datas/database/seaweedfs/`      | Persistance du stockage d'objets             |
| `Datas/database/postgres/`       | Persistance PostgreSQL (Dagster)             |
| volume nommé `docling_models`    | Cache des modèles Docling et d'embedding, monté sur `/tmp/.cache` de `docling-service` |
