# Stockage et recherche vectorielle (ChromaDB)

## Présentation du service
La base vectorielle **ChromaDB** porte la recherche sémantique du RAG. NebulaGraph conserve la structure du document et l'ordre des éléments ; ChromaDB retrouve les passages dont le sens est proche d'une question.

Chaque chunk est représenté par un *embedding* calculé par `paraphrase-multilingual-MiniLM-L12-v2` : un vecteur de 384 dimensions. Deux textes de sens voisin ont des vecteurs proches.

Le client est la bibliothèque Python officielle, `chromadb.HttpClient`, sur `chromadb:8000` (réseau `rag_network` seulement). Conteneur, version, volume et diagnostic : [services/chromadb.md](services/chromadb.md). Contrat détaillé avec l'agent : [llm_integration_plan.md §4.1](llm_integration_plan.md#41-chromadb--collection-rag_documents).

## Structure et définition des données
La collection utilisée est **`rag_documents`**.

- **Identifiant du chunk** : le hash de dix caractères hexadécimaux de l'élément d'où part la lecture du chunk. Un élément réparti sur plusieurs chunks leur donne un suffixe : `023351d5f4#0`, `023351d5f4#1`… Un élément tenant en un seul chunk garde son identifiant nu (`chunking.chunk_id`, seul site de cette forme). C'est une clause du contrat, et `verify_contract` compte les ids suffixés ([livraison.md §4.5](livraison.md#45-verify_contract--le-contrat-avec-lagent)). Ce suffixe ne protège pas de la duplication à la réingestion : c'est `extraction.extract` qui s'en charge, par `storage.forget_document`, qui purge le document par `source_path` avant de le réécrire (`vectors.delete_document`, registre §4.2, §4.31.B3).
- **Embeddings** : représentation mathématique du texte du chunk, produite par `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions), encodée par lots. Le modèle est **multilingue** : une question française retrouve les passages anglais pertinents, et réciproquement.
- **Documents** : le texte intégral du chunk. Le texte *stocké* n'est jamais tronqué ; le *vecteur* peut l'être, car le modèle tronque ce qui dépasse sa fenêtre. Le chiffre et ses deux causes sont documentés à un seul endroit, `vectors.get_chunker` dans `src/docling_service/vectors.py` (registre §3.4 bis).

**La collection ne contient pas un vecteur par élément du document, mais un vecteur par chunk**. Le découpage est confié à `HybridChunker`, le découpeur de Docling : il regroupe ce qui va ensemble en respectant la structure du document, et reçoit le tokenizer du modèle d'embedding. Tous les éléments restent en revanche dans NebulaGraph : la structure du document est intacte, et l'agent la reconstruit par `/context/{element_id}`. Voir [extraction_donnees.md](extraction_donnees.md#ce-qui-part-dans-lindex-vectoriel).

Les fragments isolés : `HybridChunker` fusionne par défaut les éléments voisins de même métadonnée (`merge_peers`). Ensuite, dans `vectors.build_chunks`, un chunk est **écarté** s'il n'a aucun caractère alphanumérique ou s'il est plus court que `MIN_CHUNK_CHARS` (24 caractères par défaut, `settings.min_chunk_chars`), **et seulement s'il est le seul chunk de son élément**. Une fenêtre du *milieu* d'un texte continu est conservée même courte : sinon, l'agent qui concatène les chunks d'un élément obtiendrait un texte troué (registre §4.28.a).

Le vecteur est par ailleurs calculé sur le texte **précédé du titre de sa section**, alors que le document stocké reste le texte brut. Le passage s'affiche donc tel quel côté agent, mais le vecteur porte son contexte.

**Métadonnées** : 19 clés, définies par `ChunkMetadata` dans `src/pipeline/schemas.py`, qui est le contrat de référence avec `rag-agent-chat`. Leur rôle clé par clé est dans [llm_integration_plan.md §4.1](llm_integration_plan.md#41-chromadb--collection-rag_documents) ; elles se rangent en cinq familles :

- **pivot vers le graphe** : `element_id` et `graph_node_id`, de même valeur, toujours le hash de l'élément et jamais l'id suffixé du chunk ;
- **provenance** : `filename` (le chapitre), `collection` (l'ouvrage), `source_path` (identité du document), `language` ;
- **position** : `label`, `page_no`, `page_no_end`, `reference_id`, `depth`, `section_title`, `page_position`, `ref_position` ;
- **découpage** : `chunk_index`, `chunk_count`, `block_size` ;
- **média** : `media_url` (adresse interne et authentifiée, que l'agent ne passe jamais à un navigateur) et `object_key` (la clé nue du même objet).

## Pourquoi un modèle d'embedding multilingue

Les questions arrivent en français ou en anglais, et le corpus de référence sur lequel ce choix a été fait mêlait les deux langues (le corpus en service, lui, est entièrement anglais). L'ancien modèle, `all-MiniLM-L6-v2`, n'était entraîné que sur de l'anglais : il **classait par langue avant de classer par sens**.

Mesure sur une question française, face à six passages :

| Rang | `all-MiniLM-L6-v2` | `paraphrase-multilingual-MiniLM-L12-v2` |
|---|---|---|
| 1 | FR pertinent (0,453) | **EN pertinent (0,746)** |
| 2 | FR proche (0,433) | **FR pertinent (0,741)** |
| 3 | **FR hors sujet (0,397)** | FR proche (0,492) |
| 4 | **EN pertinent (0,366)** | EN proche (0,441) |
| 5 | EN proche (0,267) | FR hors sujet (0,338) |
| 6 | EN hors sujet (0,105) | EN hors sujet (0,313) |

Avec l'ancien modèle, un **hors-sujet français** devançait la **bonne réponse anglaise** : poser sa question en français revenait à se couper de toute la bibliothèque anglaise. Avec le nouveau, les deux bonnes réponses arrivent en tête à 0,005 d'écart, quelle que soit leur langue.

### Comment lire ces scores

Ce sont des **similarités cosinus**, pas des pourcentages :

| Valeur | Signification |
|---|---|
| 1,0 | même sens exactement |
| 0,7 – 0,8 | dit la même chose autrement |
| 0,4 – 0,5 | même domaine, sujet différent |
| 0,0 | aucun rapport |

Ce qui compte n'est pas la valeur absolue mais **l'écart entre les candidats**.

### Ce que ça impose à `rag-agent-chat`

L'agent doit encoder ses questions avec le même modèle, sans quoi les vecteurs ne sont plus comparables et les réponses deviennent aberrantes **sans qu'aucune erreur n'apparaisse**. Changer de modèle n'est donc pas une décision locale, ni un réglage : `EMBEDDING_MODEL_NAME` ne peut désigner que `CONTRACT_MODEL` (`src/docling_service/embedding.py`), et tout autre nom est refusé (voir ci-dessous). Un changement passe par cette constante, des deux côtés, et par une réingestion complète.

### Le service refuse de démarrer sur un autre modèle

Cette panne est la plus coûteuse de la chaîne et la seule qui ne laisse **aucune trace** : ni exception, ni journal, ni sonde de santé. La recherche rend des passages plausibles et faux.

Elle est muette pour une raison qui dicte la forme de la protection : `all-MiniLM-L6-v2` produit lui aussi des vecteurs de **384 dimensions**. ChromaDB les accepte sans broncher. **Vérifier la dimension ne suffit donc pas** : le contrôle passerait avec les deux modèles. C'est le **nom** qui les distingue.

La dérive vient de l'environnement plutôt que du code. `DoclingSettings` dérive de `BaseSettings` : `EMBEDDING_MODEL_NAME` **écrase le défaut du code**. Un `.env` resté à `all-MiniLM-L6-v2`, non suivi par git, a déjà survécu à une réingestion complète avec le modèle multilingue.

Trois contrôles du côté qui **produit** les vecteurs, et un du côté qui les vérifie :

| Contrôle | Où | Ce qu'il attrape |
|---|---|---|
| `embedding.verify_model_name()` | au démarrage du service (`lifespan`), et avant le chargement du modèle (`get_embedding_model`) | un `EMBEDDING_MODEL_NAME` hors contrat, qu'il vienne du code ou de l'environnement |
| `embedding.verify_dimension()` | sur le modèle réellement chargé | un artefact qui ne correspond pas au nom sous lequel il a été chargé |
| `vectors._inscrire_le_modele()` | à l'ouverture de la collection | une ingestion sous un modèle autre que celui inscrit dans les métadonnées de la collection (clé `embedding_model`) : un index mêlant deux modèles |
| `embedding.index_model_gap()` | dans `verify_contract` | un index produit par un autre modèle que celui de la configuration, ou dont le modèle n'est pas inscrit |

L'échec au démarrage est voulu : l'exception n'est pas rattrapée dans `lifespan`, et le service ne démarre pas (`restart: always` le relance en boucle, sans jamais passer `healthy`). Un service qui ne démarre pas se voit ; un index encodé avec le mauvais modèle, non.

Le défaut de `embedding_model_name` est la constante `CONTRACT_MODEL`, et non un littéral recopié : le code ne peut pas diverger du contrat. Seul l'environnement le peut, et les contrôles ci-dessus le couvrent.

> Le préfixe d'organisation Hugging Face est accepté : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` désigne le même artefact, et le refuser serait un faux positif.

### Les quatre façons de traiter le multilingue

Quand la question et le corpus ne sont pas dans la même langue, quatre approches existent. Elles ne se valent pas.

| Approche | Ce que ça coûte | Ce que ça vaut |
|---|---|---|
| **1. Modèle d'embedding multilingue** | Une ré-ingestion, et le même modèle des deux côtés | **La plus simple et la plus sûre.** Un seul index, aucune latence ajoutée, rien à traduire. Le texte original reste la source citée. |
| **2. Traduire la question au moment de la recherche** | Un appel de modèle par question (~1 s), et le risque de traduire de travers un terme technique | Honorable si le corpus est **d'une seule langue**. Ingérable quand il en mélange plusieurs : traduire vers quoi ? |
| **3. Traduire les documents à l'ingestion** | Très cher (des heures de calcul), et lourd de conséquences | **À éviter.** Une traduction automatique déforme le vocabulaire technique, et le texte cité n'est plus celui de l'auteur. |
| **4. Double index, original et traduit** | Deux fois la place, deux fois l'ingestion | Se défend pour un corpus critique. Disproportionné ici. |

**C'est l'approche 1 qui est en place.** Quelle que soit la langue de la question, la recherche porte sur l'intégralité du corpus. Le modèle place « livraison continue » et « continuous delivery » au même endroit de l'espace vectoriel — il n'y a rien à traduire, et le texte cité reste celui de l'auteur.

La métadonnée `language` reste utile pour dire à l'utilisateur dans quelle langue sont les sources trouvées, ou pour filtrer quand la question porte explicitement sur un corpus donné.

### D'où vient la métadonnée `language`

Détectée par comptage de mots-outils sur un échantillon d'environ 20 000 caractères pris au début du document (`sample_text` puis `detect_language`, [`language.py`](../src/docling_service/language.py)). À l'échelle d'un ouvrage, c'est très discriminant, ce qui serait fragile sur une seule phrase.

Sept langues reconnues : `en`, `fr`, `es`, `de`, `it`, `pt`, `nl`. La valeur est **vide** dès que le doute est permis (moins de 30 mots, moins de 2 % de mots-outils reconnus, ou une avance de moins de 1,5 fois sur la langue suivante) : mieux vaut pas de réponse qu'une mauvaise. Les mots partagés entre plusieurs langues (`que`, `die`, `was`…) sont retirés des listes au chargement, sinon ils feraient pencher un score au hasard.

Le corpus en service est entièrement anglais : tous ses chunks portent `en` ([livraison.md §4.6](livraison.md#46-index_report--lindex-vectoriel)).

## Commandes utiles
- **Interroger la collection en Python**, depuis le conteneur `docling-service` (`docker compose exec docling-service python`). La question doit être encodée avec le modèle du contrat : `query_texts` utiliserait la fonction d'embedding par défaut de ChromaDB, qui n'est pas ce modèle.
  ```python
  import chromadb
  from sentence_transformers import SentenceTransformer

  client = chromadb.HttpClient(host="chromadb", port=8000)
  collection = client.get_collection(name="rag_documents")
  modele = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

  # Filtrer sur le type d'élément : ici, les paragraphes et les formules.
  results = collection.query(
      query_embeddings=modele.encode(["Comment calculer la médiane ?"]).tolist(),
      n_results=3,
      where={"label": {"$in": ["text", "paragraph", "formula"]}},
  )
  ```

## Problèmes rencontrés et solutions
- **Service absent après un redémarrage de la machine** :
  - *Problème* : sans politique de redémarrage, le conteneur ChromaDB ne repartait pas après un arrêt de la machine (par exemple une fermeture de WSL). `docling-service` ne trouvait plus la base et l'écriture des vecteurs échouait.
  - *Solution* : `restart: unless-stopped` sur le service dans `docker-compose.yml`. ChromaDB repart et relit ses collections depuis le volume `Datas/database/chromadb/`.
