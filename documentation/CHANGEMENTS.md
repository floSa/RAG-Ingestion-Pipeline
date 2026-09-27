# Ce qui a changé, et ce que ça implique

> **À lire en premier pour reprendre le projet, ou pour travailler sur
> `rag-agent-chat`.**
>
> Ce document liste les changements de fond, ce qu'ils impliquent côté agent, et
> renvoie vers la page détaillée de chacun. Le contrat vivant, champ par champ,
> est au [§4 de `llm_integration_plan.md`](llm_integration_plan.md#4-modèle-de-données-contrat-dinterface).
>
> **Pour l'état plutôt que les changements** (ce que le pipeline garantit
> aujourd'hui, ce qu'il ne garantit pas, ce qu'il reste à faire) : voir
> [`etat_des_lieux.md`](etat_des_lieux.md). Pour l'exploitation et les mesures
> en service : [`livraison.md`](livraison.md).

---

## 1. Le modèle d'embedding a changé — action requise côté agent

| | Avant | Après |
|---|---|---|
| Modèle | `all-MiniLM-L6-v2` | **`paraphrase-multilingual-MiniLM-L12-v2`** |
| Dimensions | 384 | **384, inchangé** |
| Langues | anglais | **français, anglais et une cinquantaine d'autres** |

### Pourquoi

L'ancien modèle n'était entraîné que sur de l'anglais. Sur un corpus mixte, il
classait **par langue avant de classer par sens**. Mesuré sur une question
française, face à six passages :

| Rang | Ancien modèle | Nouveau modèle |
|---|---|---|
| 1 | FR pertinent (0,453) | **EN pertinent (0,746)** |
| 2 | FR proche (0,433) | **FR pertinent (0,741)** |
| 3 | **FR hors sujet (0,397)** | FR proche (0,492) |
| 4 | **EN pertinent (0,366)** | EN proche (0,441) |
| 5 | EN proche (0,267) | FR hors sujet (0,338) |
| 6 | EN hors sujet (0,105) | EN hors sujet (0,313) |

Avec l'ancien modèle, un **hors-sujet français** passait devant la **bonne
réponse anglaise** : poser sa question en français revenait à se couper de toute
la bibliothèque anglaise. Avec le nouveau, les deux bonnes réponses arrivent en
tête à 0,005 d'écart, quelle que soit leur langue.

> Les scores sont des **similarités cosinus** : 1,0 = même sens, 0,7–0,8 = dit la
> même chose autrement, 0,4–0,5 = même domaine, 0 = aucun rapport. Ce qui compte
> est l'écart entre candidats, pas la valeur absolue.

### Ce que `rag-agent-chat` doit faire

**Obligatoire, sans quoi les réponses seront fausses sans qu'aucune erreur
n'apparaisse** (la recherche renverrait des passages au hasard) :

```bash
EMBEDDING_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
```

La dimension étant identique (384), aucun autre changement n'est nécessaire :
ni schéma, ni format de collection, ni code de recherche. Côté pipeline, le
service d'extraction refuse de démarrer sur un autre modèle
(`CONTRACT_MODEL`, `src/docling_service/embedding.py`).

> Détail et alternatives écartées : [base_vectorielle.md](base_vectorielle.md#pourquoi-un-modèle-dembedding-multilingue)

---

## 2. Le graphe a une vraie hiérarchie de titres

Avant, tout titre était rattaché au document : la chaîne s'arrêtait à
`élément → titre → document`. Un sous-titre et son chapitre étaient frères.

Désormais un titre est rattaché **au titre qui le domine** :

```
[0] A Developer's Approach to Data Cleaning
    [1] Understanding basic data cleaning
        [2] Common data issues
    [1] R and common data issues
        [2] Outliers
            [3] Step 1 – Profiling the data
```

| Mesure sur le corpus de référence *(disparu, voir la réserve)* | Avant | Après |
|---|---|---|
| Arêtes `SectionHeader → SectionHeader` | 0 | **759** |
| Chemins de longueur 3 depuis le document | 0 | **13 220** |
| Chemins de longueur 4 | 0 | 2 778 |
| Chemins de longueur 5 | 0 | 1 021 |

> **Ces chiffres portent sur le corpus de référence d'alors, qui n'existe
> plus.** Le §1 du registre le déclare mort : c'était un corpus mixte
> français/anglais de 42 documents, dont 6 notes Markdown et un PDF de
> 280 pages. Le corpus en service au 25 septembre 2026 compte **24 chapitres
> HTML de deux ouvrages plus un PDF de 71 pages** (23 documents ingérés),
> entièrement en anglais, et `Datas/mds/` n'existe pas. Aucun de ces nombres
> n'est reproductible (registre §6.10, §6.11).
>
> Ils sont **conservés plutôt que supprimés** : ils documentent la décision
> prise à l'époque, et les effacer laisserait le choix sans motif. Ils ne
> décrivent pas l'index d'aujourd'hui, dont les chiffres se lisent par
> `verify_contract` et `index_report`
> ([livraison.md §4.5](livraison.md#45-verify_contract--le-contrat-avec-lagent),
> [§4.6](livraison.md#46-index_report--lindex-vectoriel)).

> Sur le corpus en service, la question « le graphe est-il plat ? » a été
> mesurée : il ne l'est pas, 21 chapitres sur 22 s'imbriquent, et le seul plat
> l'est pour une raison qui vient de sa capture et non du code (registre §3.2).
> Le contrat côté agent annonçait `0` et `0` sur ces deux lignes : il mesurait
> un graphe produit par autre chose que ce code.

### Ce que ça change pour l'agent

- `reference_id` d'un titre ne vaut plus systématiquement `DOC` ; il désigne
  souvent un autre titre. **Une remontée récursive est utile** : elle
  reconstruit « chapitre > section > sous-section » pour contextualiser une
  citation.
- Clé `depth` sur chaque chunk : profondeur dans la hiérarchie, 0 pour un titre
  de tête. Elle n'a pas de plafond (registre §4.24) et atteignait 5 sur l'index
  mesuré le 2 septembre 2026. La règle et les deux échelles qui s'y croisent
  sont décrites dans `ChunkMetadata.depth` (`src/pipeline/schemas.py`).
- Rien ne casse si l'agent l'ignore : `reference_id` reste un identifiant
  d'élément valide.

> Règle, signaux par format et garde-fous :
> [extraction_donnees.md](extraction_donnees.md#4-hiérarchie-et-positions)

---

## 3. Le découpage est confié à Docling

Le découpage maison coupait à la longueur en caractères. C'est désormais
`HybridChunker`, le découpeur de Docling, qui s'en charge : il respecte la
structure du document et reçoit **le tokenizer du modèle d'embedding lui-même**.

| Mesure, sur le chapitre 1 de *Practical MLOps* | Découpage maison | `HybridChunker` |
|---|---|---|
| Chunks | 146 | **100** |
| Tokens, médiane | 67 | **91** |
| Caractères, médiane | 269 | **353** |

À contenu égal, quarante-six chunks de moins, chacun portant davantage de contexte.

> ***Practical MLOps* n'était pas dans le corpus ingéré au 25 septembre 2026**,
> dont les deux ouvrages sont *MLOps with Databricks* et *Practical MLflow for
> Generative AI on Databricks*. Il fait partie du lot versionné le
> 26 septembre 2026, pas encore ingéré. La comparaison n'est pas rejouable pour
> autant : le **découpage maison a été retiré du dépôt** (registre §5.1), ce qui
> rend la colonne de gauche définitivement non reproductible (registre §6.10).
> Elle documente la décision de confier le découpage à Docling.

**Rien ne change pour l'agent.** Les identifiants restent ceux du contrat :
chaque chunk est rattaché à l'élément d'où part sa lecture, et un élément
réparti sur plusieurs chunks leur donne les suffixes `#0`, `#1` que le contrat
prévoit déjà.

> [extraction_donnees.md](extraction_donnees.md#ce-qui-part-dans-lindex-vectoriel)

---

## 4. Nouvelles métadonnées de chunk

Trois clés se sont ajoutées à `ChunkMetadata`
([`src/pipeline/schemas.py`](../src/pipeline/schemas.py), qui reste le contrat de
référence) :

| Clé | Contenu | Usage côté agent |
|---|---|---|
| `language` | `en`, `fr`… vide si indéterminée | filtrer ou annoncer la langue des sources |
| `depth` | profondeur dans la hiérarchie des titres | reconstruire le fil des titres parents |
| `collection` | l'ouvrage dont vient le chapitre | citer le livre, pas seulement le fichier |

Toutes ont une valeur par défaut : un agent qui les ignore fonctionne comme avant.

> [base_vectorielle.md](base_vectorielle.md#structure-et-définition-des-données)

---

## 5. Médias : `media_url` et `object_key` remplacent `minio_url` — action requise côté agent

Depuis le 25 septembre 2026, le stockage objet est SeaweedFS (MinIO a été
retiré le même jour), et le contrat ne nomme plus aucun logiciel :

| Avant | Après |
|---|---|
| propriété du graphe et métadonnée de chunk `minio_url` | **`media_url`** (adresse interne et authentifiée), plus **`object_key`** (clé nue de l'objet) |
| variables nommées d'après un produit, adresse par défaut dans le code | `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` ; **aucune** adresse par défaut |
| un jeu d'identifiants partagé | deux jeux : `SEAWEEDFS_RW_*` pour le pipeline, `SEAWEEDFS_RO_*` (lecture et listage) pour l'agent |

**Ce que `rag-agent-chat` doit faire** : lire `media_url` (ou mieux
`object_key`, qui survit à un changement d'hôte), et se connecter avec le jeu en
lecture seule. `minio_url` n'existe plus dans aucun store : Nebula n'autorise pas
une colonne supprimée à revenir sous le même nom, et elle a disparu avec le
`DROP SPACE` de la purge.

> Détail et ordre de déploiement : [livraison.md §8.1](livraison.md#81-le-renommage-du-contrat--fait) ;
> droits des deux jeux : [SECURITY.md](SECURITY.md#stockage-objet--deux-jeux-didentifiants).

---

## 6. Ce qui n'est plus ingéré

| Écarté | Pourquoi |
|---|---|
| Index, sommaire, couverture, page de copyright | aucune phrase à indexer, mais tout le vocabulaire de l'ouvrage : ils ressortaient sur presque toutes les questions |
| Doublons exacts | un même fichier déposé sous deux noms n'est ingéré qu'une fois (empreinte SHA-256, `content_hash`) |

Les PDF sans couche texte ne sont plus refusés : ils passent à l'OCR.

**Préface, glossaire et annexes sont conservés**, volontairement : c'est de la
prose, et un glossaire répond bien aux questions de définition.

> [extraction_donnees.md](extraction_donnees.md#pages-écartées-dun-pdf)

---

## 7. Où trouver quoi

| Question | Document |
|---|---|
| Contrat de données avec l'agent | [llm_integration_plan.md §4](llm_integration_plan.md#4-modèle-de-données-contrat-dinterface) |
| Lancer, ingérer, purger, vérifier, revenir en arrière | [livraison.md](livraison.md) |
| Métadonnées de chunk, modèle d'embedding | [base_vectorielle.md](base_vectorielle.md) |
| Hiérarchie, découpage, nettoyage HTML | [extraction_donnees.md](extraction_donnees.md) |
| Modèle de graphe et requêtes nGQL | [graphe_connaissances.md](graphe_connaissances.md) |
| Temps d'ingestion, cadencement | [orchestration.md](orchestration.md) |
| Secrets et identifiants | [SECURITY.md](SECURITY.md) |
| Vue d'ensemble, démarrage | [README.md](../README.md) |

---

## 8. Après un changement de règle d'extraction

Les identifiants dérivent du texte extrait : toute évolution de la chaîne
d'extraction impose de reconstruire les vecteurs et le graphe. La procédure est
dans `livraison.md`, dans cet ordre :

1. **si une variable du `.env` a changé**, recréer le conteneur, car
   `docker compose restart` ne relit pas le `.env` : `docker compose up -d
   --force-recreate --no-deps docling-service`, puis contrôle par `printenv`
   ([§6.4](livraison.md#64-restart-ne-relit-pas-le-env),
   [§6.3](livraison.md#63-docker-compose-up-sans---no-deps-redémarre-les-dépendances)) ;
2. **purger** par `docker compose run --rm --no-deps … python -m src.wipe_stores`,
   **puis redémarrer `docling-service`** pour rejouer `init_schema()`
   ([§3.3](livraison.md#33-la-purge-et-le-redémarrage-qui-la-suit)) ;
3. **réingérer** en posant le marqueur `reingerer:<étiquette>` sur le curseur
   de chaque capteur de fichiers, avec une étiquette neuve
   ([§3.2](livraison.md#32-réingérer--le-marqueur-sur-le-curseur)) ;
4. **contrôler** par `verify_contract` et `index_report`
   ([§4](livraison.md#4-vérifier)).

Le modèle d'embedding, lui, ne se change pas par le seul `.env` : le service
refuse de démarrer sur un autre modèle que `CONTRACT_MODEL`
(`src/docling_service/embedding.py`), et une collection déjà tracée à un modèle
refuse les vecteurs d'un autre (`vectors._inscrire_le_modele`). En changer est
un changement de contrat, à mener des deux côtés.
