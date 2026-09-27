# Graphe de connaissances (NebulaGraph)

## Présentation du service
**NebulaGraph** conserve la structure des documents ingérés : l'ordre de lecture et l'imbrication des éléments (titres, paragraphes, tableaux, images, légendes, code…) des documents PDF, HTML et Markdown. Il permet de reconstituer un document à partir de ses éléments.

**Le graphe conserve tous les éléments extraits**, y compris ceux que l'index vectoriel écarte (fragments de mise en page, éléments trop courts pour être retrouvés utilement). La structure complète du document n'existe que dans le graphe. Le **texte** d'un sommet, en revanche, est coupé à `graph_text_max_chars` (2 000 caractères, `src/docling_service/settings.py`) ; ChromaDB garde le texte intégral. Les deux stores divergent donc sur les éléments plus longs, et `nebula.write_elements` journalise leur nombre en avertissement (registre §4.23).

Le graphe complète la recherche sémantique. Quand ChromaDB rend un fragment de page, l'agent suit l'identifiant commun (`element_id` = `graph_node_id`) jusqu'à NebulaGraph pour lire la section qui l'entoure ou la figure qui l'illustre.

Conteneurs, ports, identifiants et diagnostic : [services/nebulagraph.md](services/nebulagraph.md). Contrat détaillé (tags, propriétés, types, arêtes) : [llm_integration_plan.md §4.2](llm_integration_plan.md#42-nebulagraph--space-rag_space).

## Structure et définition des données
Toutes les données vivent dans l'espace `rag_space`, avec un tag par type d'élément. Le schéma a un seul site, `src/docling_service/ngql.py` (`DOCUMENT_PROPERTIES`, `VERTEX_PROPERTIES`, `VERTEX_TYPES`, `create_space_statement`), et `nebula.init_schema()` le pose à chaque démarrage de `docling-service`.

**Nœuds (vertices) :**
L'identifiant d'un élément est un hash de dix caractères hexadécimaux (SHA-256 tronqué, `elements.compute_id`), calculé sur la clé du document, la page, la position dans la page et le texte. Celui d'un document vaut `doc_` suivi de son **chemin** relatif sans extension (`doc_htms/Practical MLOps/Preface`, `ngql.document_vid`) : il reste lisible dans Studio et distingue deux chapitres homonymes de deux ouvrages.
- **`Document`** : racine du document. Porte `filename` (le chapitre), `collection` (l'ouvrage dont il vient), `source_path` (chemin relatif à `Datas/`), `type_file` (`pdf`, `html` ou `md`), `total_pages` (1 pour les formats non paginés), `language` (code ISO 639-1, vide si indéterminée) et `content_hash` (SHA-256 du fichier source, qui sert à reconnaître un ouvrage déjà ingéré sous un autre nom, `NebulaWriter.find_duplicate`).
- **`Paragraph`** / **`Formula`** / **`Code`** / **`ListItem`** / **`Caption`** / **`Footnote`** : éléments textuels.
- **`PageHeader`** / **`PageFooter`** : en-têtes et pieds de page, conservés dans le graphe.
- **`Picture`** / **`Table`** : éléments visuels. Ce sont les seuls à renseigner `media_url` (l'adresse de l'objet) et `object_key` (sa clé nue), qui désignent l'objet stocké dans le [stockage d'objets](stockage_objets.md). Une table HTML est du texte : elle n'a pas d'objet, et ces deux propriétés y restent vides (registre §4.32.b).
- **`SectionHeader`** : titres, qui structurent la hiérarchie.

Ces onze tags d'élément (`elements.TAG_MAP`) portent les mêmes propriétés : `label`, `page_no`, `page_no_end`, `text`, `media_url`, `object_key`, `depth`.

**Arêtes (edges) :**
- **`PARENT_OF`** : orientée d'un parent vers un élément. Le parent d'un titre est **le titre qui le domine** : un sous-titre est rattaché à sa section, elle-même rattachée à son chapitre ; un titre de premier niveau est rattaché au `Document`. **La profondeur n'a pas de plafond** (registre §4.24). La règle, les **deux échelles** de `depth` et la distribution mesurée sont décrites dans `ChunkMetadata.depth` (`src/pipeline/schemas.py`). Voir [extraction_donnees.md](extraction_donnees.md#4-hiérarchie-et-positions) pour les signaux utilisés selon la source. L'arête porte la propriété `sequence` (int), l'ordre de lecture, qui permet de reconstituer le document dans l'ordre.
- **`LINKED_TO`** : relie une légende (`Caption`) au dernier élément visuel (`Table` ou `Picture`) rencontré avant elle dans l'ordre de lecture (`nebula.write_elements`). Porte la propriété `relation` (string), qui vaut `describes`.

### Longueur des identifiants : `vid_type` à 256 octets
`VID_MAX_BYTES` (`ngql.py`) fixe `vid_type=FIXED_STRING(256)`. La longueur se compte en **octets** : un accent en coûte deux, un tiret cadratin trois, et un identifiant de document dérivé du chemin dépasse vite 64. Un space créé à 64 refuse ces documents (« *Storage Error: The VID must be a 64-bit integer or a string fitting space vertex id length limit* », mesure datée dans la docstring de `ngql.create_space_statement`). Nebula ne sait pas modifier un `vid_type` : le changer impose une purge complète des stores. Au-delà de 256 octets, `document_vid` tronque l'identifiant sur une frontière de caractère et le suffixe d'une empreinte.

### Le schéma migre en place, pas les données
Sur un space déjà peuplé, `CREATE TAG IF NOT EXISTS` ne fait rien : ce sont les `ALTER TAG … ADD` joués à chaque démarrage (`ngql.tag_schema_statements`) qui ajoutent les colonnes manquantes. Les sommets déjà écrits portent alors `NULL` dans la nouvelle colonne, jusqu'à la réécriture du document. `nebula._verifier_les_tags` relit ensuite chaque tag par `DESCRIBE TAG` : une migration refusée fait échouer `init_schema()`, et `/health` rend `graph_ready: false`.

Nebula garde l'historique de schéma d'un tag et refuse de rajouter une colonne supprimée (« Schema exisited before! ») : `ALTER TAG … DROP` n'est pas un moyen de retour arrière, et renommer une colonne laisse l'ancienne sur le tag. Le seul état propre est le `DROP SPACE` de `src/wipe_stores.py`, suivi du redémarrage de `docling-service` qui rejoue `init_schema()` ([livraison.md §3.3](livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit)).

### Ce que la réingestion d'un document retire du graphe
Avant de réécrire un document, `storage.forget_document` purge les deux stores. Côté graphe, `NebulaWriter.delete_document` exécute `DELETE VERTEX "<doc_vid>" WITH EDGE` : il retire le sommet `Document` et ses arêtes, pas les sommets d'élément. Un élément inchangé retrouve le même identifiant et son sommet est réécrit ; un élément dont le texte a changé reçoit un nouvel identifiant, et l'ancien sommet reste. Après une évolution de la chaîne d'extraction, seule la purge complète rend un graphe sans reste ([livraison.md §3.3](livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit)).

## Lire le graphe : requêtes types
Dans Nebula Studio, sélectionner l'espace `rag_space` dans la liste déroulante en haut à droite, sans `USE` dans la console (voir plus bas), puis lancer les requêtes :

1.  **Lister les documents :**
    ```ngql
    MATCH (d:Document)
    RETURN d.Document.collection AS ouvrage,
           d.Document.filename AS chapitre,
           d.Document.type_file AS format
    LIMIT 50;
    ```
2.  **Lister les chapitres d'un ouvrage donné :**
    ```ngql
    MATCH (d:Document)
    WHERE d.Document.collection == "Practical MLOps"
    RETURN d.Document.filename AS chapitre, id(d) AS identifiant;
    ```
3.  **Lister les enfants directs d'un document :**
    ```ngql
    MATCH (d:Document)-[r:PARENT_OF]->(e)
    WHERE id(d) == "doc_pdfs/statisticsfordatascience"
    RETURN e;
    ```
4.  **Récupérer un document complet (structure et contenu) :**
    ```ngql
    MATCH p=(d:Document)-[:PARENT_OF*..]->(e)
    WHERE id(d) == "doc_pdfs/statisticsfordatascience"
    RETURN p;
    ```
5.  **Lister les éléments rattachés à un titre donné :**
    ```ngql
    MATCH p=(s:SectionHeader)-[:PARENT_OF*..]->(e)
    WHERE id(s) == "<INSCRIRE_ID_DU_TITRE>"
    RETURN p;
    ```
6.  **Afficher un élément à partir de son identifiant (par exemple l'`element_id` rendu par ChromaDB) :**
    ```ngql
    MATCH (v)
    WHERE id(v) == "<INSCRIRE_ID_ICI>"
    RETURN tags(v), properties(v);
    ```

Pour compter des sommets, `MATCH … RETURN count(n)` tag par tag, et non `SHOW STATS`, qui rend 0 sur un space peuplé ([livraison.md §4.2](livraison.md#42-les-huit-comptes-et-lempreinte-des-clés)).

## Problèmes rencontrés et solutions
- **Arrêts de NebulaGraph pendant l'ingestion** :
  - *Problème* : sur une machine sans marge mémoire, NebulaGraph s'arrêtait pendant les écritures continues de Docling, et ses conteneurs ne repartaient pas après un arrêt de la machine (par exemple une fermeture de WSL).
  - *Solution* : `restart: unless-stopped` sur `metad`, `storaged` et `graphd`, et une limite mémoire de **10 Go** pour `docling-service` (`deploy.resources.limits.memory`), qui laisse de la marge au moteur de graphe.
- **« DO NOT switch between graph spaces » dans Studio** :
  - *Problème* : Studio refuse une requête qui commence par `USE rag_space; MATCH ...`.
  - *Solution* : sélectionner l'espace dans l'interface ; les requêtes de ce document n'incluent pas de `USE`.
- **Écritures perdues sans erreur** :
  - *Problème* : un `USE rag_space` en échec, ou un antislash LaTeX mal échappé, faisait rejeter les `INSERT` sans que le run échoue.
  - *Solution* : `NebulaWriter.session` lève si `USE` échoue, tout `INSERT` rejeté lève `NebulaError` et fait échouer le job, et `ngql.escape_ngql` échappe l'antislash en premier.

## Vérification de la hiérarchie

Le code qui reconstruit la hiérarchie des titres est dans `hierarchy.py` (assemblage de l'arbre) et `ranking.py` (rang de chaque titre). `ranking.py` reçoit des mesures déjà prises et ne fait que décider : il n'importe ni Docling ni PyMuPDF, et se teste donc hors de l'image d'extraction.

`tests/unit/test_hierarchie_bout_en_bout.py` part d'items tels que Docling les rend, traverse le calcul du rang, et vérifie à l'arrivée la forme de l'arbre. Un test qui injecterait le rang à la main resterait vert même si `flat_rank` et `pdf_heading_rank` rendaient toujours `None` : tous les titres deviendraient alors frères sous le document, et le graphe serait plat.

La profondeur réelle se mesure après ingestion : `src/index_report.py` compte les documents par profondeur atteinte, et la distribution de référence (maximum 5) est consignée dans `ChunkMetadata.depth`.
