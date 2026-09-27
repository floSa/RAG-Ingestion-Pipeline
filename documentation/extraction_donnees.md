# Extraction des données (Docling)

`docling-service` convertit chaque document du corpus (PDF, HTML, Markdown) en
éléments structurés, via **Docling** (bibliothèque IBM d'analyse de mise en
page), puis les écrit dans NebulaGraph et ChromaDB. Cette page décrit ce que le
service fait des documents. Le conteneur, son API, ses variables et son
diagnostic sont dans la fiche [services/docling.md](services/docling.md).

## Chaîne d'extraction

### 1. Conversion

Docling itère sur les éléments du document via `document.iterate_items()`.
Chaque item porte un label (`section_header`, `text`, `picture`, `table`,
`code`, `formula`…), un numéro de page et une boîte englobante (*bounding box*).

Avant toute conversion, le service calcule l'empreinte SHA-256 du fichier. Un
fichier identique à un document déjà ingéré sous un autre chemin est ignoré ;
sinon, le document de même `source_path` est purgé des stores
(`storage.forget_document`) avant d'être réécrit, pour ne laisser aucun élément
orphelin quand son texte a changé (`extraction.extract`, registre 4.2).

Le régime dépend du format :

| Format | Régime |
|---|---|
| PDF | converti par lots de `PDF_BATCH_PAGES` pages (5 par défaut), pour borner la mémoire ; crop des images et tables vers le stockage objet |
| HTML | converti d'un seul tenant, depuis la copie nettoyée ; les images ont déjà été téléversées en amont |
| Markdown | images extraites et téléversées, paragraphes recollés, puis conversion d'un seul tenant |

Les lots de pages **ne se chevauchent pas** : les identifiants sont
déterministes, un recouvrement ne ferait que reconvertir les mêmes pages.


#### Pages écartées d'un PDF

Avant de découper en lots, `matter.py` établit la liste des pages à ne pas
convertir : couverture, page de titre, copyright, dédicace, sommaire, pages « à
propos de l'auteur », index (`FRONT_BACK_MATTER_TITLES`). Préface, glossaire et
annexes sont conservés : ce sont de la prose. La liste vient des **signets** du
PDF, qui donnent le titre de chaque partie et sa page **physique** : la
destination est résolue par le format, elle n'est pas le numéro imprimé dans
l'ouvrage, et le décalage habituel d'une à deux pages entre les deux ne
s'applique donc pas. Une partie qui dépasserait 35 % du document
(`MAX_SKIP_RATIO`) n'est pas écartée.

Quand les signets ne désignent pas l'index, celui-ci est reconnu à sa forme :
des lignes courtes terminées par des numéros de page, cherchées dans le dernier
quart du document seulement (`matter.detect_index_pages`).

Les lots sont ensuite construits **à l'intérieur des plages conservées**, jamais
à cheval sur une page écartée (`matter.page_batches`). Les numéros de page
restent ceux du fichier : rien n'est renuméroté, et `total_pages` reste le
nombre réel de pages de l'ouvrage.

Un PDF sans couche texte (un scan) est détecté avant la conversion sur un
échantillon de pages (`extraction._has_text_layer`) et converti avec l'OCR.

#### Images des documents Markdown

Un Markdown ne contient jamais ses images : il les **désigne**. Deux syntaxes
coexistent, et Docling n'en reconnaît aucune : il les rend en texte brut.

| Syntaxe | Origine | Ce qu'elle désigne |
|---|---|---|
| `![[fichier.jpg\|1000]]` | Obsidian | un nom de fichier, résolu par le coffre |
| `![legende](chemin)` | Markdown standard | un chemin relatif à la note |

Les liens sont donc extraits **avant** la conversion et remplacés par une balise
placée exactement où était l'image. Après conversion, la balise redevient un
élément de type `picture` portant l'adresse et la clé de l'objet téléversé.

La position compte autant que l'image : l'élément occupe le même rang dans
l'ordre de lecture, si bien que la légende qui suit la figure lui reste
adjacente et que la section qui la contient reste la sienne.

La résolution des chemins reproduit le comportement d'Obsidian, qui ne met que
le nom du fichier dans le lien : chemin relatif d'abord, puis recherche par nom
parmi les fichiers situés sous le dossier de la note (typiquement un dossier
`Pièces jointes/`). Les liens situés dans un bloc de code sont laissés intacts.

Conséquence pratique : copier une note sans son dossier de pièces jointes fait
perdre ses images. Copier le dossier entier.

#### Normalisation préalable du Markdown

Docling convertit le Markdown **ligne à ligne**. Un fichier dont les paragraphes
sont coupés à 80 colonnes, forme courante des exports et des notes écrites à la
main, produirait un élément par ligne source, et la recherche vectorielle
porterait sur des fragments de 75 caractères au lieu de paragraphes.

Les lignes d'un même paragraphe sont donc recollées avant la conversion
(`markdown.normalize_markdown`). Le fichier source n'est pas touché : la version
normalisée vit dans un répertoire temporaire. Tout ce qui n'est pas de la prose
est laissé intact (blocs de code clôturés ou indentés, tableaux, titres, listes,
citations, filets horizontaux, HTML en ligne), ainsi que les retours à la ligne
explicites du Markdown (deux espaces finaux, antislash final). Un fichier dont
les paragraphes tiennent déjà sur une ligne est rendu inchangé.

### 2. Identité du document

Le nom du fichier ne suffit pas à identifier un document. Un livre découpé en
chapitres donne des noms qui se répètent d'un ouvrage à l'autre (« Preface »,
« Index », « Appendix »). Deux chapitres homonymes produiraient les mêmes
identifiants d'éléments et se recouvriraient en silence.

C'est donc le **chemin relatif à `Datas/`**, la clé de partition Dagster, qui
porte l'identité. Le pipeline le transmet au service dans `source_path`, et
`elements.document_identity` en dérive trois informations (le segment
`.cleaned` des copies HTML nettoyées est retiré) :

| Champ | Valeur pour `htms/Practical MLOps/1. Introduction.html` |
|---|---|
| `filename` | `1. Introduction` : le chapitre |
| `collection` | `Practical MLOps` : l'ouvrage |
| `key` (clé des identifiants) | `htms/Practical MLOps/1. Introduction` |

Sans `collection`, une réponse du RAG pourrait citer le chapitre sans pouvoir
dire de quel livre il vient.

### 3. Identité des éléments

Chaque élément reçoit un identifiant court et déterministe
(`elements.compute_id`) :

```
sha256(key | page_no | position_in_page | text[:50])[:10]
```

`key` est la clé du document ci-dessus, et non le seul nom de fichier. La
position retenue est celle **dans la page**, pas l'ordre global de lecture :
reconvertir un document produit les mêmes identifiants.

Le format, dix caractères hexadécimaux, est celui qu'attend `rag-agent-chat`,
qui valide `/context/{element_id}` sur `^[a-f0-9]{10}$`.


### 4. Hiérarchie et positions

**Une seule règle, quelle que soit la source :**

> Le parent d'un titre est le titre précédent de **rang supérieur**. Tout autre
> élément se rattache au titre le plus profond encore ouvert.

Le rang est un petit entier où 0 désigne le niveau le plus haut. La règle vit
dans `hierarchy.HeadingStack` ; ce qui change d'un format à l'autre, c'est
seulement d'où vient le rang (`ranking.py`) :

| Source | Signal utilisé | Ce que ça donne |
|---|---|---|
| HTML | le parent que Docling déclare | hiérarchie fidèle |
| Markdown | l'attribut `level` (1 pour `##`, 2 pour `###`) | fidèle aux dièses |
| PDF | la **taille de police** | reconstruite, voir plus bas |

Pour un document non paginé, `ranking.flat_rank` essaie le parent déclaré puis
`level` ; pour un PDF, `ranking.pdf_heading_rank` classe par taille de police.
Quand aucun signal ne répond, tous les titres reçoivent le rang 0 et restent
frères sous le document : c'est le pire cas, un graphe plat. **La hiérarchie
n'est jamais inventée.**

La section courante **survit aux lots de pages** (`DocumentAccumulator`), de
sorte que la hiérarchie d'un livre ne se brise pas toutes les cinq pages.

#### Pourquoi la taille de police pour les PDF

Docling ne déclare aucun parent sur un PDF et attribue le même niveau à tous les
titres : sur `statisticsfordatascience`, 333 en-têtes, tous au niveau 1, tous
rattachés au corps du document. La taille de police, elle, est **écrite en clair
dans le fichier** : chaque bloc de texte porte l'instruction qui la fixe. Elle
est lue, pas estimée.

Le relevé se fait une fois par document, avec PyMuPDF, sans modèle
(`extraction._pdf_font_profile`) :

1. la taille qui porte le plus de caractères est celle du **corps du texte** ;
2. les tailles supérieures sont celles des titres, classées de la plus grande à
   la plus petite ;
3. le rang dans ce classement donne le niveau.

**Aucune valeur n'est écrite en dur.** Le classement est recalculé pour chaque
fichier : un ouvrage composé en 24/22/20 points se segmente exactement comme un
ouvrage en 20/18/16.

Deux garde-fous, parce que ce signal est le seul indirect :

- un titre dont la boîte est **contenue dans une image ou un tableau** est écarté
  du classement : le texte d'une figure peut être grand sans être un titre de
  section ;
- un titre **pas plus grand que le corps du texte** ne crée pas de niveau. Sans
  cela, un faux positif de détection ouvrirait une branche parasite.

Un titre écarté par l'un de ces garde-fous reçoit le rang de repli, le plus
profond (`ranking.fallback_rank`), **jamais le rang zéro** : le promouvoir
chapitre remettrait tout l'arbre à zéro. Le nombre de titres tombés au rang de
repli est journalisé à la fin de chaque PDF (registre 4.21).

#### Profondeur : aucun plafond

`depth` compte les arêtes `PARENT_OF` qui séparent l'élément de la racine de son
document. Elle n'a pas de plafond (registre 4.24). La règle, les deux échelles
qui s'y croisent (titre ou autre élément) et la distribution mesurée sont
décrites dans `ChunkMetadata.depth` (`src/pipeline/schemas.py`).

La profondeur est toujours celle du parent plus un, jamais le rang brut. Un faux
titre minuscule se range donc juste sous son prédécesseur au lieu de tomber au
niveau 9 et de trouer l'arbre.

#### Résultat vérifié

Chapitre 3 de `statisticsfordatascience`, reconstruit par le pipeline et comparé
**ligne à ligne** au sommaire imprimé de l'ouvrage :

```
[0] 3
[0] A Developer's Approach to Data Cleaning
    [1] Understanding basic data cleaning
        [2] Common data issues
        [2] Contextual data issues
        [2] Cleaning techniques
    [1] R and common data issues
        [2] Outliers
            [3] Step 1 - Profiling the data
            [3] Step 2 - Addressing the outliers
        [2] Domain expertise
        [2] Validity checking
    [1] Summary
```

Chaque élément porte donc :

| Champ | Signification |
|---|---|
| `reference_id` | parent : identifiant du titre dominant, ou `DOC` |
| `depth` | profondeur dans la hiérarchie, 0 pour un titre de tête |
| `page_position` | rang de l'élément dans sa page |
| `ref_position` | rang de l'élément sous son parent |
| `order` | ordre de lecture global, porté par l'arête `PARENT_OF` (propriété `sequence`) |
| `page_no` / `page_no_end` | première et dernière page couvertes ; elles diffèrent pour un élément que Docling a fusionné par-dessus une frontière de page (registre 4.22) |

### 5. Contenu des tables

Une table Docling ne porte pas de texte : son `text` vaut `None` et le contenu
vit dans une structure dédiée. Sans export explicite, les tables seraient
présentes dans le graphe mais introuvables par la recherche vectorielle. Leur
contenu est donc récupéré via `export_to_markdown()` (`elements.item_text`), ce
qui les rend interrogeables en texte tout en conservant, pour les PDF, le crop
image dans le stockage objet.

### 6. Liaison légende vers ressource

Une légende (`caption`) est reliée par une arête `LINKED_TO`
(`relation = "describes"`) au dernier élément `Table` ou `Picture` rencontré
avant elle dans l'ordre de lecture, au sein du même lot
(`nebula.NebulaWriter.write_elements`).

### 7. Médias : crop, téléversement, adresse

Les trois chemins d'image passent par `extraction.poser_le_media`, qui pose
d'un seul geste `media_url` (adresse de l'objet) **et** `object_key` (clé nue,
dérivée par `images.object_key`, inverse exact de `images.object_url`). Un
élément à demi renseigné ne serait corrigé par rien, le graphe n'étant écrit
qu'une fois.

**PDF.** Pour les éléments visuels (`picture`, `table`, `figure`, `graphic`),
`images.crop_and_upload` :

1. utilise le document **PyMuPDF** déjà ouvert : une seule ouverture par
   document, et non une par image ;
2. découpe la page aux coordonnées de la boîte, avec un facteur de zoom
   (`IMAGE_CROP_ZOOM`, 2 par défaut) ;
3. pousse le PNG dans le bucket `S3_BUCKET` (`documents`) sous
   `images/<document>/<id>_<label>.png`.

Docling raisonne avec l'origine en bas de page, PyMuPDF en haut : la conversion
de coordonnées est faite dans `images.crop_and_upload`.

**Markdown.** Les fichiers désignés par la note sont téléversés tels quels
(`images.upload_file`, préfixe `images/md/`).

**HTML.** Les images ont déjà été téléversées par l'asset de nettoyage Dagster
(`src/pipeline/media.py`, préfixe `images/html/`), qui réécrit les `img src` du
HTML nettoyé. Docling ne rend pas ces adresses : le service les relit dans le
HTML nettoyé (`extraction.html_image_urls`) et les pose par correspondance
positionnelle, la n-ième `<img>` sur le n-ième `picture`
(`extraction.propager_les_url_dimages`). Si les deux comptes diffèrent, aucune
adresse n'est posée : une adresse fausse servirait l'illustration d'un autre
passage, une adresse absente est comptée par `verify_contract` (registre 3.5).

L'adresse est interne à `rag_network` et authentifiée ; le contrat de ces deux
champs est décrit dans
[llm_integration_plan.md §4](llm_integration_plan.md) et
[services/stockage_objet.md](services/stockage_objet.md).

### 8. Persistance

Chaque lot d'éléments est validé contre le schéma partagé (`DocumentElement`,
`src/pipeline/schemas.py`), puis écrit dans le graphe **puis** dans l'index
vectoriel (`storage.persist`). L'ordre compte : si NebulaGraph refuse le lot,
les vecteurs correspondants ne sont pas indexés et l'erreur remonte jusqu'au
job.

#### Ce qui part dans l'index vectoriel

Le graphe reçoit **tous** les éléments. L'index vectoriel, lui, reçoit des
chunks découpés par **`HybridChunker`**, le découpeur de Docling
(`vectors.get_chunker`).

**Pourquoi `HybridChunker`.** Un découpage à la longueur en caractères coupe
sans savoir où il coupe. `HybridChunker` respecte la structure du document et
reçoit **le tokenizer du modèle d'embedding lui-même**, avec sa fenêtre
(`max_seq_length`, lue à l'exécution). Il n'existe donc aucune taille de chunk
ni recouvrement à régler (registre 5.1). Il peut malgré tout dépasser la
fenêtre : il ne fractionne pas une table, et le titre de section est préposé
après son travail. Le chiffre et ses deux causes sont documentés dans
`vectors.get_chunker` (registre §3.4 bis).

Comparaison avec l'ancien découpage en caractères, retiré du dépôt, sur le
chapitre 1 de `Practical MLOps`. La mesure date d'un corpus antérieur et n'a
pas été rejouée (registre 5.1, 6.10).

| Mesure | Découpage en caractères (450 car.) | `HybridChunker` |
|---|---|---|
| chunks produits | 146 | **100** |
| tokens, médiane | 67 | **91** |
| caractères, médiane | 269 | **353** |

À contenu égal, quarante-six chunks de moins, chacun portant davantage de
contexte.

**Le plancher, et sa borne.** Un chunk sans caractère alphanumérique, ou plus
court que `MIN_CHUNK_CHARS`, est écarté de l'index ; il demeure dans le graphe.
Ce rejet ne s'applique qu'à un chunk qui est le **seul** de son élément
(`vectors.build_chunks`). Une fenêtre du milieu d'un texte continu est
conservée même courte : sinon, l'agent qui concatène les chunks d'un élément
obtiendrait un texte troué (registre 4.28.a).

**Les identifiants restent ceux du contrat.** `HybridChunker` rend ses chunks
avec ses références internes (`#/texts/18`), alors que le contrat impose les
hash de dix hexadécimaux du service. Le module
[`anchoring.py`](../src/docling_service/anchoring.py) fait le pont, et couvre
les deux cas qui se présentent :

- **un chunk couvre plusieurs éléments** (c'est le but du regroupement) :
  l'ancre est le **premier** élément connu, celui d'où part la lecture ;
- **plusieurs chunks partagent une ancre** (un élément trop long pour la
  fenêtre est réparti) : leur id reçoit les suffixes `#0`, `#1`
  (`chunking.chunk_id`) ; un élément tenu en un seul chunk garde son id nu.

Un chunk dont aucune référence n'est connue est **écarté** plutôt que rattaché
au hasard.

`element_id` et `graph_node_id` désignent donc toujours un nœud réel du graphe,
au format attendu par `rag-agent-chat`. La métadonnée `block_size` indique
combien d'éléments le chunk couvre.

#### Effet mesuré

Mesure historique, sans date, sur un corpus de référence qui n'est plus sur la
machine (registre 6.10) : mixte français/anglais, 42 documents dont un PDF de
280 pages, 36 chapitres HTML et des notes Markdown. Ces chiffres documentent la
décision de regrouper ; ils ne décrivent pas l'index en service.

| Mesure (corpus de référence disparu) | Avant | Après |
|---|---|---|
| chunks indexés | 22 937 | 5 246 |
| sans aucun caractère alphanumérique | 5,0 % | 0,0 % |
| de moins de 15 caractères | 36,0 % | 0,0 % |
| taille médiane d'un chunk | — | 277 car. |
| chunks issus d'une fusion | 0 % | 51,5 % |
| chunks portant un titre de section | 0 % | 100 % |

L'index perdait 77 % de ses entrées sans perdre de contenu : ce qui
disparaissait, ce sont les fragments de mise en page et les doublons de
granularité.

Les comptes de l'index en service (chunks, sommets, documents, chunks tronqués)
sont dans [livraison.md §4.2](livraison.md#42-les-huit-comptes-et-lempreinte-des-clés)
et [§4.6](livraison.md#46-index_report--lindex-vectoriel).

**Limite connue.** Une part des chunks dépasse la fenêtre du modèle
d'embedding et est tronquée par le modèle ; le texte stocké reste intégral.
`index_report` donne ce chiffre en tokenisant le texte tel que le modèle le
reçoit (préfixe du titre de section compris, via `chunking.embedding_inputs`).
Avant préfixe, les chunks qui dépassent sont des tables (registre §3.4).

#### Contextualisation des vecteurs

Un passage isolé de son titre perd une part de son sens : « la moyenne est
sensible aux valeurs extrêmes » ne dit pas de quoi elle est la moyenne. Le titre
de la section courante est donc préposé au texte **envoyé au modèle
d'embedding**, sans coût de calcul (`chunking.contextualize`, sur le principe
du `contextualize()` de Docling et du *contextual retrieval*).

Le texte **stocké** reste le texte brut : côté agent, l'utilisateur voit le
passage tel qu'il figure dans le document. Le titre part aussi en métadonnée
`section_title`. Réglable par `EMBED_SECTION_CONTEXT`.

## Format d'un élément

```json
{
  "id": "023351d5f4",
  "label": "section_header",
  "page_no": 1,
  "bbox": {"l": 108.0, "t": 267.8, "r": 190.81, "b": 257.05},
  "page_no_end": 1,
  "text": "1 Introduction",
  "order": 7,
  "reference_id": "DOC",
  "depth": 0,
  "section_title": "1 Introduction",
  "page_position": 7,
  "ref_position": 0
}
```

Les éléments visuels portent en plus `media_url` et `object_key`. `bbox` vaut
`null` pour les formats non paginés (HTML, Markdown), qui n'ont pas de
coordonnées. L'élément en mémoire porte aussi `self_ref`, la référence interne
Docling qui sert au rattachement des chunks ; elle ne part dans aucun store.

## Configuration Docling

```python
options = PdfPipelineOptions(do_ocr=ocr, do_table_structure=False)
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
)
```

(`extraction.get_converter`.) La reconstruction de structure des tables est
désactivée : elle multiplie le temps de conversion, et les tables sont de toute
façon croppées en image et poussées dans le stockage objet. L'OCR n'est activé
que pour un PDF sans couche texte (un scan), détecté avant la conversion
(`extraction._has_text_layer`).

## Problèmes connus et solutions

- **Mémoire saturée (OOM)** : 14 Go de RAM consommés sur une machine WSL de
  16 Go faisaient tomber les autres services. Solution : limite à 10 Go,
  `do_table_structure=False`, `PDF_BATCH_PAGES=5`, et le backend Docling est
  déchargé entre deux lots (`extraction._convert_batch`).

- **Crop muet** : les images n'arrivaient pas dans le bucket, sans erreur.
  Cause : axe Y inversé entre Docling (origine en bas) et PyMuPDF (origine en
  haut).

- **Formules LaTeX perdues** : l'échappement nGQL traitait le guillemet mais pas
  l'antislash, si bien qu'un texte contenant `\frac` ou `\alpha` produisait une
  requête invalide et que les nœuds `Formula` d'un livre de mathématiques
  étaient rejetés en silence. L'antislash est échappé en premier
  (`ngql.escape_ngql`, couvert par des tests).

- **Lots perdus en silence** : une erreur de conversion était journalisée puis
  oubliée, et le run se terminait en succès sur un document incomplet. Les lots
  en échec sont désormais collectés, la conversion continue jusqu'au bout, puis
  le document partiel est **retiré des stores** et le job échoue en listant les
  pages manquantes (`BatchExtractionError`, registre 4.1). Un document est
  entièrement dans les stores, ou pas du tout.

Commandes de journal, d'extraction manuelle et de suivi de job :
[services/docling.md](services/docling.md#diagnostic).
