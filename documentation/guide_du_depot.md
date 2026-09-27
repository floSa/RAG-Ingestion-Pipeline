# Guide du dépôt — sources, règles d'ingestion, structure et garde-fous

> Ce guide décrit comment ajouter une source, les règles que l'ingestion
> applique, l'exploration du graphe, la structure du dépôt, la porte qualité, les
> garde-fous git et les licences. Les procédures d'exploitation (démarrer,
> ingérer, réingérer, purger, vérifier, revenir en arrière) et toutes les
> mesures en service sont dans [`livraison.md`](livraison.md), qui fait
> référence. [`axes_amelioration.md`](axes_amelioration.md) (le registre),
> [`pilotage_du_chantier.md`](pilotage_du_chantier.md) et
> [`campagnes/`](campagnes/) sont des archives datées, non tenues à jour.

---

## Ajouter une nouvelle source

Ajouter une source (par exemple un site capturé avec [SingleFile](https://github.com/gildas-lormeau/SingleFile)) ne demande **aucun code Python** :

1. Déposer les fichiers dans un sous-dossier de `./Datas`, par exemple `Datas/captures/monsite/`.
2. Déclarer la source dans `src/pipeline/sources.yaml` :
   ```yaml
   - name: capture_monsite
     glob: "captures/monsite/**/*.html"
     type: html
     cleaning:                                    # optionnel
       extra_remove_selectors: [".cookie-banner"]
   ```
3. Recharger le code location dans l'interface Dagster (bouton **Reload definitions**). Un capteur `capture_monsite_sensor` apparaît (nom `<name>_sensor`, `src/pipeline/factory.py`) et ingère les fichiers.

Toute nouvelle source déplace les comptes de référence et l'empreinte des clés
d'objets, et périme le jeu de 30 questions ([§8.4 de `livraison.md`](livraison.md#84-les-sources-enfichables)).

### Les trois types de sources

| `type` | Chaîne d'assets | Quand l'utiliser |
|---|---|---|
| `pdf` | extraction directe, par lots de pages, images découpées (crops) vers le stockage d'objets | Livres et documents paginés |
| `html` | nettoyage universel puis extraction | Captures de sites, livres découpés en chapitres HTML |
| `md` | extraction directe | Markdown déjà propre : notes, exports, documentation |

Le Markdown ne passe pas par le nettoyage : il n'a ni boilerplate à retirer ni image inline à exporter.

```yaml
- name: markdown
  glob: "mds/**/*.md"
  type: md
```

Deux points à connaître.

**Docling convertit le Markdown ligne par ligne.** Un fichier dont les paragraphes sont coupés à 80 colonnes produirait un élément par ligne, et la recherche porterait sur des fragments de 75 caractères. Les paragraphes sont donc recollés avant conversion (`src/docling_service/markdown.py`), sans toucher au fichier source, en laissant intacts blocs de code, tableaux, listes, titres et retours à la ligne explicites.

**Un Markdown ne contient pas ses images, il les désigne.** Les deux syntaxes sont reconnues — `![[fichier.jpg|1000]]` d'Obsidian et `![légende](chemin)` du standard — et les images sont téléversées puis rattachées à leur place exacte dans le document. Il faut donc **copier le dossier entier**, notes *et* pièces jointes : une note copiée seule perd ses figures.

### Nettoyage HTML universel

Les sources HTML passent par un nettoyage en étages (`src/pipeline/cleaning.py`), sans configuration par site :

1. **Formules mathématiques** : les formules rendues (KaTeX, MathJax v2/v3, MathML) sont remplacées par leur source LaTeX — `$...$` (inline) ou `$$...$$` (bloc) — récupérée dans le DOM avant toute suppression. Sans cela, le rendu web produit du texte dupliqué illisible.
2. **Pré-passe d'hygiène** : suppression des scripts, styles, éléments cachés (`sf-hidden`, `display:none`), chrome de page (nav, rôles ARIA), commentaires, icônes inline (< 4 Ko) et décorations d'ancres dans les titres. Les **images base64 volumineuses sont exportées vers le stockage d'objets** (`src/pipeline/media.py`) et leur `src` réécrit, comme les crops PDF. Les `header`, `footer` et `aside` internes à un `<article>`/`<main>` sont conservés : le premier porte le titre de chapitre, le dernier les encadrés du livre (interviews, notes, avertissements).
3. **Extraction de contenu** : un profil par site (s'il est déclaré) gagne directement ; sinon les conteneurs sémantiques HTML5 (`<article>`, `<main>`) font autorité ; sinon [trafilatura](https://trafilatura.readthedocs.io/) et readability-lxml sont comparés et le plus complet gagne. Si aucun `<h1>` ne survit, le titre de la page est réinjecté (structure propre pour Docling).
4. **Garde-fou** : si trop peu de texte est extrait (`min_text_chars`, `min_text_ratio`), le HTML pré-nettoyé est conservé tel quel et un avertissement apparaît dans les journaux Dagster.

**Ce que le nettoyage retire.** Le fichier maigrit fortement — une capture SingleFile de 2,8 Mo tombe à 62 Ko — mais **cette division par 45 porte sur le poids du fichier, pas sur le contenu**. Le volume d'une capture est fait de scripts, de feuilles de style et d'images encodées en base64 dans le HTML. Mesuré sur les chapitres de `Practical MLOps` :

| | Avant nettoyage | Après nettoyage |
|---|---|---|
| Poids du fichier | 2,77 Mo | 61,6 Ko |
| Caractères de texte | 34 704 | 34 316 |
| Blocs de code | 186 | 186 |
| Images | 13 | 13 (déplacées sur le stockage d'objets) |
| Tableaux | conservés | conservés |

**Le texte perd environ 1 %**, et ce 1 % est le chrome du lecteur : « Table of contents », « Search », « Sign out ». Code, images, tableaux et titres passent intégralement.

La stratégie retenue, les tailles avant/après et le nombre d'images exportées sont visibles dans les métadonnées de l'asset `cleaned_html` de chaque partition. Si un site ressort mal, lui déclarer un profil `detect`/`content`/`strip` dans `sources.yaml` (voir l'exemple en tête du fichier).

### Ce qui n'est ingéré qu'une fois : détection des doublons

Le même ouvrage peut revenir sous deux noms — une copie de sauvegarde, un téléchargement refait. Deux cas, deux traitements :

| Cas | Traitement |
|---|---|
| **Le même fichier, même chemin, réingéré** | Les identifiants d'éléments sont déterministes et les écritures sont des *upserts* : la nouvelle version écrase l'ancienne. Aucun doublon possible. |
| **Le même fichier, sous un autre nom ou un autre dossier** | L'empreinte SHA-256 du fichier est portée par le nœud `Document`. Avant toute conversion, le service cherche si un autre document porte la même empreinte : si oui, le fichier est **ignoré**, le run réussit et signale `duplicate_of` avec le chemin de l'original (`src/docling_service/extraction.py`). |

Le contrôle a lieu **avant la conversion** : reconnaître un doublon coûte une lecture de fichier, le convertir pour rien coûte plusieurs minutes de calcul.

**Ce qui n'est pas détecté, volontairement** : deux éditions différentes du même livre, ou le même ouvrage en PDF et en HTML. Les fichiers diffèrent, donc les empreintes aussi. Les rapprocher demanderait une comparaison approximative, qui écarterait à tort des ouvrages légitimes — un risque plus grave que le doublon lui-même.

### La hiérarchie des titres

Un chapitre contient des sections, qui contiennent des sous-sections. Cette imbrication est reconstruite à l'ingestion, **avec une règle unique pour les trois formats** :

> Le parent d'un titre est le titre précédent de **rang supérieur**. Les autres éléments se rattachent au titre le plus profond encore ouvert.

Ce qui change d'un format à l'autre n'est pas la règle, mais d'où vient le rang (`src/docling_service/ranking.py`) :

| Format | Signal | Résultat |
|---|---|---|
| **HTML** | le parent que Docling déclare | hiérarchie fidèle, jusqu'à 4 niveaux |
| **Markdown** | l'attribut `level` (1 pour `##`, 2 pour `###`) | fidèle aux dièses du fichier |
| **PDF** | la **taille de police**, lue dans le fichier | reconstruite, voir ci-dessous |

Le code n'a aucune branche par format : il essaie les signaux dans l'ordre et prend le premier qui répond. **Si aucun ne répond, tous les titres restent frères sous le document.** La hiérarchie n'est jamais inventée.

**Le cas des PDF.** Docling ne déclare aucun parent sur un PDF et met tous les titres au même niveau — mesuré : 333 en-têtes, tous au niveau 1. Mais la taille de police est **écrite en clair dans le fichier** ; elle est lue, pas estimée. Le relevé se fait une fois par document : la taille qui porte le plus de caractères est celle du corps du texte, les tailles supérieures sont celles des titres, et leur rang donne le niveau.

**Aucune valeur n'est écrite en dur** : un ouvrage composé en 24/22/20 points se segmente exactement comme un ouvrage en 20/18/16.

Deux garde-fous : un titre dont la boîte est **contenue dans une image ou un tableau** est écarté (le texte d'une figure peut être grand), et un titre **pas plus grand que le corps du texte** n'ouvre pas de niveau. Un titre écarté prend le rang le plus profond, jamais le rang zéro : le promouvoir chapitre remettrait tout l'arbre à zéro.

**La profondeur n'est pas plafonnée** (registre §4.24). Comment lire `depth`, qui mélange deux échelles selon `label` : [§5.1 de `etat_des_lieux.md`](etat_des_lieux.md#51-depth-mélange-deux-échelles-et-label-dit-laquelle).

**Vérifié contre le sommaire imprimé de l'ouvrage, ligne à ligne :**

```
[0] 3
[0] A Developer's Approach to Data Cleaning
    [1] Understanding basic data cleaning
        [2] Common data issues
        [2] Contextual data issues
    [1] R and common data issues
        [2] Outliers
            [3] Step 1 – Profiling the data
            [3] Step 2 – Addressing the outliers
        [2] Domain expertise
    [1] Summary
```

Chaque chunk porte sa profondeur sous la clé `depth`. Le rapport d'index (`src/index_report.py`) compte les documents par profondeur atteinte, ce qui montre lesquels sont restés plats.

### La langue de chaque document

Chaque document est identifié dans l'une de sept langues (`en`, `fr`, `es`, `de`, `it`, `pt`, `nl`, `src/docling_service/language.py`), et cette langue est portée par le nœud `Document` **et par chaque chunk** : l'agent peut donc filtrer sans repasser par le graphe. La valeur reste vide en cas de doute.

Le modèle d'embedding du contrat, `paraphrase-multilingual-MiniLM-L12-v2`, est **multilingue** : une question française retrouve les passages anglais, et réciproquement. L'ancien modèle `all-MiniLM-L6-v2`, entraîné sur l'anglais seul, ne doit pas être utilisé (registre §6.14). La mesure des deux modèles, les scores comparés et les quatre façons de traiter le multilingue sont dans [base_vectorielle.md](base_vectorielle.md#pourquoi-un-modèle-dembedding-multilingue).

### Ce qui n'est pas ingéré : index, sommaire, pages liminaires

Un livre ne contient pas que du contenu. **L'index est le pire cas pour un RAG** : une liste de mots suivis de numéros de page, sans une phrase à indexer, mais qui contient tout le vocabulaire de l'ouvrage — il ressort donc sur presque toutes les questions sans rien apporter. Sommaire, couverture et page de copyright ont le même profil.

Sont écartés par défaut : `Index`, `Table of Contents`, `Contents`, `Cover`, `Copyright`, `Credits`, `Colophon`, `Title page`, `Dedication`, `About the author`, `About the reviewer`, et leurs équivalents français. La liste complète est `FRONT_BACK_MATTER_TITLES` dans [`matter.py`](../src/docling_service/matter.py).

**Ne sont pas écartés, volontairement** : préface, glossaire (`Key Terms`) et annexes. C'est de la prose, et un glossaire répond bien aux questions « c'est quoi X ? ».

Le repérage dépend du format :

| Format | Comment la partie est reconnue |
|---|---|
| Livre découpé en fichiers (HTML, MD) | **Par le nom du fichier**. `Index.html` n'est même pas transformé en partition : ni run, ni place, ni bruit. |
| PDF | **Par les signets du document** — l'arborescence cliquable du volet gauche d'un lecteur PDF. Elle donne le titre de chaque partie et sa page de début. |

**Le décalage des pages ne se pose pas.** Dans un livre, le sommaire imprimé annonce des numéros qui ne correspondent pas au rang réel de la page dans le fichier, avec un écart d'une à deux pages. Les signets, eux, portent une **destination interne** que le format résout en page physique. Vérifié sur `statisticsfordatascience.pdf` : le sommaire imprimé annonce la préface page 1, alors qu'elle commence physiquement page 19 — et le signet donne bien 19.

**Filet de sécurité.** Beaucoup de PDF n'ont pas de signets, ou en ont d'incomplets. Dans ce cas l'index est reconnu **à sa forme** : des lignes courtes terminées par un ou plusieurs numéros de page, cherchées uniquement dans le dernier quart du document (`INDEX_SEARCH_TAIL_RATIO = 0.25`) pour ne pas confondre un index avec un tableau de résultats en plein chapitre.

Un garde-fou refuse d'écarter plus de 35 % d'un document (`MAX_SKIP_RATIO`) : au-delà, c'est forcément un signet parent mal interprété, pas un index.

Pour ajuster, par source dans `sources.yaml` :

```yaml
  - name: livres_html
    glob: "htms/**/*.html"
    type: html
    skip_front_back_matter: true          # défaut
    extra_skip_titles: ["About this book"] # ajouts à la liste par défaut
```

Le nombre de pages écartées apparaît dans les métadonnées du job (`skipped_pages`) et dans les journaux du service.

---

## Ingestion à grande échelle

Le chemin nominal d'un fichier déposé est au
[§3.1 de `livraison.md`](livraison.md#31-le-chemin-nominal--un-fichier-déposé).

**Comment le débit est cadencé.** Le capteur crée une partition et un run par fichier. La file Dagster n'en exécute que deux à la fois (`max_concurrent_runs: 2` dans `dagster.yaml`), et le service Docling ne convertit qu'un document à la fois : les autres runs attendent dans **Runs → Queued**. Rien ne sature, rien ne se perd, et l'ordre est celui de la découverte.

Validé en conditions réelles : 120 fichiers déposés d'un coup produisent **120 partitions et 120 runs dans un seul passage de capteur**, traités en 6 minutes. Un test unitaire vérifie cette propriété jusqu'à 250 fichiers.

**Si le service redémarre en cours de route.** Sa file de jobs vit en mémoire : les documents en cours sont perdus. Les assets d'extraction portent donc une politique de reprise (`EXTRACTION_RETRY_POLICY`, `src/pipeline/factory.py` : deux reprises, délai de 120 s croissant exponentiellement) qui rattrape le cas sans intervention. Les échecs propres à un document ne sont pas retentés : reconvertir 400 pages pour retomber sur la même page illisible est inutile.

**Suivre un document.** Chaque run journalise l'avancement de son job au plus toutes les 15 secondes (`extraction_poll_seconds`, `src/pipeline/settings.py`) : pages traitées, éléments extraits, chunks écrits. À la fin, les métadonnées de l'asset `extracted_document` récapitulent le total et la durée. Côté service :

```bash
docker compose logs -f docling-service
```

**Ce qui fait échouer un run, et ce que cela veut dire.**

| Message | Cause | Que faire |
|---|---|---|
| `Job ... inconnu du service Docling (redemarrage ?)` | Le service a redémarré, la file est en mémoire | La politique de reprise relance ; sinon, relancer la partition depuis l'interface Dagster |
| `N batch(s) non convertis` | Des pages n'ont pas pu être lues par Docling | Les autres pages sont bien ingérées ; le message liste les pages manquantes |
| `Service Docling toujours pas pret` | Modèles ou schéma NebulaGraph pas encore initialisés | Attendre la fin du démarrage (`docker compose ps` : `healthy`) |
| `nGQL rejete ...` | Écriture refusée par le graphe | Le run échoue volontairement plutôt que de laisser un graphe incomplet |

**Débit et ressources.** Les durées d'ingestion par unité sont dans [orchestration.md](orchestration.md#combien-de-temps-prend-une-ingestion) ; la mémoire, le disque et le minimum recommandé dans le [README](../README.md#ressources-nécessaires). Pendant une ingestion continue, la mémoire de `docling-service` a été relevée toutes les 20 à 30 secondes pendant une demi-heure (111 mesures en régime) : **médiane 6,08 Gio, pic 6,43 Gio**, pour une limite de 10 Go (`docker-compose.yml`). L'essentiel est constitué des modèles, chargés une fois pour toutes. Une consommation qui grimpe au fil des livres est anormale : arrêter l'ingestion et le signaler plutôt que d'attendre le plafond.

### Ce que la purge retire

La procédure (commande, redémarrage de `docling-service`, compte attendu,
point d'arrêt) est au
[§3.3 de `livraison.md`](livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit).
`src/wipe_stores.py` purge **quatre** choses, et sa sortie titre chacune
(`--- ChromaDB ---`, `--- Stockage objet (<adresse>) ---`, `--- NebulaGraph ---`,
`--- HTML nettoye ---`) :

| Ce qui est purgé | Pourquoi |
|---|---|
| la collection ChromaDB `rag_documents` | les vecteurs |
| le space NebulaGraph `rag_space` | le graphe |
| le bucket `documents` du stockage d'objets | les crops et images ; sans purge, ceux des ingestions précédentes s'accumuleraient |
| `Datas/.cleaned/` | les copies nettoyées **orphelines**. Une réingestion réécrit déjà une copie nettoyée périmée ; ce qu'elle ne réécrit jamais, ce sont les copies des documents que le corpus n'a **plus**, qui pointent des objets supprimés par la purge du bucket (registre §4.33.a). La partition dynamique Dagster d'un document disparu survit aussi, et `wipe_stores` n'y touche pas (registre §4.34.g). Vérifié par `TestCeQueLaPurgeDuNettoyeRetireVRAIMENT` (`tests/unit/test_factory.py`) |

Le script sort en **code d'erreur** si l'une des quatre purges échoue : une purge partielle est pire qu'une purge absente, puisque la réingestion écrit alors par-dessus des restes (`test_un_echec_de_purge_du_html_fait_sortir_en_un`, `tests/unit/test_wipe_stores.py`).

**Le sous-répertoire `.cleaned` n'est pas configurable, délibérément.** C'est une constante du code (`CLEANED_SUBDIR` dans `src/docling_service/elements.py`). Configurable, il décidait seul de la cible du `rmtree` : certaines valeurs visaient `Datas/` ou son parent, d'autres, contenues dans la racine, en détruisaient le contenu, et toute valeur autre que le défaut déplaçait les `element_id` de tout le corpus. `SOURCE_DIR` reste un réglage : une racine mal réglée fait sortir le script en 1 plutôt que de supprimer ce qu'elle désigne. `purge_cleaned`, fonction publique, refuse en outre toute cible qui n'est pas `SOURCE_DIR/.cleaned` ou l'un de ses descendants, par une erreur distincte (`CibleHorsDuNettoyeError`) : la première erreur met en cause `SOURCE_DIR`, la seconde l'argument.

### Pourquoi redémarrer `docling-service` avant de réingérer

Le geste est au [§3.3 de `livraison.md`](livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit). C'est `init_schema()` qui crée le schéma du graphe et joue les `ALTER TAG … ADD`, et il n'est appelé **qu'au démarrage du service** (`src/docling_service/main.py`, dans le `lifespan`). La purge supprime le space NebulaGraph ; sans redémarrage, la réingestion écrit contre un schéma absent ou incomplet, et `graphd` rejette les `INSERT`. C'est aussi le seul moyen de faire évoluer le schéma du graphe. Redémarrer est sans coût quand le schéma est déjà à jour. `restart` ne relit pas le `.env` ([§6.4 de `livraison.md`](livraison.md#64-restart-ne-relit-pas-le-env)).

`verify_contract` distingue deux anomalies de schéma, qui demandent deux gestes différents (registre §4.29.e) :

- « la colonne n'existe pas » : redémarrer le service **puis** réingérer ;
- « la colonne existe, les données sont à NULL » : réingérer.

### Comment le marqueur de réingestion se comporte

Le geste (commande, étiquette neuve, runs attendus, lecture des curseurs) est au
[§3.2 de `livraison.md`](livraison.md#32-réingérer--le-marqueur-sur-le-curseur).
Le marqueur se pose aussi depuis l'interface Dagster : **Overview → Sensors → le
capteur → Cursor → Edit cursor**. Son préfixe est la constante
`PREFIXE_REINGESTION` (`src/pipeline/factory.py`).

| | |
|---|---|
| **Ce qui déclenche** | ce marqueur, et rien d'autre. Le tick qui le lit repart sans aucun `mtime` connu (le marqueur a remplacé le curseur JSON qui les portait), redemande une partition par fichier, et fait porter **l'étiquette** à la clé de run : c'est ce qui la rend neuve pour Dagster. |
| **Ce qui empêche un départ spontané** | deux choses, qui ne couvrent pas le même cas. D'abord **le curseur** : il vit dans le stockage de l'instance, survit au rechargement du code, aucune ligne du dépôt ne l'efface, et tant qu'il est là le capteur ne demande rien sur un corpus inchangé. Ensuite, **sans marqueur, la clé garde sa forme** `{source}_{partition}_{mtime}` : si le curseur est perdu **seul**, historique intact (remise à zéro à la main, capteur ou code location renommé), le capteur redemande tout, Dagster ne crée aucun run, et le capteur le **journalise**. `TestLaCleNominaleEstInchangee` fige cette forme. |
| **Ce qu'aucune des deux ne couvre** | la perte **simultanée** du curseur et de l'historique : ils sont dans le même Postgres (`postgres-dagster`). Le corpus entier est alors réingéré sans avertissement (registre §4.26). D'où `--no-deps` pour toute recréation de service ([§6.3 de `livraison.md`](livraison.md#63-docker-compose-up-sans---no-deps-redémarre-les-dépendances)). |
| **Si le geste est fait deux fois** | avec la **même** étiquette, les clés sont identiques et Dagster ne crée aucun run ; le capteur le journalise avec le nombre de demandes perdues, et le curseur a avancé : le geste est à refaire avec une étiquette **neuve**. |
| **Un marqueur sans étiquette** | est refusé, le curseur laissé intact, et la raison journalisée : l'honorer rendrait la clé constante, donc le second geste muet (registre §4.32.a). |
| **Si une ingestion de cette source tourne déjà** | le marqueur n'est **ni honoré ni consommé** : le tick rend un `SkipReason` qui nomme le run en cours **et son âge**, et le tick suivant relira le marqueur. Le geste est différé, pas perdu. Cela évite que deux runs réécrivent la même partition de `Datas/.cleaned/` en même temps (registre §4.33.c). Le refus se répète tant que le run n'est pas terminé ; un run gelé le prolonge au plus jusqu'au `max_runtime_seconds` de `dagster.yaml`, soit 25 h (90 000 s), à ne pas confondre avec les 24 h d'`extraction_timeout_seconds`, plafond par document. Un fichier *modifié* pendant une réingestion produit toujours une clé neuve sur une partition en cours ; ce cas reste ouvert (registre §4.34.a). |

### Réindexation lexicale de l'agent

Ce que l'appel `POST /reindex` apporte à l'agent, et la variable qui le désigne, sont au [§1.2 de `livraison.md`](livraison.md#12-le-contrat-avec-rag-agent-chat) et au [§2.2](livraison.md#22-le-env--toutes-les-variables). `AGENT_SERVICE_URL` vaut par défaut `http://agent-api:8000` (`src/pipeline/settings.py`).

L'agent compare le nombre de chunks de sa collection à celui qu'il a indexé, mais ce contrôle **ne voit pas** une réingestion qui retire autant de chunks qu'elle en ajoute — précisément le cas d'une réingestion. L'appel fait donc partie du contrat.

**Une fois par rafale, pas une fois par document.** L'appel a son propre job, `agent_reindex_job`, et son propre capteur, `agent_reindex_sensor` (`src/pipeline/reindex_job.py`). Ce capteur n'arme le job que lorsque **plus aucun run d'ingestion n'est en cours ni en file**, et qu'au moins un a réussi depuis la dernière réindexation. Une rafale de N documents donne **une** reconstruction BM25 au lieu de N ; un corpus déposé au goutte-à-goutte donne une réindexation par rafale, ce qui est voulu : un document ingéré doit devenir cherchable.

Un échec d'appel **ne fait jamais échouer une ingestion réussie**, puisque l'appel vit dans son propre run. **Ce run-là échoue** et apparaît avec les autres échecs, et le capteur le retente au tick suivant tant qu'il le faut : il compare le repère de la dernière ingestion réussie à celui de la dernière **réindexation réussie**. Si l'agent est arrêté, des runs de réindexation échouent jusqu'à ce qu'il réponde ; c'est voulu, pour qu'une réindexation manquée reste visible.

### Contrôles

Les contrôles après ingestion (`verify_contract`, `index_report`, les huit comptes, `comparer`, le jeu de questions) et leurs résultats attendus sont au [§4 de `livraison.md`](livraison.md#4-vérifier). Avant ingestion, `verify_data` vérifie que les trois stores répondent :

```bash
docker compose run --rm --no-deps -T -e PYTHONPATH=/app -w /app \
  docling-service python -m src.verify_data
```

---

## Exploration du graphe (NebulaGraph)

Chaque document est un sommet `Document` relié à ses composants (titres, paragraphes, images, etc.) par des arêtes `PARENT_OF` ; les légendes sont reliées à leur visuel par `LINKED_TO`.

### Requêtes nGQL types (onglet Console de Nebula Studio)

**Ne pas taper `USE rag_space;` dans la console.**
Dans Nebula Studio (`http://localhost:7001`), sélectionner **d'abord** l'espace `rag_space` dans le menu déroulant en haut à droite, puis exécuter les requêtes suivantes. `filename` est le nom du fichier sans son extension.

1. **Voir un document complet et sa structure** :
   ```ngql
   MATCH p=(d:Document)-[r:PARENT_OF]->(e)
   WHERE d.Document.filename == "Hands-On_RAG_for_Production_ER_-_Ofer_Mendelevitch"
   RETURN p;
   ```

2. **Visualiser uniquement le squelette (titres et sections)** :
   ```ngql
   MATCH p=(d:Document)-[:PARENT_OF]->(s:SectionHeader)
   RETURN p;
   ```

3. **Trouver les images et leurs légendes** :
   ```ngql
   MATCH p=(c:Caption)-[:LINKED_TO]->(res)
   RETURN p;
   ```

Pour compter des sommets, utiliser `MATCH … RETURN count(n)` tag par tag, et non `SHOW STATS`, qui rend 0 sur un space peuplé ([§4.2 de `livraison.md`](livraison.md#42-les-huit-comptes-et-lempreinte-des-clés)).

### Guide de visualisation (Studio v3.8.0)

Pour un rendu lisible, configurer les couleurs par **Tag** dans l'interface :
1. Sélectionner l'espace **`rag_space`** en haut à droite.
2. Dans l'onglet **Console** ou **Visualisation** :
   - **Document** : rouge (nœud racine)
   - **SectionHeader** : bleu (structure)
   - **Paragraph** : gris (contenu)
   - **Table / Picture** : vert (ressources riches)
   - **Caption** : jaune (métadonnées liées)
3. Utiliser le **Vertex Filter** pour isoler des types précis (par exemple ne montrer que `Code` et `Formula`).

---

## Structure du projet

Fichiers versionnés (`git ls-files`, 27 septembre 2026) ; le détail de
`documentation/` et de `tests/unit/` est omis.

```text
rag-ingestion-pipeline/
├── Datas/                      # Corpus source, versionné (htms/, pdfs/) ; mds/ attendu par la source markdown
│   ├── .cleaned/               # HTML nettoyés, générés par le pipeline, non versionnés
│   └── database/               # Données des stores (volumes Docker), non versionnées
├── documentation/              # Documentation technique ; campagnes/ : comptes rendus datés
├── scripts/
│   ├── campagne/               # Instruments de mesure : jeu de questions, rappel, passerelle S3,
│   │                           #   équivalence des identifiants, émiettement
│   ├── git-hooks/pre-commit    # Contrôle d'identité d'auteur
│   ├── capturer-larbre-docling.py   # Capture des arbres de titres Docling (fixture de test)
│   ├── installer-les-garde-fous.sh  # Montage des hooks git, appelé par make install
│   └── rejouer-les-mutations.py     # Rejeu des mutations, appelé par make all
├── src/
│   ├── workspace.yaml          # Code location Dagster (charge src.pipeline.definitions)
│   ├── docling_service/        # Microservice d'extraction
│   │   ├── main.py             # Application FastAPI : /extract, /jobs/{job_id}, /health
│   │   ├── jobs.py             # File de jobs et worker unique
│   │   ├── extraction.py       # Conversion Docling (PDF paginé, HTML/MD direct)
│   │   ├── elements.py         # Taxonomie des labels, hiérarchie, positions, identité d'un document
│   │   ├── anchoring.py        # Rattachement des chunks Docling aux éléments
│   │   ├── storage.py          # Persistance d'un lot : graphe puis vecteurs
│   │   ├── nebula.py           # Écritures NebulaGraph groupées, pool partagé, schéma
│   │   ├── ngql.py             # Échappement et construction des requêtes nGQL
│   │   ├── embedding.py        # Modèle d'embedding et refus d'en charger un autre
│   │   ├── vectors.py          # Embeddings par lots et upsert ChromaDB
│   │   ├── chunking.py         # Découpage des textes longs, contextualisation
│   │   ├── markdown.py         # Normalisation du Markdown avant conversion
│   │   ├── matter.py           # Index, sommaire, pages liminaires : hors contenu
│   │   ├── hierarchy.py        # Arbre des titres : pile et profondeur
│   │   ├── ranking.py          # Rang d'un titre (parent Docling, level, police)
│   │   ├── language.py         # Détection de la langue par mots-outils
│   │   ├── settings.py         # Réglages du service
│   │   ├── images.py           # Crop PyMuPDF, export d'objets, seul site du client S3
│   │   └── requirements.txt    # Dépendances de l'image d'extraction
│   ├── pipeline/               # Orchestration Dagster
│   │   ├── sources.yaml        # Déclaration des sources (1 bloc = 1 source)
│   │   ├── sources.py          # Modèles de configuration des sources
│   │   ├── factory.py          # Génération assets/jobs/capteurs par source
│   │   ├── cleaning.py         # Nettoyage HTML universel (trafilatura/readability)
│   │   ├── media.py            # Export des images base64 des captures HTML
│   │   ├── reindex.py          # Appel POST /reindex sur l'agent
│   │   ├── reindex_job.py      # Job et capteur de réindexation
│   │   ├── schemas.py          # Contrat de données partagé avec rag-agent-chat
│   │   ├── settings.py         # Réglages du pipeline
│   │   ├── definitions.py      # Point d'entrée Dagster
│   │   └── prompts/README.md   # Dossier réservé, sans template : ce pipeline n'appelle aucun LLM
│   ├── reglages_s3.py          # Réglages du stockage d'objets (S3_*), sans défaut d'adresse
│   ├── wipe_stores.py          # Purge des trois stores et de Datas/.cleaned/
│   ├── verify_data.py          # Contrôle avant ingestion des trois stores
│   ├── verify_contract.py      # Vérification du contrat avec rag-agent-chat
│   ├── index_report.py         # Rapport sur l'index vectoriel
│   ├── init_nebula.py          # Amorçage du cluster NebulaGraph sur pile neuve
│   └── equivalence_des_identifiants.py  # Instantané et comparaison des element_id
├── tests/
│   ├── conftest.py
│   ├── unit/                   # Tests unitaires (test_*.py)
│   ├── fixtures/arbres_docling.yaml   # Arbres de titres capturés
│   └── mutations/table-des-mutations.json  # Mutations rejouées par make all
├── .env.example                # Gabarit du .env (variables : livraison.md §2.2)
├── .pre-commit-config.yaml     # Hooks git
├── docker-compose.yml          # Configuration de la pile
├── docker-compose.gpu.yml      # Surcharge qui réserve un GPU à docling-service
├── dagster.yaml                # Instance Dagster (file de runs, run monitoring)
├── Dockerfile.dagster          # Environnement Dagster
├── Dockerfile.docling          # Environnement d'extraction
├── pyproject.toml              # Dépendances hôte, groupe dev, réglages ruff/mypy/pytest
├── requirements.txt            # Dépendances de l'image Dagster
├── uv.lock                     # Versions épinglées par uv
├── Makefile                    # Porte qualité
└── README.md
```

---

## Tests et porte qualité

```bash
make install && make all
```

Dans un worktree, utiliser `uv sync` à la place de `make install` (voir plus bas).

`make install` appelle `uv sync`, qui installe les dépendances de production
**et** le groupe `dev` déclaré dans `pyproject.toml` (`pytest`, `pytest-cov`,
`ruff`, `mypy`, les stubs de typage, `pip-audit`, `pre-commit`), puis arme les
garde-fous git. `make all` — la **porte qualité** — enchaîne `lint`,
`typecheck`, `test`, `mutations` et `format-check`, chaque outil derrière
`uv run`, donc aux versions épinglées par `uv.lock`, et s'arrête à la première
étape en échec.

**Un code de retour non nul est un défaut, sans exception à connaître.** Les
comptes de la dernière exécution mesurée (tests, fichiers vus par `mypy`,
mutations, fichiers formatés) sont au
[§4.1 de `livraison.md`](livraison.md#41-la-porte-qualité).

| Cible | Ce qu'elle fait | Où elle vit |
|---|---|---|
| `make lint` | **constate** — `ruff check src/ tests/ scripts/` | première étape de `make all` |
| `make typecheck` | **constate** — `mypy src/ scripts/` | deuxième étape |
| `make test` | `pytest tests/` | troisième étape |
| `make mutations` | rejoue les mutations de `tests/mutations/table-des-mutations.json` sur une copie jetable : chacune doit faire échouer au moins un test | quatrième étape |
| `make format-check` | **constate** — `ruff format --check src/ tests/ scripts/` | dernière étape |
| `make format` | **écrit** — `ruff format src/ tests/ scripts/` | geste volontaire, dans aucune porte |
| `make test-cov` | `pytest tests/ --cov=src --cov-report=term-missing` | hors porte |
| `make audit` | `pip-audit` sur `requirements.txt` et `src/docling_service/requirements.txt` | hors porte |

La porte ne réécrit pas le dépôt qu'elle contrôle : `make all` constate le
formatage, il ne l'applique pas. `lint` et `format-check` couvrent `tests/` et
`scripts/`, comme le hook `ruff`, qui voit tout ce qui est indexé : sans cela,
`make all` pourrait rendre 0 sur un arbre dont le hook refuse le commit.
`typecheck` n'inclut pas `tests/` : c'est `pyproject.toml` qui les exclut de
`mypy` (`exclude = ["tests/"]`), par choix déclaré.

`pyproject.toml` porte déjà `strict = true` pour `mypy`, avec une exception
motivée, `disallow_untyped_decorators = false`, pour les décorateurs Dagster et
FastAPI. Lancer `mypy --strict` à la main annule cette exception et produit des
erreurs qui n'en sont pas ; la porte est `make all`.

`pyproject.toml` porte aussi `addopts = "-q --tb=short"` pour `pytest` : ne pas
ajouter un second `-q`, qui supprime la ligne `N passed` quand tout passe
(commentaire de la cible `test` du `Makefile`).

Pour lire les premières étapes seules :

```bash
make lint typecheck test
```

### Les garde-fous du dépôt — une seule installation

```bash
make install
```

Ce geste, et lui seul, arme les hooks déclarés dans `.pre-commit-config.yaml`
**et** le contrôle d'identité d'auteur. Un garde-fou déclaré mais non installé
est pire qu'absent : il donne l'illusion d'être protégé (registre §5.5).

`make install` fait `uv sync`, puis `sh scripts/installer-les-garde-fous.sh`.
Ce script monte les deux couches **dans l'ordre**, sur les deux types de hook
`pre-commit` et `pre-merge-commit`, ne passe **jamais** `-f`, et **vérifie son
propre résultat** : il sort en erreur si le montage n'est pas celui qu'il
annonce.

**`uv` est requis.** Le script appelle `uv run pre-commit` (sauf si la variable
`PRE_COMMIT` désigne un autre exécutable). Sans `uv` au `PATH`, il sort en
`rc=1` après avoir posé les deux copies du contrôle d'identité, sans aucun hook
du framework ni `.legacy`, et le dit sur sa sortie d'erreur (mesuré le
31 août 2026).

**Le lancer depuis le clone principal, pas depuis un worktree.**
`pre-commit install` écrit dans le hook généré une ligne
`INSTALL_PYTHON=<interpréteur de l'arbre d'où il est lancé>`, et les hooks vivent
dans le répertoire commun du clone (`git rev-parse --git-common-dir`), partagé
par tous ses arbres de travail. Si cet arbre disparaît (un `git worktree remove`
après fusion, par exemple) et qu'aucun `pre-commit` n'est au `PATH`, **tout
commit du dépôt et de tous ses arbres de travail** est refusé, avec le seul
message « `` `pre-commit` not found. `` », qui ne nomme pas la cause. Le refus
est sans danger pour l'historique. **Pour en sortir :** relancer `make install`
depuis le clone principal.

| Hook | Ce qu'il fait | Écrit ? |
|---|---|---|
| `identite-auteur` | refuse un commit dont l'adresse d'auteur **ou** de committer n'est pas dans la liste blanche — tous les chemins qui créent un commit ne sont pas couverts, voir plus bas | non |
| `trailing-whitespace`, `end-of-file-fixer` | hygiène de fin de ligne et de fin de fichier | oui, sur les fichiers **indexés** |
| `check-yaml` | YAML valide | non |
| `check-added-large-files` | refuse un fichier **nouvellement ajouté** de plus de 500 ko (`--maxkb=500`). Ne voit **pas** un fichier déjà suivi et modifié, quelle que soit sa taille | non |
| `ruff` | `--fix` sur les violations de lint | oui, sur les fichiers **indexés** |
| `ruff-format` | `--check` — **constate**, ne reformate pas | non |
| `detect-secrets` | refuse un secret dans un fichier **indexé** | non |

Les hooks qui écrivent ne touchent que ce qui est **déjà indexé**, refusent le
commit, et **nomment chaque fichier corrigé**, sans montrer le diff (sortie :
`- files were modified by this hook` puis `Fixing <fichier>`). Le diff
s'obtient avec `--show-diff-on-failure`, un drapeau de la ligne de commande que
le hook généré ne porte pas et qu'aucune clé de `.pre-commit-config.yaml` ne
peut activer :

```bash
git diff                                   # ce que le hook vient d'écrire
uv run pre-commit run --show-diff-on-failure --all-files
```

Relire, puis réindexer.

#### Le contrôle d'identité est installé deux fois

Il est déclaré à deux endroits, et ce n'est pas une redondance :

- comme hook `repo: local` dans `.pre-commit-config.yaml` — donc dans l'**arbre
  de travail** ;
- comme `pre-commit.legacy` et `pre-merge-commit.legacy` dans le répertoire des
  hooks, les copies que `pre-commit install` déplace et continue d'exécuter —
  donc **hors** de l'arbre de travail.

Les deux pointent le même script versionné, `scripts/git-hooks/pre-commit` : la
liste blanche d'adresses (`ADRESSES_AUTORISEES`) n'a qu'**un site versionné**.

**Une fois armée, elle en a deux.** La copie `.legacy` est **figée à
l'installation** ; le hook `repo: local` relit le script versionné à chaque
commit. Mesuré le 31 août 2026, après une édition **commitée** de
`ADRESSES_AUTORISEES` :

| Édition | Effet au commit suivant |
|---|---|
| **ajouter** une adresse | **sans effet** — la couche `repo: local` l'accepte, puis `pre-commit.legacy` refuse (`rc=1`, HEAD inchangé) en affichant l'**ancienne** liste |
| **retirer** une adresse | **appliqué** — la couche `repo: local` refuse (`rc=1`, HEAD inchangé) |

Le refus l'emporte dans les deux sens : de la friction, jamais une exposition.
**Après toute édition de `ADRESSES_AUTORISEES`, relancer `make install`**, qui
réécrit la copie. Une adresse fraîchement ajoutée qui n'apparaît pas dans la
liste affichée par le refus est ce cas-là.

**Seule la seconde couche est inconditionnelle.** Le hook généré par le
framework ouvre sa configuration en chemin **relatif** : un arbre de travail
dont `.pre-commit-config.yaml` ne déclare pas le contrôle est désarmé, sans
avertissement. C'est le cas de tout `git checkout` d'un commit ancien, de tout
`git bisect`, de tout HEAD détaché sur une révision antérieure au contrôle.
C'est pourquoi `scripts/installer-les-garde-fous.sh` copie le script **avant**
d'appeler `pre-commit install`, et pourquoi **`-f` ne doit jamais être passé** :
`-f` supprime la copie `.legacy`, et `pre-commit install` le suggère lui-même
dans sa sortie.

`tests/unit/test_installation_des_garde_fous.py` vérifie cette propriété : il
monte un dépôt jetable dont la configuration ne porte **pas** le contrôle, y
exécute le script livré, et constate que le refus tient.

#### Ce que le contrôle d'identité couvre, et ce qu'il ne couvre pas

`git commit` n'est pas le seul chemin qui crée un commit, et git ne déclenche
pas les mêmes hooks sur tous. Mesuré le 31 août 2026, en journalisant chaque
hook de `.git/hooks` :

| Geste | Couvert | Par quoi |
|---|---|---|
| `git commit` | **oui** | `pre-commit` |
| `git commit --amend` | **oui** | `pre-commit` |
| `git merge --no-ff` | **oui** | `pre-merge-commit` |
| `git revert` | **non** | git n'y déclenche ni `pre-commit` ni `commit-msg` |
| `git cherry-pick` | **non** | idem |
| `git rebase` | **non** | aucun hook de la famille ; le rebase réécrit le committer |
| `git commit --no-verify` | **non** | par construction. À ne jamais utiliser |

**`git revert` et `git cherry-pick` restent ouverts.** Le seul point d'accroche
que git y déclenche est `prepare-commit-msg`, et un contrôle posé là laisserait
passer le défaut : lors d'un `cherry-pick`, `git var GIT_AUTHOR_IDENT` y rend
l'identité **locale**, pas celle du commit produit. La fermeture correcte est
un hook `pre-push` ; elle est inscrite au registre.

#### Ce que `detect-secrets` protège, et ce qu'il ne protège pas

`.env` porte les identifiants du stockage d'objets, du graphe et de PostgreSQL
(variables : [§2.2 de `livraison.md`](livraison.md#22-le-env--toutes-les-variables)).
Mais **un hook `pre-commit` ne voit que les fichiers indexés, et `.env` est dans
`.gitignore`** : il n'est jamais indexé, donc jamais scanné. Le gain est
ailleurs : empêcher qu'un secret parte un jour dans un fichier **versionné**.
`docker-compose.yml` passe par des variables d'environnement.

Il n'y a **pas de baseline** (`.secrets.baseline` a été supprimée, registre
§5.5). Un faux positif se déclare **au site**, avec sa justification, par un
commentaire `# pragma: allowlist secret` placé **sur la ligne qui porte la
valeur** — pas sur la ligne qui ouvre le dictionnaire ou l'appel : posé une
ligne trop haut, il ne filtre rien et le commit est refusé sans que le message
dise pourquoi.

Les lignes qui portent le pragma (à distinguer de celles qui le citent en prose)
se comptent ainsi :

```bash
git ls-files -z -- '*.py' '*.yaml' | xargs -0 grep -nE '#[[:space:]]*pragma: allowlist secret$'
```

La commande porte `'*.py' '*.yaml'` et non `--include='*.py'` : bornée au
Python, elle ne verrait pas les porteuses des fichiers YAML. Mesuré le
27 septembre 2026, elle rend **16** lignes, toutes des faux positifs :

| Nature | Exemples |
|---|---|
| un **nom** d'en-tête HTTP | `src/pipeline/reindex.py` (`API_KEY_HEADER`) |
| le mot de passe **public** du graphd de développement, celui de `docker-compose.yml` | `src/docling_service/settings.py` (`nebula_password`) |
| des identifiants d'essai posés dans les tests | `tests/conftest.py`, `tests/unit/test_settings.py`, `test_reindex.py`, `test_nebula.py`, `test_init_nebula.py`, `test_verify_data.py` |
| des empreintes SHA-256, lues comme des « Hex High Entropy String » | `tests/fixtures/arbres_docling.yaml`, `src/equivalence_des_identifiants.py`, `documentation/campagnes/2026-09-02-jeu-de-questions.yaml` |

Ce compte n'est pas à recopier : la commande fait foi.

Pour scanner tout le dépôt hors corpus :

```bash
git ls-files -z -- ':!Datas/' | xargs -0 uv run --with detect-secrets==1.5.0 detect-secrets-hook
```

**La commande ne doit rien afficher** : c'est son verdict. Le `:!Datas/` est
nécessaire : `detect-secrets` est appelé **directement**, donc
l'`exclude: '^Datas/'` de `.pre-commit-config.yaml`, que seul le framework
applique, ne le filtre pas, et le scan bute sur des faux positifs du corpus.

Deux réserves avant de lire son code de retour :

- **le code de retour est celui de `xargs`, pas celui de `detect-secrets`** :
  `xargs` traduit un échec du programme appelé en **123**, jamais en 1. Tester
  `rc ≠ 0`, pas `rc = 1`, et sans tube supplémentaire (un `| tail` rendrait le
  code de `tail`) ;
- ce `:!Datas/` et l'`exclude: '^Datas/'` de `.pre-commit-config.yaml` disent
  la même chose à deux endroits : si l'un change, l'autre doit suivre. Le second
  est vérifié par `tests/unit/test_hooks_contre_le_corpus.py` ; le premier ne
  l'est pas, et c'est inscrit au registre.

Pour lire un fichier tel qu'il est dans une autre révision, utiliser
`git show <rev>:<fichier>`, jamais `git checkout <branche> -- .` dans un arbre
qui porte des commits : cela réécrit l'arbre sans avertissement.

#### Le corpus est hors de portée des hooks

`Datas/htms/` et `Datas/pdfs/` sont **versionnés**. Ce sont des données
d'entrée, pas du code, et `.pre-commit-config.yaml` les soustrait à **tous** les
hooks par un `exclude: '^Datas/'` au niveau racine.

Sans cette exclusion, mesuré sur une fusion d'essai, avec le corpus de
25 fichiers d'alors :

| Hook | Effet sur le corpus |
|---|---|
| `detect-secrets` | **refusait** le commit — deux `Hex High Entropy String`, faux positifs. Un `# pragma` est impossible ici : le **contenu** entre dans le calcul de `element_id` (contrat, exigences 2 et 3) |
| `trailing-whitespace`, `end-of-file-fixer` | **écrivaient** — 24 fichiers sur 25, 240 lignes. Au commit, `git add` puis recommit faisait entrer le fichier **altéré**, sans erreur |
| `check-added-large-files` | **refusait** tout fichier **nouveau** de plus de 500 ko : le corpus ne pouvait plus grandir |

La deuxième ligne est la plus grave. Le corpus est une donnée de mesure : deux
postes dont les fichiers diffèrent d'un caractère produisent des `element_id`
différents, donc des campagnes impossibles à comparer, **sans qu'aucune erreur
ne le signale**.

**Pour étendre le corpus :**

```bash
git add "Datas/htms/<ouvrage>/<chapitre>.html" && git commit
```

Rien de particulier : aucun `--no-verify`, aucun seuil à relever, aucune
exception à ajouter. Deux règles seulement :

- **ne jamais renommer un fichier du corpus**, même pour « ranger » :
  `source_path` entre dans `element_id`. Les noms doivent être identiques au
  caractère près d'un poste à l'autre ;
- au-delà de **50 Mo par fichier**, GitHub avertit ; au-delà de **100 Mo**, il
  refuse. Mesuré le 27 septembre 2026
  (`git ls-files -z -- Datas | xargs -0 stat -c '%s %n'`) : **63** fichiers
  versionnés sous `Datas/` (60 HTML, 2 PDF, 1 archive `.zip`), 166 186 111 o au
  total ; le plus gros est l'archive, **20 678 625 o**
  (`Datas/htms/The Statistics and Calculus with Python Workshop/The-Statistics-and-Calculus-with-Python-Workshop-master.zip`),
  que le motif `htms/**/*.html` n'ingère pas ; le plus gros HTML pèse
  **7 778 415 o** (`Datas/htms/Practical MLOps/5. AutoML and KaizenML.html`).
  La marge sous l'avertissement de GitHub est d'environ **2,4×**.

**Ce que l'exclusion coûte** : un secret réel déposé sous `Datas/` ne serait pas
vu par `detect-secrets`. C'est accepté : le corpus est une capture de
documentation publique, et l'alternative consisterait à altérer les données de
mesure. La borne est étroite : ce chemin-là, et lui seul.

### Ce que les tests couvrent

La logique sensible du service d'extraction vit dans des modules sans dépendance
lourde : elle est testée sans Docling, torch ni NebulaGraph. Couverture relevée
par `make test-cov` (valeurs non remesurées au 25 septembre 2026) :

| Module | Rôle | Couverture |
|---|---|---|
| `ngql.py` | Échappement et construction des requêtes du graphe | 100 % |
| `chunking.py` | Ce que le modèle d'embedding reçoit, la forme de l'id de chunk, le filtre du bruit | 100 % |
| `elements.py` | Hiérarchie, positions, identifiants | 100 % |
| `markdown.py` | Normalisation avant conversion | 100 % |
| `matter.py` | Repérage des parties hors contenu (index, sommaire) | 100 % |
| `hierarchy.py` | Assemblage de l'arbre des titres | 100 % |
| `ranking.py` | Rang d'un titre selon la source | 100 % |
| `language.py` | Détection de la langue d'un document | 100 % |
| `jobs.py` | File de jobs et worker | 99 % |
| `cleaning.py` | Nettoyage HTML universel | 94 % |

`vectors.py` et `main.py` sont des adaptateurs, vers ChromaDB et vers FastAPI :
ils ne sont pas couverts en unitaire et se valident par une ingestion réelle.
Chacun a tout de même sa propriété décisive sous test : `vectors.py` le contrôle
du modèle d'embedding et la page de fin des chunks (`tests/unit/test_vectors.py`),
`main.py` le refus de démarrer hors contrat (`tests/unit/test_main.py`).

Trois modules étaient inimportables côté hôte, donc intestables ; ils sont
atteints ainsi :

| Module | L'obstacle | La solution | Le test |
|---|---|---|---|
| `nebula.py` | `import nebula3` au niveau du module | l'import est **différé** dans la fonction qui en a besoin | `test_nebula.py` — l'identité du document, `source_path` et jamais `filename` |
| `extraction.py` | `import docling` au niveau du module | l'import est **différé** | `test_extraction.py` — l'oubli avant réécriture, le retrait d'un document partiel, la chaîne d'images, le compteur de pages perdues |
| `main.py` | `fastapi` absent de l'environnement du dépôt | aucune modification du module | `test_main.py` — un faux paquet `fastapi` placé en tête de `PYTHONPATH`, dans un sous-processus |

`main.py` **reste inimportable côté hôte**, et c'est le seul module de `src/`
dans ce cas (`EXCEPTIONS_CONNUES`, `tests/unit/test_importabilite_cote_hote.py`) :
il **est** l'application FastAPI, et c'est le test qui le charge derrière un faux
paquet. Ce test importe tous les modules de `src/` dans un sous-processus et
échoue dès qu'un module inimportable n'est pas déclaré comme tel (registre §3.4,
§4.4, §4.5, §4.19, §4.28.d).

---

## Licences & composants

Dépendances directes déclarées dans `pyproject.toml`, `requirements.txt` et
`src/docling_service/requirements.txt`, et images de `docker-compose.yml`.

| Composant | Rôle | Licence |
|---|---|---|
| Dagster (`dagster`, `dagster-webserver`, `dagster-postgres`, `dagster-docker`) | Orchestration du pipeline | Apache-2.0 |
| Docling (`docling`, `docling-core`) | Extraction de documents | MIT |
| PyMuPDF (`pymupdf`) | Lecture des PDF, découpe des images | **AGPL-3.0** (ou licence commerciale Artifex) |
| sentence-transformers, transformers | Modèle d'embedding | Apache-2.0 |
| PyTorch | Calcul du modèle | BSD-3-Clause |
| `paraphrase-multilingual-MiniLM-L12-v2` | Modèle d'embedding | Apache-2.0 |
| FastAPI / uvicorn / python-multipart | Service d'extraction | MIT / BSD-3-Clause / Apache-2.0 |
| pydantic / pydantic-settings | Modèles et réglages | MIT |
| BeautifulSoup4 / lxml | Parsing HTML | MIT / BSD-3-Clause |
| trafilatura | Extraction de contenu web | Apache-2.0 |
| readability-lxml | Extraction d'article | Apache-2.0 |
| PyYAML | Lecture de `sources.yaml` | MIT |
| requests | Client HTTP | Apache-2.0 |
| antlr4-python3-runtime | Dépendance de Docling | BSD-3-Clause |
| ChromaDB (image `chromadb/chroma`, client `chromadb`) | Base vectorielle | Apache-2.0 |
| NebulaGraph (images `vesoft/nebula-*`, client `nebula3-python`) | Graphe de connaissances | Apache-2.0 |
| PostgreSQL (image `postgres`) | Métadonnées Dagster | PostgreSQL License |
| SeaweedFS (image `chrislusf/seaweedfs`) | Stockage d'objets | Apache-2.0 |
| minio (minio-py) | Bibliothèque cliente S3 | Apache-2.0 |
| **Ce projet** | Code applicatif | aucun fichier `LICENSE` versionné : licence non déclarée |

**PyMuPDF est sous AGPL-3.0.** Il est installé dans l'image `docling-service`
(`src/docling_service/requirements.txt`) et importé par
`src/docling_service/images.py` et `extraction.py`. Distribuer l'image, ou
exposer le service à des tiers, engage les obligations de l'AGPL, sauf licence
commerciale.
