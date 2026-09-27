# ChromaDB (base vectorielle)

## Rôle

Base vectorielle qui stocke les chunks des documents et leurs embeddings, pour la recherche sémantique. Modèle de données, modèle d'embedding et découpage : [base_vectorielle.md](../base_vectorielle.md). Contrat avec l'agent (identifiants, 19 clés de métadonnées définies par `ChunkMetadata` dans `src/pipeline/schemas.py`) : [llm_integration_plan.md §4.1](../llm_integration_plan.md#41-chromadb--collection-rag_documents).

Écrite par `docling-service` seul (`src/docling_service/vectors.py`) ; le pipeline Dagster n'y touche pas. Lue par `rag-agent-chat` (autre dépôt) et par les instruments `verify_data`, `verify_contract`, `index_report` ; `wipe_stores` supprime la collection.

## Conteneur

| Service | Image | Conteneur | Port d'écoute | Publié sur l'hôte |
|---|---|---|---|---|
| `chromadb` | `chromadb/chroma:0.6.3` | nom attribué par Compose | 8000 (`expose`) | non |

Réseau `rag_network`, `restart: unless-stopped`.

Le client Python (`chromadb==0.6.3`, `src/docling_service/requirements.txt`) est tenu sur la même version que l'image serveur, alors que la branche 1.x existe. `rag-agent-chat` est passé de son côté en 1.5.9 : monter ici du 0.x au 1.x suppose de changer le client et l'image ensemble, puis de vérifier que les collections déjà écrites restent lisibles.

## Collection

Une seule collection, `rag_documents` (`vectors.COLLECTION_NAME`), créée au premier accès (`get_or_create_collection`).

Ses métadonnées de collection portent la clé `embedding_model` : le modèle qui a produit ses vecteurs, inscrit à la première ouverture de la collection par le service (`vectors._inscrire_le_modele`). Une ingestion sous un autre modèle est refusée, et `verify_contract` affiche ce nom (ligne `modele des vecteurs`, [livraison.md §4.5](../livraison.md#45-verify_contract--le-contrat-avec-lagent)).

## Volume

`./Datas/database/chromadb:/chroma/chroma`

## Variables consommées

Le conteneur n'en lit aucune. Les clients lisent `CHROMA_HOST` (défaut `chromadb`) et `CHROMA_PORT` (défaut `8000`) dans `src/docling_service/settings.py`, et `EMBEDDING_MODEL_NAME` pour le modèle. Rôle : [livraison.md §2.2](../livraison.md#22-le-env--toutes-les-variables).

## Dépendances

Aucune. `docling-service` ne déclare pas de `depends_on` vers `chromadb`.

## Sonde de santé

Aucune dans `docker-compose.yml` : le service n'affiche que `running`.

## Diagnostic

Les images de la pile n'embarquent pas `curl` (`Dockerfile.docling`, `Dockerfile.dagster`). Interroger le battement de cœur depuis `docling-service` :

```bash
docker compose exec -T docling-service python -c \
  "import urllib.request; print(urllib.request.urlopen('http://chromadb:8000/api/v1/heartbeat', timeout=10).read().decode())"
```

Compter les chunks : `python -m src.verify_data` ; état de l'index : `python -m src.index_report`. Forme de lancement et valeurs attendues : [livraison.md §4](../livraison.md#4-vérifier).

Journaux :

```bash
docker compose logs chromadb --tail 50
```
