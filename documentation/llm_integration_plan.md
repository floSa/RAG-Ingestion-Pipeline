# Plan d'intégration LLM / agent RAG

> **Statut du document.** Deux natures de contenu coexistent ici :
>
> - la **section 4** (« Modèle de données ») est le **contrat d'interface
>   vivant** entre ce pipeline et l'agent. Elle décrit le système actuel et se
>   confronte au code : `ChunkMetadata` dans `src/pipeline/schemas.py`,
>   `src/docling_service/ngql.py`, `nebula.py`, `vectors.py` et `images.py`.
>   `src/verify_contract.py` en contrôle l'application sur les stores
>   ([livraison.md §4.5](livraison.md#45-verify_contract--le-contrat-avec-lagent)) ;
> - les **sections 1 à 3 et 5 à 11** sont le **plan initial de l'agent**, qui
>   vit dans un autre dépôt, `rag-agent-chat`. Rien de ces sections n'est
>   implémenté ici, ce pipeline n'appelle aucun LLM, et les choix de
>   `rag-agent-chat` peuvent différer de ce plan : sa propre documentation fait
>   foi.

## 1. Contexte et vision

Le pipeline d'ingestion (`rag-ingestion-pipeline`) transforme des documents
PDF, HTML et Markdown par extraction structurée (Docling) et les écrit dans un
graphe de connaissances (NebulaGraph), une base vectorielle (ChromaDB) et un
stockage objet S3 pour les médias.

L'agent RAG est un **projet séparé** (`rag-agent-chat`) qui consomme ces stores
en lecture.

### Principe directeur

Un RAG classique transmet au modèle des chunks isolés. Ici, le **graphe de
connaissances sert à reconstruire le contexte structurel** du document autour de
chaque chunk trouvé. L'utilisateur garde le contrôle en sélectionnant les sources
avant la génération.

---

## 2. Architecture du flux agent

```
Utilisateur
    |
    | 1. Question
    v
[Query Processing]
    |
    | 2. Embedding de la question
    v
[ChromaDB] -----> top-K chunks + metadatas (graph_node_id, section_title, document, score)
    |
    | 3. Reranking (cross-encoder)
    v
[Source Preview]
    |
    | 4. Affichage groupé par document, avec extraits et scores
    | 5. L'utilisateur selectionne / elimine des sources
    v
[Graph Context Reconstruction]  <-- ETAPE CLE
    |
    | 6. Pour chaque chunk selectionne :
    |    - NebulaGraph: remonter PARENT_OF jusqu'au section_header
    |    - NebulaGraph: redescendre pour recuperer tous les enfants de la section
    |    - Stockage objet: recuperer les images/tables de la section
    v
[Enriched Context Builder]
    |
    | 7. Assemblage : markdown structure avec hierarchie,
    |    images en base64/URL, metadatas de position
    v
[LLM Generation]
    |
    | 8. Reponse avec citations [source:element_id]
    |    + images jointes si pertinentes
    v
[Post-processing]
    |
    | 9. Extraction des citations, validation guardrails
    | 10. Si le modele a besoin de plus : TOOL search_vectors(query)
    |     -> retour a l'etape 6 (max 3 iterations)
    v
Reponse finale a l'utilisateur
    (texte + citations + images)
```

---

## 3. Détail des étapes

### 3.1 Retrieval initial (ChromaDB)

```python
collection.query(
    query_embeddings=[embed(question)],
    n_results=20,                          # sur-recuperer pour le reranking
    include=["documents", "metadatas", "distances"],
)
```

Chaque résultat contient dans ses métadonnées (liste complète : §4.1) :
- `graph_node_id` : ID du nœud NebulaGraph (= `element_id`) ;
- `element_id` : hash sha256[:10] de l'élément ;
- `page_position`, `ref_position` : position dans la page et sous le parent ;
- `media_url` : adresse de l'image ou de la table, si applicable ;
- `object_key` : la clé nue du même objet.

### 3.2 Reranking

Après le retrieval brut, un **cross-encoder** re-score les chunks par rapport
à la question pour améliorer la précision. Les 10 meilleurs sont conservés.

Motif : les embeddings bi-encoder (`paraphrase-multilingual-MiniLM-L12-v2`) sont
rapides mais imprécis. Le cross-encoder est lent mais beaucoup plus précis sur
le classement.

### 3.3 Source Preview et sélection utilisateur

Affichage groupé par document :

```
Resultats pour "Comment Docling gere-t-il les tableaux ?"

[x] 2408.09869.pdf (score: 0.92)
    - "Table structure recognition..." (p.4, section 3.3)
    - "TableFormer model..." (p.5, section 3.3)

[x] docling_manual.pdf (score: 0.78)
    - "Configuration options..." (p.12, section 5.1)

[ ] unrelated_paper.pdf (score: 0.45)
    - "Table of contents..." (p.1)

> Deselectionner les sources non pertinentes, puis valider.
```

L'utilisateur peut :
- décocher des documents entiers ;
- décocher des chunks individuels ;
- valider pour lancer la génération.

### 3.4 Graph Context Reconstruction (étape clé)

C'est l'étape qui distingue cette approche. Pour chaque chunk sélectionné :

**Phase 1 — Remonter au `section_header`**

```ngql
-- Trouver le chemin du chunk vers le section_header parent.
-- En REVERSELY, src(edge) est le parent ; dst(edge) rendrait le noeud de depart.
GO FROM "element_id" OVER PARENT_OF REVERSELY
YIELD src(edge) AS parent_id
| GO FROM $-.parent_id OVER PARENT_OF REVERSELY
YIELD src(edge) AS grandparent_id;
```

Les arêtes `PARENT_OF` sont remontées jusqu'à un nœud portant le tag
`SectionHeader` (ou `Document` s'il n'y a pas de section parente). Par défaut,
la remontée s'arrête au premier `SectionHeader` rencontré.

**Stratégie de profondeur** : si le chunk est dans la section 3.2.1 :
- la section **immédiate** (3.2.1) est reconstruite avec tous ses enfants ;
- la **chaîne de breadcrumbs** est remontée jusqu'au Document :
  `Document > 3. Processing Pipeline > 3.2 Layout Analysis > 3.2.1 Table Recognition` ;
- les sections parentes sont **mentionnées par leur titre** (pas reconstruites),
  ce qui donne au modèle le contexte hiérarchique sans exploser le budget de tokens.

Exemple de contexte injecté :

```
[Breadcrumb] 2408.09869.pdf > 3. Processing Pipeline > 3.2 Layout Analysis

## 3.2.1 Table Recognition

TableFormer is a deep learning model that predicts the structure of tables...
[paragraphe complet]

[Table: structure_example.png] (img:28b88acbd9)

Caption: Figure 3 - Example of table structure prediction.
```

**Phase 2 — Redescendre pour récupérer le contexte complet**

```ngql
-- Recuperer tous les enfants de la section, dans l'ordre
GO FROM "section_header_id" OVER PARENT_OF
YIELD properties($$).label AS label,
      properties($$).text AS text,
      properties($$).media_url AS media_url,
      properties($$).object_key AS object_key,
      properties(edge).sequence AS seq
| ORDER BY $-.seq ASC;
```

**Phase 3 — Récupérer les images et les tables**

Pour chaque enfant ayant un `media_url` non vide :
- télécharger l'image depuis le stockage objet par `object_key`, qui est
  l'identité de l'objet, plutôt qu'en décomposant l'adresse ;
- l'encoder en base64 pour injection dans le prompt (LLM multimodal) ;
- ou re-servir l'objet à l'affichage. **L'adresse ne va jamais au navigateur** :
  elle est interne et authentifiée, un `GET` anonyme y rend 403, et l'agent sert
  de proxy.

**Résultat** : au lieu d'un chunk isolé de 500 caractères, le modèle reçoit
la section complète avec sa hiérarchie, ses images et ses tableaux.

### 3.5 Génération LLM

Le prompt système :

```
Tu es un assistant qui repond aux questions en te basant UNIQUEMENT
sur les sources fournies. Chaque source est une section de document
avec sa hierarchie, ses images et ses tableaux.

Regles :
- Cite tes sources avec [src:ELEMENT_ID] apres chaque affirmation
- Si une image ou un tableau est pertinent, inclus-le dans ta reponse
  avec la reference [img:ELEMENT_ID]
- Si tu as besoin de plus d'informations, utilise l'outil search_vectors
- Ne reponds JAMAIS au-dela de ce que disent les sources
- Si les sources ne permettent pas de repondre, dis-le explicitement
```

### 3.6 Boucle agentique (recherche itérative)

Le modèle dispose d'un outil `search_vectors(query: str)` qui :
1. effectue une nouvelle recherche ChromaDB avec la sous-question ;
2. reclasse les résultats ;
3. reconstruit le contexte par le graphe, sans repasser par la sélection de
   l'utilisateur ;
4. injecte le nouveau contexte dans la conversation.

**Garde-fous** :
- au maximum **3 itérations** de recherche par question ;
- un budget total de tokens (par exemple 100K tokens de contexte au plus) ;
- le modèle doit justifier son besoin d'informations supplémentaires.

### 3.7 Post-traitement de la réponse

1. **Extraction des citations** : analyser les `[src:ELEMENT_ID]` pour construire
   la liste des sources utilisées.
2. **Inclusion des images** : pour chaque `[img:ELEMENT_ID]`, récupérer l'objet
   et l'attacher à la réponse.
3. **Validation par garde-fous** : vérifier que la réponse ne contient pas de
   PII, que chaque affirmation porte une citation, etc.

---

## 4. Modèle de données (contrat d'interface)

### 4.1 ChromaDB — collection `rag_documents`

Nom fixé par `COLLECTION_NAME` (`src/docling_service/vectors.py`). La définition
de référence des métadonnées est `ChunkMetadata` (`src/pipeline/schemas.py`) :
`vectors.build_chunks` construit chaque métadonnée à travers ce modèle, et
`verify_contract` attend exactement ses champs (`ChunkMetadata.model_fields`).

| Champ          | Type          | Description                                |
|----------------|---------------|--------------------------------------------|
| id             | string        | `element_id`, ou `element_id#n` si l'élément a été découpé en plusieurs chunks (`chunking.chunk_id`) |
| embedding      | float[384]    | Vecteur `paraphrase-multilingual-MiniLM-L12-v2` |
| document       | string        | Texte du chunk, intégral (le vecteur, lui, est tronqué au-delà de la fenêtre) |
| metadata.element_id    | string | Hash de l'**ancre** du chunk, toujours au format `^[a-f0-9]{10}$` |
| metadata.graph_node_id | string | = `element_id`, clé du sommet NebulaGraph |
| metadata.filename      | string | Nom du fichier source, sans extension : le **chapitre** |
| metadata.collection    | string | Dossier sous la racine de la source : l'**ouvrage** dont vient le chapitre (`""` si le fichier est à plat) |
| metadata.source_path   | string | Chemin complet relatif à `Datas/`, avec son extension : identité unique du document |
| metadata.language      | string | Code ISO 639-1 du document (`en`, `fr`…), vide si indéterminée |
| metadata.label         | string | Label Docling de l'ancre (`text`, `table`, `code`…) |
| metadata.page_no       | int    | Première page du chunk (1 pour les formats non paginés) |
| metadata.page_no_end   | int    | **Dernière** page du chunk. Égale à `page_no`, sauf pour un élément que Docling a fusionné par-dessus une frontière de page : citer « page N » seule est alors inexact |
| metadata.media_url     | string | Adresse de l'objet si l'ancre est une image ou une table (`""` sinon), de forme `http://{S3_ENDPOINT}/{S3_BUCKET}/{object_key}` (`images.object_url`). **Interne et authentifiée**, jamais servie telle quelle à un navigateur |
| metadata.object_key    | string | La clé nue du même objet, exactement celle passée à `put_object` (`images.object_key`, inverse exact de `images.object_url`). L'adresse porte l'hôte et devient fausse s'il change ; la clé reste valable |
| metadata.reference_id  | string | Section parente, ou `DOC` |
| metadata.depth         | int    | Profondeur dans la hiérarchie. **Deux échelles s'y croisent** : sur un titre elle compte les titres au-dessus (0 pour un titre rattaché au document) ; sur tout autre élément elle vaut celle de son titre + 1 (0 s'il est rattaché directement au document). C'est `label` qui dit laquelle. Aucun plafond. Définition de référence : `ChunkMetadata.depth` |
| metadata.section_title | string | Titre de la section, pour l'affichage des citations |
| metadata.page_position | int    | Rang de l'élément dans sa page |
| metadata.ref_position  | int    | Rang de l'élément sous son parent |
| metadata.chunk_index / chunk_count | int | Position du chunk parmi ceux de son élément, et leur nombre |
| metadata.block_size    | int    | Nombre d'éléments fusionnés dans ce chunk (1 : le chunk correspond exactement à un élément) |

Aucune métadonnée `minio_url` n'existe plus : l'adresse s'appelle `media_url`
depuis le 25 septembre 2026, accompagnée d'`object_key`
([livraison.md §8.1](livraison.md#81-le-renommage-du-contrat--fait)).

**Modèle d'embedding** : `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions,
fenêtre de **128** tokens). L'agent doit utiliser le **même** modèle pour encoder
les questions. Le nom du modèle est inscrit dans les métadonnées de la collection
(`embedding_model`), et le service d'extraction refuse d'écrire des vecteurs d'un
autre modèle dans une collection déjà tracée.

La fenêtre vaut **128** tokens (mesure du 2 septembre 2026,
`python -m src.index_report` : « limite : 128 tokens »). Ce n'est pas un
réglage : elle est lue à l'exécution sur le modèle (`modele.max_seq_length`). Le
texte **stocké** est intégral ; le **vecteur** ne l'est pas toujours, car le
modèle tronque ce qui dépasse. Le chiffre et ses deux causes sont documentés
dans `vectors.get_chunker` (registre §6.2). Un budget de contexte côté agent se
calcule donc sur 128 tokens par chunk.

**Granularité** : un vecteur par **chunk**, pas par élément. Le découpage est
confié à `HybridChunker` de Docling, qui regroupe ce qui va ensemble en
respectant la **structure** du document.

Ce que la production écarte, dans `vectors.build_chunks` : un chunk sans aucun
caractère alphanumérique, ou plus court que `min_chunk_chars` (24 caractères
par défaut, `src/docling_service/settings.py`), **et seulement s'il est le seul
chunk de son élément**. Une fenêtre du milieu d'un texte continu est conservée
même courte, sans quoi l'agent concaténerait un texte troué (registre §4.28.a).
Les éléments écartés de l'index restent présents dans NebulaGraph.

**Conséquences pour l'agent** :

- `id` (le `chunk_id`) peut porter un suffixe `#n` ; **`element_id` n'en porte
  jamais** et reste exploitable tel quel par `/context/{element_id}` ;
- `element_id` désigne le **premier** élément couvert par le chunk. C'est un
  nœud réel du graphe : la reconstruction de contexte fonctionne à l'identique ;
- tous les éléments écartés de l'index vectoriel **restent dans NebulaGraph**.
  Le graphe est la source de vérité de la structure, l'index vectoriel celle de
  la recherche ;
- le vecteur est calculé sur le texte **précédé du titre de sa section**
  (`chunking.embedding_inputs`, réglage `embed_section_context`), alors que
  `document` contient le texte brut. L'agent affiche donc le passage tel quel,
  sans préfixe parasite.

**Citer une source complète.** `filename` seul ne suffit pas : un livre découpé
en chapitres donne des noms qui se répètent d'un ouvrage à l'autre (« Preface »,
« Index », « Appendix »). Une citation lisible se construit avec les trois :

```
{collection} > {filename} > {section_title}
Practical MLOps > 1. Introduction to MLOps > Qu'est-ce que le MLOps
```

`source_path` sert quand il faut remonter au fichier lui-même, ou distinguer
deux documents sans ambiguïté.

L'id est stable d'une ingestion à l'autre : il dérive de la position dans la
page, pas de l'ordre global de lecture, et du **chemin** du document et non de
son seul nom ; deux chapitres homonymes de deux ouvrages différents ne se
recouvrent donc pas. L'id dérive aussi du texte, si bien que **toute évolution
de la chaîne d'extraction change les ids** et laisse les anciennes entrées
orphelines. Les stores sont à purger avant une réingestion qui suit une
évolution du pipeline
([livraison.md §3.3](livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit)).

### 4.2 NebulaGraph — space `rag_space`

**Tags (types de nœuds)** :

| Tag            | Propriétés                                      |
|----------------|-------------------------------------------------|
| Document       | `filename`: string, `type_file`: string, `total_pages`: int, `collection`: string, `source_path`: string, `language`: string, `content_hash`: string |
| les **11** tags d'élément : SectionHeader, Paragraph, Table, Picture, ListItem, Caption, Code, Formula, Footnote, PageHeader, PageFooter | `label`: string, `page_no`: int, `page_no_end`: int, `text`: string, `media_url`: string, `object_key`: string, `depth`: int |

Les onze tags d'élément partagent le même schéma, défini une seule fois par
`VERTEX_PROPERTIES` / `VERTEX_TYPES` dans `src/docling_service/ngql.py` ; le tag
`Document` suit `DOCUMENT_PROPERTIES`, dans le même fichier. Un label Docling
est rattaché à son tag par `TAG_MAP` (`src/docling_service/elements.py`).
Aucune propriété `minio_url` n'est écrite.

**`text` est coupé dans le graphe, pas dans ChromaDB.** Au-delà de
`graph_text_max_chars` (2 000 caractères par défaut,
`src/docling_service/settings.py`), le texte d'un sommet est tronqué ; le
`document` ChromaDB du même élément reste intégral. `nebula.py` journalise le
nombre d'éléments coupés.

**`media_url` et `object_key` sont renseignés sur les sommets `Picture` et
`Table`** qui ont un visuel téléversé, et valent `""` sur tout autre sommet.
`verify_contract` compte les sommets visuels privés de l'un ou de l'autre.

**`NULL` n'est pas `0`.** Le schéma Nebula migre en place, les **données** non :
un `ALTER TAG … ADD` laisse à `NULL` tous les sommets déjà écrits, et seule une
réécriture du document les renseigne. Un `page_no_end` absent signifie « fin
inconnue », jamais « tient sur une page ». `verify_contract` le compte.

`depth` est le niveau déclaré du nœud, calculé à l'extraction : il vaut le
nombre d'arêtes `PARENT_OF` qui le séparent du sommet `Document`, moins une
(0 pour un titre ou un élément rattaché directement au document). C'est le
**seul niveau déclaré** lisible sur un titre : aucun `section_header` n'est
jamais un chunk, donc la métadonnée `depth` de ChromaDB n'en décrit jamais un
(registre §4.24). Un nœud écrit avant l'ajout de la colonne porte `NULL`.

**Arêtes (relations)** :

| Arête      | Propriétés       | Description                                |
|------------|------------------|--------------------------------------------|
| PARENT_OF  | sequence: int    | Document → SectionHeader → éléments ; un titre peut être l'enfant d'un autre titre |
| LINKED_TO  | relation: string | Caption → dernier Picture ou Table rencontré avant elle (`"describes"`) |

#### `sequence` : trois réserves de lecture

**L'exigence 4 du contrat est tenue** : `sequence` est présente sur **toutes** les
arêtes `PARENT_OF`, et, triée par `sequence`, `page_no` ne décroît jamais dans un
document. `verify_contract` le vérifie sur la totalité des arêtes.

Trois propriétés sont à connaître avant de s'en servir :

1. **`sequence` repart à 0 dans chaque document.** Elle n'est **pas** globalement
   monotone : tout « avant / après » doit être **borné au document**. Comparer
   deux `sequence` de documents différents n'a aucun sens.
2. **Elle n'est pas contiguë sous un parent, par construction.** C'est un ordre
   de lecture **global au document**, pas un rang sous le parent : l'écart entre
   deux enfants consécutifs est la taille du sous-arbre du frère précédent.
3. **Les trous sont grands.** Le plus grand écart entre deux enfants consécutifs
   d'un même parent se compte en **centaines**.

**Conséquences pour l'agent :**

- une « fenêtre d'éléments » implémentée comme « les enfants de P dont `sequence`
  est dans `[s-k, s+k]` » rendra **silencieusement moins** d'éléments que demandé.
  Pour obtenir les `k` voisins, il faut **trier les enfants de P par `sequence`
  puis prendre les rangs voisins**, jamais filtrer sur un intervalle de valeurs ;
- lire la contiguïté comme un indice d'intégrité ferait **conclure à une perte de
  données qui n'existe pas**.

Les chiffres de ces trois réserves sont documentés à un seul endroit, le
docstring de `verify_contract.inversions_de_page`, mesurés sur le corpus complet.

Le registre §6.16 reste **ouvert** : ces réserves décrivent la façon dont l'agent
lit `sequence`, et doivent aussi être reportées dans la documentation de
`rag-agent-chat` (`pour_le_pipeline_ingestion.md`), dans l'autre dépôt.

**Format des VID** : `FIXED_STRING(256)`, défini par `VID_MAX_BYTES` dans
`src/docling_service/ngql.py`. Un space créé à 64 refuserait **16 des
23 documents du corpus**, dont l'identifiant va jusqu'à **111** octets, et un
`vid_type` ne se modifie pas après coup. Mesures et méthode :
[services/nebulagraph.md](services/nebulagraph.md), section « Schéma nGQL ».

- Document : `doc_{source_path sans extension}` (`ngql.document_vid`). **La clé,
  jamais le nom de fichier seul** : le corpus porte deux `Preface.html`, et
  `doc_{filename}` les ferait collisionner sur un seul sommet (contrat,
  exigence 3). Au-delà de 256 octets, l'identifiant est tronqué et suffixé d'une
  empreinte de 10 caractères hexadécimaux.
- Éléments : hash sha256[:10] (ex. : `a950b65a3b`).

**Requêtes utiles pour l'agent** :

```ngql
-- Trouver le parent d'un element (remonter la hierarchie).
-- En REVERSELY, src(edge) est le parent.
GO FROM "element_id" OVER PARENT_OF REVERSELY YIELD src(edge) AS parent;

-- Trouver les enfants d'une section (reconstruire le contexte)
GO FROM "section_id" OVER PARENT_OF
YIELD dst(edge) AS child, properties(edge).sequence AS seq
| ORDER BY $-.seq;

-- Trouver le document d'un element, quelle que soit sa profondeur
MATCH (d:Document)-[:PARENT_OF*1..20]->(v)
WHERE id(v) == "element_id"
RETURN id(d) AS doc;

-- Trouver la legende qui decrit une image ou une table (Caption -> visuel)
GO FROM "element_id" OVER LINKED_TO REVERSELY
YIELD src(edge) AS caption, properties(edge).relation AS rel;
```

### 4.3 Stockage objet — bucket `documents`

| Champ         | Description                                        |
|---------------|----------------------------------------------------|
| Endpoint      | la valeur de `S3_ENDPOINT` (`seaweedfs:8333` sur la pile actuelle). **Aucune valeur par défaut** ([livraison.md §6.2](livraison.md#62-ladresse-du-stockage-na-aucune-valeur-par-défaut)) |
| Bucket        | la valeur de `S3_BUCKET` (`documents`) |
| Clé d'objet   | PDF : `images/{filename}/{element_id}_{label}.png` (`images.crop_and_upload`) ; Markdown : `images/md/{doc_key}/{rang:04d}_{nom}` (`images.upload_file`) ; HTML : `images/html/{doc_key}/img_{rang:04d}.{ext}` (`src/pipeline/media.py`, téléversé par Dagster) |
| Content-Type  | `image/png` pour les crops PDF ; type d'origine pour les images HTML et Markdown |
| Accès         | Par un client S3 générique, avec le jeu d'identifiants **en lecture seule** (`SEAWEEDFS_RO_*` du `.env` de ce dépôt) côté agent ([SECURITY.md](SECURITY.md#stockage-objet--deux-jeux-didentifiants)) |

`doc_key` est le chemin du document relatif à `Datas/`, sans extension, assaini
en `[A-Za-z0-9/_.-]`.

**Le code ne nomme pas le serveur** (SeaweedFS) : seul `S3_ENDPOINT` le désigne.
Changer de serveur ne touche donc à aucune ligne de téléversement.

### 4.4 Schémas Pydantic (réutilisables)

Les modèles de `src/pipeline/schemas.py`, hors `ChunkMetadata` (§4.1) et les
modèles de requête du service d'extraction :

```python
class BoundingBox(BaseModel):
    left: float = Field(alias="l")
    top: float = Field(alias="t")
    right: float = Field(alias="r")
    bottom: float = Field(alias="b")

    model_config = {"populate_by_name": True}

class DocumentMetadata(BaseModel):
    filename: str
    type_file: str
    total_pages: int = 0

class DocumentElement(BaseModel):
    id: str                        # hash sha256[:10]
    label: str                     # section_header, text, picture, table, ...
    page_no: int = 1
    page_no_end: int = 1
    bbox: BoundingBox | None = None
    text: str = ""
    order: int = 0
    media_url: str | None = None
    object_key: str | None = None
    content: str | None = None
    reference_id: str = "DOC"      # ID du parent
    depth: int = 0
    section_title: str = ""
    page_position: int = 0
    ref_position: int = 0
    type: str = "text"             # "text" ou "resource"

class ExtractedDocument(BaseModel):
    metadata: DocumentMetadata
    elements: list[DocumentElement] = Field(default_factory=list)
```

L'agent peut copier ces schémas ou les importer comme dépendance.

---

## 5. Stack technologique recommandée

| Composant        | Choix                   | Raison                                          |
|------------------|-------------------------|-------------------------------------------------|
| Framework agent  | **LangGraph**           | Machine à états, outils natifs, débogage avec LangSmith |
| LLM principal    | **Claude Sonnet/Opus**  | Long contexte (200K), multimodal natif, tool-use |
| LLM de repli     | **GPT-4o**              | Alternative si besoin                           |
| Embedding requête | **`paraphrase-multilingual-MiniLM-L12-v2`** | Obligatoire : même modèle que l'ingestion |
| Reranking        | **à trancher, voir la réserve ci-dessous** | `ms-marco-MiniLM-L6-v2` est anglais |
| Frontend         | **Streamlit** ou **Gradio** | Prototypage rapide, sélection interactive    |
| API backend      | **FastAPI**             | Même stack que le service Docling               |
| Observabilité    | **Langfuse**            | Open-source, auto-hébergeable en Docker         |
| Garde-fous       | **NeMo Guardrails**     | Validation entrée/sortie, anti-hallucination    |
| Détection de PII | **Presidio**            | Détection et anonymisation d'informations personnelles |

**Reranker : à choisir multilingue** (registre §6.6). `cross-encoder/ms-marco-MiniLM-L6-v2`
est entraîné sur MS MARCO, un jeu anglais. Côté agent, il a été mesuré avec une
étendue de scores de **0,0 %** sur 20 candidats en français : il ne classe plus
rien et renvoie l'ordre d'entrée, sans erreur ni journal. Le défaut est sans effet
tant que corpus et questions sont en anglais, mais il apparaît dès qu'une question
française vise un passage anglais, ce que l'embedder multilingue rend possible. Le
choix d'un reranker multilingue relève de `rag-agent-chat` et d'une campagne de
mesure ; ce plan ne prescrit plus `ms-marco-MiniLM-L6-v2`.

### Pourquoi LangGraph plutôt que LangChain classique

La boucle agentique (le modèle qui relance une recherche) est un **workflow à
états** :
- état initial, puis retrieval, attente de la sélection, reconstruction,
  génération, boucle si besoin, réponse finale.

LangGraph le modélise comme un graphe d'états avec des transitions
conditionnelles. LangChain classique (chaînes) gère mal les boucles et
l'intervention humaine en cours de flux.

---

## 6. Architecture envisagée du projet agent

Nom de travail du plan initial : `agent-llm-rag`. Le projet réel s'appelle
`rag-agent-chat` et a sa propre structure.

```
agent-llm-rag/
    docker-compose.yml        # Langfuse + agent API + Streamlit
    .env.example
    requirements.txt
    src/
        agent/
            __init__.py
            graph.py           # LangGraph state machine (noeud central)
            state.py           # AgentState dataclass
            retriever.py       # ChromaDB query + reranking
            graph_context.py   # Reconstruction via NebulaGraph
            objets_client.py   # Recuperation des images du stockage objet
            llm.py             # Client LLM (Claude/GPT)
            tools.py           # Tool search_vectors pour l'agentic loop
            guardrails.py      # Validation input/output
            settings.py        # pydantic-settings
        api/
            __init__.py
            main.py            # FastAPI endpoints
            schemas.py         # Request/Response models
        frontend/
            app.py             # Streamlit UI
        prompts/
            system.txt
            answer_with_context.j2
            rewrite_query.j2
    tests/
    documentation/
```

---

## 7. Machine à états LangGraph

```python
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    question: str
    chat_history: list[dict]
    retrieved_chunks: list[ChunkResult]
    reranked_chunks: list[ChunkResult]
    selected_sources: list[str]           # element_ids apres selection user
    enriched_context: list[SectionContext] # sections reconstruites
    response: str
    citations: list[Citation]
    images: list[ImageRef]
    search_count: int                     # compteur agentic loop (max 3)
    needs_more_info: bool

graph = StateGraph(AgentState)

graph.add_node("retrieve", retrieve_chunks)
graph.add_node("rerank", rerank_chunks)
graph.add_node("await_source_selection", present_sources_to_user)
graph.add_node("reconstruct_context", reconstruct_via_graph)
graph.add_node("generate", generate_response)
graph.add_node("postprocess", extract_citations_and_images)

graph.add_edge("retrieve", "rerank")
graph.add_edge("rerank", "await_source_selection")
graph.add_edge("await_source_selection", "reconstruct_context")
graph.add_edge("reconstruct_context", "generate")
graph.add_edge("generate", "postprocess")

# Agentic loop : si le modele veut plus d'info ET < 3 iterations
graph.add_conditional_edges("postprocess", should_search_more, {
    True: "retrieve",    # re-chercher avec la sous-question du modele
    False: END,
})

graph.set_entry_point("retrieve")
agent = graph.compile(interrupt_before=["await_source_selection"])
```

---

## 8. Connexion aux stores (accès réseau)

L'agent accède aux trois stores de données. Deux options :

**Option A — Même réseau Docker** (recommandée pour le développement)
L'agent tourne sur `rag_network` et accède directement :
- ChromaDB : `http://chromadb:8000` ;
- NebulaGraph : `graphd:9669` ;
- stockage objet : la valeur de `S3_ENDPOINT` (`seaweedfs:8333`).

**Option B — Accès externe** (production ou projet séparé)
Publier les ports voulus par un `docker-compose.override.yml` local du projet
d'ingestion (fichier non versionné) ; les adresses sont alors celles que cet
override publie sur l'hôte.

Identifiants : ceux du `.env` du projet d'ingestion pour NebulaGraph
(`NEBULA_USER`, `NEBULA_PASSWORD`) ; pour le stockage objet, le jeu **en lecture
seule** `SEAWEEDFS_RO_*`, jamais le jeu `SEAWEEDFS_RW_*` du pipeline. ChromaDB
n'a pas d'authentification sur cette pile.

---

## 9. Variables d'environnement de l'agent

```env
# --- Stores (du projet d'ingestion) ---
CHROMA_HOST=chromadb
CHROMA_PORT=8000
NEBULA_HOST=graphd
NEBULA_PORT=9669
NEBULA_USER=root
NEBULA_PASSWORD=nebula
S3_ENDPOINT=seaweedfs:8333      # aucune valeur par defaut : sans elle, l'agent ne demarre pas
S3_ACCESS_KEY=                  # le jeu LECTURE SEULE, pas celui du pipeline
S3_SECRET_KEY=
S3_BUCKET=documents

# --- LLM ---
ANTHROPIC_API_KEY=              # ou OPENAI_API_KEY
LLM_MODEL=claude-sonnet-4-20250514
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# --- Retrieval ---
EMBEDDING_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2   # DOIT etre le meme que l'ingestion
# A choisir multilingue : ms-marco-MiniLM-L6-v2 est anglais (voir la section 5).
RERANK_MODEL=<a-trancher-multilingue>
RETRIEVAL_TOP_K=20
RERANK_TOP_K=10
MAX_SEARCH_ITERATIONS=3
CONTEXT_DEPTH=1                  # profondeur de reconstruction graphe

# --- Observabilite ---
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

---

## 10. Plan d'implémentation par phases

### Phase 1 — Retrieval basique et interface (2 à 3 jours)
- Mise en place du projet, réglages, client ChromaDB
- Retrieval simple (requête vers top-K chunks)
- Frontend Streamlit : saisie de la question, affichage des résultats
- Ni reranking, ni graphe

### Phase 2 — Reranking et sélection des sources (2 jours)
- Intégrer un cross-encoder pour le reranking
- Interface : affichage groupé par document, cases de sélection
- API FastAPI pour le backend

### Phase 3 — Reconstruction du contexte par le graphe (3 à 4 jours)
- Client NebulaGraph (`nebula3-python`)
- Algorithme de remontée `PARENT_OF` jusqu'au `section_header`
- Algorithme de descente vers les enfants de la section
- Récupération des images du stockage objet
- Assemblage du contexte enrichi en Markdown structuré

### Phase 4 — Génération LLM (2 jours)
- Intégration de Claude par le SDK Anthropic
- Prompt système avec instructions de citation
- Injection du contexte enrichi (texte et images, multimodal)
- Réponse en flux

### Phase 5 — Boucle agentique et LangGraph (3 jours)
- Modéliser le flux complet en LangGraph
- Outil `search_vectors` pour la recherche itérative
- Intervention humaine pour la sélection des sources (interruption)
- Garde-fous : nombre maximal d'itérations, budget de tokens

### Phase 6 — Post-traitement et garde-fous (2 jours)
- Extraction automatique des citations
- Attachement des images à la réponse
- Intégration de NeMo Guardrails ou de Presidio
- Multi-tour (historique de conversation)

### Phase 7 — Observabilité et évaluation (2 jours)
- Déployer Langfuse en Docker
- Tracer chaque requête (retrieval, génération, latence, tokens)
- Évaluer avec Ragas sur le jeu de référence (voir
  [rag_evaluation_strategy.md](rag_evaluation_strategy.md))

---

## 11. Risques et mitigations

| Risque                                    | Impact | Mitigation                              |
|-------------------------------------------|--------|-----------------------------------------|
| Contexte trop large (section entière)     | Tokens | Budget maximal par section, troncature   |
| Boucle infinie de recherche               | Coût   | 3 itérations au plus, budget global de tokens |
| Latence NebulaGraph sur de grands graphes | UX     | Cache des reconstructions récentes       |
| Images trop lourdes en base64             | Tokens | Redimensionner avant injection (1 Mo au plus) |
| Modèle d'embedding différent entre requête et index | Qualité | Imposer `paraphrase-multilingual-MiniLM-L12-v2` dans les réglages |
| L'utilisateur désélectionne toutes les sources | UX | Au moins une source requise pour générer |
