# Registre des axes d'amélioration

> **Archive datée, non réécrite.** Registre du chantier, tenu jusqu'au 25 septembre 2026. L'état en service est décrit par [`livraison.md`](livraison.md).
>
> **MinIO est retiré depuis le 25 septembre 2026 ; les mentions qui suivent sont
> historiques.** Le stockage d'objets est SeaweedFS, le dépôt ne nomme plus aucun
> serveur — seule `S3_ENDPOINT` le désigne — et le contrat publie `media_url` et
> `object_key`. Ce fichier n'est **pas** réécrit : ce sont des mesures datées, et
> les réécrire les falsifierait. L'état courant est à
> [`etat_des_lieux.md`](etat_des_lieux.md), la procédure de retrait à
> [`campagnes/2026-09-25-retrait-du-stockage-precedent.md`](campagnes/2026-09-25-retrait-du-stockage-precedent.md).

Ce fichier est la mémoire du chantier d'audit et de refonte du pipeline
d'ingestion. **Chaque ligne y est vérifiable dans le code** : un constat sans
preuve `fichier:ligne` n'a pas sa place ici, et un constat corrigé se déplace
en section « Traité » avec le commit qui l'a fermé — il ne s'efface pas.

Trois étiquettes accompagnent tout chiffre : `mesuré` (relevé par une commande
dont la sortie a été lue), `calculé` (dérivé de valeurs mesurées) ou `supposé`
(hypothèse à vérifier). Une valeur reprise d'ailleurs sans remesure porte sa
réserve **une fois**, à son site canonique ; les autres mentions y renvoient.

---

## 0. Le contrat avec `rag-agent-chat`

Ces sept points ne sont pas des demandes ponctuelles. Ce sont les conditions
sans lesquelles `rag-agent-chat` ne peut pas reprendre son propre chantier. Ils
survivent aux conversations qui travaillent ici. La source est
[`documentation/pour_le_pipeline_ingestion.md`](https://github.com/floSa/rag-agent-chat)
côté agent ; ce qui suit est autosuffisant.

### Les cinq exigences dures

1. **Le modèle d'embedding est `paraphrase-multilingual-MiniLM-L12-v2`
   (384 dimensions), identique des deux côtés.** Un désaccord est la panne la
   plus coûteuse du système et elle est parfaitement silencieuse : les **deux**
   modèles candidats rendent 384 dimensions, donc ChromaDB accepte sans
   broncher, aucune sonde ne voit rien, et la recherche rend des passages
   plausibles et faux. C'est déjà arrivé : un `.env` de juin portait
   `all-MiniLM-L6-v2`, un modèle anglais, face à un agent multilingue.
   Vérifier la dimension ne protège de rien — c'est le **nom** qui discrimine.

2. **`element_id` est déterministe, dérivé du contenu, 10 caractères
   hexadécimaux** (`^[a-f0-9]{10}$`). Le jeu de questions de l'agent désigne
   des `element_id` : un identifiant qui change rend toute la mesure historique
   incomparable. Le `source_path` entre dans le calcul, donc **tout renommage
   de fichier après ingestion tue le jeu de questions.**

3. **`source_path` est l'identité d'un document, jamais `filename` seul.** Le
   corpus actuel le prouve : `Index.html` et `Preface.html` existent dans les
   deux ouvrages.

4. **La propriété `sequence` de l'arête `PARENT_OF` porte l'ordre, et doit être
   monotone.** L'agent s'en sert pour la fenêtre d'éléments et pour le
   « avant / après » entre sections voisines. Absente ou non monotone, elle
   casse la reconstruction sans erreur visible.

5. **`POST /reindex` sur l'agent, en fin de pipeline.** L'agent tient un index
   BM25 en mémoire ; sans cet appel, un document ingéré après son démarrage est
   invisible en recherche lexicale. Son filet interne compare
   `collection.count()` au nombre de chunks indexés : il est donc aveugle à une
   réingestion qui retire autant de chunks qu'elle en ajoute — exactement notre
   cas.

### Ce que le graphe déclare de la hiérarchie — la partie qui est à nous

**Le mandat du lot 3 demandait « écris au contrat ce que l'agent doit lire », et
le §0 canonique n'en disait rien.** Le lot l'avait écrit dans `schemas.py`, au
§4.24 et dans `llm_integration_plan.md` ; il argumentait que la moitié « côté
agent » vit dans l'autre dépôt, et c'est défendable. Mais **le contrat canonique
est ici**, et la moitié qui décrit ce que CE pipeline écrit est à nous. La voici.

**Le signal exact est la chaîne `PARENT_OF`**, et elle est saine : 0 sommet à deux
parents, acyclique, une racine `Document` par document, tout `SectionHeader`
atteignable (`mesuré`).

**Chaque sommet d'élément porte `depth`** — les 11 tags d'élément, pas seulement
`SectionHeader`. C'est le nombre d'arêtes `PARENT_OF` qui séparent l'élément de
la racine de son document, **sans plafond** : il vaut 0 sur une racine et atteint
5 sur ce corpus. Il donne la longueur de la chaîne sans avoir à la parcourir.

**`depth` MÉLANGE DEUX ÉCHELLES, et la valeur seule ne dit pas laquelle on lit.**
C'est `label` qui le dit :

| l'élément | ce que `depth` compte |
|---|---|
| un **titre** (`label = section_header`, `title`, `heading`) | les titres au-dessus de lui |
| **tout autre** élément | celui de son titre, **plus 1** |

Un paragraphe sous un titre de premier niveau vaut donc **1**, comme un
sous-titre. Retirer le plafond ne fusionne pas les deux échelles : il rend
seulement `depth` exact dans chacune.

**Et `depth` n'est lisible que dans le GRAPHE.** Aucun `section_header` n'est
jamais un chunk (`mesuré` : `section_header` = 0 dans les labels ChromaDB) : la
métadonnée `depth` de ChromaDB existe, mais elle ne décrit **jamais** un titre.
Un agent qui voudrait le niveau d'un titre doit lire le sommet du graphe, ou
remonter la chaîne.

**`NULL` n'est pas `0`.** Le schéma Nebula migre en place, les **données** non :
un `ALTER TAG … ADD (depth int)` laisse à `NULL` tous les sommets déjà écrits, et
seule une réécriture du document les renseigne. Un `depth` absent signifie
« profondeur inconnue », jamais « racine ». `verify_contract` le compte.

**Ce qui reste à écrire côté agent**, et que ce dépôt ne peut pas faire : les
trois réserves de lecture de `sequence` (§6.16). C'est la moitié pour laquelle
§6.16 reste ouvert.

### Les deux contraintes d'ordre

6. **L'ablation du graphe ne se mesure pas avant que la profondeur RÉELLE du
   graphe ait été constatée**, pas seulement le code relu. Le code hiérarchique
   existe (`hierarchy.py`, `ranking.py`) mais n'a jamais tourné sur un corpus.
   Un graphe plat ne restitue qu'un seul titre, jamais
   `Chapitre 3 > 3.2 > 3.2.1` : mesurer l'ablation dessus répondrait à une
   autre question, et la campagne — une demi-heure — serait à rejouer.

7. **Une hiérarchie réelle coûte de la fenêtre de contexte** : le cadrage d'une
   source vaut 34 caractères sans fil d'Ariane, 134 à deux niveaux, 275 à cinq
   (`mesuré` côté agent). C'est prévu là-bas ; la première campagne le verra.

---

## 1. La conception du jeu d'évaluation

Décision de conception, pas consigne de circonstance. L'ancien jeu de 138
questions est mort avec l'ancien corpus, et il ne doit pas être reconstruit
comme avant.

**Pourquoi l'ancien générateur fabriquait des questions faciles.** La stratégie
d'évaluation côté agent liste cinq garde-fous, dont « la preuve doit être
RECOPIÉE du passage » et « la question doit PARTAGER DU VOCABULAIRE DISTINCTIF
avec lui ». Le second garantit un recouvrement lexical entre question et
passage : l'embedding n'a plus aucun travail à faire.

**La conséquence est grave.** Si chaque question se répond avec **un seul**
passage, la reconstruction par le graphe — ±6 éléments, ±3 sections voisines —
ne peut que coûter du contexte, jamais en apporter. L'ablation conclurait « le
graphe ne sert à rien », et cette conclusion serait un artefact de la
population de questions. On aurait tranché le pari central du projet sur un
test incapable de le voir.

**La méthode retenue.** Un modèle capable lit des chapitres **entiers** et écrit
des questions dures, en notant quels passages contiennent la réponse — sans
quoi le rappel n'est plus calculable, et c'est la seule contrainte qu'on ne
peut pas lâcher.

**L'échantillonnage.** Les questions sont tirées de 2 chapitres par ouvrage plus
une section d'environ 5 pages du PDF. Mais **on ingère tout**, et elles sont
cherchées contre le corpus entier : grosse meule de foin, échantillon
d'aiguilles. L'erreur inverse — échantillonner l'ingestion — rend le rappel
trivial et la mesure creuse.

**Le volume : 30 questions au premier tour**, concentrées et non étalées sur six
strates (à 4 par strate, aucune ne dit rien) :

| Strate                                        | Nombre | Ce qu'elle sert à voir      |
|-----------------------------------------------|--------|-----------------------------|
| multi-passages, 2 ou 3 sections différentes    | 12     | rend l'ablation lisible     |
| simple, un passage                             | 8      | plancher de contrôle        |
| sans réponse                                   | 4      | teste l'abstention          |
| de suivi, avec `chat_history`                  | 4      | il n'y en avait **aucune**  |
| reformulée, vocabulaire différent du texte     | 2      | échantillon                 |

Les questions pièges sont **reportées au second tour** : c'est la strate où un
modèle écrit le plus facilement un faux piège, et elle demande une relecture
humaine.

**Ce que 30 questions peuvent et ne peuvent pas.** Elles suffisent à prouver que
la chaîne fonctionne de bout en bout et à voir un défaut grossier. Elles ne
suffisent pas à arbitrer un réglage : un écart de 2 points sur 25 questions est
du bruit, et le test de signe de l'agent le dira lui-même. **Première mesure =
contrôle de bon fonctionnement, pas décision d'architecture.**

**L'ordre est forcé.** Les `element_id` sont créés **par** l'ingestion, donc les
questions viennent **après** : ingérer tout → lire les chapitres échantillonnés
dans le store → écrire les 30 questions avec les vrais identifiants. Un
chapitre fait environ 60 000 caractères, soit ~15 000 tokens (`calculé`) : lire
4 chapitres est praticable. Les deux ouvrages font 764 000 et 554 000
caractères de texte réel, hors images inline (`mesuré`, source : relevé
préalable au chantier).

**Conséquence à consigner.** L'ancien corpus était mixte français/anglais, et 58
questions sur 138 portaient sur des documents français. Le nouveau est
**entièrement anglais**. La mesure translinguistique est donc coupée en deux :
« question française → document anglais » reste possible, « question anglaise →
document français » disparaît. Le réglage `TRANSLATION_WEIGHT=1.0` de l'agent
ne sera plus vérifiable que dans un sens.

---

## 2. État mesuré du dépôt — 28 puis 29 août 2026

Toutes les valeurs de cette section sont `mesuré`, dans ce dépôt, à la date
qui les accompagne.

| Objet | Tests | `ruff check src/` | `mypy src/` |
|---|---|---|---|
| `main` (77d4f5b) | **395** verts | propre | propre |
| `claude/rag-ingestion-pipeline-restore-5e9fa1` (832c566) | **477** verts | propre | **2 erreurs** |

Les 5 commits de la branche, individuellement : 420 / 430 / 430 / 457 / 477
tests verts ; `ruff` propre partout ; **`mypy` rouge dès le premier commit**
(`a739571`). Aucun commit de la branche ne passe `make all`.

Le chiffre « 407 tests verts » annoncé pour cette branche est **faux** : la
mesure donne 477.

Stabilité : 25 graines `PYTHONHASHSEED` sur `main` → 25/25 vertes.

**Après le lot 0** (branche `claude/rag-pipeline-lot-0-repairs-b232a1`, pointe
`390ce8a`, 8 commits sur `main`) : `make all` passe sur **chacun des 8 commits
pris individuellement** — 395 / 420 / 430 / 430 / 457 / 477 / 508 / 508 tests
verts, `ruff` propre et `mypy --strict` sans erreur partout (`mesuré`). Le
compte canonique de tests vit désormais dans `README.md`, section Tests :
**508**. Stabilité : graine 0 puis graines 1 à 25 → **26/26 vertes sur chacun
des 8 commits** (la graine 0 désactive la randomisation du hachage, c'est un
cas distinct et elle est comptée à part).

**Apres la reparation du lot 0 et sa fusion** (fusion `--no-ff` `b59bf38`,
14 commits : les 8 du lot plus les 6 de la reparation) : `make all` passe sur
**chacun des 6 commits de reparation pris individuellement** — 508 / 508 / 511 /
521 / 532 / **535** tests verts, `ruff` propre et `mypy --strict` sans erreur
partout. Stabilite : graine 0 plus 25 graines aleatoires sur chacun des 6
commits → **156/156 vertes**. Sur le resultat de la fusion lui-meme, verifie par
le pilote avant de pousser : **535 verts**, `ruff` propre, `mypy` « no issues
found in 36 source files » (`mesure`, 29 aout 2026). Le compte canonique reste
dans `README.md`, section Tests.

**Apres la fusion du lot 0b** (fusion `--no-ff` `e998e7d`, 31 aout 2026 :
les 3 commits de livraison, 5 de premiere reparation, 10 de seconde). Verifie
par le pilote **sur le commit de fusion lui-meme** (`mesure`, 31 aout 2026) :
**552 tests verts**, `ruff` propre, `mypy` « no issues found in 36 source
files », `make all` en **2** — le rouge d'alors, `format-check` sur les quatre
fichiers plies a la main (§5.4) — et l'arbre **non sali**. *(Mesure conservee
telle quelle : elle decrit le commit de fusion du lot 0b. Ces quatre fichiers ont
ete reformates depuis, et `make all` rend **0** — §5.4.)* La porte sur chacun
des 18 commits pris individuellement, et le balayage de graines, sont aux
rapports des developpeurs ; le pilote a rejoue la porte sur cinq commits et un
sondage de graines, plus la mesure de fusion ci-dessus. Le compte canonique
reste dans `README.md`, section Tests.

**L'etat non versionne a change de perimetre le 31 aout 2026.** Le corpus
**est desormais versionne** (`a005172`, 25 fichiers, 57 381 999 octets
`mesure`) : il voyage avec le clone. Ne restent hors du depot que le `.env`, les
stores et la pile Docker. Sur le poste verifie le 31 aout 2026, **aucun** des
trois n'etait present : ni `.env`, ni conteneur du projet, ni reseau
`rag_network`, ni volume — et le hook d'identite n'etait pas installe. Le poste
avait ete annonce comme le poste d'origine du chantier. **Mesure le poste,
jamais ce paragraphe.**

**508 est un volume, pas une garantie.** Le fichier
`tests/unit/test_hierarchie_bout_en_bout.py` fabrique l'arbre imbriqué qu'il
prétend vérifier et reste vert des deux côtés de son défaut (§3.3) ; il compte
pourtant dans les 508. Le développeur du lot 0 l'a signalé de lui-même plutôt
que de laisser le chiffre parler seul. Toute lecture de ce compte doit porter
cette réserve.

**L'etat non versionne differe d'un poste a l'autre, et ce n'est pas un
detail.** Le corpus et les stores ne voyagent pas avec un clone. Ce qui suit
decrit le poste de reference. Sur le poste `/home/florian/mes_projets/`
(`mesure`, 29 aout 2026) : les stores ne sont **pas** vides — ChromaDB porte la
collection `rag_documents` avec **137 854** vecteurs, MinIO un bucket
`documents` non vide — et le corpus present n'est pas celui decrit ci-dessous :
36 fichiers HTML de deux autres ouvrages, un autre PDF, plus 170 fichiers dans
`Datas/mds/`, l'ancien corpus mixte francais/anglais que le §1 declare mort.
**Avant tout lot qui ingere, verifier le poste plutot que ce paragraphe.**

Corpus en place : 24 fichiers HTML (2 ouvrages × 12) + 1 PDF de **71** pages
(`mesuré` le 31 août 2026 par trois voies concordantes — `/Count` de l'arbre de
pages lu dans les octets bruts, `fitz.open()` et `Document.total_pages` écrit à
l'ingestion. **Le chiffre 73 qui vivait ici sous l'étiquette `mesuré` était
faux** : c'est le pire cas, un chiffre erroné sous la plus forte des trois
étiquettes. Un comptage régex brut de `/Type /Page` rend 72 — il compte des
objets, pas des pages, et ne tranche rien.) Parmi les 12 fichiers de chaque ouvrage, `Index.html` est écarté par
le capteur (`matter.py:40`) ; **`Preface.html` ne l'est pas** — « preface » n'est
pas dans `FRONT_BACK_MATTER_TITLES`. Il sera donc ingéré depuis les deux
ouvrages, ce qui est le cas d'école de l'exigence 3.

---

## 3. Ouvert — bloque une mesure

Un défaut qui bloque une mesure passe devant un défaut plus grave mais inerte.

### 3.2 → MESURÉ par le lot 1 et son audit — le graphe n'est PAS plat, et la correction proposée était un no-op

**Fermé le 31 août 2026.** Deux conversations indépendantes ont mesuré, la
seconde sur les **22** chapitres retenus par le capteur et non sur deux.

**Ce que le constat annonçait.** `ranking.docling_parent_rank` (`ranking.py:56-71`)
rend `0`, et non `None`, dès que le premier parent est `#/body` ;
`ranking.flat_rank` (`ranking.py:130-148` — l'ancien renvoi
`extraction.py:370-373` était **périmé**) ne bascule sur `docling_level_rank`
que si le premier signal rend `None`. Donc, *si* Docling n'imbriquait pas les
titres d'une capture SingleFile, tous les titres seraient frères sous le
document. L'antécédent était `supposé`. **Il est faux, sauf sur un chapitre.**

**Mesuré, sur les 22 chapitres HTML, en mémoire et sans écrire dans aucun
store** : **659 titres**, dont **146 de rang 0** et **513 imbriqués** ;
`docling_parent_rank` répond sur **659 sur 659**, et le signal `level` n'est
donc **jamais** consulté. **21 chapitres imbriquent, 1 est plat.**

**Le périmètre exact, à ne pas élargir.** Le chapitre plat est
`Datas/htms/Practical MLflow for Generative AI on Databricks/10. Unifying GenAI Systems with MLflow.html`
— 8 titres, tous `label=title`, tous `parent.cref == "#/body"`, tous `level`
absent, tous de rang 0. **La cause est dans la capture, pas dans le code.** Le
pilote l'a recompté sur le corpus versionné : le nombre de titres de rang 0
**égale le nombre de `<h1>`** dans **22 chapitres sur 22**.

#### « Le seul chapitre retenu sans aucun `<h2>` » était FAUX — ils sont trois

Ce constat écrivait, et le mandat §5.1 ter avec lui, que ce chapitre était « le
seul chapitre retenu sans aucune balise `<h2>` ». **C'est faux, et le tableau des
balises était sous les yeux de qui l'a écrit.** Remesuré par la réparation du lot
3 sur les **22** chapitres retenus par le capteur (`matter.is_front_back_matter`
écarte les deux `Index.html`) :

```bash
# comptage des <h2> sur les 22 chapitres retenus, sur le corpus versionné
uv run python -c "…BeautifulSoup(f).find_all('h2')…"   # voir tests/unit/test_non_platitude.py
```

| chapitre retenu sans aucun `<h2>` | `<h1>` | `<h6>` | son graphe |
|---|---|---|---|
| `MLOps with Databricks/Preface.html` | 9 | 4 | **`{0: 9, 1: 4}` — il s'imbrique** |
| `Practical MLflow…/Preface.html` | 8 | 4 | **`{0: 8, 1: 4}` — il s'imbrique** |
| `Practical MLflow…/10. Unifying GenAI Systems…` | 8 | 1 | `{0: 8}` — **plat** |

*(Distributions `mesuré`es le 31 août 2026 sur le graphe vivant des 23 documents,
produit par le code du lot 3 : `MATCH (v:SectionHeader) RETURN
v.SectionHeader.depth`, regroupé par racine de la chaîne `PARENT_OF`. Comptes de
balises `mesuré`s sur le corpus versionné.)*

**« Sans aucun `<h2>` » n'est donc PAS la propriété discriminante.** Deux
chapitres sur trois la portent et s'imbriquent quand même.

**Ce qui discrimine, mesuré :** le chapitre plat est le seul dont **aucune balise
de titre sous `<h1>` ne devient un titre pour Docling**. Il n'en porte qu'une, et
c'est la légende de sa figure — `<h6>Figure 10-1. MLflow as an integration plane
for traces, assistants…</h6>` — que Docling classe **`caption`**, rattachée à
l'image. Sa capture porte exactement 1 `picture` et 1 `caption`, et 8 items à
label de titre pour 8 `<h1>`. Les deux Prefaces, elles, portent quatre `<h6>` qui
sont des **libellés d'admonition** — `Tip`, `Note`, `Warning`, `Note` — et Docling
les rend comme des titres, imbriqués sous le `<h1>` qui précède.

**Et la formulation prudente s'arrête là.** Que « toute légende de figure en
`<h6>` devienne un `caption` » est une généralisation à partir d'**un** cas : ce
qui est mesuré, c'est ce chapitre-ci. La propriété qui se teste sans extrapoler
est celle-ci, et c'est elle que `test_non_platitude.py` asserte : **le graphe d'un
chapitre est plat quand son nombre de titres rendus égale son nombre de `<h1>`**,
c'est-à-dire quand rien ne survit sous le niveau de tête.

**Une réserve de lecture, mesurée.** Les deux `Preface.html` n'imbriquent que par
des libellés d'admonition : leur hiérarchie n'est pas éditoriale. Sur tout le
corpus HTML, **55 des 513 titres imbriqués (10,7 %) sont des admonitions**.

**Le graphe réellement écrit** (3 documents ingérés par le lot 1, `mesuré`,
rejoué par le pilote) : 2 288 sommets, 2 285 arêtes `PARENT_OF`, **159 arêtes
`SectionHeader → SectionHeader` contre 29 `Document → SectionHeader`**, des
chaînes jusqu'à **5 sauts**, et des fils d'Ariane réels — `Getting from Raw
Data to Chunks > Chunking > Embedding window considerations`. L'audit a prouvé
en plus ce que le compte ne disait pas : **0 sommet à deux parents, graphe
acyclique, exactement 3 racines toutes `Document`** — donc aucun sous-arbre
flottant, et l'arbre est bien un arbre.

**Et la correction que ce constat proposait est un NO-OP.** Faire rendre `None`
à `#/body` fait retomber `flat_rank` sur `docling_level_rank`, qui rend `None`
puisque `level` est absent sur **tous** les `label=title` concernés ; puis
`elements.py:272` fait `place(element_id, heading_rank or 0)` → **rang 0, à
l'identique**. Vérifié dans le code par le pilote. La correction n'aurait rien
changé, et l'avertissement de §3.3 demandait de casser deux tests justes pour
l'appliquer.

**Le signal `level` aurait produit un arbre PIRE**, et la phrase d'origine
— « l'attribut `level`, signal fiable du HTML, est écrasé par un signal moins
fiable » — est **inversée** : le signal parent répond sur 100 % des titres et
reproduit exactement l'imbrication des balises `h`, tandis que `level` est
absent sur les 146 titres de tête et vaut **5** sur les 55 admonitions, qui
seraient enfoncées à cinq niveaux.

**Les deux chiffres qui s'opposaient.** `CHANGEMENTS.md:78-83` annonce 759
arêtes titre → titre « sur le corpus de référence », qui n'existe plus ; le
contrat côté agent annonce 0 et 0. Sur 3 documents d'ici : **159**. Aucun des
deux n'est réfuté — ils portent sur d'autres corpus — mais **le 0/0 côté agent
mesure un graphe produit par autre chose que ce code.**

**Conséquence de plan : le lot 2 disparaît.** Pas parce que « le graphe est
imbriqué » — il l'est à 21/22 — mais parce que **sa correction ne fait rien**.
Ce qui en sort vivant est §4.11, qui n'a jamais dépendu de la platitude.

**Projection au corpus complet** (`calculé` — somme des 22 chapitres mesurés en
mémoire et du PDF mesuré dans le graphe, ce n'est **pas** un état du graphe) :
**163** arêtes `Document → SectionHeader` contre **583** titre → titre.

### 3.3 → RETOURNÉ par le lot 1 et son audit — les deux tests assertent le comportement JUSTE

**Fermé le 31 août 2026, dans l'autre sens que celui où il avait été ouvert.**

Ce constat reprochait à `test_hierarchie_bout_en_bout.py::test_un_titre_racine_a_le_rang_zero`
d'« exercer exactement le cas de production (parent `#/body`) et d'asserter
`== 0`, lisant le symptôme comme un succès ». **`== 0` est le comportement
juste** : mesuré, **146 titres sur 659** ont `parent.cref == "#/body"` dans les
22 chapitres, et leur compte égale le nombre de `<h1>` dans 22 chapitres sur 22.
Un titre accroché à `#/body` **est** un titre racine.

L'« avertissement pour le lot 2 » — « appliquer la correction fait tomber
**deux** tests, les deux sites sont à amender ensemble » — instruisait donc de
casser deux tests corrects, **et pour rien**, la correction étant un no-op
(§3.2). Il est **retiré**.

**Ce qui reste vrai, et qui ne se referme pas.** Le fichier **fabrique** bien
l'arbre qu'il prétend vérifier (`enchaine()` pose `item.parent = Ref("#/texts/0", parent)`),
donc son docstring — « des items tels que Docling les rend » — est **faux** :
c'est une prétention à corriger, pas une couverture absente. L'audit du lot 0
avait mesuré sa valeur marginale à **3 mutations sur 7 que lui seul voit**.

### 3.4 → traité par le lot 3 — l'instrument tokenise ce que le modèle reçoit

**Le constat, tel qu'il était ouvert.** `index_report.py` tokenisait
`documents`, c'est-à-dire le texte **stocké**, quand `vectors.py` encode
`contextualize(texte, section_title)`, le texte **préfixé du titre de section**.

**Remesuré par le lot 3 sur le CORPUS COMPLET** — 4 365 chunks, 23 documents,
fenêtre 128 (`mesuré` le 31 août 2026 ; le lot 1 mesurait 773 chunks sur 3
documents) :

| | médiane | maximum | au-dessus de 128 |
|---|---|---|---|
| texte **stocké**, ce que l'instrument tokenisait | 88 | **140** | **65 (1,5 %)** |
| texte **encodé**, ce que le modèle reçoit | 95 | **149** | **137 (3,1 %)** |

**PROVENANCE, ET L'ÉTIQUETTE ÉTAIT FAUSSE.** Ces chiffres portaient la mention
« index produit par le code de `main` **avant toute correction** ». C'est
inexact : l'index de ce poste a été produit par le code du **lot 3** lui-même —
le Postgres Dagster est reparti vierge et les sensors, livrés armés, ont
réingéré le corpus complet (§4.26). *Un chiffre mesuré avant ton changement n'est
pas un chiffre mesuré après.*

**La conclusion est robuste, et c'est l'étiquette qui était à reprendre** :
l'audit a remesuré les sept valeurs — 65 / 137 / 72 / 88 / 95 / 140 / 149 — sur
l'index actuel et obtient les **mêmes**. C'est attendu, la correction portant sur
l'INSTRUMENT et non sur ce qu'il mesure. Mais la robustesse se démontre en
remesurant, jamais en étiquetant.

**72 chunks franchissent la fenêtre par le seul préfixe de titre.** Le facteur
de sous-comptage vaut **2,1** ici ; le lot 1 avait mesuré « exactement 2 » sur
son échantillon de 773 — la conclusion tenait, le facteur exact était propre à
l'échantillon.

**Ce qui a été corrigé n'est pas le calcul, c'est la DIVERGENCE.** Deux endroits
décidaient du même texte. Corriger l'instrument aurait fermé l'écart du jour et
laissé les deux sites libres de diverger à nouveau. La construction du texte
encodé vit désormais à un seul endroit, `chunking.embedding_inputs`, et les deux
appelants la partagent. Elle refuse une entrée désalignée : un décalage d'un
rang préfixerait chaque chunk du titre de son voisin, sans que rien ne le
signale.

Le rapport dit désormais **sur quel texte il compte**, et le réglage
`embed_section_context` a deux positions : à faux, il n'y a pas de préfixe, et
l'instrument le dit plutôt que de laisser croire qu'il en tient compte.

**Et l'instrument n'était gardé par aucun test, pour une raison mécanique** :
`index_report` importait `chromadb` et le modèle d'embedding au niveau du
module, donc aucun test ne pouvait l'importer sans l'image d'extraction (10,4 Go).
Ces imports sont passés dans `main`, la mesure est devenue une fonction pure à
tokeniseur injecté, et un sous-processus garde la propriété. *Ce qu'un test
n'importe pas, il ne teste pas.*

### 3.4 bis → traité par le lot 3 — les deux phrases d'exhaustivité de `vectors.py`

`vectors.py` affirmait en en-tête « **plus de troncature** », et dans
`get_chunker` que recevoir le tokenizer du modèle « est ce qui **garantit
qu'aucun chunk ne sera tronqué** à l'encodage ». Deux phrases d'exhaustivité,
dans le fichier qui produit les vecteurs, et **toutes deux fausses**.

Elles le sont de deux façons distinctes, mesurées :

1. **`HybridChunker` ne peut pas fractionner une table.** Une table sérialisée
   en Markdown est un bloc indivisible : il la rend telle quelle, plus longue
   que la fenêtre. Les **65** chunks qui dépassent déjà sur le texte stocké sont
   **65 tables sur 65** — aucun autre label (le lot 1 mesurait 8 sur 8 sur son
   échantillon). Ce n'est pas un réglage : réduire la fenêtre ne fractionne pas
   davantage. **Ce qui manquait était de le mesurer et de l'écrire** ; refaire
   le découpage des tables est un chantier à part, §7.1 ;
2. **le titre est préposé APRÈS le découpage.** Le découpeur compte ses tokens
   sur sa propre sérialisation ; `write_elements` préfixe ensuite. **72** chunks
   franchissent par ce seul geste, et le découpeur ne pouvait pas le prévoir.
   L'aggravant que §3.4 étiquetait `supposé` est donc **mesuré**, et confirmé.

Les deux docstrings portent désormais le chiffre et la cause. `architecture.md`
portait la même affirmation — « (aucune troncature) » — et est corrigé dans le
même commit.

### 3.6 bis → le test de non-platitude, livré par le lot 3

L'audit du lot 1 réclamait un test qui distingue « **Docling** imbrique » de
« **ce chapitre-là** imbrique ». Le chantier a failli supprimer un lot entier sur
un antécédent jamais mesuré : `tests/unit/test_non_platitude.py` le mesure.

Il rejoue le code de rang de production sur des arbres Docling **capturés depuis
les captures réelles et versionnées**, et non sur un arbre fabriqué à la main —
le reproche exact fait à `test_hierarchie_bout_en_bout.py`, qui pose lui-même
les parents qu'il vérifie (§3.3). Il couvre les deux cas (`mesuré`) :

| chapitre | titres | distribution des rangs | `<h1>` du source |
|---|---|---|---|
| `MLOps with Databricks/7. Foundation Models…` | **41** | **{0: 5, 1: 10, 2: 21, 3: 5}**, 36 imbriqués | 5 |
| `Practical MLflow…/10. Unifying GenAI Systems…` | 8 | **{0: 8}** — réellement plat | 8, et **aucun titre rendu sous le niveau de tête** |

*(Ces deux lignes portaient **39 titres** et **{0: 5, 1: 10, 2: 21, 3: 3}** sous
l'étiquette `mesuré`. **C'était faux**, et le paragraphe qui suit dit pourquoi.
Les valeurs ci-dessus sont remesurées de deux façons indépendantes qui
concordent : en rejouant le code de rang sur la capture corrigée, et sur le
**graphe vivant** — `MATCH (v:SectionHeader) RETURN v.SectionHeader.depth`,
regroupé par racine de la chaîne `PARENT_OF`, `mesuré` le 31 août 2026 sur
l'index des 23 documents produit par le code du lot 3.)*

### La capture jetait les nœuds de groupe, et le test ne pouvait pas le voir

**C'était le défaut central de ce fichier, et il vivait dans le test qui est la
raison d'être du point 6.** `scripts/capturer-larbre-docling.py` capturait via
`document.iterate_items()`, dont le paramètre `with_groups` vaut `False` par
défaut : **les nœuds de groupe n'étaient jamais rendus.** Or
`ranking.docling_parent_rank` **remonte** la chaîne des parents et **franchit**
ces conteneurs sans les compter — une capture qui les omet casse la remontée au
premier groupe rencontré.

Mesuré sur la capture du lot 3 : **1 175** références de parent pointaient un
nœud absent (1 130 sur le chapitre imbriqué, 45 sur le plat), et **262** nœuds de
groupe manquaient (257 et 5). Deux titres du chapitre imbriqué avaient un groupe
pour parent **direct** — `#/texts/389` → `#/groups/79` et `#/texts/468` →
`#/groups/91`. Pour ces deux-là, `_Ref.resolve` rendait `None`,
`docling_parent_rank` rendait `None`, `flat_rank` retombait sur
`docling_level_rank` (absent) et rendait `None` — et le filtre
`[rang for rang in rangs if rang is not None]` **les jetait en silence**.

**Et le silence coûtait bien plus que deux titres.** Sans aucun nœud de groupe
dans la capture, la mutation « compter les conteneurs anonymes comme des
titres » n'avait plus rien à mordre : **le test bâti sur du réel était aveugle au
mécanisme même qu'il existe pour éprouver sur du réel.** Mesuré, mutation
`ranking.py:68` — `if str(getattr(cible, "label", "")) in HEADING_LABELS` → `if
True` :

| état | `test_non_platitude.py` sous la mutation |
|---|---|
| lot 3, capture sans groupes | **VERT**, 10 tests — aveugle. Seul `test_ranking.py`, l'arbre fabriqué à la main, la voyait |
| après réparation | **ROUGE**, `rc=1`, deux tests |

**Couverture marginale, remesurée sur sept mutations du code de rang** (`mesuré`,
script rejouable, les sept ancrages sont dans le message du commit) :

| fichier | avant | après |
|---|---|---|
| `test_non_platitude.py` | 5/7 | **6/7** |
| `test_hierarchie_bout_en_bout.py` | 5/7 | 5/7 |
| `test_ranking.py` | 5/7 | 5/7 |

*(Ce jeu de sept mutations n'est **pas** celui de l'audit du lot 3, qui annonçait
1/7 contre 3/7 : sa liste n'a pas été retrouvée, et un ratio ne se compare pas
d'un jeu à l'autre. Ce qui se compare, et qui est le résultat, est la
**bascule de M-G** sur un jeu tenu constant entre les deux colonnes.)*

**Trois corrections en découlent, et elles tiennent ensemble :**

1. la capture passe `with_groups=True`. Les deux empreintes SHA-256 sont
   **inchangées** — la capture décrit exactement le même HTML, seul l'arbre s'est
   complété ;
2. **l'assertion qui interdit le silence** vit dans l'aide `_rangs` et non dans
   un test : **autant de rangs que de titres dans la capture**. Elle vaut donc
   pour tous les appelants à la fois, parce que c'est le silence qui était
   structurel, pas l'oubli d'un test. Sans elle, le défaut se reformerait au
   prochain changement de Docling ;
3. deux gardes de structure s'ajoutent : **aucune référence de parent ne pointe
   hors de la capture** — elle rougit pour toute famille de nœud oubliée, pas
   seulement pour les groupes — et **les groupes sont là, et aucun ne porte un
   label de titre**. Le second est le témoin du premier : si Docling étiquetait
   un jour un groupe `section_header`, tous les rangs sous lui augmenteraient
   d'un.

**Et le cas plat seul aurait été vert des deux côtés du défaut.** Mesuré par
mutation : `docling_parent_rank` forcé à rendre 0 — le graphe devient plat —
fait rougir des tests **tous du chapitre imbriqué** ; les assertions du chapitre
plat restent vertes, puisqu'il rend 0 dans les deux cas. C'est exactement
pourquoi il fallait les deux, et pourquoi un test à un seul cas n'aurait rien
prouvé.

**Et il asserte la bonne cause de la platitude, pas celle qui avait été
écrite.** Le lot 3 avait recopié du §3.2 « c'est le seul chapitre retenu sans
aucune balise `<h2>` », et son test portait une assertion nommée
`test_the_flatness_comes_from_the_source_which_has_no_h2` : **une causalité que la
mesure démentait.** Trois des 22 chapitres retenus n'ont aucun `<h2>`, et deux
s'imbriquent (§3.2). Le test asserte désormais, **à pleine portée du corpus** :

- que ces trois chapitres existent, et que le chapitre plat en est un — donc que
  « sans `<h2>` » ne peut pas être la cause, puisque la propriété est partagée ;
- que la propriété qui discrimine est **« aucun titre rendu sous le niveau de
  tête »** : titres rendus = `<h1>` = 8 pour le plat, 41 contre 5 pour l'autre ;
- que la cause mesurée de ce chapitre-ci est que sa seule balise de titre sous
  `<h1>` est une **légende de figure**, que Docling classe `caption`.

Coût de cette assertion à pleine portée : **+0,86 s** (`mesuré`) — la lecture des
balises `<h2>` des 22 chapitres. C'est payé volontairement : elle convertit une
mesure écrite dans un document, que le chantier a recopiée trois fois sans la
vérifier, en un garde qui rougit.

**Il prouve qu'il a atteint le chapitre qu'il croit**, par l'empreinte SHA-256 du
HTML brut versionné **et** par celle du HTML nettoyé, que le test recalcule en
faisant tourner le vrai nettoyage. Deux développeurs de ce chantier s'étaient
fabriqué un faux vert en bouclant sur une liste non protégée : le test échoue
aussi si la capture ne porte pas exactement les deux cas attendus.

**La capture est en YAML et non en JSON**, et ce n'est pas un goût : les deux
empreintes SHA-256 sont lues par `detect-secrets` comme des « Hex High Entropy
String ». Le dépôt déclare ses faux positifs **au site**, par un
`pragma: allowlist secret` justifié — et JSON n'admet pas de commentaire. Le
YAML porte la justification à côté de la valeur, où un relecteur la voit, et
`check-yaml` le contrôle. Aucune baseline, aucune règle relâchée.

**Ce qu'il ne voit pas, et qui le voit à sa place.** Un changement de
comportement de Docling : la conversion est capturée une fois par
`scripts/capturer-larbre-docling.py`, que `--verifier` rejoue en comparant.
`docling` est épinglé à 2.117.0, et rejouer ce script fait partie du geste qui
change cette version.

**Et cette frontière est exactement là où le défaut est passé.** Le test ne peut
pas voir ce que la capture ne porte pas, et la capture portait un arbre troué. La
leçon est plus étroite que « une capture peut être fausse » : **le test rejoue un
algorithme de REMONTÉE, donc sa fixture doit porter l'arbre COMPLET, pas
seulement les nœuds qui l'intéressent.** Une capture réduite au contenu est une
capture juste pour un algorithme qui descend et fausse pour un algorithme qui
monte. C'est ce que gardent désormais les deux assertions de structure.

**Pourquoi le test ne convertit pas lui-même**, `mesuré` le 31 août 2026 :
`uv pip install docling==2.117.0` ajoute **85 paquets** — dont `torch` et
**quinze paquets NVIDIA CUDA** — et **rétrograde `websockets`** (17.0.1 → 16.1.1),
une dépendance de l'orchestrateur. Sur une chaîne qui tourne sur processeur et
dont le `pyproject.toml` dit que « les deps lourdes d'extraction vivent dans
`Dockerfile.docling` », faire porter cela à `make install` n'était pas
défendable.

**Coût, remesuré après la réparation** (`mesuré`,
`pytest tests/unit/test_non_platitude.py --durations=5`) : le fichier entier
tient en **2,57 s**, dont deux postes qui font tout le reste —

| poste | coût |
|---|---|
| `test_the_real_cleaning_still_produces_what_was_captured` (le nettoyage réel des deux chapitres) | **0,99 s** |
| `test_the_absence_of_h2_is_shared_by_three_chapters_so_it_explains_nothing` (les balises des 22 chapitres) | **0,90 s** |
| tout le reste, 12 tests | < 0,3 s |

La livraison du lot 3 mesurait **+1,26 s** sur `make test` ; la réparation ajoute
la seconde du contre-exemple à pleine portée. **C'est payé volontairement** : ce
poste-là convertit en garde une mesure qui vivait dans un document et que le
chantier a recopiée trois fois sans la vérifier — c'est précisément comme cela
que « le seul chapitre sans `<h2>` » a survécu du lot 1 au lot 3.

**Aucun marquage** : ni `slow`, ni `skip`, ni `xfail`. Un marqueur sortirait le
test de la porte par défaut, et un garde qu'on n'exécute pas n'est pas un garde ;
deux secondes et demie sur une suite de 11 s ne le justifient pas.

### 3.5 La chaîne d'images HTML est ROMPUE — mesuré, 199 images sans `minio_url`

**CONFIRMÉ le 31 août 2026, et la cause est plus radicale que ce constat ne
l'écrivait.**

`cleaning.py:422-423` réécrit `img src` avec l'URL MinIO ;
`extraction.py:335-337` ne propage cette URL que si `item.image.uri` commence
par `http`. **Cette description du code est exacte et trompeuse comme cause** :
le test du préfixe n'est **jamais atteint**, parce que `item.image` vaut `None`.

Mesuré sur le **producteur**, sur les **22** chapitres retenus, en convertissant
en mémoire sans écrire dans aucun store :

| | |
|---|---|
| `<img src="http…">` dans le HTML nettoyé | **199** |
| items `label=picture` rendus par Docling | **199** |
| dont `item.image` non `None` | **0 / 199** |
| dont `item.image.uri` commençant par `http` | **0 / 199** |

`item.source`, `item.references` et `item.meta` sont vides aussi : **l'URL
n'atterrit nulle part d'exploitable**. Seul `captions` est renseigné.

Dans le graphe réellement écrit (3 documents) : **26 images de capture HTML sur
26 sans `minio_url`**, et **26 objets MinIO orphelins sur 39** — téléversés,
payés en place et en temps, et **inatteignables par l'agent**, qui ne sert que
ce que le graphe référence (`RESTRICT_MEDIA_TO_GRAPH=true`). Les 13 seuls
sommets porteurs d'une URL sont **10 `Picture` et 3 `Table`** issus du **PDF**,
produits par un tout autre chemin (`images.py`) : la chaîne PDF fonctionne, la
chaîne HTML non.

**Le périmètre réel est 199 images, pas 26** : 26 est ce que le lot 1 a ingéré,
199 est ce que le corpus porte.

---

## 4. Ouvert — grave mais inerte tant que le corpus ne bouge pas

### 4.1 Un lot PDF en échec laisse un document partiel écrit dans les stores

`extraction.py:468-487` : sur exception d'un lot, on journalise et **on
continue** ; les lots suivants sont persistés (`storage.persist`, l.485).
L'erreur n'est levée qu'en fin de document (`extraction.py:498-502`), et
`factory.py:198-201` la marque `allow_retries=False`. Résultat : la partition
Dagster est rouge, **et l'ouvrage est dans l'index, tronqué, sans que rien ne
l'en retire**. `verify_contract.py` ne peut pas le voir : les `element_id`
écrits sont valides.

C'est le pire cas de la Partie II sous une autre forme — non pas un run vert
sur un corpus incomplet, mais un run rouge sur des stores incomplets qu'on
croit vides.

### 4.2 Une réingestion d'un document modifié laisse des orphelins

Les identifiants dérivent du texte (`elements.py:153`) : un texte modifié donne
de nouveaux identifiants, les anciens survivent dans ChromaDB comme dans
NebulaGraph. `NebulaWriter.delete_document` (`nebula.py:262-265`) existe et
**n'a aucun appelant**. Or le capteur Dagster déclenche sur `mtime`
(`factory.py:361-372`) : mettre à jour un document est le chemin nominal.

Inerte aujourd'hui (stores vides, corpus figé), fatal dès la première
correction de corpus.

### 4.3 `nebula.py:125` code en dur les identifiants du graphe

`get_session("root", "nebula")`. `NEBULA_USER` et `NEBULA_PASSWORD` existent
dans `.env.example:15-16` et ne sont exposés par **aucun** settings :
`DoclingSettings` ne les déclare pas. Deux autres sites font de même :
`verify_contract.py:104` et `verify_data.py`. Le `.env` ment donc sur ce qui est
réellement lu.

**Ce constat annonce TROIS sites. Il y en avait QUATRE**, et le quatrième est
`src/init_nebula.py`, que ce constat ne nomme pas. Les quatre lisent désormais les
réglages, `DoclingSettings` portant `nebula_user` et `nebula_password` avec les
défauts de `docker-compose.yml` — aucun poste ne change de comportement. **Un
seul des quatre reste sans garde**, et lequel est mesuré : voir §4.29.d.

### 4.4 → traité par le lot 3 — le contrat est vérifié là où il casse en silence

**Le constat, tel qu'il était ouvert.** `verify_contract.py` ne testait ni
l'existence des arêtes `PARENT_OF`, ni l'ordre de `sequence` (exigence 4), ni
que `source_path` est non vide (exigence 3), ni la cohérence
`chunk_index` / `chunk_count`, ni le modèle qui a produit les vecteurs
(exigence 1). Il rendait donc **rc=0 et « Contrat respecté »** sur l'index
complet du 31 août 2026 (`mesuré`, 4 365 chunks) — le même index où **251
sommets visuels sur 264 n'ont aucune URL**.

**Ce qui a été ajouté**, et pour chacun l'exigence qu'il garde :

| Contrôle | Exigence | Sur l'index vivant, `mesuré` sur la pointe de la réparation |
|---|---|---|
| `page_no` ne décroît pas dans l'ordre des `sequence`, par document | 4 | **0 inversion sur 15 173 arêtes** |
| `source_path` non vide | 3 | 0 chunk fautif |
| `0 ≤ chunk_index < chunk_count` | — | 0 chunk fautif |
| présence d'arêtes `PARENT_OF` | 4 | 15 173 |
| `minio_url` sur les sommets visuels | — | **251 sur 264 sans URL → anomalie** |
| modèle inscrit sur la collection | **1** | `paraphrase-multilingual-MiniLM-L12-v2` — **tracé, aucune anomalie** |
| **l'index n'est pas vide** *(neuf)* | toutes | 4 365 chunks |
| **`sequence` présente sur chaque arête** *(neuf)* | **4** | 0 arête sans `sequence` |
| **le jeu `{chunk_index}` est complet par élément** *(neuf)* | — | **2 éléments sur 3 750 troués → anomalie** |
| **`depth` non nul sur les sommets** *(neuf)* | — | 0 sur 15 173 |
| **le tag `Document` porte ses 7 colonnes** *(neuf)* | **3** | 7, aucune manquante |
| ancres présentes dans le graphe | 2 | **3 750 / 3 750** — la totalité, plus un échantillon |

**Deux affirmations de cette section étaient fausses, et la mesure les dément.**
Elle écrivait « modèle **non tracé** → anomalie » et, plus bas, « il redeviendra
vert quand le lot 4 aura réparé la chaîne d'images **et qu'une réingestion aura
inscrit le modèle** ». La collection **porte déjà** `embedding_model` — le lot 3
a réingéré le corpus complet avec son propre code, donc `_inscrire_le_modele` a
tourné. `verify_contract` affiche le modèle et ne lève **aucune** anomalie de
modèle. C'est la question la plus productive du chantier — *qu'est-ce que la
documentation affirme que le code ne fait pas ?* — appliquée au lot qui l'a
posée.

**Et un piège de provenance s'y cachait.** Le service Docling monte `/app/src`
depuis le **clone principal**, donc `docker compose exec docling-service python
-m src.verify_contract` exécute le code de `main` : il rend `rc=0` et « Contrat
respecté », c'est-à-dire exactement le défaut que ce constat ferme. Toute mesure
du code d'une branche doit monter le `src` de cette branche (voir §4.27).

**Le garde de `sequence` est celui du §6.16, et pas un autre.** La propriété
« aucun parent ne porte deux fois la même valeur » est l'**unicité sous un
parent** : une numérotation aléatoire distincte par parent la satisferait sans
porter aucun ordre. Les trois réserves mesurées dictent la forme du contrôle et
sont écrites à son site : `sequence` repart à 0 par document — d'où un contrôle
**borné au document**, sans quoi deux documents entrelacés rendraient des
inversions fausses — elle n'est pas contiguë sous un parent, et le plus grand
écart vaut **994** de différence, soit 993 valeurs intercalaires, donc **exiger
la contiguïté rougirait sur un graphe sain**. Le site canonique de ces chiffres
est le docstring d'`inversions_de_page` ; ne les recopie pas, renvoie-y.

**La phrase d'exhaustivité est corrigée, et l'échantillon est SUPPRIMÉ.** « Une
rupture de contrat est systématique » est vraie d'un FORMAT et fausse d'un ORDRE.
Le lot 3 avait borné l'échantillon de 400 à la seule présence des ancres, « le
seul contrôle dont le coût croît vraiment avec le corpus ».

**Cette dernière justification est démolie par la mesure.** L'échantillon valait
400 sur 3 750 avec `random.seed(0)` : **les mêmes 89 % n'étaient jamais
vérifiés**, exécution après exécution. Une graine fixe ne fait pas d'un
échantillon une couverture — elle fait d'un angle mort un angle mort **stable**.
Et le contrôle complet tient en **une** requête nGQL : `mesuré` le 31 août 2026
sur l'index complet, chronométré autour du seul `session.execute`, **0,053 s**
pour les 3 750 identifiants contre **0,008 s** pour 400. Soit 6,6 fois le coût
pour 9,4 fois la couverture. Il n'y avait rien à échantillonner.

**Et l'absence d'échantillon est GARDÉE**, ce qui n'allait pas de soi : `mesuré`,
remettre `identifiants[:400]` laissait la suite **entièrement verte**. Retirer un
échantillonnage sans garder son absence, c'est le laisser revenir au premier lot
qui trouvera le contrôle lent — et il le trouvera lent, puisque personne ne
remesure. Le garde asserte les identifiants **un par un** dans la requête, et son
témoin asserte le dénominateur : un échantillonnage qui réduirait les deux côtés
resterait vert sur une simple égalité.

#### Les cinq trous que l'audit a trouvés, et ce que chacun laissait passer

1. **`rc=0` SUR UN INDEX VIDE**, et c'est le pire des cinq parce que **tous** les
   contrôles vivent derrière ce garde. `if not metadatas: print("Index vide…");
   return` — donc une purge, une ingestion en échec ou un nom de collection
   erroné passaient pour « Contrat respecté », dans un outil dont le docstring
   dit « pour un usage en pré-déploiement ». Le défaut préexistait sur
   `main:52-54` ; sa portée s'était élargie à tout ce que le lot 3 avait ajouté
   derrière lui. Il sort désormais en **1** en nommant les causes usuelles ;
2. **il LEVAIT au lieu de rapporter quand `sequence` est NULL.**
   `int(ligne[2].as_int())` sans garde `is_null()`, alors que `page_no` en avait
   un à la ligne suivante. L'exigence 4 est « absente **OU** non monotone » : sur
   la moitié « absente », le rapport avortait sur une
   `InvalidValueTypeException`. Un outil de pré-déploiement qui plante ne dit pas
   « non conforme », il ne dit **rien**. Les arêtes sans `sequence` sont
   désormais comptées et nommées — et **écartées** du contrôle d'ordre plutôt que
   comptées à zéro, ce qui fabriquerait une fausse inversion ;
3. **`chunks_incoherents` ne voyait pas la panne que son docstring nomme.** Un
   morceau qui MANQUE est invisible depuis un chunk isolé : chaque chunk présent
   satisfait `0 ≤ index < count` même quand un frère a disparu. `mesuré` :
   **2 éléments sur 3 750** annoncent 7 et 4 chunks alors que 6 et 3 existent —
   `aa3de10738` (index 4 manquant) et `eb52c4ec8f` (index 3 manquant) — et le
   contrôle rendait « 0 chunk fautif ». `jeux_de_chunks_incomplets` vérifie le
   **jeu** complet. La **cause** n'est pas réparée ici et va au lot 4 (voir
   ci-dessous) ;
4. **`depth` n'était pas vérifié non nul sur les sommets** — la charge utile du
   §4.11. Le schéma migre en place, les **données** non : un `ALTER TAG … ADD`
   laisse à NULL tous les sommets déjà écrits. Un index à moitié migré était donc
   possible, et l'agent aurait lu `depth` sur les sommets récents et `NULL` sur
   les anciens sans qu'aucune erreur ne distingue « profondeur 0 » de
   « profondeur inconnue ». Le garde porte son témoin : **`depth = 0` est une
   profondeur, pas une absence** — un compteur écrit `if not profondeur`, la
   faute naturelle, rougirait sur un graphe sain, et c'est précisément le piège
   que `depth` tend depuis que le plafond est retiré (§4.24) ;
5. **le tag `Document` n'était pas couvert** — le défaut que
   `_verifier_les_tags` venait de fermer restait ouvert **d'un tag**. Elle reçoit
   `sorted(set(TAG_MAP.values()))`, c'est-à-dire les **11 tags d'élément** ; le
   tag `Document` n'en fait pas partie, son schéma lui étant propre. Or ses
   quatre `ALTER TAG Document ADD` (`nebula.py:333-340`) sont `required=False`
   par construction — « la colonne existe déjà » est leur cas nominal — donc une
   migration **réellement** refusée ne disait rien. Et parmi ces colonnes,
   `source_path` **est l'exigence 3 du contrat**. Un `DESCRIBE` en échec est
   désormais une anomalie et non une liste vide lue comme « aucune manquante » :
   *ne pas savoir n'est pas savoir que c'est bon.*

**Le contrôle du modèle a deux moitiés, et la seconde ferme la panne.** Rien
n'enregistrait quel modèle avait écrit l'index : un `.env` changé entre deux
ingestions laissait une collection portant des vecteurs de **deux** modèles,
tous deux en 384 dimensions. `vectors._inscrire_le_modele` inscrit le modèle sur
la collection à l'ouverture, et **lève** si elle en porte un autre — le job
échoue plutôt que d'écrire un index mixte. `verify_contract` lit la même
inscription après coup. Un index écrit avant ce garde n'est pas déclaré bon : il
est déclaré **non traçable**, ce qui n'est pas la même chose.

#### La levée n'était gardée par RIEN, et c'est le garde le plus important du lot

Cette section écrivait « (`mesuré` : la levée se produit) ». **C'est une
observation faite à la main une fois, pas un garde**, et la distinction est
exactement celle que ce chantier traque. `mesuré` par l'audit du lot 3 :
remplacer le `raise` de `vectors.py` par un `logger.warning` laissait **639 tests
verts**. Le garde contre la panne la plus coûteuse du système — exigence 1 du
contrat — reposait sur une relecture.

**Et il n'existait aucun `tests/unit/test_vectors.py`, pour une raison
mécanique.** `vectors.py` importait `chromadb` au niveau du module, et `chromadb`
n'est pas dans le venv du dépôt : aucun test ne pouvait importer le module.
C'est **le même défaut** que `index_report` (§3.4), `verify_contract` (ci-dessus)
et `verify_data` (§4.5) — le lot 3 l'avait fermé sur trois modules et manqué le
quatrième, **le seul des quatre dont le contrat est un `raise`**. L'import est
différé dans `get_collection`, et `tests/unit/test_vectors.py` existe.

Il porte ses deux témoins, sans lesquels il serait creux : le **même** modèle
écrit sous son nom préfixé `sentence-transformers/` ne doit **pas** lever — sinon
un garde qui lève sur tout passerait —, et la panne est assertée **dans les deux
sens**, la collection portant le bon modèle et l'ingestion tournant avec le
mauvais étant la même panne renversée.

#### Le seul contrôle d'ordre du contrat était neutralisable en silence

`mesuré` par l'audit : neutraliser la remontée de
`verify_contract.racine_de_chaque_element` laissait **639 tests verts**, et
`test_verify_contract.py` **n'importait même pas cette fonction** — *ce qu'un
test n'importe pas, il ne teste pas.*

**La conséquence n'est pas une anomalie manquée, c'est un succès faux.**
`inversions_de_page` groupe par document ; si le rattachement rend chaque élément
à lui-même, chaque groupe ne porte plus qu'**une** arête, et une seule arête ne
peut pas être en désordre. Le contrôle rend donc **zéro anomalie** sur un graphe
réellement cassé. Mesuré sur un graphe portant une vraie inversion de page : le
code livré rapporte `[('doc', 2, 9, 2)]`, la mutation rapporte `[]`.

**Le garde asserte la COMPOSITION, et pas la fonction seule.** Prise isolément,
`racine_de_chaque_element` a l'air d'une commodité, et un test de son seul
contrat aurait pu passer sans que l'ordre soit gardé. La composition vit
désormais dans `verify_contract.rattacher_au_document`, fonction pure — elle
existe pour être testable sans graphd, non pour factoriser une ligne — et le
garde porte son **témoin** : les mêmes arêtes **sans** rattachement rendent zéro
inversion. C'est ce témoin qui est le résultat.

**Ces contrôles n'étaient testables par rien**, le module faisant ses imports de
`chromadb` et `nebula3` au niveau du module. Ils sont différés dans `main`, les
décisions sont des fonctions pures, et un sous-processus garde la propriété.

**Conséquence à connaître : `verify_contract` sort désormais en 1 sur l'index de
ce poste**, et c'est le verdict juste. Il redeviendra vert quand le lot 4 aura
réparé la chaîne d'images (§3.5) et qu'une réingestion aura inscrit le modèle.
Un outil qui ne peut pas être vert aujourd'hui vaut mieux qu'un outil vert sur
un index cassé.

### 4.5 → traité par le lot 3 — `verify_data.py` ne fait plus rien à l'import

Le module n'avait pas de `main()` : `settings = get_settings()`, `failures = []`
puis les trois contrôles étaient des instructions de **niveau module**. Un
`import` accidentel — un outil qui parcourt le paquet, une complétion, un
`pytest --collect-only` — ouvrait une connexion ChromaDB, listait un bucket
MinIO, interrogeait NebulaGraph, et pouvait appeler `sys.exit(1)`.

**Et rien n'était testable** : un test qui importe le module aurait exigé les
trois stores debout. C'est le troisième module du lot dans ce cas, après
`index_report` et `verify_contract` — *ce qu'un test n'importe pas, il ne teste
pas*, et un module qu'on ne peut pas importer, personne ne le teste.

Les contrôles sont trois fonctions, les clients de stores sont importés dans
`main`, et la liste des échecs est **passée en argument** au lieu d'être un état
de module : un état de module survit à l'appel, donc deux exécutions dans un
même processus cumuleraient leurs échecs et la seconde sortirait en erreur pour
ceux de la première.

Le garde passe par un **sous-processus** : un `import` de plus dans
l'interpréteur courant ne rejouerait pas un module déjà chargé, donc le test
serait vert des deux côtés du défaut.

**Mais le lot 3 avait gardé l'import et LAISSÉ LE CODE DE SORTIE.** `mesuré` par
son audit : remplacer le `sys.exit(1)` de `main()` par `sys.exit(0)` laissait
**639 tests verts**. C'est **mot pour mot** la leçon que le lot 0 a payée sur
`wipe_stores` — « un code de sortie documenté et justifié n'était asserté nulle
part » — et l'équivalent y est gardé par cinq tests depuis `1c002f2`. Le même
défaut, dans le même dépôt, sur le module d'à côté, quatre lots plus tard.

Le garde est **décliné de celui de `wipe_stores`**, et pour la même raison : le
code de sortie **est** le comportement, pas son témoin. C'est ce qu'un
`docker compose exec` remonte et ce qu'un `&&` lit dans une procédure
d'avant-vol. Un `import` laisserait attraper `SystemExit` — prouver qu'un objet a
été levé, pas que la commande échoue. Les trois clients de stores sont bouchonnés
comme de vrais paquets en tête de `PYTHONPATH`, et non dans `sys.modules` : sinon
les bouchons survivraient au test et l'ordre des tests deviendrait significatif.

Quatre chemins d'échec sont couverts, et le quatrième est celui qu'on oublie :
ChromaDB injoignable, MinIO injoignable, `pool.init` qui rend **`False`** — une
branche distincte de l'exception —, et une **requête nGQL rejetée** alors que les
trois stores répondent. Sans ce dernier, un garde qui n'observerait que les
connexions serait vert sur un graphd debout dont le space n'existe pas. Plus le
témoin : les trois stores debout sortent en **0**.

### 4.6 Un nettoyage peut jeter 95 % du texte sans que rien ne le dise

`sources.py:63-66` : `min_text_ratio = 0.05`. `cleaning.py:494` accepte donc un
candidat qui ne conserve que 5 % du texte pré-nettoyé. Aucun seuil haut, aucun
journal — `cleaning.py` n'a pas de logger — et
`factory.py:243-251` ne publie ni `precleaned_bytes` ni le ratio dans les
métadonnées Dagster. La perte est structurellement invisible.

### 4.7 `except Exception` muet dans le choix de stratégie de nettoyage

`cleaning.py:486-489` : `except Exception: candidate = None`, sans justification
écrite au site et sans trace. Une stratégie qui plante devient un non-candidat
silencieux. Violation directe de la règle du dépôt.

### 4.8 Clés MinIO des crops PDF : ni assainies, ni porteuses de l'ouvrage

`images.py:174` : `f"images/{pdf_stem}/{image_id}_{element_type}.png"` où
`pdf_stem` est `identity.filename`, c'est-à-dire le nom **seul**, non assaini.
Deux PDF homonymes dans deux ouvrages écriraient au même endroit, et les
espaces ou caractères pleine chasse partent tels quels dans la clé d'objet.
`images.upload_file` (l.112), lui, assainit — deux conventions dans le même
module. Inerte à un seul PDF.

### 4.9 L'arête légende → illustration ne franchit pas une frontière de lot

`nebula.py:160` : `last_visual_id` est une variable locale de `write_elements`,
donc remise à `None` à chaque lot de pages. Une légende en tête de lot dont
l'image finit le lot précédent perd son arête `LINKED_TO`.

### 4.10 Un doublon exact rend une partition verte avec zéro élément

`extraction.py:132-141` retourne `{"elements": 0, "chunks": 0, ...}` et
`duplicate_of`. Mais `factory._record_metadata` (l.303-313) ne publie ni
`duplicate_of`, ni `pages_skipped`, ni `ocr`, ni `language`, ni
`failed_batches` : dans l'interface Dagster, un document écarté ressemble à un
document ingéré vide.

### 4.11 → traité par le lot 3 — `depth` est écrit sur le sommet, et la migration se constate

**Le constat, tel qu'il était ouvert.** `nebula.py:49` portait
`VERTEX_PROPERTIES = ("label", "page_no", "text", "minio_url")`. Ni `depth`, ni
`section_title`, ni `reference_id` n'étaient écrits sur les sommets ; `depth`
n'existait que dans les métadonnées ChromaDB. L'agent pouvait remonter les
`PARENT_OF`, mais ne pouvait lire aucun niveau déclaré.

**Ce qui est écrit, et ce qui a été écarté.** Une seule propriété est ajoutée :
`depth`. Les deux autres ont été écartées, et pour la même raison — elles
seraient une **seconde source de vérité** pour une information que le graphe
porte déjà exactement :

- `reference_id` **est** l'extrémité source de l'arête `PARENT_OF`. L'écrire sur
  le sommet crée deux versions du même lien, qui peuvent diverger ; aucune
  requête n'en a besoin, puisque l'arête se traverse ;
- `section_title` **est** le `text` du sommet parent, atteignable en une arête.
  L'écrire dupliquerait le texte de chaque titre sur chacun de ses descendants.

`depth`, lui, n'est déductible qu'en **parcourant** la chaîne jusqu'à la racine :
c'est la seule des trois qui apporte quelque chose. Elle est écrite sur **tous**
les tags d'élément et non sur le seul `SectionHeader` — ils partagent un schéma
unique, et `depth` est déjà calculée pour tout élément.

**La migration retenue, et l'affirmation du plan qu'elle corrige.** Le plan
disait « cela change le schéma Nebula, et le schéma n'évolue pas en place ;
toute correction impose une réingestion ». **L'antécédent est faux, et c'est
mesuré** : `ALTER TAG <tag> ADD (depth int)` réussit sur `rag_space` peuplé de
2 288 puis de 15 196 sommets, sans purge ni recréation. Ce qui n'évolue pas en
place est le `vid_type` du space (`ngql.py`, `FIXED_STRING`), pas une propriété
de tag.

**La conclusion d'ordre du plan tient quand même, pour une autre raison.** Le
schéma migre ; les **données** non. Les sommets déjà écrits portent `NULL`
(`mesuré` : 188 sur 188 après l'ALTER), et seule une réécriture du document les
renseigne. §4.11 doit donc bien précéder le lot 6 — non parce que le schéma
serait figé, mais parce que peupler la colonne coûte une réingestion complète.
*Un raisonnement juste sur un antécédent faux se relit comme une preuve.*

Le mécanisme est celui qui existait déjà pour le tag `Document` :
`CREATE TAG IF NOT EXISTS` pour un space neuf, puis un `ALTER TAG ... ADD` par
colonne, dont l'échec « Existed! » est toléré. Un `ALTER` par colonne et non
pour la seule colonne du jour : il n'y a aucune liste à tenir à jour.

**Et le lot a découvert le garde qui manquait, en le subissant.** `mesuré` le
31 août 2026 : sur un space où un `ALTER ... DROP` avait été joué,
`init_schema()` a rendu **`True`** alors que **onze tags sur douze** seulement
avaient migré. Nebula avait refusé le douzième avec **« Schema exisited
before! »** — il conserve l'historique de schéma d'un tag et **n'autorise jamais
une colonne supprimée à revenir sous le même nom**. L'échec d'un `ALTER` étant
toléré par construction, rien ne l'a signalé : le défaut ne se serait vu qu'à la
**première écriture**, sur un rejet du graphd, document à moitié écrit.

`NebulaWriter._verifier_les_tags` constate donc désormais le résultat au lieu de
le supposer : elle relit `DESCRIBE TAG` et lève si une colonne manque, en
nommant le tag, la colonne et le geste de réparation. `init_schema()` rend
`False`, et le service refuse de se déclarer prêt — un service mort se voit.
**Vérifié sur le cas réel** : sur le space empoisonné, `init_schema()` rend
`False` là où le code de `main` rendait `True`.

**La propriété est lisible sur le space réel, après réingestion complète**
(`mesuré` le 31 août 2026, corpus entier, 23 documents) : le tag `SectionHeader`
porte `depth`, **746 sommets sur 746 la portent, 0 à NULL**, et sa distribution
— `{0: 163, 1: 301, 2: 234, 3: 40, 4: 8}` — est **identique** à la profondeur
calculée indépendamment en remontant les chaînes `PARENT_OF` avant le changement.
Les deux voies concordent. `Paragraph` atteint désormais `depth = 5`, valeur que
le plafond rendait inatteignable.

**Deux conséquences à connaître, écrites ici parce qu'elles ne sont écrites
nulle part ailleurs :**

1. **une migration n'est pas réversible.** `ALTER ... DROP` condamne le tag
   jusqu'à la recréation du space. Ne l'utiliser jamais comme retour arrière ;
2. **un space existant qui a subi un `DROP` doit être recréé.** C'est le cas du
   `rag_space` de ce poste au 31 août 2026, et c'est le lot 3 qui l'a mis dans
   cet état en éprouvant la réversibilité — le dire plutôt que le taire.

### 4.12 Échelles de rang mélangées

`docling_parent_rank` compte à partir de 0 ; `docling_level_rank`
(`ranking.py:83-84`) rend le `level` de Docling, qui part à 1. Un document
offrant les deux signaux sur des titres différents produirait un arbre faux.
**Inerte, et sa condition d'activation annoncée était fausse — mesuré le
31 août 2026.** Le registre disait « le devient au moment même où 3.2 est
corrigé. À traiter dans le même lot ». Faux : sur ce corpus, le signal 1 répond
sur **659 titres sur 659**, le signal 2 n'est **jamais** consulté, et il est
indisponible (`level` absent) **précisément** sur les 146 titres où le signal 1
rend 0. Corriger §3.2 n'active donc rien — et §3.2 est de toute façon un no-op.

**Le vrai déclencheur, à surveiller** : le jour où un document **Markdown**
entre dans le corpus. `sources.yaml` déclare une source `markdown`
(`glob: mds/**/*.md`), `Datas/mds/` est vide et ignoré, et c'est sur le Markdown
que `docling_level_rank` est le signal annoncé. Reste ouvert, inerte, avec cette
condition — pas avec l'ancienne.

**Une seconde protection, non consignée jusqu'ici** : `HeadingStack.place`
dérive la profondeur du **parent** et jamais du rang brut, ce qui absorbe le
mélange d'échelles. Un rang trop **grand** est donc inoffensif ; un rang trop
**petit** dépilerait des ancêtres, et ce cas n'a pas été observé.

**Et RIEN NE GARDE L'ORDRE DES DEUX SIGNAUX — `mesuré` par la réparation du lot
3, consigné et non traité.** `flat_rank` (`ranking.py:147-148`) essaie
`docling_parent_rank` **puis** `docling_level_rank`, et cet ordre est le sujet de
ce constat. Inverser les deux lignes laisse la **suite entière verte** — `rc=0`,
639 tests. Aucun test du dépôt n'exerce la priorité, parce que sur ce corpus
`level` est absent partout où le signal parent répond, et le second n'est donc
jamais consulté (659 titres sur 659, ci-dessus).

C'est le même déclencheur que le reste du constat : le jour où un Markdown entre
au corpus, les deux signaux répondront sur des titres différents, et l'ordre
cessera d'être inerte. **Le garde à écrire ce jour-là est un test de priorité sur
un item qui offre les deux signaux** — pas une mesure sur le corpus, qui restera
verte des deux côtés. Le lot qui fera entrer un Markdown doit lire cette ligne
avant d'écrire une seule assertion.

### 4.13 `LINKED_TO(relation="describes")` là où le contrat annonce `DESCRIBES`

`nebula.py:184`, `nebula.py:217`, `nebula.py:345`. La documentation d'ici l'écrit
fidèlement (`graphe_connaissances.md:29`, `services/nebulagraph.md:33`) ; celle
de l'agent annonce une arête `DESCRIBES`. L'agent accepte les deux, mais la
divergence n'était documentée d'aucun côté d'ici. Elle l'est désormais.

### 4.14 → traité par le lot 3 — le contrat est gardé, et sa conséquence était mal décrite

Le découpage en lots vit désormais dans `matter.page_batches`, fonction pure, et
`_extract_pdf` la consomme. Le motif du déménagement est mécanique :
`extraction.py` importe `docling` au niveau du module, donc **aucun test ne peut
l'importer** sur un poste sans l'image d'extraction ; `matter.py` est importable,
et il portait déjà `kept_ranges`, dont le découpage en lots est la suite.

**Ce constat annonçait une conséquence, et elle est fausse — `mesuré` par
mutation.** Il écrivait : « le remplacer par `start_page = end_page` laisserait
la suite verte ». La première moitié est vraie — la suite reste verte, personne
n'exerçait cette boucle. **La seconde est fausse** : cette mutation ne produit
pas un chevauchement silencieux, elle produit une **boucle infinie**. Avec
`start_page = end_page`, `end_page = min(start + n − 1, range_end)` cesse de
progresser dès que la plage est épuisée, et la conversion ne termine jamais
(`mesuré` : `rc=124`, la suite tuée au bout de 120 s). Un run qui ne finit pas
n'est pas un run vert sur un graphe faux — c'est un run gelé, et le §4.15 dit ce
qu'un run gelé coûte à la réindexation.

**Le vrai chevauchement se produit autrement**, et c'est lui que les tests
gardent : allonger un lot d'une page (`lots.append((debut, fin + 1))`) fait
rougir **4 tests**, dont `test_batches_do_not_overlap`. L'erreur symétrique — un
pas de deux, une page sautée en silence — en fait rougir **5**.

**Et le chevauchement n'est pas inoffensif**, ce que le constat ne disait pas :
`compute_id` dérive l'identifiant d'un élément de
`(document, page, rang dans la page, texte)`, donc convertir une page deux fois
**réécrit les mêmes sommets** — rien ne duplique, et c'est ce qui rend la chose
invisible. Mais `DocumentAccumulator._global_order` est un compteur **global au
document** : il a avancé, et `sequence` avec lui. **L'exigence 4 du contrat casse
sans qu'aucune erreur ne le signale.** C'est le vrai coût, et il est plus grave
que « des éléments en double ».

---

### 4.15 Famine : un run bloqué gèle la réindexation, sur deux jobs

`reindex_job.py` saute tant qu'un run d'ingestion est non terminal, **et**
tant qu'un run de réindexation est en vol (garde ajoutée par la réparation).
Les deux gardes sont justes et partagent le même mode de panne : un run coincé
en `STARTED` — worker tué, daemon interrompu — bloque la réindexation
**indéfiniment**. Aucun délai de garde, aucune alerte.

Le *run monitoring* de Dagster, qui reprend les runs orphelins, est **absent de
`dagster.yaml`**. C'est là que se corrige la famille entière, d'un seul geste,
plutôt qu'au cas par cas dans chaque sensor.

### 4.16 Deux réindexations concurrentes restent possibles, en plus étroit

La réparation a fermé le cas large (le sensor relançait à chaque tick pendant
qu'un run travaillait). Reste la fenêtre étroite : deux évaluations du sensor
qui se croiseraient **avant** qu'un run ne soit enregistré. C'est précisément
pourquoi le `run_key` reste déterministe **à l'intérieur** d'un tick — la
déduplication de Dagster est la seconde ligne. Consigné pour ne pas croire le
cas clos.

### 4.17 La classification des statuts terminaux n'est gardée par aucun test

`reindex_job.py` dérive `STATUTS_EN_COURS` par soustraction des terminaux, et
la soustraction est correcte : vérifié contre le Dagster **épinglé** (1.13.16),
`FINISHED_STATUSES` vaut exactement `{SUCCESS, FAILURE, CANCELED}`. Mais
retirer `CANCELED` de `STATUTS_TERMINES` laisse la suite **verte** : une
ingestion annulée bloquerait alors la réindexation pour toujours.

Aggravant : le docstring écrit « les trois **seuls** états dont un run Dagster
ne revient pas » — une phrase d'exhaustivité, qu'une montée de version de
Dagster peut rendre fausse en silence.

### 4.19 Le refus de démarrer hors contrat n'est prouvé par aucun test

`main.py:93` place le contrôle du modèle d'embedding **hors** du `try` du
préchargement, avant `queue.start()` : le service refuse donc bien de démarrer
sur un modèle hors contrat, et `README.md:78` l'annonce. Mais retirer cette
ligne, ou la déplacer *dans* le `try`, laisse la suite verte.

Le contrat lui-même reste tenu par `get_embedding_model` (gardé). C'est le
**fail-fast** — la propriété que la documentation vend — qui repose sur une
relecture. C'est mot pour mot la leçon du mandat : « un code de sortie
documenté et justifié n'était asserté nulle part ».

### 4.20 `make audit` est rouge, et n'audite pas ce que la porte installe

Deux choses distinctes, toutes deux antérieures au lot 0 (`mesuré`, 29 août
2026) :

- **rouge** : `pip-audit` sort en 1 — `chromadb 0.6.3`, `CVE-2026-45830`,
  `-45831`, `-45833`, **sans version corrective proposée**. Il n'y a donc pas
  de correction à appliquer, mais il y a une décision à prendre et à écrire ;
- **aveugle** : la cible n'audite que les deux `requirements.txt`, ni le groupe
  `dev` de `pyproject.toml`, ni `uv.lock`. Or le lot 0 fait de `pyproject.toml`
  la source de vérité : l'audit vise désormais à côté de ce que la porte
  installe.

`make audit` ne fait pas partie de `make all` : la porte est verte, l'audit est
rouge, et rien ne le rappelle.

### 4.21 → traité par le lot 3 — le repli est compté, et il n'est pas réparé

**Le constat, tel qu'il était ouvert.** Sur le seul PDF du corpus, 86 des 87
titres du graphe retrouvés par leur taille de police réelle :

| taille | rang | origine | titres |
|---|---|---|---|
| 27,5 pt | 0 | rang **mesuré** | 17 |
| 21,2 pt | 1 | rang **mesuré** | 21 |
| 16,9 pt | 2 | rang **mesuré** | 8 |
| 15,0 pt (= corps) | 3 | **repli `inclassable`** | 39 |
| 11,2 pt (< corps) | 3 | **repli `inclassable`** | 1 |

**Aucun compteur ne disait combien de titres tombaient au repli.** Il y en a un
désormais, et il compte **à la source** — au moment où le rang est attribué,
et non a posteriori en retrouvant les tailles.

**Remesuré par le compteur livré** (`mesuré` le 31 août 2026, journal de
`_extract_pdf` sur le PDF entier) : **39 titres sur 87, soit 45 %**, et le
document ne classe que **3 niveaux** (corps à 15,0 pt, `fallback_rank` = 3).
Le chiffre est **juste** — l'audit l'a reproduit à la source.

**Mais l'explication écrite ici ne tenait pas, et elle est corrigée.** Elle
disait : « Le lot 1 annonçait 40 sur 86 : l'écart d'une unité est le titre que sa
méthode n'avait pas retrouvé. Les deux mesures concordent. » **L'écart n'est pas
d'une unité, et il ne porte pas sur un titre.** Les deux dénominateurs se
décomposent :

| | mesures | replis | total |
|---|---|---|---|
| lot 1, tailles retrouvées après coup | 17 + 21 + 8 = **46** | 40 | **86** |
| ce compteur, à la source | **48** | 39 | **87** |

**Deux titres changent de CLASSE** — ils passent du repli à un rang mesuré — et
un titre de plus est vu au total. Dire « l'écart d'une unité » décrivait la
différence des totaux et masquait le mouvement réel. C'est la famille de défaut
que ce lot existe pour fermer : *deux erreurs qui se compensent se cachent
mutuellement*, et ici c'est une différence qui en cachait deux.

`ranking.fallback_rank` existe pour que la **décision** et le **compteur** lisent
la même valeur : recalculer le repli dans le compteur reviendrait à compter
autre chose que ce qui est attribué. Un test le verrouille.

**Le mécanisme typographique n'est PAS refait**, et c'est délibéré : l'audit du
lot 1 a montré qu'il n'est robuste que sur ce PDF-ci, une refabrication
`calibre 7.4.0` depuis un EPUB dont les tailles sont des multiples CSS exacts
d'un `em` de 15 pt. Un PDF composé à la main rendrait 16,94 / 16,96 / 17,02 pour
un seul niveau logique. **Le mesurer suffit ; le refaire est un chantier.** Le
reste du constat d'origine — `_pdf_font_profile` prend toute taille arrondie
supérieure au corps comme un niveau, le niveau 0 mélange couverture, « Revision
History » et titres de chapitre — **reste ouvert et non traité**, au lot 4.

**Ce que le compteur n'a PAS fait, et pourquoi.** Le mandat demandait de le dire
« dans le rapport d'index ». Il n'y est pas : `index_report` lit ChromaDB, et
**aucun `section_header` n'est jamais un chunk** (§4.24) — l'information n'y
existe pas et n'a pas de raison d'y être. Le compteur vit donc là où le dépôt met
déjà `pages_skipped`, `ocr` et `failed_batches` : le journal, en
**avertissement**, et le bilan que `_extract_pdf` retourne, sous
`headings` / `headings_fallback`. C'est un écart au mandat, déclaré.

### 4.23 → traité par le lot 3 — la coupe à 2 000 caractères se journalise

**Le constat, tel qu'il était ouvert.** `graph_text_max_chars = 2000` coupait
sans un mot : aucun journal, aucune métrique. ChromaDB n'est pas touché — le
découpeur repart du document Docling — donc **graphe et vecteurs divergent en
silence** sur ces éléments-là, l'agent lisant un texte tronqué d'un côté et
complet de l'autre.

**Remesuré sur le corpus complet** (`mesuré` le 31 août 2026, 15 173 éléments du
graphe) : **18 éléments font exactement 2 000 caractères** — 14 tables et
4 paragraphes. Le lot 1 en comptait 4, sur 3 documents.

`nebula.write_elements` compte désormais les éléments dont le texte dépasse la
limite et émet un **avertissement**, pas un `info` : c'est une perte de texte,
bornée et voulue, mais une perte. Le message nomme la divergence avec ChromaDB,
qui est ce qui rend la coupe dangereuse.

Le comptage vit dans `ngql.compter_les_textes_coupes`, donc testable sans
graphd. La borne est stricte : un texte qui fait exactement la limite n'est pas
coupé — un test le verrouille, sans quoi le compteur exagérerait d'autant.

**Ce qui reste ouvert** : la divergence elle-même. Ce lot la rend bruyante, il ne
la supprime pas. Réconcilier les deux stores demande soit de couper aussi le
texte envoyé au découpeur — donc de perdre du texte des deux côtés — soit de ne
plus couper le graphe. C'est un arbitrage, pas un correctif.

### 4.22 Six pages du PDF n'ont aucun élément — leur texte est attribué à la page précédente

`mesuré` : les pages **8, 18, 19, 25, 68, 69** sur 71 n'ont **aucun** élément
dans le graphe, alors que PyMuPDF y lit 1 181 à 1 472 caractères. **Le texte
n'est pas perdu** — 72 316 caractères écrits sur 72 326, soit 100,0 % — il est
**attribué à la page précédente** : le début de la page 8 se retrouve dans un
élément de la page 7, celui de la page 18 dans la 17, 25 → 24, 68 et 69 → 67.

Cause : `page_no` vient de la **première** provenance de l'item, et Docling
fusionne un paragraphe qui enjambe une page. Conséquence : toute citation « page
7 » couvre en réalité 7 **et** 8. Run vert, aucun compteur, aucun signal.

### 4.24 → traité par le lot 3 — le plafond est retiré, les deux échelles sont écrites au contrat

**Le constat, tel qu'il était ouvert.** `HeadingStack.place` (`hierarchy.py:91`)
plafonnait la profondeur d'un **titre** à `MAX_DEPTH = 3`, mais **`parent_id`
n'était pas plafonné** : l'arête `PARENT_OF` pointe le vrai parent, donc la
chaîne était plus longue que `depth`. `add_item` donne aux **non-titres**
`depth = profondeur_du_titre + 1`, sans plafond. Résultat dans ChromaDB :
`depth ∈ {1: 92, 2: 238, 3: 345, 4: 98}` — il ne vaut **jamais 0**, et
**`depth = 4` recouvrait les vraies profondeurs 4 ET 5** (`mesuré` par le lot 1
sur 773 chunks).

**Ce qui a été tranché, et pourquoi le plafond ne se défendait pas.** Il ne
bornait aucune structure : `parent_id` n'a jamais été plafonné, donc les arêtes
écrites dans le graphe étaient **les mêmes** avec ou sans lui. Son motif écrit
— « au-delà, un RAG n'y gagne rien : l'objectif est de reconstruire un bloc avec
ses titres parents, pas de reproduire une arborescence complète » — décrivait
une limitation de l'arbre qui n'a jamais existé. **Et il ne tenait pas sa propre
promesse** : un non-titre recevait `profondeur_du_titre + 1` sans plafond, donc
la valeur 4 existait déjà dans ChromaDB alors que le maximum annoncé était 3.
Son seul effet mesurable était de rendre `depth` **non injectif**.

Le plafond est retiré, et `MAX_DEPTH` avec lui. `depth` est désormais le nombre
d'arêtes `PARENT_OF` qui séparent l'élément de la racine de son document.

**Et ce n'était pas un no-op — mesuré avant/après sur le même corpus**, 4 365
chunks réingérés (`mesuré` le 31 août 2026) :

| | distribution de `depth` dans ChromaDB |
|---|---|
| avant, avec le plafond | `{1: 912, 2: 1993, 3: 1164, 4: 296}` |
| après | `{1: 912, 2: 1993, 3: 1164, 4: 256, 5: 40}` |

**40 chunks changent de valeur**, soit 0,9 % : ils valaient 4 et valent 5. Les
296 de la valeur 4 recouvraient bien deux profondeurs réelles. Le total et les
autres valeurs sont inchangés — la correction est exactement aussi étroite
qu'annoncé.

**Les deux échelles subsistent, et elles sont désormais ÉCRITES.** Retirer le
plafond ne les fusionne pas : sur un titre, `depth` compte les titres au-dessus ;
sur tout autre élément, il vaut celui de son titre + 1. Un paragraphe sous un
titre de premier niveau vaut donc 1, comme un sous-titre. **La valeur seule ne
dit pas quelle échelle on lit — c'est `label` qui le dit**, et c'est écrit au
site du contrat, `schemas.py`, sur `ChunkMetadata.depth`.

Aggravant décisif, toujours vrai : **aucun `section_header` n'est jamais un
chunk** — labels ChromaDB mesurés : `text` 502, `code` 157, `list_item` 79,
`table` 25, `caption` 10, **`section_header` 0**. L'agent ne peut donc **jamais**
lire le niveau d'un titre par ChromaDB. C'est la charge utile de §4.11, que le
même lot ferme en écrivant `depth` sur le sommet du graphe.

**Ce que l'agent doit lire : la chaîne `PARENT_OF`, et le `depth` du sommet.**
La chaîne reste le signal exact, et `depth` en donne désormais la longueur sans
avoir à la parcourir.

**Deux jeux de chiffres de cette section étaient ceux du lot 1, repris au
présent.** Ils portaient sur 3 documents et 773 chunks ; l'index en porte 23 et
4 365. Remesurés le 31 août 2026 sur l'index vivant :

| affirmation | ce qu'elle disait | `mesuré` aujourd'hui |
|---|---|---|
| racines de la chaîne `PARENT_OF` | « 3 racines toutes `Document` » | **23**, toutes `Document` |
| labels ChromaDB | `text` 502, `code` 157, `list_item` 79, `table` 25, `caption` 10 | **2604 / 973 / 484 / 196 / 108** |

**La moitié qui porte l'argument tient toujours**, et c'est elle qui compte :
`section_header` vaut **0**. Aucun titre n'est jamais un chunk, donc l'agent ne
peut pas lire un niveau par ChromaDB — c'est la charge utile de §4.11, et elle
est intacte. Les propriétés qualitatives de la chaîne tiennent aussi : 0 double
parent, acyclique, une racine `Document` par document.

### 4.25 Les URL du graphe rendent 403 en GET anonyme

`mesuré` : les 13 URL portées par le graphe existent bien comme objets
(`stat_object` avec un client S3 authentifié — 0 URL morte sur 13), et rendent
**`403` en `GET` anonyme**. La forme stockée est `http://minio:9000/documents/…` :
inutilisable sans identifiants et **hors du réseau Docker**. « 0 URL morte »
dépend donc entièrement de la méthode de lecture. À trancher avec l'agent, qui
« ne sert que ce que le graphe référence ».

### 4.26 → traité par le lot 3 — la pile est remontée depuis le clone principal

**Le constat, tel qu'il était ouvert.** Le lot 1 avait monté la pile depuis son
arbre de travail : les cinq stores étaient des bind mounts de
`.claude/worktrees/lot-1-observation-b12761/Datas/database/`, `src` et `Datas` du
service Docling aussi, et le seul `.env` du poste y vivait. Supprimer cet arbre —
ce que le §7 du mandat prescrit après une fusion — aurait détruit le graphe, les
vecteurs, les objets et le Postgres, sans qu'aucun garde-fou git ne s'y oppose.

**Ce qui a été fait, et pourquoi pas une réingestion.** `docker compose down`
depuis l'arbre du lot 1, copie de `.env` et de `Datas/database/` vers le clone
principal, `docker compose up -d` depuis celui-ci. Déménager plutôt que
réingérer préservait **l'antécédent** : un index produit par le code de `main`,
sur lequel prouver que `verify_contract` était vert alors qu'il n'aurait pas dû
l'être. Le graphe a survécu à l'octet — **2 288 sommets avant, 2 288 après**
(`mesuré`), 773 chunks, mêmes empreintes de fichiers.

État après (`mesuré`, 31 août 2026) : projet compose **`rag-ingestion-pipeline`**,
bind mounts sous le clone principal, `.env` dans le clone principal.
`docker compose ps` depuis le clone principal voit les dix services.
**L'arbre du lot 1 n'ancre plus rien** ; ses données y restent en copie, filet
volontaire, et il peut être supprimé.

**Ce qui n'a PAS pu être déménagé, et ce qu'il en est sorti.**
`Datas/database/postgres` appartient à `root` dans le conteneur : `Permission
denied`. Le Postgres de Dagster est donc reparti **vierge**, les curseurs des
sensors avec lui — et **les sensors étant livrés armés** (§4.18, fermé par le
lot 0b), le simple `docker compose up -d` a déclenché **l'ingestion complète du
corpus**. Ce n'est pas un défaut, c'est le comportement voulu ; c'est un effet à
connaître avant de remonter la pile, et il n'était écrit nulle part.

Il en est sorti un bénéfice inattendu : le lot 3 a mesuré tous ses antécédents
sur le **corpus complet** — 23 documents, 15 196 sommets, 4 365 chunks — et non
sur les 3 documents du lot 1. Plusieurs chiffres du registre s'en trouvent
élargis, et **la projection `calculé` du §3.2 est confirmée à l'unité près** :
elle annonçait 746 titres au total, le graphe en porte **746**.

### 4.27 Pièges de mesure — cinq, le quatrième est du PILOTE et le cinquième est du dépôt

**1. `SHOW STATS` rend 0 sur un space peuplé.** `mesuré` : 0 partout sur
`rag_space`, faute de `SUBMIT JOB STATS`. Un space qui porte 15 196 sommets y
ressemble à un space vide. Les stores s'interrogent par `MATCH`,
`collection.count()` et `list_objects`, jamais par une statistique qu'aucun job
n'a calculée — ni par une taille de dossier (un ChromaDB vide pèse 250 Mo).

**2. Un `WHERE` sur une propriété rend `IndexNotFound` — mais pas sur tous les
tags.** `mesuré` le 31 août 2026 sur `rag_space` :

| requête | résultat |
|---|---|
| `MATCH (v:SectionHeader) RETURN v.SectionHeader.depth` | **OK** |
| `MATCH (v:SectionHeader) WHERE v.SectionHeader.depth == 0 RETURN v` | **`IndexNotFound: No valid index found`** |
| `MATCH (v:Document) WHERE v.Document.source_path == '…' RETURN v` | **OK** |

**La condition exacte est l'absence de TOUT index de tag**, et non la propriété
filtrée : `Document` porte `doc_index` — sur `filename`, pas sur `source_path` —
et l'optimiseur s'en sert pour restreindre puis filtrer. Les 11 tags d'élément
n'ont **aucun** index, donc aucun filtre nGQL n'y passe.

Le lot 3 a évité le piège **en filtrant en Python**, et à l'insu du suivant :
rien ne l'écrivait. `verify_contract._lire_les_profondeurs` le fait aussi, et le
dit à son site. **Le geste : lire la propriété et filtrer côté client**, ou créer
un index de tag — ce qui est une décision de schéma, pas un contournement de
mesure.

**3. Le service Docling exécute le code du CLONE PRINCIPAL, pas celui de ta
branche.** `docker inspect` le montre : `/home/ubuntu/RAG/rag-ingestion-pipeline/src
-> /app/src`. Donc `docker compose exec docling-service python -m src.verify_contract`
mesure le code de `main`, quelle que soit la branche sortie dans ton arbre de
travail. `mesuré` le 31 août 2026 : la même commande rend **`rc=0` « Contrat
respecté »** avec le code de `main` et **`rc=1` avec deux anomalies** avec celui
de la réparation du lot 3 — et un `rc=1` peut tout aussi bien venir d'un
`ImportError` que d'un garde. **Le pilote s'y est fait prendre.**

Le geste, pour mesurer SON code contre l'index vivant :

```bash
docker run --rm --network rag_network \
  -v "$PWD/src":/app/src:ro \
  -v /var/lib/docker/volumes/rag-ingestion-pipeline_docling_models/_data:/tmp/.cache \
  --env-file /home/ubuntu/RAG/rag-ingestion-pipeline/.env \
  -e HOME=/tmp -e PYTHONPATH=/app -w /app \
  rag-ingestion-pipeline-docling-service python -m src.verify_contract
```

**4. `git merge-tree` a DEUX formes, et l'ancienne rend `rc=0` sur un conflit.**
Le piège est du **pilote**, et il est écrit ici parce qu'il appartient à la même
famille que les trois précédents et que le F3 du §8 : *un code de retour lu comme
un verdict alors qu'il répondait à une autre question.*

Le prompt d'audit du lot 6 annonçait « `git merge-tree` : **0 conflit** » entre
`main` et la branche du lot. **C'était faux** : il y a un conflit, dans
`documentation/axes_amelioration.md`. Le pilote avait employé l'**ancienne**
forme, puis grepé les marqueurs de conflit dans sa sortie, lu 0, et conclu.

`mesuré` le 3 septembre 2026, `git` 2.53.0, base `efbbf0a`, `main` `eb140fd`,
branche `499ecb2`, **`rc` lu sans tube** :

| Invocation | `rc` | Ce qu'elle rend |
|---|---|---|
| `git merge-tree <base> <a> <b>` — **ancienne** forme | **0** | 116 713 octets d'un diff de fusion. **`grep -c '<<<<<<< HEAD'` rend 0** — elle écrit `<<<<<<< .our`, pas le marqueur conventionnel. Un `grep` du marqueur habituel ne trouve donc rien |
| `git merge-tree --write-tree --messages <a> <b>` — **bonne** forme | **1** | l'arbre écrit, les trois étages du fichier en conflit, et la ligne `CONFLICT (content): Merge conflict in documentation/axes_amelioration.md` |

**Ce qui distingue les deux, et c'est le fond : l'ancienne forme ne répond pas à
la question « y a-t-il un conflit ».** Elle imprime un diff de fusion, et son
`rc` vaut 0 dès qu'elle a pu s'exécuter — il ne dit rien du résultat. Seule la
forme `--write-tree` porte un `rc` qui **est** un verdict, et elle nomme le
fichier plutôt que de laisser un `grep` le deviner.

**Le geste : `git merge-tree --write-tree --messages`, et lire son `rc`.** Jamais
un `grep` de marqueurs sur l'ancienne — ni ceux de la bonne, dont les messages
sont en clair.

**5. `pytest -q` sur ce dépôt donne `-qq`, qui SUPPRIME la ligne `N passed` en
laissant `rc=0`.** Même famille que les quatre précédents et que le F3 du §8 :
*une sortie lue comme un verdict alors qu'elle répondait à une autre question* —
ici, l'absence de compte lue comme l'absence de mesure à faire.

`pyproject.toml` porte déjà `addopts = "-q --tb=short"`. Un `-q` ajouté en ligne
de commande s'y **additionne**, et `-qq` retire la ligne de résumé.

`mesuré` le 22 septembre 2026, `pytest` 9.1.1, sur `tests/unit/test_wipe_stores.py`,
**`rc` lu sans tube** :

| Invocation | `rc` | Dernière ligne de sortie |
|---|---|---|
| `uv run pytest tests/unit/test_wipe_stores.py` | 0 | `50 passed in 3.95s` |
| `uv run pytest -q tests/unit/test_wipe_stores.py` | **0** | les points de progression, **et rien d'autre** — la sortie entière tient en **une** ligne |

**La borne est étroite, et c'est elle qui rend le piège vicieux** : `mesuré` sur
un couple vert + rouge, `-qq` imprime toujours `1 failed, 1 passed`, le
`FAILURES` et le `short test summary info`. **Le compte ne disparaît que quand
tout passe.** Un balayage de graines entièrement vert est donc exactement le cas
où l'on n'a plus rien à lire, et un balayage rouge ne prévient pas du piège. Un
vérificateur de ce chantier a produit **cinq** mesures de graines « vertes » sans
aucun compte de tests avant de s'en apercevoir.

**Le geste : ne jamais ajouter `-q`.** `addopts` le porte déjà, et la cible
`make test` ne l'ajoute pas non plus. Un compte de tests qui manque n'est pas un
détail de présentation : c'est ce qui distingue « 925 verts » de « 900 verts ».
Un fichier de tests qui cesse d'être **collecté** — renommé hors de `test_*.py`,
déplacé hors de `testpaths` — retire ses tests **sans un seul rouge** et sans
changer le `rc`. *(Le cas « zéro test collecté », lui, se voit : `pytest` rend
alors **5**, `mesuré`. C'est la réduction PARTIELLE et silencieuse qui est
dangereuse, pas la disparition totale.)*

### 4.28 → CONSIGNÉ par la réparation du lot 3, NON traité — pour le lot 4

Cinq constats trouvés en réparant, et laissés hors du diff. Périmètre strict.

#### 4.28.a `chunk_count` est mensonger — deux éléments perdent un morceau

`anchoring.resolve_anchors` fixe `chunk_count` **avant** que
`vectors.build_chunks:186` ne jette les chunks échouant `has_content` ou plus
courts que `min_chunk_chars`. Le compte annoncé est celui d'**avant** le filtrage.

`mesuré` le 31 août 2026 sur l'index vivant, 4 365 chunks et 3 750 éléments :

```
element_id=aa3de10738  chunk_count=7  présents=[0,1,2,3,5,6]  MANQUE 4
element_id=eb52c4ec8f  chunk_count=4  présents=[0,1,2]        MANQUE 3
```

**Un morceau de texte disparaît de la reconstitution sans aucune erreur.** L'agent
concatène ce qu'il trouve et rend un texte troué. **Le CONTRÔLE est livré**
(§4.4, `jeux_de_chunks_incomplets`) : la panne est désormais bruyante. **La CAUSE
va au lot 4** — il faut décider si `chunk_count` se recalcule après filtrage, ou
si les chunks filtrés doivent cesser de l'être.

#### 4.28.b Les 199 images HTML sont absentes de MinIO — le bucket porte 13 objets

`mesuré` : `list_objects` sur `documents` rend **13** objets, et ce sont **tous**
des crops du PDF (chaîne `images.py`, qui fonctionne). Les 199 images des
captures HTML n'y sont **pas** — ni téléversées, ni référencées.

Deux conséquences que §3.5 ne dit pas encore : `Datas/.cleaned/` référence encore
les URL `http://minio:9000/…` dans son HTML nettoyé, donc le HTML pointe des
objets inexistants ; et **`wipe_stores` ne purge pas `Datas/.cleaned/`**, donc une
purge suivie d'une réingestion repart du HTML nettoyé périmé. Seule une exécution
Dagster de l'asset `cleaned_html` les restaurerait.

**Le lot 4 doit lire ceci AVANT d'attaquer §3.5** : le constat §3.5 décrit 199
images sans `minio_url` dans le graphe ; il faut savoir en plus qu'elles ne sont
pas non plus dans le bucket.

#### 4.28.c `dagster-daemon` est arrêté, et l'exigence 5 n'est pas éprouvable ici

> **Renvoi.** Ce constat est **fermé** — voir §4.42, qui le dit avec ses
> mesures. Les **67 `ReindexError`** relevés ci-dessous sont un instantané pris
> au milieu de la **fenêtre 2** des 886 échecs, caractérisés au **§4.43.a** :
> même cause, même job, et rien depuis le 3 septembre 2026. Et l'exigence 5 a
> été exercée **une seconde fois** derrière SeaweedFS, à la
> [campagne du 25 septembre](campagnes/2026-09-25-bascule-seaweedfs.md) — le run
> `agent_reindex_job` est parti seul et a rendu `ok — 4367 chunks indexes`.

`mesuré` : le daemon est arrêté — le lot 3 l'a arrêté pour que les sensors ne
réingèrent pas par-dessus ses mesures (§7.2 du mandat) — un run est `QUEUED`
depuis deux heures, et l'historique porte **67 `ReindexError`**.

C'est le **§4.15 en vrai** : un run bloqué gèle la réindexation indéfiniment,
sans délai de garde ni alerte. Et la conséquence pratique : **l'exigence 5 du
contrat — `POST /reindex` en fin de pipeline — n'est pas éprouvable sur ce poste
en l'état.** Lot 4, avec la famille §4.15 à §4.17.

#### 4.28.d `document_vid` : le piège est fermé au nom, pas au garde

`ngql.document_vid` reçoit `identity.key` de ses trois appelants, et le graphe est
juste — les 23 sommets `Document` ont 23 identifiants distincts, dont
`doc_htms/MLOps with Databricks/Preface` et
`doc_htms/Practical MLflow …/Preface` (`mesuré`). Mais son paramètre s'appelait
`filename` et son docstring disait « Nom du document, sans extension » : une
**invitation** à passer `identity.filename`, ce qui ferait collisionner les deux
`Preface.html` sur un seul sommet — perte silencieuse d'un document entier, et
violation directe de l'exigence 3.

Le paramètre est renommé `cle_du_document` et le docstring dit ce qu'il attend.
**Mais l'appelant n'est gardé par aucun test** : `mesuré`, remplacer
`document_vid(identity.key)` par `document_vid(identity.filename)`
(`nebula.py:154`) laisse la suite **entièrement verte**.

La raison est **mécanique et connue** : `nebula.py` importe `nebula3` au niveau du
module, donc aucun test ne peut l'importer côté hôte. **C'est le cinquième module
dans ce cas**, après `index_report` (§3.4), `verify_contract` (§4.4),
`verify_data` (§4.5) et `vectors` (§4.4). Les quatre premiers sont fermés ;
`nebula.py` est le plus gros, et le déverrouiller dépasse le périmètre de cette
réparation. **À faire au lot où `nebula.py` est touché** — et il l'est au lot 4.

#### 4.28.e Le lot 6 est entamé sans avoir été décidé

L'ingestion **complète** a eu lieu, `verify_contract` et `index_report` ont tourné
sur le corpus complet : les trois premières étapes du lot 6 sont faites. Restent
les 30 questions, et **l'ordre reste forcé** — les `element_id` sont créés par
l'ingestion.

**Le fait qui doit décider, et il est mesuré** : `compute_id` dérive de
`(identity.key, page_no, position_in_page, text[:50])`. Or §4.22 (six pages du PDF
sans élément, leur texte attribué à la page précédente) et §4.6 / §4.7 (le
nettoyage) sont **tous au lot 4**, et **tous peuvent déplacer `page_no` et
`text`** — donc les `element_id`, donc **tuer un jeu de questions écrit avant
eux**. Écrire les 30 questions avant le lot 4 est un travail à refaire.

#### RETOURNÉ par le lot 4 — les `element_id` NE BOUGENT PAS, et l'ordre tient quand même

**Mesuré, et reproduit trois fois indépendamment** (le lot 4, son audit
indépendant, et le pilote statiquement) : les ensembles d'`element_id` sont
**rigoureusement égaux** entre `main` et la pointe du lot 4 — **15 173** de
chaque côté, différence symétrique **nulle** —, et les **3 750** identifiants de
l'index vivant sont un sous-ensemble strict des deux.

**La cause est mécanique, et elle se lit dans le code sans rien exécuter.**
`compute_id` dérive de `(identity.key, page_no, position_in_page, text[:50])`.
Sur `main`, `page_no` valait `int(prov.page_no)` où `prov = prov[0]`
(`elements.py:256-257` de `main`) ; sur la pointe, il vaut `pages[0]` rendu par
`item_page_span` (`elements.py:215`, `:328`). **C'est la même valeur par
construction** : `page_no_end` est une propriété AJOUTÉE, `page_no` n'a pas
changé de définition. Le §4.22 ne déplace donc rien — il rend LISIBLE ce qui
était déjà écrit.

**Le raisonnement qui rangeait §4.22 parmi les causes de rupture était juste sur
son mécanisme et faux sur son antécédent.** Il supposait que « corriger
l'attribution des pages » changerait `page_no`. La correction retenue ne le
change pas : elle ajoute une page de FIN. *Un raisonnement juste sur un
antécédent faux se relit comme une preuve* — la leçon du §3.2, appliquée au
plan que ce registre écrit lui-même.

**MAIS L'ORDRE DU PLAN RESTE FORCÉ, POUR DEUX AUTRES RAISONS.** C'est la moitié
qui tient, et c'est elle qu'il faut lire :

1. **le jeu de CHUNKS change.** Le lot 4 cesse de filtrer les chunks qui ont des
   frères (§4.28.a) : deux éléments retrouvent le morceau qu'ils perdaient, donc
   **4 365 → 4 367** *(chiffre du lot 4, non remesuré ici : il décrit un index
   qui n'existe pas encore, et il ne se vérifiera qu'à la réingestion. L'index
   vivant en porte bien **4 365**, `mesuré` le 1er septembre 2026)*. Un jeu de
   questions désigne des `element_id`, mais un rappel se calcule sur des chunks :
   deux chunks de plus déplacent le dénominateur ;
2. **`page_no_end` demande une réingestion pour être peuplé.** Le schéma migre en
   place, les **données** non. `mesuré` le 1er septembre 2026,
   `DESCRIBE TAG Paragraph` rendait `label, page_no, text, minio_url, depth` : la
   colonne n'existait pas. **`mesuré` le 2 septembre 2026, après un redémarrage de
   `docling-service` : elle existe, sur les tags d'élément, et 7 251 sommets
   `Paragraph` sur 7 251 sont à `NULL`** (§4.29.e). La conclusion ne bouge pas —
   un jeu de questions écrit contre l'index actuel ne peut pas exercer le cadrage
   « page N à M » — mais **son antécédent a changé**, et le second état est celui
   qui vaut aujourd'hui.

**Ce qui est retourné, et ce qui tient — les deux moitiés, côte à côte :**

| Affirmation | État |
|---|---|
| « les `element_id` bougeront » (§4.28.e, mandat §6 et §7) | **FAUX** — 15 173 = 15 173, différence symétrique nulle |
| « §4.22 déplace `page_no` » | **FAUX** — `prov[0].page_no` et `pages[0]` sont la même valeur |
| « §4.6 / §4.7 déplacent `text` » | **non mesuré ici**, et sans objet pour la conclusion : le point 1 suffit |
| « le lot 6 attend le lot 4 » | **VRAI**, pour le jeu de chunks et pour `page_no_end` |
| « écrire les 30 questions avant est un travail à refaire » | **VRAI**, et pour une raison qui n'est plus celle-là |

**À RETOURNER SUR `main` APRÈS FUSION, par le pilote** : ce §4.28.e et le §6 du
mandat, qui portent tous deux « les `element_id` bougeront » comme motif de
l'ordre. Le motif change, la conclusion ne change pas. La part du lot 4 est
d'écrire la mesure ici pour que le pilote l'ait sous les yeux ; il n'appartient
pas à une branche de réécrire le plan.

*(Et la leçon de forme, parce qu'elle vaut plus que le fait : la conclusion
« le lot 6 attend le lot 4 » était juste, elle a été soutenue pendant deux lots
par un antécédent faux, et personne ne l'a vu parce que la conclusion, elle,
était vérifiable. **Une conclusion juste ne valide pas sa prémisse.**)*

**RETOURNÉ le 2 septembre 2026 : le fait ci-dessus est FAUX, et la conclusion tient
quand même.** C'est le seul épisode du chantier où une conclusion a survécu à
l'effondrement de son motif, et il vaut d'être lu en entier.

Le motif était un **raisonnement sur le code, jamais mesuré** : puisque `compute_id`
dérive de `page_no` et de `text`, et puisque §4.22, §4.6 et §4.7 les touchent, les
`element_id` bougeraient. Mesuré trois fois — par le lot 4, reproduit
indépendamment par son audit, confirmé **statiquement** par le pilote — les
ensembles d'`element_id` sont **rigoureusement égaux** de part et d'autre du lot 4 :
15 173 des deux côtés, différence symétrique nulle, et les 3 750 identifiants de
l'index vivant sont un sous-ensemble strict des deux. La cause se lit dans le code :
`page_no_end` est **additif**, et `pages[0]` vaut exactement ce que valait
`prov[0].page_no`.

**L'ordre reste forcé, pour deux raisons neuves et mesurées** : le jeu de *chunks*
change (4 365 → 4 367, §4.28.a) et **`page_no_end` n'est peuplé sur aucun sommet**
— la colonne existe depuis le redémarrage du 2 septembre 2026, et les 7 251
`Paragraph` sont à `NULL` (§4.29.e), donc une réingestion reste requise ; elle
reste précédée d'un redémarrage de `docling-service`, qui est sans coût quand le
schéma est déjà à jour. Les 30
questions attendent donc toujours, mais pas pour la raison écrite ici.

**Ce que le chantier doit en retenir** : ce paragraphe portait un raisonnement
plausible et non mesuré, sans étiquette `supposé`, et il a servi de fondement à une
décision de plan. Il a fallu trois mesures indépendantes pour le renverser.
**Étiquette `supposé` tout ce qui n'a pas été mesuré, même quand ta conclusion te
paraît sûre** — c'est cette étiquette qui a économisé le lot 2 au §6, et son absence
ici a failli coûter un lot entier de travail à refaire.

*(Décision d'origine, conservée parce qu'elle dit comment on s'est trompé :)* le
fait ci-dessus décide seul, et il n'y avait rien à arbitrer au-delà de lui.
Deux points à garder, parce qu'ils ne se déduisent pas du fait :

1. **ce qui est acquis l'est vraiment.** Le corpus complet est indexé et les deux
   instruments ont rendu leur verdict dessus — c'est l'antécédent mesuré du lot 4,
   et il n'aurait pas été gratuit à produire. L'accident a rendu service ;
2. **le piège est d'écrire les questions *quand même*, pour avancer.** Elles
   paraîtraient bonnes jusqu'à la réingestion — un jeu de questions ne rougit pas,
   il devient faux en silence. C'est le motif de tout ce chantier, appliqué à son
   propre plan.

### 4.29 → CONSIGNÉ par la réparation du lot 4, NON traité

Neuf constats trouvés en réparant, laissés hors du diff. **Périmètre strict**, et
chacun porte la **forme du garde à écrire** — sans quoi un constat n'est qu'une
observation qui vieillit.

Deux d'entre eux **corrigent un chiffre du mandat de cette réparation**, remesuré
plutôt que recopié : le b et le f. C'est le principe du chantier, et il vaut
aussi pour les chiffres que le chantier vient d'écrire.

#### 4.29.a → traité par le lot 5 — `CLEANED_SUBDIR` n'est plus un réglage, et son TROISIÈME dégât n'avait pas été mesuré

Le bloquant B1 est fermé : `purge_cleaned` refuse toute cible qui n'est pas
**strictement contenue** dans `source_dir` après résolution (`wipe_stores.py`).
Cela ferme les quatre valeurs de `CLEANED_SUBDIR` qui font viser la racine ou
au-dessus — `""`, `"."`, `".."`, un chemin absolu.

**Cela ne ferme pas une cible bien contenue et fausse.** `mesuré` le
1er septembre 2026, sur un faux corpus jetable : `CLEANED_SUBDIR=htms` est
strictement contenu dans la racine, passe le garde, et `rmtree` détruit
`Datas/htms/` — **24 des 25 fichiers du corpus versionné**. Le test correspondant
rougissait sur le code livré, et il a été retiré du juge : la décision du pilote
est le containment, et l'étendre de ma main aurait été rediscuter une décision
prise, non la tenir.

**La forme du garde à écrire**, si le pilote veut fermer ce reste : `purge_cleaned`
n'accepte qu'un chemin dont **chaque composant relatif** est celui que l'asset
`cleaned_html` écrit — c'est-à-dire une comparaison à `PipelineSettings`
`cleaned_subdir` **par défaut**, et un refus de toute autre valeur. Le test existe
déjà en négatif : remettre le cas `("htms", …)` dans la paramétrisation de
`TestUneCibleHorsDeLaRacineEstREFUSEE`, plus un témoin sur la valeur par défaut.

**Et la question qui décide n'est pas technique** : `CLEANED_SUBDIR` doit-il
rester un réglage ? Un réglage annoncé dont trois valeurs sur quatre détruisent le
corpus est un réglage qui coûte plus qu'il ne rend.

**TRANCHÉ par le pilote le 2 septembre 2026 : non. `CLEANED_SUBDIR` cesse d'être un
réglage, et le geste va au lot 5, en PREMIER point.** Personne ne configure où
l'étape de nettoyage écrit — c'est un détail d'implémentation — et une configuration
que rien ne configure est de la configuration morte, ce qui est le périmètre de ce
lot au mot près. Le sous-répertoire devient une constante ; **le containment livré
par le lot 4 reste**, parce qu'il protège en plus contre un `source_dir` mal réglé,
qui demeure un réglage légitime.

**Et ce constat n'a PAS bloqué la fusion du lot 4, délibérément.** Le pilote a
remesuré le reste de lui-même, sur un faux corpus jetable : `CLEANED_SUBDIR=htms`
détruit le corpus, `=database` détruit les stores. Il ne bloque pas pour deux
raisons, et elles sont dites pour que personne ne les redécouvre comme une
négligence : le corpus est **versionné** depuis `a005172`, donc récupérable par un
`git restore` — c'est précisément ce que le versionnement a acheté (§2.2) — et
`Datas/database/` est ce que `wipe_stores` **existe** pour effacer. Le pire cas est
un geste de récupération connu, pas une perte. Le chantier décide l'ordre au coût de
l'attente, pas à la sévérité (§6).

**Le réparateur a eu raison de consigner plutôt que d'étendre la décision de sa
main**, et c'est à son crédit : son test rougissait déjà sur le code livré, il l'a
retiré du juge et l'a écrit ici. Un développeur qui élargit un périmètre tranché
« parce que c'est mieux » retire au pilote la décision qu'il a prise.

#### 4.29.b → traité par le lot 5 — les deux classes de réglages sont gardées d'accord

L'objet est téléversé dans `PipelineSettings.minio_bucket` /
`.minio_endpoint` (`media.py:50`, `:64`) ; l'URL publiée est construite par
`images.object_url`, qui lit `DoclingSettings` (`images.py:117-118`). **Deux
classes de réglages décident du même objet.**

Les deux lisent les mêmes variables d'environnement et portent les **mêmes
défauts** — `minio:9000` et `documents` de chaque côté (`settings.py:18`, `:21`
et `settings.py:25`, `:28`) —, donc **aucune conséquence aujourd'hui**. Mais rien
ne garde leur accord : `mesuré` le 1er septembre 2026 **sur le code livré par
cette réparation**, porter `PipelineSettings.minio_bucket` à une autre valeur
laisse la suite **entièrement verte, 857 tests**.

Une image téléversée dans un bucket et publiée sous un autre est **un objet qui
existe et une URL qui 404** — le §4.28.b refait, dans le geste qui vient de le
fermer.

**La forme du garde à écrire** : une assertion d'égalité entre les deux réglages,
dans un test qui importe les deux classes. Deux lignes. Son témoin : la faire
porter sur les deux couples (`minio_endpoint` **et** `minio_bucket`), sans quoi
la moitié non assertée redeviendrait libre de dériver.

#### 4.29.c → traité par le lot 5 — la correspondance colonne → type est gardée, `CREATE` **et** `ALTER`

L'invariant est écrit au site — « les deux tuples sont lus ensemble par
`tag_schema_statements` : les désaligner produit un `CREATE TAG` qui n'a pas les
colonnes que les `INSERT` écrivent » (`ngql.py:275-278`). Le lot 4 porte les deux
tuples de **5 à 6** entrées, `page_no_end` étant ajoutée.

**Le mandat de cette réparation annonçait « les désaligner laisse 825 tests
verts ». Remesuré sur le code livré, c'est vrai d'une moitié et faux de l'autre**
(`mesuré` le 1er septembre 2026, mutation appliquée puis révoquée, texte vérifié
changé) :

| Mutation | Suite entière |
|---|---|
| un type **retiré** — longueur 5 contre 6 | **ROUGE**, `rc=1`, **5** tests de `TestTagSchemaStatements` |
| le type de `page_no_end` passé à `string` — longueurs égales, correspondance fausse | **VERT**, **857** tests |

La **longueur** est donc gardée, et pas par un test : par le `strict=True` des
deux `zip` (`ngql.py:208`, `:218`), qui lève. C'est un garde réel, et il est au
site. Ce qui n'est gardé par rien est la **correspondance colonne → type**, celle
qui décide qu'un `page_no_end` est un `int`.

Antérieur au lot, échec **bruyant** — le graphd rejette chaque `INSERT` —, d'où
la sévérité basse. Mais un `int` déclaré `string` ne rejette pas forcément : il
accepte et stocke la mauvaise forme.

**La forme du garde à écrire** : un test qui asserte le couple attendu pour chaque
colonne, `{"page_no": "int", "page_no_end": "int", "depth": "int", "label":
"string", …}`, contre le `CREATE TAG` rendu par `tag_schema_statements`. Son
témoin : que le test rougisse aussi sur une **permutation** des types, pas
seulement sur un type changé — sans quoi il serait vert sur deux colonnes de même
type échangées.

#### 4.29.d → CONSIGNÉ par le lot 5, NON traité — le motif est au bas de ce constat

Le lot 4 a exposé `NEBULA_USER` / `NEBULA_PASSWORD` en réglages et corrigé les
**quatre** sites qui codaient `("root", "nebula")` en dur (§4.3, qui en annonçait
trois). **Le lot a ensuite consigné que « deux modules » restaient sans garde.
C'est faux : il en reste UN.**

`mesuré` de mes mains le 1er septembre 2026, mutation
`get_session(settings.nebula_user, settings.nebula_password)` →
`get_session("root", "nebula")` appliquée site par site, texte vérifié changé,
suite entière relancée :

| Site | Suite entière sous mutation |
|---|---|
| `src/verify_contract.py:438` | **VERTE** — aucun garde |
| `src/verify_data.py:94` | ROUGE — `test_verify_data.py::…::test_le_env_decide_des_identifiants` |
| `src/init_nebula.py:41` | ROUGE — `test_init_nebula.py::…::test_l_adresse_et_les_identifiants_viennent_du_env` |
| `src/docling_service/nebula.py:143` | ROUGE — `test_nebula.py::…::test_la_session_recoit_les_identifiants_des_reglages` |

`init_nebula.py` a gagné son garde au commit suivant celui qui a écrit « deux
modules » : le constat a péri dans le lot qui l'a posé. **Remesuré ici plutôt que
repris de l'audit**, qui annonçait le même chiffre.

**La forme du garde à écrire** : celui de `verify_data`, transposé — un bouchon
`nebula3` qui **imprime** les identifiants qu'il reçoit, et
`python -m src.verify_contract` lancé pour de bon en sous-processus. Son témoin,
et il n'est pas optionnel : le test doit **retirer** les deux variables de
l'environnement hérité avant de poser les siennes, sans quoi un poste qui les
déclare rendrait le témoin vert ou rouge selon la machine.

*(Le harnais du bloquant B2.d bouchonne désormais `nebula3` pour
`_verifier_le_graphe`, mais par `monkeypatch.setitem` et non en sous-processus :
il n'observe pas ce que `pool.get_session` reçoit. Il rapproche le geste, il ne le
fait pas.)*

**POURQUOI LE LOT 5 NE L'A PAS TRAITÉ, et le motif n'est pas le périmètre.** Le
garde à écrire est un sous-processus qui bouchonne `nebula3` et **imprime** les
identifiants reçus — le patron de `test_verify_data.py`, transposé. Le lot 5 a
écrit trois gardes de cette famille (§4.29.b, §4.29.c, §4.29.e) et celui-ci
aurait été le quatrième : il est faisable, et il n'est pas fait.

La raison est que **ce lot a déjà touché `verify_contract.py` en profondeur**
pour §4.29.e — une fonction pure neuve, un `DESCRIBE TAG` ajouté au chemin de
lecture, et le harnais de session du lot 4 étendu pour y répondre. Ajouter dans
le même souffle un second harnais, en sous-processus celui-là, sur le même
module, aurait mêlé deux montages de test différents dans un diff que personne
ne relirait pour les deux. La sévérité le permet : l'échec est **bruyant** — un
graphd qui refuse les identifiants ne laisse rien passer en silence.

**Le geste reste écrit, il est petit, et il n'a pas bougé.** Son témoin non
optionnel est rappelé ici : le test doit **retirer** `NEBULA_USER` et
`NEBULA_PASSWORD` de l'environnement hérité avant de poser les siens, sans quoi
un poste qui les déclare rendrait le témoin vert ou rouge selon la machine.

#### 4.29.e → traité par le lot 5 — les deux états ne se confondent plus, et l'ordre des branches est le sujet

`verify_contract.py:486-491` dit, quand des sommets n'ont pas de `page_no_end` :

> « le tag a migré, les données non — il faut une réingestion pour peupler la
> colonne »

**Dans le cas mesuré, le tag n'a PAS migré : la colonne n'existe pas.** `mesuré`
le 1er septembre 2026 sur le space vivant, `DESCRIBE TAG Paragraph` et
`SectionHeader` rendent `label, page_no, text, minio_url, depth` — cinq colonnes,
sans `page_no_end`. Le message décrit donc un état qui n'est pas celui du poste,
et il prescrit le geste qui ne suffit pas.

> **CE FAIT A PÉRIMÉ LE 2 SEPTEMBRE 2026, ET IL FAUT LE LIRE COMME UN ÉTAT DE
> POSTE.** `docling-service` a été redémarré, `init_schema()` a joué, et
> `DESCRIBE TAG Paragraph` comme `DESCRIBE TAG SectionHeader` rendent désormais
> **six** colonnes — `label, page_no, text, minio_url, depth, page_no_end` —
> tandis que **7 251 sommets `Paragraph` sur 7 251 portent `NULL`** (`mesuré`,
> lecture directe depuis le conteneur d'extraction). Le poste est donc passé du
> **premier** état au **second** : le schéma a migré, les données non.
>
> **Ce n'est pas le monde qui a menti, c'est une phrase non datée qui a vieilli.**
> C'est la même famille que les quatre bloquants de la réparation, produite cette
> fois par le monde et non par une main : *un état de poste n'est vrai qu'à une
> date, et la seule défense est l'étiquette et la date.* Les deux mesures sont
> conservées côte à côte, chacune datée, plutôt qu'une seule réécrite — c'est ce
> qui rend le mouvement lisible.
>
> **Ce que cela ne change PAS** : la forme du garde à écrire ci-dessous, ni la
> consigne « redémarrer puis réingérer ». Le contrôle doit toujours distinguer les
> deux états, et le poste vient de prouver que **les deux existent vraiment**.

**Et `init_schema()` n'est joué qu'au DÉMARRAGE du service** (`main.py:72`, dans
le `lifespan`). La consigne complète est donc **« redémarrer `docling-service`,
PUIS réingérer »**. Un opérateur qui suit la phrase telle quelle réingère contre
un tag sans la colonne, et le graphd rejette chaque `INSERT`.

La consigne est écrite au `README.md`, section « Ré-ingérer proprement », là où un
opérateur la trouve. **Le message d'anomalie, lui, n'est pas corrigé** — il est
dans le module que ce lot livre, et le corriger demande de distinguer deux états
que le contrôle actuel confond.

**La forme du garde à écrire** : le contrôle doit lire `DESCRIBE TAG` **avant** de
compter les NULL, et rendre deux anomalies distinctes — « la colonne n'existe pas,
redémarrer le service » et « la colonne existe, les données sont à NULL,
réingérer ». Le mécanisme existe déjà : `_verifier_le_tag_document` fait
exactement ce `DESCRIBE` pour le tag `Document`, et `ngql.colonnes_manquantes`
rend les colonnes absentes d'un tag réel. Son témoin : les deux états doivent
rendre des messages différents, sans quoi la distinction serait faite dans le code
et perdue dans la sortie.

#### 4.29.f → CONSIGNÉ par le lot 5, NON traité — le motif est au bas de ce constat

`vectors.py:229-230` : `autonome = ancre.count == 1`, puis
`if autonome and (not has_content(texte) or len(texte) < settings.min_chunk_chars)`.
**Dès que `ancre.count > 1`, le filtre ne s'applique plus** — c'est la borne
volontaire du §4.28.a, et elle est argumentée à son site. Un chunk vide ou
purement typographique qui a des frères entre donc dans l'index vectoriel.

**Zéro occurrence sur ce corpus** : les 4 365 chunks de l'index vivant portent
tous du texte.

**Le mandat de cette réparation annonçait « le vecteur d'une chaîne vide a une
norme SUPÉRIEURE à celle des textes réels (4,07 contre ~2,9–3,0) : un voisin
plausible pour n'importe quelle requête ». Remesuré, la première moitié est
inexacte et la seconde n'est pas établie.**

`mesuré` le 1er septembre 2026, dans l'image d'extraction, sur la **totalité** des
4 365 vecteurs de la collection :

| | norme L2 |
|---|---|
| chaîne vide | **4,073** |
| une espace | 4,073 |
| chunks réels — minimum | **2,630** |
| chunks réels — médiane | **3,427** |
| chunks réels — maximum | **5,498** |
| chunks réels dont la norme **dépasse** 4,073 | **181 sur 4 365 (4,1 %)** |

La chaîne vide se place donc au **95,9ᵉ centile** des normes réelles, et non
au-dessus de toutes. Le « ~2,9–3,0 » décrivait un échantillon, pas le corpus.

**Et la conséquence dépend de la distance, que la collection ne déclare pas.**
`mesuré` : les métadonnées de la collection `rag_documents` portent
`{'embedding_model': 'paraphrase-multilingual-MiniLM-L12-v2'}` et **aucun
`hnsw:space`** ; le défaut de ChromaDB est `l2`
(`HnswParams.__init__`, `metadata.get("hnsw:space", "l2")`). **Sous une distance
L2, une norme élevée éloigne d'une requête, elle n'en rapproche pas** : le
raisonnement « voisin plausible pour n'importe quelle requête » vaudrait sous un
produit scalaire, pas ici.

**Ce qui reste, et c'est réel** : le mécanisme est ouvert, et sa conséquence est
inconnue plutôt que grave. Borne connue, à surveiller si le corpus change.

**La forme du garde à écrire** — et c'est un garde de **serrage**, pas un garde
« ça marche » : un test qui pose un chunk vide **avec des frères** et exige qu'il
n'entre pas dans l'index, plus son témoin — le morceau court du **milieu**, lui,
doit être conservé, sinon le garde rouvrirait le §4.28.a. La distinction à écrire
est « vide ou sans caractère alphanumérique » contre « court », et non
« autonome » contre « avec frères » : c'est la longueur qui justifiait la borne,
pas la vacuité.

**Et une décision préalable, qui n'est pas à moi** : déclarer `hnsw:space`
explicitement sur la collection. Le laisser au défaut fait dépendre le
comportement de recherche d'une valeur que personne n'a écrite — la famille des
`CHUNK_SIZE=900` du §5.1, dans l'autre sens.

**POURQUOI LE LOT 5 NE L'A PAS TRAITÉ.** Deux raisons, et la première suffit.

1. **Le garde demandé est un garde de SERRAGE sur un comportement à décider.**
   Le constat le dit lui-même : la distinction à écrire est « vide ou sans
   caractère alphanumérique » contre « court », et non « autonome » contre « avec
   frères ». C'est un **changement du filtre d'indexation**, donc du jeu de
   chunks écrit — exactement ce que le §6 du mandat interdit de bouger avant la
   campagne de référence, puisque le rappel se calcule sur des chunks. Le
   périmètre du lot 5 est le code mort et l'écart documentation/code ; celui-ci
   est un correctif de comportement.
2. **Sa conséquence est inconnue plutôt que grave, et c'est mesuré** — zéro
   occurrence sur les 4 365 chunks de l'index, et la chaîne vide se place au
   95,9ᵉ centile des normes réelles sous une distance L2 qui l'**éloigne** des
   requêtes.

**Ce que le lot 5 laisse au lot suivant** : la décision `hnsw:space` doit être
prise **avant** ce garde, parce qu'elle décide si une norme élevée rapproche ou
éloigne — donc si le mécanisme est un défaut ou une curiosité. Les deux dans le
même geste, ou aucun.

#### 4.29.g → traité par le lot 5 — le test lit le launcher EFFECTIF, hors ligne

`tests/unit/test_dagster_yaml.py:123`. Sa première assertion est
`"DefaultRunLauncher" in texte`, sur le contenu brut de `dagster.yaml`. `mesuré`
le 1er septembre 2026 : la chaîne apparaît sur **trois** lignes du fichier, et
**les trois sont des commentaires** — `grep -v '^\s*#' dagster.yaml | grep -c
DefaultRunLauncher` rend **0**.

Le test ne trouve donc **que du commentaire**, dans un fichier dont le docstring
affirme « **Ce fichier n'est pas un test de texte**, et la distinction compte ».
Le docstring a raison sur le reste du fichier — la configuration est validée par
le processeur de configuration de Dagster lui-même, et ses seuils sont comparés
aux réglages réels du pipeline — et faux sur cette assertion-là.

**Sa seconde assertion est, elle, substantielle** : `"run_launcher:" not in texte`
détecte l'apparition d'un bloc `run_launcher` explicite, c'est-à-dire exactement
l'événement qui rendrait `max_resume_run_attempts: 0` mauvais. Elle porte le
raisonnement ; la première ne porte rien.

**La forme du garde à écrire** : lire le launcher **effectif** plutôt que le
texte. `DagsterInstance.from_config` sur le `dagster.yaml` livré expose
`instance.run_launcher`, et l'assertion devient
`isinstance(instance.run_launcher, DefaultRunLauncher)`. C'est le même geste que
celui déjà employé deux tests plus haut pour `max_runtime_seconds` — comparer une
valeur du fichier à un réglage réel — appliqué au dernier endroit du fichier qui
lit encore une chaîne.

#### 4.29.h → VÉRIFIÉ par le lot 5, non traité — divergence permanente et assumée

`src/docling_service/main.py` n'a **AUCUNE ligne modifiée** dans le diff du lot 4
(`mesuré` : `git diff main..HEAD -- src/docling_service/main.py` rend le vide). Il
est atteint par un bouchon `fastapi` posé comme un vrai paquet en tête de
`PYTHONPATH`. Je l'avais déclaré « déverrouillé » au même rang que `nebula.py` et
`extraction.py`, dont les imports sont réellement différés. **Un module atteint
par un bouchon n'est pas un module importable.**

Corrigé au `README.md` avec le bloquant B6, dans le même geste que la phrase
d'exhaustivité qu'il soutenait — les deux vivaient dans le même paragraphe, et la
seconde était la conséquence de la première.

**Non corrigé, et c'est une divergence permanente et assumée** : le message de
commit de `2f6d8eb` porte « **`main.py` etait le SEPTIEME module inimportable cote
hote** » puis « Plus aucun module du depot n'est inimportable cote hote ». La règle
du chantier interdit de réécrire un commit dont la porte a été prouvée verte pour
un gain documentaire — c'est le précédent du §5.8, et il vaut ici. La divergence
est écrite pour que personne ne la redécouvre comme un défaut.

**Il n'y a pas de garde à écrire pour celui-ci**, et c'est le point : un écart se
déclare à sa taille exacte **au moment où on le prend**, et aucun test ne le fera
à la place de qui le prend. Ce qui est gardé désormais est la conséquence, pas la
déclaration — `tests/unit/test_importabilite_cote_hote.py` rougirait si `main.py`
devenait importable, en exigeant qu'on retire l'exception plutôt que la garder.

#### 4.29.i → CONSIGNÉ par le lot 5, NON traité — c'est un arbitrage à poser au pilote, pas un correctif

`extraction.py` fait `storage.forget_document(identity)` **avant** la conversion,
et l'ordre est gardé (`test_extraction.py`, `ordre == ["oubli", "conversion"]`).
C'est le §4.2 fermé, et l'ordre est le bon : purger après avoir écrit détruirait
ce qu'on vient d'écrire.

**Mais une panne DURE de conversion retire désormais un document SAIN de
l'index**, là où `main` laissait la version précédente en place. C'est cohérent
avec l'invariant que le lot installe — *un document est entièrement dans les
stores, ou pas du tout* — et la partition rouge le dit. Ce n'est pas un défaut.

**C'est un changement de comportement du chemin NOMINAL, et c'est pour cela qu'il
mérite le registre et pas seulement un docstring.** Le capteur déclenche sur
`mtime` (`factory.py:407-418`) : toucher un fichier suffit. Un document dont la
conversion échoue durablement — un HTML corrompu, un service d'extraction à
genoux — **disparaît de l'index à chaque tick**, et l'ancienne version, qui
servait, n'est plus servie. Avant le lot, elle l'était.

**La forme du garde à écrire**, si le pilote juge le troc mauvais : conserver la
version précédente jusqu'au succès de la conversion, c'est-à-dire écrire sous une
clé provisoire puis basculer. C'est un chantier, pas un correctif — et il faut
d'abord trancher lequel des deux états on préfère : *un index qui sert un document
périmé* ou *un index qui n'en sert aucun*. Le lot a choisi le second et l'a écrit ;
le choix n'est pas évident et il n'a pas été posé au pilote.

#### TRANCHÉ par le pilote le 2 septembre 2026 : le second, et le troc est bon

**Entre un index qui sert un document périmé et un index qui n'en sert aucun, le
second est retenu.** Le comportement livré par le lot 4 est donc confirmé, pas
toléré.

**Le motif est la doctrine de ce chantier, et il tient en une opposition.** Un
document périmé servi avec des citations d'apparence valide est une perte
**silencieuse** : l'agent rend des passages, l'utilisateur les lit, les
`element_id` sont bien formés, `verify_contract` ne voit rien — *personne ne peut
la voir*. Une absence est **bruyante** : la partition Dagster rougit,
`index_report` compte les documents et en annoncerait **22 là où le corpus en
porte 23** (`calculé` — le corpus versionné porte 23 documents, §2), et
`verify_contract` le dit. Le chantier a passé quatre lots à apprendre que la
perte silencieuse coûte plus que la panne bruyante ; il n'allait pas trancher
dans l'autre sens.

**Ce que la décision NE dit pas, et il faut l'écrire aussi.** Elle ne dit pas que
le comportement actuel est le meilleur possible. **La conception « écrire sous une
clé provisoire puis basculer » serait strictement meilleure** — elle donne
l'absence de perte silencieuse *et* la continuité de service — et elle **va au
plan, après le lot 6**. Elle n'y va pas avant, pour une raison mesurable : rien
ne dit aujourd'hui à quelle fréquence une conversion échoue durablement sur ce
corpus, et **c'est la première campagne de référence qui le dira**. Un chantier
de bascule à clé provisoire décidé avant cette mesure serait décidé sur un
antécédent `supposé` — la faute que le §3.2 et le §4.28.e ont chacune coûté un
raisonnement au chantier.

**Décision datée, pas question ouverte.** Ce paragraphe remplace « le choix n'est
pas évident et il n'a pas été posé au pilote » : il a été posé, et il est
tranché.

**LE LOT 5 NE LE TRAITE PAS, ET C'EST LE SEUL DES NEUF QU'IL NE POUVAIT PAS
TRAITER.** Ce constat n'est ni du code mort, ni un écart entre la documentation
et le code : le code fait ce que sa documentation dit, et le comportement est
cohérent avec l'invariant que le lot 4 installe. **C'est une question posée au
pilote**, et elle attend une réponse, pas un commit — « écrire sous une clé
provisoire puis basculer » suppose de trancher lequel des deux états on préfère.
Un développeur qui trancherait de sa main retirerait au pilote la décision, ce
qui est exactement ce que le §4.29.a félicite le réparateur du lot 4 de n'avoir
pas fait.

**Ce que le lot 5 ajoute, et c'est tout ce qu'il pouvait ajouter** : la question
est posée nettement, et son coût est borné. Le déclencheur est le capteur `mtime`
— toucher un fichier suffit — donc le cas se produit à **chaque tick** tant que
la conversion échoue, et non une fois.

### 4.30 → CONSIGNÉ par le lot 5 — ce qu'il a trouvé en cherchant autre chose

Onze constats, tous mesurés, et **aucun n'était au registre**. Ils se ressemblent :
chacun est né dans un commit qui faisait bien son travail, et qu'aucun périmètre
n'obligeait à relire la phrase décrivant l'état d'avant. C'est le motif du lot 5,
appliqué au lot 5 lui-même — trois de ces onze ont été trouvés en relisant mes
propres commits.

#### 4.30.a « La profondeur est plafonnée à 3 » vivait à QUATRE documents

Le lot 3 a retiré `MAX_DEPTH` (§4.24) et corrigé `schemas.py`,
`services/nebulagraph.md` et `llm_integration_plan.md`. Périmètre strict, il a
laissé `README.md`, `documentation/graphe_connaissances.md`,
`documentation/extraction_donnees.md` — **dans un titre de section** — et
`documentation/CHANGEMENTS.md`. Remesuré sur l'index vivant :
`{1: 912, 2: 1993, 3: 1164, 4: 256, 5: 40}`, maximum **5**, soit **296 chunks sur
4 365 (6,8 %) au-delà de 3**. Le motif écrit du plafond était faux aussi, et
`README.md` le recopiait mot pour mot. **Traité par le lot 5.** Le code, lui,
était juste et gardé depuis le lot 3 : remettre le plafond rougit 2 tests.

#### 4.30.b `chunk_ids` n'était pas du code mort, il était CONTOURNÉ

§5.1 le range parmi les symboles sans appelant. Exact — et `vectors.build_chunks`
reconstruisait la **même** forme par une expression en ligne, la seule que la
production exécute, et **que rien ne gardait** : un suffixe inconditionnel
laissait la suite entièrement verte (**857 tests, rc=0** sur `main` à `27a6304`,
remesuré par la réparation ; ce constat écrivait 862, un compte pris sur l'arbre
du lot et non sur celui qu'il décrit). L'amputer comme du code mort aurait retiré les seuls
tests d'une clause du contrat dont le site d'exécution n'a aucun garde.
**Traité par le lot 5** : la fonction devient `chunk_id`, unitaire, et
l'appelant la traverse.

> **La CONSÉQUENCE que ce constat écrivait — « cette mutation fait dupliquer tout
> l'index à chaque réingestion » — est FAUSSE, et corrigée par la réparation.**
> Elle l'est depuis le lot 4, et elle a survécu au commit qui l'a rendue fausse.
> Ce que la mutation casse réellement est la clause elle-même, que
> `verify_contract` compte : **974 ids suffixés sur 4 365**. Le détail et la
> mesure sont au **§4.31.B3**. *L'écart, lui, reste justifié : le site de
> production n'était gardé par rien.*

**La leçon, et elle est neuve : « aucun appelant » et « code mort » ne sont pas la
même chose.** Un symbole sans appelant dont un *doublon* est appelé est le
contraire du code mort — c'est la version testée d'un comportement dont la
version vivante ne l'est pas. Avant de retirer un symbole sans appelant, cherche
si son *comportement* a un second site.

#### 4.30.c Le vestige « le modèle ne parle qu'anglais » avait un TROISIÈME site

§6.14 et §6.15 en nomment deux. Le troisième est
`src/docling_service/language.py` — le module dont la langue **est** le sujet, et
celui qu'un développeur ouvre pour comprendre à quoi sert la clé `language`.
**Traité par le lot 5.**

#### 4.30.d L'ancre morte de §6.14 était citée DEUX fois

`#limite-mesurée--le-modèle-dembedding-ne-parle-quanglais` ne correspond à aucun
titre de `base_vectorielle.md`. §6.14 nomme le renvoi du `README.md` ; celui de
`documentation/CHANGEMENTS.md` n'était pas relevé. **Traité par le lot 5**, avec
un balayage de **tous les liens `](fichier#ancre)`** des documents livrés,
résolus contre les titres réels de leur cible : **0 ancre morte** après
correction, et la commande est rejouable.

> **LA BORNE ÉTAIT DANS LE MESSAGE DE `d2562d6` ET ELLE EST TOMBÉE ICI.** Le
> commit écrit « tous les liens `](fichier#ancre)` », ce qui est exact et borné ;
> ce constat écrivait « tous les **renvois internes**… 0 mort », ce qui est plus
> large que ce qui a été mesuré. **Il y a deux familles de renvoi interne**, et
> une seule avait été balayée :
>
> | Famille | Balayée par le lot | `mesuré` par la réparation, 2 septembre 2026 |
> |---|---|---|
> | ancres — `](cible#ancre)` | **oui** | 10 vérifiées, **0 morte** |
> | liens de **fichier** — `](chemin)` | **non** | 41 vérifiés, **1 mort** |
>
> Le lien mort est `documentation/base_vectorielle.md` →
> `src/docling_service/language.py` : il manquait le `../`, dans un document que
> le lot modifie. Corrigé.
>
> **Le critère du balayage**, parce qu'un balayage dont le critère n'est pas
> écrit n'est pas reproductible : les 21 `*.md` du dépôt hors `.venv` et `.git`,
> **privés de leurs blocs et de leurs spans de code** — sans cette soustraction,
> les illustrations de syntaxe `![legende](chemin)` du `README.md` et
> d'`extraction_donnees.md` comptent pour trois liens morts qu'elles ne sont
> pas — chaque cible relative devant exister, et chaque ancre devant figurer
> parmi les ancres GitHub des titres de sa cible.

#### 4.30.e « Aucune troncature » survivait à DIX sites, dont un dans `vectors.py`

Le mandat du lot 5 en annonce deux. L'inventaire en rend dix, et le plus
instructif est `vectors.build_chunks` : « remplit la fenêtre du modèle sans jamais
la dépasser », **à cent-cinquante lignes de l'en-tête du même fichier qui dit le
contraire**. Le lot 3 avait corrigé les deux docstrings *nommés* et laissé le
troisième. Sept sites portaient un chiffre, trois l'affirmation seule.
**Traité par le lot 5**, tout renvoyant à `vectors.get_chunker`.

#### 4.30.f `page_no_end` manquait de TOUS les schémas documentés

Le lot 4 a ajouté la colonne aux onze tags d'élément et à `ChunkMetadata`. Il n'a
touché **aucun** des quatre documents qui décrivent ces schémas (`mesuré` :
`git log e9ebe43~1..79cd2bc --name-only` sur ces fichiers rend le vide). §6.18
relève que le tag `Document` porte 7 propriétés et non 2 ; il ne relève pas que
les tags d'élément en portent 6 et non 5. **Traité par le lot 5.**

#### 4.30.g Le README annonçait « les trois stores » quand la purge en fait QUATRE

Le lot 4 a ajouté la purge de `Datas/.cleaned/` — le piège le plus discret de
cette purge — sans recompter la phrase d'exhaustivité du `README.md`. Le compte
est mesuré sur la sortie du script, qui titre chacune des quatre.
**Traité par le lot 5.**

> **ET LE LOT 5 A LAISSÉ LA MÊME PHRASE UNE LIGNE PLUS LOIN.** `README.md`
> écrivait encore « le script sort en code d'erreur si l'un des **trois** stores
> résiste », **trente-cinq lignes sous le tableau qui en compte quatre, dans la
> section que ce constat corrige**. `mesuré` sur le code : **quatre** branches
> alimentent `echecs` dans `wipe_stores.main` — ChromaDB, MinIO, NebulaGraph,
> HTML nettoyé — et la quatrième est gardée par le test que le lot a écrit
> lui-même, `test_un_echec_de_purge_du_html_fait_sortir_en_un`. **Le lot prouvait
> quatre et écrivait trois.** Corrigé par la réparation ; c'est la troisième
> occurrence du motif de dénombrement dans ce lot, après §4.31.B2 et §4.31.C3.

#### 4.30.h `CLEANED_SUBDIR` cassait les `element_id`, et personne ne l'avait mesuré

§4.29.a nomme deux dégâts : les quatre valeurs qui visent la racine, et les
valeurs contenues mais fausses. **Il y en avait un troisième, plus discret et plus
grave.** Deux sites décidaient du nom du répertoire : `PipelineSettings.
cleaned_subdir`, selon lequel l'asset `cleaned_html` **écrit**, et
`elements.CLEANED_SUBDIR`, selon laquelle `document_identity` **retire** le
segment. `mesuré` avec `CLEANED_SUBDIR=.propre`, sur le chemin nettoyé d'un
chapitre réel : `key` passe de `htms/MLOps with Databricks/Preface` à
`.propre/htms/…`, `collection` passe de l'ouvrage au dossier de source, et
l'`element_id` passe de `fab608f4eb` à `9d6460cded`. **L'exigence 2 rompue, et
l'exigence 3 avec elle, sans qu'aucune erreur ne soit levée.** Traité par le
lot 5, et c'est l'argument qui rend la décision du pilote plus forte qu'elle ne
se présentait.

#### 4.30.i La liste de « renvois vérifiés justes » du §6.17 avait ROTÉ

Deux des sept le sont encore. Le détail et la leçon de méthode sont au §6.17 :
**un renvoi `fichier:ligne` est une mesure dont la provenance comprend la
révision**, et re-vérifier une liste ne la stabilise pas. Le geste durable est de
désigner un **symbole**. Le renvoi de §6.9 a roté deux fois en trois jours.

#### 4.30.j Le piège de mesure §4.27 n° 2 vaut aussi pour les propriétés d'ARÊTE

Le §4.27 documente qu'un `WHERE` sur une propriété de **tag** sans index rend
`IndexNotFound`. `mesuré` : c'est vrai aussi d'une propriété d'**arête** —
`MATCH (a)-[e:PARENT_OF]->(b) WHERE e.sequence == 0` rend « Error found in
optimization stage: IndexNotFound: No valid index found ». Le geste est le même,
filtrer côté client. **Et l'échec ne ressemble pas à un échec** : la requête rend
zéro ligne, donc un `row_values(0)` lève un `IndexError` qui se lit comme un bug
de script.

#### 4.30.k La fenêtre du modèle n'était gardée par rien, et deux documents l'avaient déjà fausse

`index_report` lit `modele.max_seq_length` : `mesuré`, la remplacer par
`limite = 256` — le nombre même qui était faux dans `services/chromadb.md` et
`llm_integration_plan.md` — laissait 834 tests verts. L'instrument pouvait donc
rapporter une fenêtre fabriquée, **et son taux de troncature avec elle**.
**Traité par le lot 5**, garde en sous-processus, avec le témoin qui exige que
deux modèles rendent deux fenêtres.

**Le motif commun des onze, et il est unique** : *une phrase, un chiffre ou un
renvoi survit au commit qui rend son objet faux, parce que le périmètre du commit
ne l'obligeait pas à le relire.* Le §11 du mandat le formule pour les commits qui
ferment un angle mort ; ces onze montrent que cela vaut pour **tout** commit qui
change un fait, y compris ceux d'un lot dont c'est le sujet.

---

### 4.31 → la RÉPARATION du lot 5 — quatre bloquants et quatre constats de ligne

Le pilote a jugé le lot fusionnable **après réparation** : ses trois défauts de
comportement sont confirmés, ses chiffres reproduits, ses écarts validés. Ce qui
suit est ce qu'il a fermé, avec le juge de chacun.

**Et le motif est dur à entendre : les quatre bloquants sont, quatre fois, la
famille que ce lot existe pour fermer — commise par lui.** Un renvoi qu'il a
rendu faux **au commit suivant** celui qui l'écrivait (§4.31.B1), un
dénombrement qui contredit le déverrouillage sur lequel reposent ses propres
tests (§4.31.B2), une conséquence devenue fausse au lot précédent et recopiée à
**neuf passages dans six fichiers** (§4.31.B3), et un invariant énoncé dans un
docstring sans le garde qui va avec (§4.31.B4).

**Ce n'est pas une charge contre le lot : c'est la mesure de la difficulté du
travail, et personne n'y échappe.** Le lot s'est fait prendre **deux fois de son
propre aveu** (§4.30.b, §4.30.i) ; son audit en a trouvé **deux de plus** ; le
**pilote** a recopié « le seul chapitre retenu sans aucun `<h2>` » **deux fois,
le tableau des balises sous les yeux** (§3.2, mandat §5.1 ter) ; et la
**réparation elle-même** en a produit trois qu'elle a dû corriger en cours de
route — « huit sites » pour neuf passages, « ~37 lignes » repris sans mesure, et
« trois liens morts » dont deux étaient des illustrations de syntaxe. Chacune est
écrite au site où elle a été faite, parce qu'une famille de défaut qu'on ne
documente que chez les autres n'est pas comprise.

#### 4.31.B1 Cinq renvois `mesuré` que le lot a rendus faux LUI-MÊME

Il écrivait `mesuré à src/docling_service/vectors.py:230` à **cinq sites** : le
docstring de `chunking.has_content`, `base_vectorielle.md`,
`extraction_donnees.md`, `llm_integration_plan.md` et `services/chromadb.md`.

*Le juge est une mesure*, `mesuré` le 2 septembre 2026 sur la pointe du lot :

```bash
sed -n '230p' src/docling_service/vectors.py   # -> `ids: list[str] = []`
grep -n 'autonome' src/docling_service/vectors.py   # -> 267, 268
```

Le filtre vit donc à **267-268**, et non à 230.

**La chronologie est mesurée, commit par commit**, et elle est plus instructive
que le fait :

```bash
for c in $(git rev-list --reverse main..e5103cf); do
  git show "$c:src/docling_service/vectors.py" | grep -n 'if autonome and'
done
git show --numstat --format= 765f5ee -- src/docling_service/vectors.py
git log --oneline -S 'vectors.py:230' main..e5103cf
```

| | ligne du `if autonome and …` |
|---|---|
| `main` (`27a6304`) et les trois premiers commits du lot | **230** |
| **`765f5ee`** et les huit suivants | **268** |

Le renvoi a été écrit par **`c563f45`**, le troisième commit du lot, et il était
**exact ce jour-là**. **`765f5ee` — le commit SUIVANT — l'a rendu faux** en
portant `vectors.py` de +46/−8 lignes, soit un décalage net de 38 qui est
exactement `268 − 230`. *Le renvoi n'a donc pas vieilli : il a été tué par le
commit d'après, dans le lot dont c'est le sujet.*

C'est le §4.30.i au mot près — « un renvoi `fichier:ligne` est une mesure dont la
provenance comprend la révision » — et le §6.17 prescrivait déjà le remède : **le
geste durable est de désigner un SYMBOLE et non une ligne.** Les cinq sites
nomment désormais `vectors.build_chunks`.

##### Le balayage complet des renvois `fichier:ligne` du diff, avec son critère

Corriger cinq renvois ne dit rien des autres. Le balayage porte sur **toute ligne
ajoutée** par `git diff main..HEAD -U0` contenant un motif
`<chemin>.<py|md|yml|yaml|toml|sh>:<n>[-<m>]`, le fichier visé étant cherché tel
quel puis sous `src/`, `src/docling_service/`, `src/pipeline/`, `tests/unit/` et
`documentation/`. Un balayage dont le critère n'est pas écrit n'est pas
reproductible.

`mesuré` le 2 septembre 2026 : **10 renvois distincts**, 0 fichier introuvable.

| Renvoi | État |
|---|---|
| `vectors.py:230` (5 sites) | **FAUX** — corrigé ci-dessus, par le symbole |
| `ranking.py:56-71`, `ranking.py:83-84` | **justes à `e5103cf`** — vérifiés ligne à ligne : ce sont bien les corps de `docling_parent_rank` et `docling_level_rank`. La révision est nommée parce que c'est la moitié de la provenance qui manquait au §6.17, et ces deux-là rotteront comme les autres |
| `README.md:317`, `extraction.py:335-337`, `index_report.py:75-84`, `nebula.py:49`, `nebula.py:160`, `schemas.py:94-95` | **citations, pas des renvois** : ils vivent dans le tableau du §6.17 qui les déclare périmés ou dérivés, et ce tableau existe pour dire qu'ils le sont. Les corriger en `fichier:ligne` neuf serait refaire le défaut à trois jours près |

#### 4.31.B2 « Onze modules sans dépendance externe » : ils sont QUATORZE, et le sept niait le déverrouillage

`services/docling.md` annonçait **onze** modules ne dépendant que de la
bibliothèque standard, et **sept** portant une dépendance de niveau module.

*Le juge est une mesure* — balayage AST rejoué le 2 septembre 2026, **critère
écrit au site** parce qu'un balayage dont le critère n'est pas écrit n'est pas
reproductible : les **18 modules** de `src/docling_service/` (les `*.py`, moins
le marqueur de paquet `__init__.py`, vide), un module portant une dépendance
externe quand une instruction `import` du **corps du module** nomme un paquet
racine qui n'est ni relatif, ni `src`/`docling_service`, ni dans
`sys.stdlib_module_names`.

**Résultat : 18 modules, 4 porteurs, 14 sans aucune dépendance** —
`extraction.py` (`bs4`), `images.py` (`minio`), `main.py` (`fastapi`),
`settings.py` (`pydantic_settings`).

**Et le compte de sept était plus grave que le compte de onze : il NIAIT le
déverrouillage livré par les lots 3 et 4** (§3.4, §4.4, §4.28.d), celui-là même
sur lequel reposent `test_vectors.py` et `test_nebula.py`. Il rangeait
`embedding.py`, `nebula.py` et `vectors.py` parmi les porteurs alors que leurs
imports lourds sont **différés**. La preuve est dure, et elle tient en deux
mesures : `chromadb`, `nebula3` et `sentence_transformers` **ne sont pas dans le
venv du dépôt** (`importlib.util.find_spec` rend `None` pour les trois), et
`uv run python -c "import src.docling_service.vectors"` — de même pour `nebula`
et `embedding` — rend `rc=0` côté hôte.

La liste ne venait pas d'un balayage : elle venait du **registre §6.8 corrigé à
la main**, et §6.8 était marqué ✅ sur ce compte faux. Il est corrigé, pas
rouvert : le constat — *le document énumère mal* — est bien fermé une fois
l'énumération juste.

**Le balayage est converti en garde**, parce que la phrase est une phrase
d'exhaustivité et que le chantier n'en laisse plus passer sans borne ni test :
`tests/unit/test_dependances_de_niveau_module.py` rejoue l'AST, sans rien
importer — donc sans dépendre du venv ni de l'ordre des tests. `mesuré`,
mutation appliquée puis révoquée, texte vérifié changé :

| Mutation | Suite entière |
|---|---|
| `import minio` ajouté au corps de `storage.py` — un porteur de plus, rien d'autre ne casse | **rc=1, UN seul rouge** : `test_seuls_quatre_modules_portent_une_dependance` |
| `import chromadb` remis au corps de `vectors.py` — le déverrouillage défait | **rc=2**, la collecte est **interrompue** sur 3 erreurs (`test_vectors.py`, `test_storage.py`, `test_extraction.py`). *Le garde ne rougit pas là : il n'est jamais atteint.* C'est ce qui rend la première mutation nécessaire — elle est la seule qui isole la propriété |

Trois témoins : le balayage doit avoir lu au moins 18 modules, il doit rendre
`bs4` sur `extraction.py` (sans quoi un balayage qui ne détecte rien passerait),
et il doit rendre l'ensemble vide sur `ngql.py` (sans quoi un balayage qui
détecte tout passerait aussi).

#### 4.31.B3 « Un suffixe inconditionnel fait DUPLIQUER tout l'index » : faux depuis le lot 4

L'affirmation vivait à **neuf passages** répartis dans **six fichiers**, et le
mandat de la réparation en nommait quatre. L'inventaire, `mesuré` — `grep -rn
'dupliqu' src/ tests/ documentation/ README.md`, puis lecture de chaque ligne
pour écarter celles qui parlent d'autre chose (le déterminisme des `element_id`,
le chevauchement de pages, la déduplication de `detect-secrets`) :

| Fichier | Passages |
|---|---|
| `src/docling_service/chunking.py` — docstring de `chunk_id` | **2** |
| `src/docling_service/vectors.py` — commentaire de `build_chunks` | 1 |
| `tests/unit/test_chunking.py` | 1 |
| `tests/unit/test_vectors.py` — docstring de classe, docstring de test, message d'assertion | **3** |
| `documentation/base_vectorielle.md` | 1 |
| ce registre, §4.30.b | 1 |

*(Ce paragraphe a d'abord écrit « huit sites » : neuf passages, six fichiers, et
« site » ne disait pas lequel des deux. **Une erreur de dénombrement dans la
section qui traite des erreurs de dénombrement** — c'est la difficulté du
travail, et elle se corrige en recomptant, pas en s'en méfiant.)*

*N'audite pas la liste qu'on te donne : construis la tienne, puis diffe.* Le §5.1
s'y ajoute d'une autre façon : il ne portait pas l'affirmation, il décrivait
l'état d'**avant** le lot sous un titre qui annonce « traité par le lot 5 ». Il
est réécrit.

*Le juge est une mesure, et elle se lit dans le code livré sans rien exécuter :*

```bash
grep -n 'forget_document\|_already_ingested' src/docling_service/extraction.py
grep -n 'where=' src/docling_service/vectors.py          # -> {"source_path": ...}
git log --oneline -S 'storage.forget_document(identity)' -- src/docling_service/extraction.py
```

- `extraction.extract` appelle **`storage.forget_document(identity)` avant la
  conversion** ; l'ordre est gardé (`test_extraction.py`,
  `ordre == ["oubli", "conversion"]`) ;
- `vectors.delete_document` supprime par `where={"source_path": …}`, **jamais par
  id** — la clause vise `source_path` parce que c'est l'identité d'un document
  (exigence 3) ;
- donc **une forme d'id changée ne laisse aucun orphelin** : les chunks du
  document partent en entier avant que les nouveaux ne soient écrits ;
- le seul chemin qui saute la purge est le **doublon exact**
  (`_already_ingested`), et il retourne sans rien écrire ;
- et la ligne qui a rendu la phrase fausse est **`a54636c`, du lot 4**
  (1er septembre 2026), « delete_document n'avait aucun appelant ». **La phrase a
  survécu au commit qui l'a rendue fausse**, et elle vivait dans la
  justification d'un écart du lot 5 : *sa propre famille, appliquée à lui-même.*

**L'écart, lui, reste justifié et n'est pas rediscuté.** Le site de production —
l'expression en ligne de `build_chunks` — n'était gardé par rien : la mutation
« suffixe inconditionnel » laissait la suite entièrement verte sur `main` à
`27a6304` — **857 tests, rc=0**, remesuré de mes mains dans un arbre dédié — et
elle rougit maintenant à **2 tests**,
`test_chunking.py::TestChunkId::test_un_chunk_seul_garde_l_id_nu` et
`test_vectors.py::…::test_un_element_d_un_seul_chunk_est_ecrit_sous_son_id_nu`.
*(Le lot annonçait 862 : c'est son propre arbre, pas celui qu'il décrivait —
famille F2.)* Ce qui était faux est la **conséquence**, pas la décision.

**La vraie conséquence, et elle est mesurée.** La forme de l'id de chunk est une
**clause du contrat**, et `verify_contract` la compte : « ids de chunk suffixés
en #n ». `mesuré` le 2 septembre 2026 sur l'index vivant, lecture directe de la
collection `rag_documents` : **4 365 chunks, 974 ids suffixés, 3 391 ids nus**.
Un suffixe inconditionnel porterait le compte à **4 365 sur 4 365**.

**Et il faut dire ce que ce compteur est** : `verify_contract` l'**imprime**, il
n'en lève **aucune anomalie**. C'est une lecture d'instrument, pas un garde — ce
qui est exactement la raison pour laquelle la clause a besoin d'un test, et
pourquoi retirer `chunk_ids` comme du code mort aurait été une perte.

#### 4.31.B4 Le TREIZIÈME garde creux du chantier, et il était dans le lot qui les chasse

`verify_contract._lire_les_tags_sans_la_colonne` **énonce** son invariant dans
son docstring — « Un `DESCRIBE` en échec est compté comme "colonne absente" : ne
pas pouvoir constater n'est pas constater que tout va bien », qui est la leçon du
cinquième trou du lot 3 (§4.4) — et **rien ne le gardait**.

`mesuré` le 2 septembre 2026 sur le code livré, mutation appliquée puis révoquée,
texte vérifié changé par empreinte SHA-256 :

| État | `if colonne not in colonnes` → `if colonnes and colonne not in colonnes` |
|---|---|
| lot 5 tel que livré | **rc=0, 857 tests, ZÉRO rouge** |
| après ce garde | **rc=1, 3 rouges** — `test_un_describe_rejete_est_compte_comme_colonne_absente`, `test_un_seul_describe_rejete_suffit_a_nommer_son_tag`, `test_l_anomalie_qui_en_decoule_prescrit_le_redemarrage` |

*(La même mutation, la suite **privée de la classe neuve** : rc=0, 0 rouge. C'est
la bascule, et elle est mesurée sur le même arbre.)*

**Le motif est celui des douze gardes creux précédents** : *le test observe une
absence.* Le compte de douze est `calculé` et il se dérive : **trois** au lot 3 —
M15, M12, M20, les gardes neufs que rien ne gardait (§4.4, §4.5) — et **neuf** au
lot 4, cinq trouvés par le lot lui-même et quatre par son audit (mandat
§5.1 quinquies). Celui-ci est donc le treizième. `_verifier_le_tag_document` porte le sien depuis le lot 3 ; la fonction
que le lot 5 vient d'écrire, non.

**Ce que la mutation coûtait, et ce n'est pas une élégance** : un graphd qui
refuse le `DESCRIBE` rend `tags_sans_la_colonne == []`, donc
`anomalie_de_colonne` prend sa **seconde** branche et prescrit « réingérez » là où
il faut « redémarrez **puis** réingérez ». **C'est le §4.29.e rouvert par le
commit qui le ferme.**

Le garde porte deux témoins : un schéma entièrement migré ne rend aucun tag —
sans quoi un garde qui rougirait toujours passerait — et un `DESCRIBE` en échec
**sur un seul tag** ne nomme que celui-là, sans quoi un garde qui ne verrait que
« tous les `DESCRIBE` échouent » resterait vert sur l'état le plus plausible, un
tag verrouillé par une migration en cours.

#### 4.31.C1 L'écart maximal de `sequence` : 994, sous un chapitre HTML, et « écart » n'était pas défini

Le site canonique — le docstring de `verify_contract.inversions_de_page` —
écrivait « le plus grand trou vaut **993**… le trou venant du **PDF** dont les
sous-arbres dominent ».

*Le juge est une mesure*, `mesuré` le 2 septembre 2026 sur le graphe vivant, en
lecture seule, depuis le conteneur d'extraction :

```ngql
MATCH (a)-[e:PARENT_OF]->(b) RETURN id(a) AS parent, e.sequence AS seq;
```
puis, côté client, les `sequence` triées par parent et les différences entre
valeurs consécutives (le §4.30.j interdit un `WHERE` sur une propriété d'arête).

| | |
|---|---|
| arêtes `PARENT_OF` lues | **15 173** |
| parents distincts | **763** |
| parents à `sequence` non contiguës | **167** (21,9 %) |
| **écart maximal — différence** | **994** |
| **écart maximal — valeurs intercalaires** | **993** |
| entre les `sequence` | **203** et **1197** |
| sous le parent | `doc_htms/MLOps with Databricks/7. Foundation Models and Context Engineering` |

**Deux corrections, et la seconde vaut plus que la première.**

1. **Ce n'est pas le PDF.** C'est un **chapitre HTML**, et le parent est la
   **racine du document elle-même**. « Le trou venant du PDF » était une
   explication vraisemblable, jamais mesurée — la famille du §3.2 ;
2. **« écart » n'était pas défini, et les deux lectures ne donnent pas le même
   nombre.** 994 de différence ou 993 valeurs intercalaires : les deux sont
   vraies, elles ne disent pas la même chose, et **aucune des deux n'était
   écrite**. Un agent qui dimensionne une fenêtre sur « le trou vaut 993 » se
   trompe d'un rang. La définition est désormais au site, avec les deux nombres.

Les mentions du registre renvoient au site canonique au lieu de recopier, et les
chiffres du lot 1 qui y vivaient encore (44 parents sur 185) portent désormais
leur périmètre — 3 documents, 2 285 arêtes.

#### 4.31.C2 « Les trois stores » : la purge en fait QUATRE — corrigé au §4.30.g

Le constat et sa mesure vivent au **§4.30.g**, c'est-à-dire au site que la phrase
fausse contredisait, et non ici : c'est là que le prochain lecteur cherchera.
En deux lignes : `README.md` écrivait « le script sort en code d'erreur si l'un
des **trois** stores résiste », **trente-cinq lignes sous le tableau qui en compte
quatre**, dans la section que le §4.30.g corrige. `mesuré` : **quatre** branches
alimentent `echecs` dans `wipe_stores.main`, et la quatrième est gardée par le
test que le lot a écrit lui-même. **Il prouvait quatre et écrivait trois.**

#### 4.31.C3 « Les DEUX documents réels du corpus » : ils sont SEIZE sur 23

`services/nebulagraph.md` et `llm_integration_plan.md` écrivaient qu'un space
créé à `FIXED_STRING(64)` « refuse les **deux** documents réels du corpus
(identifiants de 65 et 67 octets) ».

*Le juge est une mesure*, `mesuré` le 2 septembre 2026 sur le graphe vivant :

```ngql
MATCH (v:Document) RETURN id(v) AS vid;
```
puis `len(vid.encode("utf-8"))` côté client.

| | |
|---|---|
| sommets `Document` | **23** |
| identifiants **> 64 octets** | **16** |
| minimum / maximum | **38** / **111** |

65 et 67 sont les **deux premiers trouvés** au-dessus du seuil, pas les deux
seuls : `…/1. MLOps Principles and Components` et
`…/Practical MLflow…/Preface` à 65, `…/5. Machine Learning Model Deployment` à
67 — et treize autres jusqu'à 111.

**Le défaut est préexistant au lot 4**, et c'est la raison pour laquelle il
compte quand même : il vit dans le bloc que le lot 5 déclare **relu et fermé au
§6.18**. Un bloc déclaré relu porte la responsabilité de ce qu'il laisse.

La longueur et sa méthode de mesure ont désormais **un seul site**,
`services/nebulagraph.md`, section « Schéma nGQL » ; `llm_integration_plan.md`
y renvoie.

#### 4.31.C4 Une borne perdue entre le commit et le registre, plus un lien mort

Le message de `d2562d6` est **juste et borné** : « tous les liens
`](fichier#ancre)` des documents livrés… 0 renvoi mort ». Le §4.30.d a laissé
tomber la borne et écrit « tous les **renvois internes**… 0 mort ». *Une borne
qui tombe entre le commit et le registre est un élargissement d'affirmation que
personne ne mesure.*

Balayage refait aux **deux** familles, `mesuré` le 2 septembre 2026 : **0 ancre
morte sur 10**, mais **1 lien de fichier mort sur 41** — `base_vectorielle.md` →
`src/docling_service/language.py`, où il manquait le `../`, **dans un document
que le lot modifie**. Corrigé, et la borne rétablie au §4.30.d avec le critère
du balayage.

**Une leçon de méthode au passage.** Le premier passage du balayage a rendu
**trois** liens morts ; deux étaient des illustrations de syntaxe —
`![legende](chemin)` — vivant dans des spans de code. Le critère corrigé
soustrait les blocs et les spans de code avant de chercher. *Un balayage se
mesure avec son critère, et un critère se corrige en regardant ce qu'il a
attrapé* — sans quoi la réparation aurait écrit « trois liens morts » et créé,
dans le geste qui ferme le constat, exactement le défaut qu'il ferme.

#### 4.31.N Deux faits de poste mesurés pendant la réparation, et l'un rendait la documentation fausse

Ils ne viennent ni du lot ni de son audit : le **monde** les a produits pendant
que la réparation travaillait. C'est la même famille que les quatre bloquants —
*une phrase survit à ce qui la rend fausse* — à ceci près qu'aucune main ne l'a
écrite. **La seule défense est l'étiquette et la date.**

**1 — `page_no_end` EXISTE désormais dans le graphe vivant.** `docling-service` a
été redémarré, `init_schema()` a joué. `mesuré` le 2 septembre 2026, lecture
directe depuis le conteneur d'extraction :

| | 1er septembre 2026 | 2 septembre 2026 |
|---|---|---|
| `DESCRIBE TAG Paragraph` | 5 colonnes, **sans** `page_no_end` | **6 colonnes**, `page_no_end` comprise |
| `DESCRIBE TAG SectionHeader` | idem | idem |
| sommets `Paragraph` à `NULL` | — | **7 251 / 7 251** |

Donc « la colonne n'existe pas encore » est **devenu faux** au `README.md`, au
§4.29.e, au §4.28.e et au mandat (§6 et §7.2). Les cinq sites portent désormais
les **deux** mesures, chacune datée, plutôt qu'une seule réécrite : c'est ce qui
rend le mouvement lisible. Et chacun dit explicitement que **ce fait périme, parce
que c'est un état de poste et non une propriété du code** — un `docker compose
restart` suffit à le retourner, et c'est exactement ce qui vient d'arriver.

Le poste est passé du **premier** des deux états que `anomalie_de_colonne`
distingue au **second**. La consigne, elle, ne périme pas : redémarrer avant de
réingérer est sans coût quand le schéma est déjà à jour, et c'est la seule des
deux choses qui vaille d'être apprise par cœur.

**2 — `dagster-daemon` tournait depuis quatre heures**, et le pilote l'a arrêté
pour protéger l'antécédent. **L'index est intact**, et la réparation l'a remesuré
de ses mains le 2 septembre 2026 — les cinq chiffres concordent :

| | |
|---|---|
| chunks ChromaDB | **4 365** |
| sommets | **15 196** |
| arêtes `PARENT_OF` | **15 173** |
| documents | **23** |
| objets MinIO | **13** |

Le §7.2 du mandat le dit arrêté : c'est **redevenu** vrai. Ce qu'il faut retenir
n'est pas l'incident mais sa leçon : **« le daemon est arrêté » n'est pas une
propriété stable**, elle se remesure avant toute mesure qui en dépend — et les
sensors étant livrés armés (§4.18), un daemon qui repart réingère.

### 4.32 → CONSIGNÉ par le lot 6, la première campagne de référence — **un des quatre traité**

> **§4.32.a est FERMÉ par le lot 8** (22 septembre 2026). Les **trois** autres
> — `b`, `c`, `d` — restent ouverts : le lot 8 était borné au `a` et n'y a pas
> touché. Le compte est `calculé`, `grep -c '^#### 4.32' ` rend quatre.

**Quatre** constats trouvés en menant la campagne, tous mesurés, laissés **hors
du diff**. Périmètre strict. Chacun porte la **forme du garde à écrire** —
sauf le dernier, qui n'en admet pas, et qui dit pourquoi à son site.

*(Cette phrase a d'abord écrit « trois », comptés avant que le quatrième ne soit
mesuré. Une erreur de dénombrement dans la section qui en consigne une : c'est
la difficulté du travail, et elle se corrige en recomptant.)*

Le détail de la campagne elle-même — les trois gestes et l'effet de chacun, les
23 runs, le verdict des deux instruments, le jeu de 30 questions et son plancher
de rappel dense — vit à son site canonique,
[`documentation/campagnes/2026-09-02-premiere-campagne-de-reference.md`](campagnes/2026-09-02-premiere-campagne-de-reference.md).
Ne recopie pas ses chiffres ici : renvoie-y.

#### 4.32.a → TRAITÉ par le lot 8 — le `run_key` du capteur interdisait toute réingestion, et il le faisait EN SILENCE

> **FERMÉ le 22 septembre 2026.** Le constat ci-dessous est conservé **tel qu'il
> a été écrit**, parce qu'il est la seule trace de l'état mesuré le 2 septembre.
> Ce qui a changé vit à la fin du constat, sous « Ce que le lot 8 a fait ».
>
> **Renvoi.** Le geste de réingestion a été exercé **deux fois** le 25 septembre
> 2026, et les deux fois le silence ne s'est pas produit : à la
> [deuxième campagne de référence](campagnes/2026-09-25-deuxieme-campagne-de-reference.md)
> — 23 runs créés, `958 → 981` — et à la
> [bascule vers SeaweedFS](campagnes/2026-09-25-bascule-seaweedfs.md), sous
> l'étiquette `reingerer:2026-09-25-bascule-seaweedfs` — 23 runs créés,
> `982 → 1 005`. Voir §4.42 et §4.43.


**C'est le défaut le plus grave que la campagne ait trouvé, et il est mot pour
mot celui que la réparation du lot 0 a fermé dans `reindex_job.py` — resté
intact dans `factory.py`, et consigné nulle part.**

> **COTATION RELEVÉE D'UN CRAN, ET TRANCHÉ PAR LE PILOTE LE 3 SEPTEMBRE 2026 :
> ce constat passe DEVANT §4.29.i en tête du plan d'après-lot-6.** Le motif est
> un lien que la première rédaction de ce constat ne faisait pas, et qui le fait
> passer d'une gêne à **un chemin de récupération cassé vers lequel un message
> d'erreur pointe** :
>
> - **le message d'anomalie de `verify_contract` prescrit lui-même le geste
>   mort.** `anomalie_de_colonne` rend, mot pour mot, « Le geste est REDEMARRER
>   docling-service PUIS **reingerer** » sur sa première branche, et « seule une
>   **reingestion** les renseigne » sur la seconde (`mesuré`, lecture de
>   `src/verify_contract.py`) ;
> - **le `README.md` prescrit le même geste, et ne dit jamais comment le
>   déclencher.** Sa section « Ré-ingérer proprement » donne la **purge** —
>   `wipe_stores` — puis « redémarrer, puis réingérer », sans une ligne sur ce
>   qui provoque la réingestion. Le chemin nominal est le capteur, et il est
>   mort ;
> - **donc le système ordonne un geste dont le chemin nominal échoue EN
>   SILENCE** — `skip_reason=None`, aucune ligne au journal du tick qui perd 22
>   runs. **Un opérateur qui purge puis attend garde des stores vides
>   indéfiniment**, en ayant suivi la documentation à la lettre, sans qu'aucun
>   message ne lui dise que rien ne viendra.
>
> C'est ce qui le fait passer devant §4.29.i : la bascule à clé provisoire
> améliore un troc déjà tranché et déjà bon, tandis que celui-ci laisse la
> procédure de récupération documentée sans issue.

`factory.py`, `file_sensor` :
`run_key=f"{source.name}_{partition_key}_{mtime}"`. La clé est donc déterministe
sur `(source, partition, mtime)`. Or Dagster cherche un `run_key` consommé dans
**tout** l'historique, sans borne de temps. **Un fichier du corpus dont le
`mtime` n'a pas changé ne peut donc JAMAIS être réingéré par le capteur** — et
le geste de récupération naturel, vider le curseur, ne rattrape rien.

`mesuré` le 2 septembre 2026, sur l'objet que Dagster enregistre :

| | `livres_html_sensor` | `pdfs_sensor` |
|---|---|---|
| curseur vidé, vérifié à 0 entrée | oui | oui |
| premier tick après démarrage du daemon | 12:52:02.534 UTC | 12:52:01.822 UTC |
| **`run_keys` demandées** | **22** | **1** |
| **runs créés** | **0** | **0** |
| **`skip_reason`** | **`None`** | **`None`** |
| curseur après le tick | **revenu à 22 entrées** | revenu à 1 |

Le curseur revenu à 22 entrées est la seconde preuve, indépendante de la
première : il n'est réécrit que dans la branche qui vient d'ajouter une demande
de run. Le capteur a donc bien construit ses 23 demandes, et Dagster en a créé
**zéro**.

**Et l'échec ne ressemble pas à un échec.** Le tick qui perd 22 runs porte
`skip_reason = None` : le journal du daemon ne dit rien à ce tick-là, et la
phrase « Sensor function returned an empty result » n'apparaît qu'aux ticks
**suivants**, quand le curseur est de nouveau plein — donc pour une raison qui
n'est plus celle-là. **22 runs perdus sans un mot.**

**Ce qui a fait croire le contraire pendant deux lots.** Au lot 3, le Postgres de
Dagster était reparti **vierge** (§4.26) : l'historique ne portait aucun
`run_key`, et `docker compose up -d` a bien déclenché l'ingestion complète. C'est
de cet épisode que vient la phrase du mandat « le démarrer déclenche
l'ingestion ». Elle était vraie **de ce poste-là, ce jour-là**, et elle est
fausse dès que le Postgres survit — c'est-à-dire dans le cas nominal.

**La forme du garde à écrire.** Le patron existe déjà dans ce dépôt : la
réparation du lot 0 a fait porter au `run_key` de `reindex_job` **la rafale et la
tentative** plutôt qu'un repère seul. Ici, la propriété à garder est *« deux
évaluations successives du capteur, curseur vidé entre les deux, produisent des
`run_key` distincts »* — et son témoin, sans lequel le garde serait creux : *deux
évaluations successives sans vider le curseur ne doivent produire **aucune**
demande*, sinon un `run_key` rendu aléatoire relancerait l'ingestion à chaque
tick. Le harnais de `test_factory.py` appelle déjà la fabrique et exerce le
capteur ; ce qui manque est une assertion sur la clé, pas un montage.

**Attention à la borne, et elle est étroite** : `run_key=None` supprimerait la
seule protection contre deux évaluations concurrentes, ce que la réparation du
lot 0 a explicitement écarté. Le geste n'est pas « retirer la clé », c'est « lui
faire porter la tentative ».

*Contournement mesuré, en attendant :* lancer les partitions explicitement,
`dagster job launch -j <job> --tags '{"dagster/partition": "<clé>"}'`. Il passe
par le vrai coordinateur et le vrai lanceur, et il exerce tout le chemin
d'ingestion — seule la création du run par le capteur reste hors d'atteinte.

**CE QUE LE LOT 8 A FAIT** — trois commits, `d4e336e`, `1dea19c`, `2440dd1`.

*La réingestion se demande, et elle ne part jamais toute seule.* Le geste est un
marqueur posé à la main dans le curseur du capteur, `reingerer:<étiquette>`. Les
trois questions sont répondues au site, au-dessus de `PREFIXE_REINGESTION` dans
`src/pipeline/factory.py` : ce qui déclenche (ce marqueur, et rien d'autre), ce
qui garantit que rien ne parte seul (le curseur, plus le fait que **sans
marqueur la clé garde exactement sa forme historique**), et ce que fait le geste
refait à l'identique (les mêmes clés, donc aucun run — et le capteur le dit).

*La borne du registre est tenue* : la clé n'est ni supprimée ni rendue
aléatoire. Elle porte l'étiquette du geste, comme celle de `reindex_job` porte
la tentative. Deux évaluations concurrentes du même curseur marqué construisent
les **mêmes** clés, donc un seul run par partition : le témoin que ce constat
réclamait est `test_sans_marqueur_un_corpus_inchange_ne_demande_rien`, doublé de
`TestLaCleNominaleEstInchangee`, qui fige la forme littérale de la clé nominale,
et de `TestLaCleDeReingestionNePorteQueLEtiquette`, qui fige celle de l'autre.

*La dérogation à la forme prescrite reste bonne, et sa justification était
fausse.* Le registre prescrivait « lui faire porter la tentative » ; le lot 8 a
laissé la clé **nominale** intacte et fait porter l'étiquette à la seule clé
marquée. Il a d'abord justifié ce choix par la protection contre « une
réingestion accidentelle à chaque redémarrage du daemon » — c'est-à-dire par le
§4.26. **Cet événement ne départage pas les deux formes.** Le §4.26 dit mot pour
mot : « Le Postgres de Dagster est donc reparti **vierge**, les curseurs des
sensors avec lui ». Curseurs et historique des runs vivent dans le **même**
Postgres : ils se perdent ensemble, et sous l'une comme sous l'autre forme de
clé, tout est alors réingéré **en silence**. La preuve vit dans ce dépôt et elle
est à charge : `test_des_cles_neuves_ne_declenchent_aucun_avertissement` monte
une instance vierge, obtient ses trois demandes et **aucun** avertissement.

Ce que la clé nominale inchangée couvre **vraiment** est un autre scénario, plus
étroit et bien réel : **le curseur perdu seul, historique intact**. Une remise à
zéro du curseur à la main depuis l'interface, un capteur renommé, une code
location renommée — dans les trois cas le curseur repart vide et l'historique
reste. Sous la forme prescrite au registre, ce cas réingérait tout en silence ;
sous celle du lot 8, le capteur reconstruit des clés consommées **et le dit**,
avec son compte. C'est cela, et cela seul, que la dérogation achète. Les deux
sites qui portaient la fausse justification — le bloc au-dessus de
`PREFIXE_REINGESTION` et le tableau du `README` — ont été redressés (commits
`f416a2f` et `f9742b0`). Sans ce redressement, le lot suivant héritait d'une
assurance qu'aucune mesure ne soutient.

*Le silence est fermé par `_cles_deja_consommees`*, qui reproduit la règle du
daemon — même `run_key` **et** même `sensor_name`, `dagster/_daemon/sensor.py::
fetch_existing_runs` — et journalise le **compte** des demandes perdues avant de
les émettre. C'était la moitié du constat : le tick qui a perdu 22 runs n'a rien
écrit du tout.

*Les deux messages qui prescrivaient le geste mort nomment le geste réel* :
`COMMENT_REINGERER` dans `src/verify_contract.py`, porté par les **deux**
branches d'`anomalie_de_colonne`, et la section « Ré-ingérer proprement » du
`README.md`. Trois gardes tiennent la correspondance, dont un qui exerce le
**capteur** sur le marqueur que le message prescrit — sans lui, les deux
constantes pourraient dériver ensemble vers une chaîne que personne n'honore.

*Quinze mutations du producteur, quinze rouges, `rc=1` chacune.* Le détail vit
au rapport du lot 8 ; les gardes vivent dans `tests/unit/test_factory.py` et
`tests/unit/test_verify_contract.py`.

**CE QUE LE LOT 8 N'A PAS PU MESURER, ET IL FAUT LE LIRE AVANT LE LOT SUIVANT.**
Il lui était interdit de réingérer — l'index en place est l'antécédent de la
campagne. Il a donc prouvé **autrement**, et voici la limite exacte de sa
preuve : le capteur a été rejoué **hors du daemon**, contre le curseur réel lu
au `SELECT` et contre le corpus réel, sur une instance Dagster éphémère ; ce
rejeu dit ce que le capteur **demande**, et la règle du daemon, reproduite et
recoupée sur l'historique réel, dit ce que Dagster **en fait**. Ce qui n'est pas
prouvé, et qui ne pouvait pas l'être : qu'un run réellement créé par ce chemin
aille au bout. Le premier geste de réingestion reste donc à faire sous les yeux
de quelqu'un.

#### 4.32.b `verify_contract` compte des sommets que son producteur exclut par construction

`verify_contract` ne peut **pas** rendre 0 sur ce corpus, quoi qu'on ingère, et
ce n'est pas un défaut d'ingestion : c'est un désaccord entre deux sites du code
livré, dont un seul l'écrit.

`mesuré` le 2 septembre 2026 sur l'index de la campagne, en remontant les chaînes
`PARENT_OF` côté client (§4.30.j interdisant un `WHERE` sur une propriété
d'arête) :

| origine | tag | avec `minio_url` | sans |
|---|---|---|---|
| HTML | `Picture` | **199** | **0** |
| HTML | `Table` | 0 | **52** |
| PDF | `Picture` | **10** | 0 |
| PDF | `Table` | **3** | 0 |

Les 52 sommets que `verify_contract` rapporte sont donc **52 tables HTML sur
52**, et la chaîne d'images HTML du §3.5 est **entièrement fermée** — 199 sur
199, contre 0 sur 199 mesurés par le lot 1 sur le producteur.

Les deux sites :

- `extraction.propager_les_url_dimages` **exclut délibérément** les tables, et
  son docstring dit pourquoi : « Seuls les `picture` sont ciblés… un `table` est
  visuel mais n'est pas une `<img>` du HTML. Le compter décalerait toutes les
  URL. » Une table HTML est rendue par Docling en Markdown — les 52 textes
  commencent tous par `|` — il n'y a **aucune image à téléverser** ;
- `verify_contract._lire_les_urls_visuelles` lit `minio_url` sur les sommets
  `Picture` **et** `Table`, et compte l'absence comme une anomalie.

**Ce n'est pas le §3.5 rouvert.** C'est un instrument dont le dénominateur
englobe une catégorie que la chaîne qu'il mesure n'alimente pas.

> **LE PARTAGE EST LE BON ; LA FORMULATION PEUT ÊTRE PLUS PRÉCISE, et c'est le
> compteur qu'elle vise.** Ce constat se lit comme si le tort du contrôle était
> de **compter les tables**. Ce n'en est pas un : `mesuré` le 3 septembre 2026
> sur le graphe vivant — **55 sommets `Table`**, dont **3 portent une URL
> réelle**, et ce sont les trois tables du **PDF**.
>
> **Le tort du compteur est de FUSIONNER DEUX CHEMINS sous un seul
> dénominateur**, pas de compter une catégorie de trop. La chaîne PDF
> (`images.py`) téléverse un crop pour ses tables ; la chaîne HTML n'a rien à
> téléverser pour les siennes, une table HTML étant du Markdown. Le contrôle
> additionne les deux et rapporte un manque là où il n'y a **qu'un chemin sur
> deux** qui devait pourvoir.
>
> **Et « le texte commence par `|` » n'est pas le discriminant non plus** : sur
> les 3 tables du PDF qui portent une URL, **2 commencent aussi par `|`**
> (`mesuré`). Ce qui discrimine est le **chemin d'origine**, lisible en remontant
> la chaîne `PARENT_OF` jusqu'au document — ce qui est exactement ce que la
> première branche de l'arbitrage ci-dessous demande de savoir faire.
>
> Ce qui reste inchangé, et qui est le cœur du constat : **ne pas retirer `Table`
> du contrôle**. Les 3 tables du PDF portent une URL réelle, et cesser de les
> vérifier ouvrirait un angle mort là où la chaîne fonctionne.

**La forme du garde à écrire, et la décision qui la précède.** La décision
n'appartient pas à une branche : soit le contrôle borne son dénominateur à ce que
la chaîne téléverse — `Picture` sur le chemin HTML, `Picture` et `Table` sur le
chemin PDF, ce qui demande de connaître le chemin depuis le graphe — soit il
garde son dénominateur et **dit** que les tables HTML n'en portent jamais, en
sortant 0. Le garde, dans les deux cas : un témoin qui compte les deux
catégories séparément, sans quoi un contrôle qui les fusionne resterait vert sur
une vraie perte d'image HTML. **Ce qu'il ne faut PAS faire est de retirer
`Table` du contrôle** : les 3 tables du PDF portent une URL réelle, et cesser de
les vérifier ouvrirait un angle mort là où la chaîne fonctionne.

#### 4.32.c `make lint` et `make format-check` ne voient pas `scripts/`, le hook si

La divergence de portée de la famille **D7**, une nouvelle fois, et à un
troisième endroit. `make lint` et `make format-check` portent sur `src/ tests/` ;
le hook `ruff` voit **tout ce qui est indexé**, donc `scripts/`. `mesuré` le
2 septembre 2026 : `ruff format --check src/ tests/` voit **74** fichiers,
`src/ tests/ scripts/` en voit **77**.

Le dépôt portait déjà `scripts/capturer-larbre-docling.py` et
`scripts/installer-les-garde-fous.sh` dans cet angle ; le lot 6 y ajoute deux
fichiers Python. **`ruff` n'en voit que TROIS**, et ce sont les trois `.py` :
`installer-les-garde-fous.sh` est du **shell**, que `ruff` ne lit pas. *(Ce
paragraphe écrivait « les quatre passent `ruff check` » — un fichier qu'un outil
ne lit pas ne « passe » pas cet outil ; il en est hors de portée, ce qui est un
état différent et moins rassurant.)* Les trois passent `ruff check` et
`ruff format --check` — `mesuré` le 3 septembre 2026, « All checks passed! » et
« **3** files already formatted » —, **et la porte ne le dira pas à la place du
suivant** : un script qui
dériverait serait déclaré propre par `make all` et refusé au commit, avec le
message qui arrive au mauvais moment — exactement le récit de D7 et celui des
deux commits du lot 4 refusés pour des règles que `make all` venait de déclarer
propres.

**La forme du geste**, et c'est un geste et non un garde : étendre les deux
cibles à `scripts/`. Le coût est mesuré et nul — les fichiers sont déjà propres.
Ce qui l'a retenu ici est le périmètre : changer la portée de la porte qualité
n'est pas le mandat d'une campagne de mesure, et le §5.4 montre qu'un changement
de portée mérite d'être décidé, pas glissé.

**ET LA MÊME DÉCISION DE PORTÉE EN PORTE UNE SECONDE, PLUS COÛTEUSE :
`scripts/campagne/verifier-le-jeu-de-questions.py` n'est appelé par RIEN.**
`mesuré` le 3 septembre 2026 —
`grep -rn 'verifier-le-jeu-de-questions' Makefile .pre-commit-config.yaml
pyproject.toml $(git ls-files '*.sh')` rend **`rc=1`, aucune occurrence**.

Ce script est le seul garde de la **provenance** du jeu de 30 questions : il
relit chaque ancrage dans l'index vivant et sort en 1 au premier désaccord. Il
rougit vraiment — trois mutations le prouvent (compte rendu §6.3). Mais rien ne
le déclenche.

La justification écrite au compte rendu — `chromadb` n'est pas dans le venv du
dépôt — explique pourquoi ce n'est pas un **test**. Elle n'explique ni pourquoi
ce n'est pas une **cible `make`**, ni pourquoi ce n'est pas une ligne de
procédure d'avant-campagne : ces deux-là peuvent lancer le geste du §4.27, comme
la campagne l'a fait.

**En l'état, le jour où le corpus est renommé ou réingéré, `make all` reste vert
et le jeu de questions devient faux en silence** — exactement ce que le script
existe pour empêcher, et exactement la famille « un garde-fou qui repose sur la
mémoire du suivant n'est pas un garde-fou ». **À trancher avec le geste
ci-dessus : c'est la même décision.**

#### 4.32.d Tout le lot 5 est daté du 3 septembre 2026, et aucun commit du dépôt ne l'est

C'est la famille que le lot 5 existe pour fermer, appliquée à la trace qu'il a
laissée de lui-même. Elle est **inerte** — aucune décision n'en dépend — et elle
est consignée parce qu'un chantier qui étiquette ses mesures par une date ne peut
pas se permettre que la date soit fausse.

`mesuré` le 2 septembre 2026 :

| Ce qui est écrit | Ce que git dit |
|---|---|
| « Dernière mise à jour : 3 septembre 2026, après la fusion du lot 5 » (mandat) | `d8c67c5` porte `2026-09-02 12:29:51 +0000` en auteur **et** en committer |
| « Le lot 5 a été fusionné le 3 septembre 2026 » (mandat §5.1, §5.1 sexies, §8 du registre) | idem |
| « `mesuré` le 3 septembre 2026 » sur les cinq points du §7.2 | l'horloge du poste rendait `2026-09-02 12:40 UTC` au début du lot 6 |

Commandes : `git log -1 --format='%ai %ci' main`, `date -u`, et
`git log --format='%ad' --date=short | sort -u`, qui rend **14** dates distinctes
— de `2026-04-29` à `2026-09-02` —, dont **six** dans la plage `2026-08-03` →
`2026-09-02` que ce constat citait, et **aucune** au 3 septembre. *(Cette ligne
écrivait « qui rend six dates » : six est le compte de la plage du chantier, pas
ce que la commande rend. Une commande citée doit rendre le chiffre qu'on lui
prête, sans quoi le lecteur qui la rejoue croit avoir trouvé une divergence.)*

**L'écart total est de neuf mentions** : `git grep -c '3 septembre 2026'` rend
**7** au mandat et **2** au registre.

**Ce que la campagne en a fait** : elle a daté **toutes** ses mesures du
2 septembre 2026, celle de l'horloge du poste, et l'a écrit en tête de son
compte rendu. Les neuf mentions ne sont **pas** corrigées ici — corriger la date
d'un lot fusionné dans les deux documents de gouvernance est un geste de pilote,
pas de branche, et le §4.28.e pose la règle : « il n'appartient pas à une
branche de réécrire le plan ». La part de ce lot est d'écrire la mesure pour que
le pilote l'ait sous les yeux.

**Il n'y a pas de garde à écrire pour celui-ci, et c'est le point.** Aucun test
ne peut vérifier qu'une date écrite en prose est celle du commit qu'elle décrit.
Ce qui peut se faire est plus étroit et plus utile : **prendre la date du poste
au moment de mesurer** — `date -u` — plutôt que de la déduire du contexte. Le
§4.31.N le dit déjà pour les états de poste ; il vaut aussi pour la date qui les
étiquette.

---

### 4.33 → CONSIGNÉ par le lot 8 et sa réparation — le **a** et le **c** sont TRAITÉS par le lot 9

**Cinq** constats, tous mesurés, laissés **hors du diff par le lot 8**. Périmètre
strict. Le compte est `calculé`, `grep -c '^#### 4.33'` rend cinq. Les deux
premiers viennent du lot 8 lui-même ; les trois suivants de sa réparation, le
22 septembre 2026. Le `c` était le plus urgent des cinq, et il portait sa forme
de garde : **il devait être tranché avant le premier geste de réingestion réel.**

**ÉTAT AU 22 SEPTEMBRE 2026, APRÈS LE LOT 9 : deux sur cinq sont traités**, le
`a` et le `c` — et le `c` l'est **avec sa borne écrite**, parce qu'il n'est fermé
que du côté du marqueur. Restent ouverts le `b` (un geste de campagne, pas un
développement), le `d` et le `e`. Le compte est `calculé` :
`grep -c '^#### 4.33.* → TRAITÉ'` rend deux.

#### 4.33.a → TRAITÉ par le lot 9 — le `README` justifiait la purge de `Datas/.cleaned/` par un mécanisme qui n'existe pas

La section « Ré-ingérer proprement » range `Datas/.cleaned/` parmi les quatre
purges avec ce motif, mot pour mot : « le HTML nettoyé porte les URL MinIO des
images, et **l'asset `cleaned_html` ne se rematérialise pas si son fichier
existe déjà** : une purge suivie d'une réingestion repartait du HTML périmé ».

La seconde moitié de la phrase est fausse sur le code livré. `mesuré` le
22 septembre 2026, par lecture : `clean_html_file`
(`src/pipeline/cleaning.py:627-631`) lit la source, nettoie, **écrit
inconditionnellement** la destination ; l'asset `cleaned_html`
(`src/pipeline/factory.py`) l'appelle sans condition. `grep -rn "exists()"` sur
`src/pipeline/cleaning.py` et `src/pipeline/factory.py` rend **deux** lignes, et
aucune ne porte sur la destination du nettoyage : ce sont les deux contrôles
d'existence de la **source**, aux assets `cleaned_html` et `extracted_document`.
Il n'y a **aucun** court-circuit « le fichier nettoyé existe, on ne refait pas ».

**Pourquoi ce n'est pas qu'une phrase à corriger.** La purge de `.cleaned/` est
la seule des quatre dont la nécessité repose entièrement sur cette
justification. Si elle est fausse, deux lectures restent possibles, et le lot 8
n'a pas tranché entre elles : ou bien la purge de `.cleaned/` est inutile et le
`rmtree` le plus risqué du dépôt — celui dont le registre §4.29.a raconte qu'un
réglage mal posé emportait 24 des 25 fichiers du corpus versionné — ne sert à
rien ; ou bien elle est nécessaire pour une **autre** raison, qui n'est écrite
nulle part. Les deux demandent une réponse, et ce n'est pas la même.

**La forme du garde à écrire.** La propriété est *« une seconde matérialisation
de `cleaned_html` réécrit sa destination »*, et son témoin, sans lequel le garde
serait creux : *une destination au contenu différent doit être remplacée, pas
laissée en place*. Le harnais existe déjà —
`TestLeNettoyagePublieCeQuIlAJete._executer` appelle le corps livré de l'asset
sur un `tmp_path`. Ce qui manque est un second appel et une assertion sur le
fichier écrit, pas un montage.

**CE QUE LE LOT 9 A TRANCHÉ, ET C'EST LA SECONDE LECTURE : la purge est
NÉCESSAIRE, pour une raison que personne n'avait écrite.** Les deux mesures sont
du 22 septembre 2026, sur des copies temporaires, en appelant le corps livré de
l'asset :

1. **la phrase est fausse**, confirmé par la mesure et plus seulement par la
   lecture : une destination remplie d'un contenu périmé est **réécrite**, et
   l'octet rendu est celui du premier nettoyage ;
2. **ce que la purge retire, et elle seule, ce sont les ORPHELINS** : deux
   documents nettoyés, la source de l'un retirée du corpus, l'autre
   rematérialisé — la copie nettoyée du document disparu est **toujours là**.

Rien ne la relit, rien ne l'efface, et c'est borné par un troisième test : le
glob d'une source est ancré sous son propre sous-répertoire (`htms/**/*.html`),
et `.cleaned` porte de surcroît un point de tête que `glob` n'ouvre jamais, même
derrière `**` ; `cleaned_html` ne peut pas s'exécuter pour elle, son contrôle
d'existence portant sur la **source**. Et un orphelin est périmé **sans
recours** : il porte les URL MinIO de ses images, la purge du bucket — trois
blocs plus haut dans le même `main()` — vient de supprimer les objets qu'elles
désignent, et `cleaned_html` est le seul chemin qui les re-téléverse (`mesuré`
par la campagne du 2 septembre 2026 : 0 objet avant le geste 3, 199 après).

Sans cette purge, `wipe_stores` laisserait donc derrière lui **le seul artefact
dérivé qui porte des URL MinIO mortes** pour un document que le corpus n'a plus.

*(Cette phrase a d'abord été écrite « le seul endroit du système qui décrive
encore un document que le corpus n'a plus », à trois sites, et la passe de
relecture du lot 9 l'a mise en défaut sur son propre dépôt : la partition
dynamique Dagster de ce document survit elle aussi, et `wipe_stores` n'y touche
pas. C'est le §4.34.g, et c'est la septième fois que ce registre attrape une
phrase d'exhaustivité — celle-ci écrite par le lot qui les traque.)*

Le garde est `TestCeQueLaPurgeDuNettoyeRetireVRAIMENT`
(`tests/unit/test_factory.py`) et il tient les **deux** natures — une seule
serait creuse. Mutations : un court-circuit `if not dest_path.exists()` devant le
`write_text` de `clean_html_file` → **1 rouge** ; `shutil.rmtree(cible)` → `pass`
→ **14 rouges**, dont l'orphelin.

**ET LA BORNE DU `rmtree` A ÉTÉ RESSERRÉE AU PASSAGE.** `purge_cleaned` est une
fonction **publique**, et son containment acceptait toute cible contenue dans la
racine — dont `Datas/htms`, qui portait 24 des 25 fichiers du corpus versionné.
Le réglage qui produisait ces valeurs est mort avec le lot 5 ; le garde, lui, ne
tenait plus que par la constante de son appelant. La cible doit désormais être
`SOURCE_DIR/.cleaned` ou l'un de ses descendants, par un refus **distinct**
(`CibleHorsDuNettoyeError`). La forme nominale est comparée **non résolue** :
la résoudre ferait suivre au garde le même lien que la cible, et un `.cleaned`
qui serait un lien vers `Datas/htms` résoudrait des deux côtés vers la même
chose. Le test `test_une_cible_profondement_contenue_est_acceptee` visait
`Datas/a/b/c` et se justifiait par « une cible légitime si le réglage la
désigne » — ce réglage n'existe plus ; il est rétréci au contrat que le code
compose vraiment, et son témoin conservé.

#### 4.33.b La stabilité des `element_id` à travers une réingestion est prouvée à moitié, et la moitié manquante est celle du convertisseur

Le lot 8 devait répondre en lecture seule à : *les 44 `element_id` que le jeu de
30 questions désigne survivent-ils à une réingestion ?* La réponse complète vit
à son rapport. Ce qui doit rester au registre est la **borne** :

- **prouvé par lecture** : `compute_id`
  (`src/docling_service/elements.py:200-217`) ne prend ni le `mtime`, ni la
  date, ni le moindre compteur global. Ses quatre entrées sont la clé du
  document, le numéro de page, le rang dans la page et les 50 premiers
  caractères du texte. Rien dans la formule ne périme ;
- **prouvé par mesure**, le 22 septembre 2026, sur les 22 HTML du corpus : deux
  passes du nettoyage rendent le **même octet** (22/22), et surtout le texte
  extrait, le nombre de balises et le nombre de `<img>` du HTML rejoué sont
  identiques à ceux de la copie `.cleaned/` produite le 2 septembre — 22/22 sur
  les trois. Ce que cette mesure prouve est donc **le texte**, et lui seul,
  parmi les quatre entrées de `compute_id`. **Le rang n'en est pas** :
  `position_in_page` n'est pas fourni par le HTML, c'est un compteur tenu sur
  l'itération de Docling (`src/docling_service/elements.py:393-394`). Un HTML
  identique à l'octet rend l'**entrée** du convertisseur identique, pas
  l'**ordre** de sa sortie — ce que la puce suivante déclare justement non
  prouvé. La première rédaction de cette puce comptait le rang parmi les acquis,
  et mettait donc les deux en contradiction : elle donnait pour mesuré le seul
  point que ce constat existe pour laisser ouvert ;
- **NON prouvé, et non prouvable sans réingérer** : que Docling, pour un même
  fichier, rende la même segmentation — mêmes items, même ordre, mêmes pages.
  C'est une propriété du **convertisseur et de ses modèles**, pas du dépôt, et
  elle est hors d'atteinte du venv de l'hôte. Elle est surtout la seule qui
  porte sur le PDF, où l'OCR entre en jeu et où `pages_skipped` et
  `failed_batches` existent précisément parce que la conversion peut échouer
  **par endroits** — un lot de pages perdu à une ingestion et pas à l'autre
  retire ses éléments sans déplacer ceux des autres pages, mais il les retire.

**Ce qui la fermera, et il existe déjà** :
`scripts/campagne/verifier-le-jeu-de-questions.py` relit chaque ancrage dans le
store et sort en `1` au premier désaccord. Le lot qui réingère doit le lancer
**avant** et **après**, et consigner les deux sorties. C'est un geste, pas un
développement.

#### 4.33.c → TRAITÉ par le lot 9, et la borne est écrite — aucune garde « une réingestion est déjà en vol »

**À trancher AVANT le premier geste de réingestion réel.** C'est le seul des
cinq qui puisse coûter des données.

Le capteur de source n'a **aucune** garde de concurrence. Un second marqueur,
étiquette neuve, posé pendant qu'une réingestion tourne encore, produit un
**second jeu complet** de demandes de run — clés neuves, donc aucun refus de
Dagster, donc des runs réellement créés. Le dépôt porte pourtant le patron
exact, écrit avec son motif : `src/pipeline/reindex_job.py:356-368` interroge
`RunsFilter(job_name=..., statuses=STATUTS_EN_COURS)` et rend un `SkipReason`
nommé — « une réindexation en vol n'est ni faite ni perdue : on attend son
issue ».

**Ce n'est pas théorique, et c'est `mesuré`.** `pdfs_sensor` ne porte qu'**un**
fichier — donc une seule partition — et `dagster.yaml` fixe
`max_concurrent_runs: 2` **sans aucune clé de concurrence par partition**. Deux
runs simultanés sur la **même** partition sont donc atteignables. Ils écriraient
tous les deux `Datas/.cleaned/<fichier>`, en même temps.

**La forme du garde à écrire.** La propriété est *« un marqueur lu alors qu'un
run de ce job est non terminal n'émet aucune demande, et le dit »*, et son
témoin, sans lequel le garde serait creux : *le même marqueur, une fois le run
précédent terminal, doit émettre ses demandes* — sinon un garde qui refuse
toujours rendrait la réingestion impossible, c'est-à-dire le §4.32.a par l'autre
bout. Le curseur ne doit pas être consommé par le tick qui refuse, sans quoi le
geste serait perdu au lieu d'être différé. Le harnais existe :
`TestLeTickQuiPerdSesRunsLeDit._instance_avec_les_cles` peuple déjà une instance
éphémère de runs tagués ; ce qui manque est un statut non terminal, pas un
montage.

**CE QUE LE LOT 9 EN A FAIT.** Le marqueur lu pendant qu'un run **de ce job** est
non terminal rend un `SkipReason` nommé, qui décrit le run en vol et son âge. Le
filtre porte sur le **job**, donc sur tout run de la source — une réingestion
précédente comme une ingestion nominale — et le message dit donc « une
**ingestion** est déjà en vol » : ce qui est dangereux n'est pas « deux
réingestions », c'est deux runs sur la même partition, et nommer le mauvais
coupable enverrait l'opérateur chercher un second marqueur qu'il n'a pas posé.

**Le mode de panne de ce garde est celui du §4.15, et il en partage l'issue.** Un
run coincé en `STARTED` n'est jamais terminal, donc le refus se répéterait. Ce
n'est pas indéfini : `dagster.yaml` arme `run_monitoring` avec un
`max_runtime_seconds` posé juste au-dessus du plafond que le pipeline s'accorde
lui-même, et le daemon marque alors le run en échec. Le prix est donc **borné, et
haut** — **25 h** au pire, soit le `max_runtime_seconds` de 90 000 s, et **non** les 24 h de `extraction_timeout_seconds`, qui borne le *pipeline* par document et non le *run monitoring* —, ce qui est écrit au site plutôt que laissé à découvrir. Le
refus est un `SkipReason` et non un `SensorResult` vide, parce qu'un résultat
vide porterait `skip_reason=None` — le silence exact du §4.32.a. Et parce que
c'est un `SkipReason`, `update_cursor` n'est pas atteint : **le marqueur reste en
place et le tick suivant le relira.** Le geste est différé, pas perdu.

`STATUTS_EN_COURS` et `_decrire_le_run` sont **importés** de `reindex_job` et non
recopiés : le premier se définit par soustraction des trois états terminaux, et
une seconde énumération classerait comme terminé tout statut que Dagster
ajouterait. Le sens de l'import est sûr — `reindex_job` ne connaît que les *noms*
des jobs d'ingestion, passés par `definitions.py`.

Quatre natures sont échantillonnées, et il en faut quatre : le refus ; le témoin
(*la même étiquette, une fois le run terminal, émet ses demandes* — sans lui le
garde serait le §4.32.a par l'autre bout) ; le marqueur non consommé ; et un run
d'un **autre** job qui ne bloque rien, sans quoi la réindexation bloquerait la
réingestion. Mutations : `if en_vol:` → `if False:` → **3 rouges** ; le
`SkipReason` remplacé par un `SensorResult` vide → **2 rouges** ;
`RunsFilter(job_name=job_name, …)` → `RunsFilter(…)` → **1 rouge** ;
`statuses=list(STATUTS_EN_COURS)` → `statuses=None` → **5 rouges**.

**LA PORTÉE EST LE MARQUEUR, et un cinquième test l'écrit** plutôt que de le
laisser croire : *le chemin nominal n'est **pas** gardé*. Il n'en a pas besoin
pour ne pas repartir — sa clé est `(source, partition, mtime)` — mais un fichier
**modifié** pendant une réingestion produit bien une clé neuve sur une partition
en vol. Ce cas reste **ouvert** : voir §4.34.a.

`_instance_avec_les_cles` créait des runs `NOT_STARTED`, c'est-à-dire **en vol**,
alors qu'elle modélise une ingestion **passée**. Le défaut ne gênait pas tant que
rien ne regardait les statuts ; la garde les regarde, et elle skippait donc
quatre tests au lieu de les laisser mesurer ce qu'ils mesurent. Le statut est
désormais terminal, et le motif est écrit à la fixture.

#### 4.33.d Les trois copies de la prose du geste de réingestion ne sont tenues par rien

La même prose vit à **trois** endroits : le bloc au-dessus de
`PREFIXE_REINGESTION` dans `src/pipeline/factory.py`, le tableau de la section
« Ré-ingérer proprement » du `README.md`, et ce §4.32.a. Rien ne garde leur
concordance. La réparation du 22 septembre l'a vérifié en le vivant : la
justification par le mauvais scénario était écrite au site du code **et** dans
le tableau du `README`, dans des mots différents, et le registre n'en disait
rien du tout. Il a fallu redresser les trois à la main, un par un, sans qu'aucun
test ne signale ceux qui restaient.

Le tableau du `README` n'est gardé par **rien** en particulier : `mesuré`, une
reformulation qui le rendrait faux laisse la suite entièrement verte. Les deux
gardes existants (`TestLaDocumentationNommeLeGesteQuExisteVraiment`) vérifient
que le `README` **nomme** le marqueur et les capteurs — pas ce qu'il en **dit**.

**La forme du garde à écrire, et elle est modeste.** Garder la concordance
littérale de trois proses est un piège : le garde deviendrait un frein à toute
reformulation. Ce qui se garde utilement est le petit nombre de **faits
vérifiables** qu'elles partagent — le préfixe (déjà gardé), la liste des
capteurs (déjà gardée), et la forme des **deux** clés, nominale et marquée, que
`TestLaCleNominaleEstInchangee` et `TestLaCleDeReingestionNePorteQueLEtiquette`
figent désormais côté code. Ce qui manque est de faire **lire ces deux formes au
`README`** plutôt que de les y recopier : un garde qui construit la clé par le
capteur et exige la chaîne dans le `README`, comme le garde du préfixe le fait
déjà pour la constante.

#### 4.33.e `pre-commit run --all-files` échoue sur `main` déjà, et ce n'est imputable à aucun lot

`mesuré` le 22 septembre 2026, sur `main` (`db8e7b5`) :
`documentation/stockage_objets.md` porte **une** ligne à espace terminal (la 29),
et le hook `trailing-whitespace` la refuse — `rc=1`, « files were modified by
this hook ». Il ne se contente pas de refuser : **il écrit**.

Ce n'est imputable à aucun lot récent, et c'est précisément ce qui le rend
piégeux. Le défaut est **hors de portée de `make all`**, dont les cibles ne
regardent que `src/` et `tests/`, et **invisible des hooks**, qui ne voient que
ce qui est **indexé** — ce fichier n'a été touché par aucun commit depuis que le
framework est installé. Quiconque lance un balayage `--all-files` pour vérifier
l'état du dépôt conclura que `main` est cassé, et cherchera la cause du mauvais
côté.

C'est le même angle mort que le D7 du registre, déplacé une fois de plus : deux
gardes qui voient des choses différentes. La correction est d'une ligne ; ce qui
mérite d'être consigné est **pourquoi personne ne l'a vue**.


---

### 4.34 → CONSIGNÉ par le lot 9 — NON traité

**Sept** constats, tous mesurés le 22 septembre 2026, laissés **hors du diff**.
Périmètre strict. Le compte est `calculé`, `grep -c '^#### 4.34'` rend sept. Le
`a` est le plus coûteux des sept, et c'est la moitié du §4.33.c que le lot 9 n'a
pas fermée. Le `g` est le seul des sept qui ne vienne pas du mandat : il vient de
la passe de relecture, qui a mis en défaut une phrase que le lot 9 venait
d'écrire.

#### 4.34.a Le chemin NOMINAL du capteur n'a pas de garde de concurrence, et la vraie racine est dans `dagster.yaml`

La garde du §4.33.c porte sur le **marqueur**, et le lot 9 l'a bornée par un test
plutôt que par une phrase (`test_le_chemin_nominal_n_est_pas_garde_et_c_est_borne_expres`).
Ce qu'elle ne couvre pas : **un fichier modifié pendant une réingestion**. Son
`mtime` change, donc sa clé est neuve, donc le run est réellement créé — sur une
partition dont un run est peut-être encore en vol. C'est la **même** collision,
par l'autre porte.

**Pourquoi le lot 9 ne l'a pas fermée.** Bloquer le chemin nominal derrière une
réingestion de plusieurs heures rendrait invisible tout dépôt de fichier pendant
ce temps, et un capteur qui ne détecte plus est exactement ce que le §4.32.a
punissait. Le geste juste n'est pas dans le capteur.

**Il est dans `dagster.yaml`, et il y manque.** `mesuré` : le fichier fixe
`max_concurrent_runs: 2` et ne porte **aucune** clé `tag_concurrency_limits`.
Deux runs simultanés sur la **même** partition sont donc autorisés par la file
elle-même, quelle que soit la prudence des capteurs. Une limite de concurrence
**par partition** fermerait la famille entière d'un geste, capteurs compris, là
où le §4.15 a déjà mis le délai de garde « pour que la famille entière se ferme
d'un geste ».

**Ce n'est pas un développement de branche, c'est un réglage de déploiement** :
le démon tourne, `src/` du clone principal est monté dedans, et fusionner est un
déploiement. Un réglage de file qui changerait le comportement de la production
dans la minute qui suit une fusion mérite d'être décidé, pas glissé.

#### 4.34.b Un curseur qui n'est pas du JSON repart toujours à zéro, et redemande tout

Le lot 9 a nommé les curseurs **JSON mais pas curseurs** sans les rendre muets.
Il n'a **pas** touché la branche voisine : `except json.JSONDecodeError` →
`context.log.warning("Invalid cursor format, resetting.")` → `cursor_data = {}` →
**tout le corpus est redemandé**.

Cette branche a la propriété que le §4.33 met en garde contre : elle transforme
un curseur illisible en réingestion complète. Elle est moins grave que l'était
l'autre — elle **avertit**, et les clés reconstruites sont les clés nominales,
donc l'historique les refuse et le §4.32.a le dit avec son compte. Elle reste
une remise à zéro décidée par le code et non par un humain.

**Elle n'est pas traitée parce que c'est le comportement de premier tick**, et
qu'un curseur absent est indistinguable ici d'un curseur corrompu. Les séparer
demande de savoir si le capteur a déjà tourné, c'est-à-dire de regarder ailleurs
que dans le curseur. C'est une décision, pas une correction.

#### 4.34.c Rien ne compte ni ne nomme les orphelins de `Datas/.cleaned/`

Le §4.33.a établit que les orphelins sont **la seule** chose que la purge
retire. Personne ne sait combien il y en a. `wipe_stores` imprime « N fichiers
retirés », un total qui ne distingue pas la copie d'un document vivant de celle
d'un document disparu, et aucun autre outil ne regarde ce répertoire.

`mesuré` par la campagne du 2 septembre 2026 : `Datas/.cleaned/` portait **22**
fichiers pour **22** HTML au corpus — **zéro orphelin** ce jour-là. C'est un état
de poste, il périme, et rien ne le remesure.

**Le geste utile est petit** : compter, à la purge, les fichiers de `.cleaned/`
dont la source n'existe plus, et les nommer. Un opérateur qui lit « 22 fichiers
retirés, dont 0 orphelin » apprend que son corpus et ses copies nettoyées sont
en accord ; « dont 7 orphelins » lui apprend que sept documents ont quitté le
corpus sans que personne ne l'ait noté.

#### 4.34.d `set(files)` est reconstruit à chaque itération du journal des écartés

`src/pipeline/factory.py`, dans le capteur :

```python
ecartes = [os.path.relpath(f, source_dir) for f in discovered if f not in set(files)]
```

`set(files)` est dans la **condition**, donc réévalué pour chaque élément de
`discovered` — un coût quadratique là où un ensemble construit une fois donnerait
un coût linéaire.

**Inerte sur ce corpus, et c'est pourquoi il n'est pas traité** : `discovered`
vaut 22 pour `livres_html` et 1 pour `pdfs`. Le constat est écrit parce qu'un
corpus de quelques milliers de fichiers le rendrait visible à chaque tick, et
parce que la ligne se lit comme si l'ensemble était construit une fois.

#### 4.34.e Le §4.33.e est toujours vrai, et il est désormais BORNÉ

`mesuré` le 22 septembre 2026, sur la branche du lot 9 :
`git grep -c ' $' -- '*.md'` rend **un seul fichier**,
`documentation/stockage_objets.md`, avec **une seule** ligne — la 29. C'est donc
la **seule** ligne à espace terminal de tout le Markdown du dépôt, et le hook
`trailing-whitespace` la refuse toujours sur un `pre-commit run --all-files`.

Ce que cette borne ajoute au §4.33.e : la correction n'est pas « une ligne parmi
d'autres à chercher », c'est **cette** ligne, et il n'y en a pas d'autre. Le lot
9 ne la corrige pas — périmètre strict, et le fichier n'a rien à voir avec son
mandat — mais le suivant sait exactement où il va.

#### 4.34.f Le §4.33.d a coûté un troisième redressement manuel, et rien ne le garde toujours

La prose du geste de réingestion vit à **trois** endroits : le bloc au-dessus de
`PREFIXE_REINGESTION`, le tableau « Ré-ingérer proprement » du `README.md`, et le
§4.32.a. La garde de concurrence du §4.33.c ajoute un cas au geste — « si une
réingestion tourne déjà » — et le lot 9 a donc dû écrire la même chose **trois
fois, à la main**, comme la réparation du lot 8 l'avait fait avant lui.

Rien ne signale celui qu'on oublie. Le §4.33.d porte déjà la forme du garde à
écrire — faire **lire** au `README` les formes construites par le capteur plutôt
que de les y recopier — et elle reste à écrire. Ce constat ne la répète pas : il
en compte la **troisième** occurrence, parce qu'un constat qu'on paie trois fois
n'est plus un constat, c'est un coût.

#### 4.34.g La partition dynamique d'un document retiré du corpus n'est jamais supprimée

Trouvé en relisant le lot 9 lui-même. Le §4.33.a écrivait, à trois sites, que
`Datas/.cleaned/` serait « **le seul endroit du système** qui décrive encore un
document que le corpus n'a plus ». **C'est faux, et c'est une phrase
d'exhaustivité exactement du genre que ce registre traque.**

`mesuré` le 22 septembre 2026, et **ceci est le site canonique du chiffre** — la
commande est donnée ici et nulle part ailleurs, pour qu'aucun docstring citant
son motif ne la fasse mentir :

```bash
grep -rn 'build_delete_request' src/ | wc -l    # rend 0
```

Aucun appel de suppression de partition dynamique n'existe dans le dépôt. Quand
un document quitte le corpus :

- sa **partition dynamique** Dagster reste déclarée, donc visible dans
  l'interface, et sélectionnable pour une matérialisation ;
- son **historique de matérialisations** reste, avec ses métadonnées ;
- `wipe_stores` ne touche ni l'un ni l'autre — il purge trois stores et le HTML
  nettoyé, pas le stockage Dagster.

**Ce que cela change au §4.33.a, et rien de plus** : la purge de `.cleaned/`
retire le seul artefact dérivé qui porte des **URL MinIO mortes**, ce qui reste
sa raison d'être et ce que le garde tient. Elle n'assainit pas le système entier,
et le §4.33.a ne le prétend plus.

**Pourquoi ce n'est pas traité ici.** Supprimer une partition dynamique est une
perte d'historique irréversible, et la décision n'appartient pas à un capteur :
un fichier absent d'un tick peut l'être parce qu'il a été retiré, ou parce qu'un
montage n'était pas là. Le §4.26 raconte déjà ce que coûte un état perdu qu'on
croyait dérivable. Le geste juste est probablement un **rapport** — nommer les
partitions dont la source a disparu — avant toute suppression, et il rejoint le
§4.34.c : personne ne compte les orphelins, sous aucune de leurs deux formes.


### 4.35 → CONSIGNÉ par la réparation du lot 9 — le **a** est TRAITÉ, les quatre autres NON

Cinq constats, mesurés le 23 septembre 2026. Le `a` est le seul qui entre au
diff ; les quatre autres sont **hors du diff**, périmètre strict. Le compte est
`calculé`, `grep -c '^#### 4.35'` rend cinq.

#### 4.35.a → TRAITÉ — la durée annoncée était celle d'un **autre** plafond, à trois sites

`max_runtime_seconds: 90000` vaut **25 h**, pas 24. Les 24 h sont celles
d'`extraction_timeout_seconds` (86 400 s), qui est le plafond que le **pipeline**
s'accorde par document — pas celui du **run monitoring**. Et le passage se
contredisait dans son propre paragraphe : `dagster.yaml` explique, dix lignes
plus haut, que `max_runtime_seconds` est posé « JUSTE AU-DESSUS » du plafond du
pipeline, puis trois sites annonçaient comme prix ce plafond même.

**Six sites nommaient une de ces deux durées en heures**, et la correction n'a
pas été bornée aux trois que le mandat citait — c'est la leçon du §4.31.
`mesuré` sur `f124512`, et **ceci est le site canonique du chiffre** :

```bash
git grep -nIE -e '(24|25)[ _]?h\b' f124512 -- ':!Datas' ':!uv.lock'   # rend 6
```

Trois étaient **faux** et sont corrigés — `README.md:351` (tableau du capteur de
réingestion), ce registre au §4.33.c, et `src/pipeline/factory.py:729` (le
commentaire du garde du run en vol). Trois étaient **justes** et n'ont pas
bougé : `dagster.yaml:79`, `src/pipeline/settings.py:45` et
`documentation/orchestration.md:62` parlaient bien du plafond du pipeline. Les
trois du mandat étaient donc bien tous les faux, et rien de plus.

L'arithmétique est désormais écrite **une fois**, au site qui porte la valeur :

    max_runtime_seconds          90 000 s = 25 h 00
    extraction_timeout_seconds   86 400 s = 24 h 00
    écart                         3 600 s =  1 h 00   ← DÉLIBÉRÉ

**ET LA BORNE N'ÉTAIT GARDÉE QUE PAR EN DESSOUS.** `mesuré` par l'audit, et
rejoué : `max_runtime_seconds` porté à **500 000** rendait `rc=0` et **925
verts, zéro rouge** ; porté à **3 600**, il rendait **1 rouge**. La borne ne
pouvait pas descendre sous le plafond du pipeline, mais elle pouvait être
multipliée par 5,5 sans qu'un test bronche — alors que le fichier de test
affirmait, en toutes lettres, être « le seul garde du dépôt qui rougirait si
l'un des deux réglages bougeait sans l'autre ». Vrai vers le bas, **faux vers le
haut** : c'est la huitième phrase d'exhaustivité que ce registre attrape.

Deux gardes la ferment, et **la raison de chaque forme est écrite au site**.

`test_la_borne_reste_juste_au_dessus_du_plafond_du_pipeline` tient la
**propriété**, pas la valeur. Une égalité à 90 000 rougirait aussi bien pour un
ajustement légitime que pour un changement de nature, sans distinguer les deux,
et se recopierait sans qu'on y pense. Ce que `dagster.yaml` revendique est que
la borne soit posée *juste au-dessus* du plafond du pipeline, **parce qu'elle
est la dernière ligne et non un second plafond** — et c'est cela qui se perd
quand elle dérive. Le seuil est un **dixième** du plafond du pipeline : l'écart
livré vaut 4,2 %, il peut donc **plus que doubler** sans rougir. Le garde
n'interdit pas l'ajustement, il interdit le changement de nature.

`test_la_duree_annoncee_par_la_documentation_est_celle_de_la_valeur_livree`
tient la **prose**, et c'est assumé comme un test de texte dans un fichier qui
les refuse par ailleurs : ce qui doit être éprouvé **est** une propriété du
texte — « la documentation dit la vérité sur la valeur » — et il n'y a pas de
comportement à observer. Il part de la valeur **effective**, jamais d'un
littéral, et exige que `dagster.yaml` et `documentation/orchestration.md` la
nomment et en annoncent les heures justes. Deux sites et pas cinq : ce sont ceux
qui **donnent** le chiffre, les autres le citent, et tous les garder par du
texte rendrait le garde plus fragile que la chose gardée.

Les deux mutations du critère, rejouées (`PYTHONHASHSEED=1337`, `rc` du
processus `pytest`, mutation vérifiée **sémantique** — le YAML se charge et la
valeur lue est bien celle substituée) :

| Mutation | `rc` | Rouges |
|---|---|---|
| `max_runtime_seconds: 90000` → `500000` | 1 | `test_la_borne_reste_juste_au_dessus_du_plafond_du_pipeline`, `test_la_duree_annoncee_par_la_documentation_est_celle_de_la_valeur_livree` |
| `max_runtime_seconds: 90000` → `3600` | 1 | `test_la_borne_de_duree_ne_contredit_pas_le_plafond_du_pipeline`, `test_la_duree_annoncee_par_la_documentation_est_celle_de_la_valeur_livree` |

**Aucune valeur effective ne change** : `dagster.yaml` ne gagne que des
commentaires. Le démon en cours d'exécution lit
`/home/ubuntu/RAG/rag-ingestion-pipeline/dagster.yaml` — le clone principal, pas
un arbre de travail (`mesuré` par `docker inspect` sur les deux conteneurs
Dagster) — et Dagster ne relit ce fichier qu'au **démarrage du processus**. Rien
n'a été redémarré, et il n'y avait rien à redémarrer.

#### 4.35.b Les deux phrases d'exhaustivité qui portent la justification du `rmtree` ne sont tenues par aucun test

La justification de la purge de `Datas/.cleaned/` repose sur une chaîne dont le
dernier maillon est : *`cleaned_html` est le **seul** chemin qui re-téléverse les
images d'un document, et il ne s'exécutera jamais pour un document absent.* Ce
maillon repose lui-même sur deux phrases d'exhaustivité, écrites dans le
docstring de `purge_cleaned` et dans celui de l'asset :

- `MinioImageExporter` n'est instancié qu'à **un** endroit ;
- `clean_html_file` n'a qu'**un** appelant de production.

**Les deux sont vraies.** `mesuré` le 23 septembre 2026, revérifié à la main :

```bash
grep -rn 'MinioImageExporter(' src/   # 1 ligne  : factory.py:341, l'instanciation
grep -rn 'clean_html_file(' src/      # 2 lignes : cleaning.py:610 la DEFINITION,
                                      #            factory.py:343 le seul appel
```

**Et aucun test ne les tient.** Le jour où un second appelant apparaît — un
service de prévisualisation, un script de rattrapage, une commande de
maintenance — la justification de la purge devient fausse, et **rien ne le
dit** : la suite reste verte, le docstring continue d'affirmer ce qui n'est plus
vrai, et un `rmtree` garde une raison d'être qu'il n'a plus.

**LA FORME DU GARDE COMPTE, ET C'EST TOUT L'OBJET DE CE CONSTAT.** Un garde qui
**compte les sites** — `assert len(grep('MinioImageExporter(')) == 1` — est
fragile de deux manières à la fois : il rougit sur un renommage, un import
déplacé ou un commentaire, donc il crie pour rien ; et il reste vert si le second
appelant passe par une indirection, donc il se tait quand il faudrait crier. Il
garde l'orthographe, pas la chose.

Le garde qui tient est celui qui tient la **propriété** : *les images d'un
orphelin ne sont re-téléversées par aucun chemin*. Sa forme, telle qu'elle est
proposée et **non écrite** :

1. sur un corpus temporaire, matérialiser un document avec un exporteur
   d'images **espion**, et vérifier qu'il a reçu des appels — c'est le **témoin**,
   sans lui le test serait vert sur un pipeline débranché ;
2. retirer la source du corpus ;
3. rejouer **tous** les assets du pipeline sur cette partition, par le chemin de
   production, l'espion remis à zéro ;
4. asserter que l'espion n'a **rien** reçu.

Ce garde-là ne connaît ni le nom `MinioImageExporter` ni le nombre de ses sites.
Il rougit exactement quand la propriété tombe — c'est-à-dire quand un second
chemin se met à téléverser — et il reste vert sur tout renommage. **Non écrit :
périmètre strict.**

#### 4.35.c L'option plus étroite n'est écartée nulle part, et la décision est prise ici

Ne supprimer que les **orphelins**, plutôt que tout le répertoire. L'option n'a
jamais été écrite, ni retenue ni écartée, alors qu'elle est la première que
lirait quiconque relit ce `rmtree`.

Le chiffre qui la rend tentante est réel. `mesuré` le 23 septembre 2026, en
lecture seule sur `/home/ubuntu/RAG/rag-ingestion-pipeline/Datas/.cleaned` :

| | |
|---|---|
| copies nettoyées | **22** |
| dont la source existe encore | **22** |
| **orphelins** | **0** |

La purge détruit donc aujourd'hui **22 copies valides pour éliminer zéro cible**.

**LA DÉCISION EST DE GARDER LA PURGE LARGE**, et voici les deux arguments qui la
portent.

Le premier est une question de **surface**. Un `rmtree` gardé sur **un**
répertoire — containment strict, cible dérivée d'une constante et non d'un
réglage, refus dur sur tout ce qui n'est pas exactement `<racine>/.cleaned`, le
tout mesuré sur 15 scénarios dont 6 détruisaient le corpus avant le lot 9 — est
une surface **plus petite** qu'une logique de suppression fichier par fichier
sur un chemin destructeur. Cette seconde forme ferait boucler la suppression sur
une liste *calculée*, donc dépendante d'une dérivation source ↔ copie qui peut
diverger ; c'est exactement le mode de panne du §4.29.a, où deux sites lisaient
le sous-répertoire depuis deux endroits différents. Un `rmtree` unique se garde
par **un** invariant ; une boucle de `unlink` se garde par autant d'invariants
qu'elle a de chemins.

Le second est que le coût mesuré ci-dessus est **nul dans le seul contexte où la
purge s'exécute**. `purge_cleaned` n'a qu'un appelant de production,
`wipe_stores.main()` — `mesuré` : `grep -rn 'purge_cleaned(' src/` rend deux
lignes, `wipe_stores.py:153` la **définition** et `wipe_stores.py:395` le seul
appel — et `main()` vient de vider ChromaDB, le bucket MinIO et NebulaGraph. Le geste entier n'a de sens qu'avant une **réingestion complète**,
qui réécrira les 22 copies de toute façon — `clean_html_file` écrit sa
destination sans la regarder, il n'existe aucun court-circuit « le fichier
nettoyé existe » (§4.33.a, `mesuré`). Les « 22 copies valides détruites » ne sont
donc pas une perte : ce sont 22 fichiers qui allaient être réécrits dans la
minute.

**Ce que cette décision ne dit pas**, et qui reste ouvert : personne ne **compte**
ni ne **nomme** les orphelins avant de les détruire. C'est le §4.34.c, et il est
toujours vrai. Un rapport avant purge vaudrait mieux qu'une purge silencieuse,
et il ne change rien à la décision ci-dessus — il l'accompagne.

#### 4.35.d Le garde du maillon « le capteur ne voit pas `.cleaned` » garde la bibliothèque, pas l'usage

`test_le_glob_de_la_source_ne_voit_jamais_le_repertoire_nettoye`
(`tests/unit/test_factory.py:507`) tient le maillon (c) de la justification du
`rmtree`. Il appelle `globlib.glob(...)` **dans le test**, avec le motif de la
source reconstruit à la main. Il garde donc une propriété de la **bibliothèque
standard** — `glob` n'ouvre pas un répertoire à point de tête, même derrière
`**` — et non l'usage qu'en fait la production, `factory.py:758`.

`mesuré` le 23 septembre 2026, mutation du code **livré**, protocole complet
(site compté à 1, `git diff --stat` non vide, module réimporté pour vérifier que
la mutation est **sémantique** et non un plantage au chargement,
`git status --porcelain` vide après restauration) :

| Mutation | `rc` | Rouges |
|---|---|---|
| `globlib.glob(pattern, recursive=True)` → `globlib.glob(pattern, recursive=True, include_hidden=True)` dans `factory.py` | **0** | **aucun** — 927 verts |

**L'impact réel est nul**, et il faut le dire aussi clairement que le défaut :
l'ancrage du motif protège seul. Le glob d'une source est `htms/**/*.html`, donc
ancré sous le sous-répertoire de la source, et `.cleaned` est un **frère** de
`htms` et non un descendant — `include_hidden` ne peut pas l'atteindre. Les deux
protections que le docstring du test annonce tenir ne sont pas d'égale force : la
première suffit, la seconde est du confort, et c'est la seconde que le test
éprouve.

**Ce qui est en défaut est donc le garde, pas le code.** Un test qui passerait
par le capteur de production — et non par `globlib` directement — rougirait sur
cette mutation, et dirait alors quelque chose du système plutôt que de la
stdlib. **Non écrit : périmètre strict**, et la priorité est basse puisque
l'impact est nul.

#### 4.35.e Les tables de mutations ne sont pas versionnées, donc la preuve de non-décorativité périt

Un garde n'est pas décoratif s'il **rougit** quand la chose gardée tombe, et la
seule preuve en est une table de mutations. Sur ce chantier, cette table vit dans
une **conversation** — qui périt — alors que le garde, lui, est versionné.

`mesuré` le 23 septembre 2026, sur les six commits du lot 9 (`34e740f..f124512`) :

```bash
# les six commits du lot 9, depuis leur base
git log 34e740f..f124512 --format='%B' | grep -ciE '[0-9]+ rouges?'          # rend 0
# les deux sections que le lot 9 a écrites à ce registre
awk '/^### 4\.33 /,/^### 4\.35 /' documentation/axes_amelioration.md \
  | grep -ci 'mutation'                                                      # rend 2
```

**Aucun** message de commit du lot 9 ne chiffre une mutation. Le registre en
chiffre **six**, en deux endroits : deux au §4.33.a (le court-circuit devant le
`write_text` → 1 rouge ; `shutil.rmtree` → `pass` → 14 rouges) et quatre au
§4.33.c. Le lot en a annoncé davantage dans sa conversation de livraison — le
chiffre de 17 circule dans le mandat de réparation — et **ce chiffre n'est
vérifiable nulle part dans le dépôt**. C'est exactement le constat : l'auditeur a
dû reconstruire ses propres tables de sa main, et la réparation aussi.

L'écart est donc plus large que « 17 annoncés contre 6 consignés » : le dépôt ne
porte **que** les 6 du registre, et **zéro** dans les commits qui livrent les
gardes.

**La pratique n'est pas changée ici — ce serait une décision du pilote**, et elle
a un coût qui doit être pesé avant d'être payée : une table par garde alourdit
chaque message de commit, et une table fausse est pire qu'absente. Le constat est
consigné pour que la décision se prenne sur une mesure. *(Les deux commits de
cette réparation portent chacun leur table, chiffrée et rejouable, `rc` compris :
c'est un échantillon de ce que la pratique coûterait, pas son adoption.)*


### 4.36 → CONSIGNÉ par le lot 11, **CORRIGÉ par sa reprise** — quatre mesures, **aucune correction** ; la réparation des `ListItem` vides est **ÉCARTÉE** (option (a), 24 septembre 2026, §4.37.h)

Quatre constats, mesurés le 23 septembre 2026. **Aucun n'entre au diff** : ce
sont des mesures sans correction. Le compte est `calculé`, `grep -c '^#### 4.36'`
rend quatre.

**CE TITRE ANNONÇAIT « un TRAITÉ (le harnais) », et aucun des quatre constats ne
le décrivait** (audit du lot 11, point 7). Le harnais n'est pas un constat de ce
paragraphe ; sa version du lot 11 était, de plus, **non fusionnable** — il ne
pouvait pas dire non après la campagne. Sa réécriture est consignée au **§4.37**.

**ET LA PRÉMISSE DE LA RÉPARATION ÉTAIT FAUSSE** (audit, point 3, confirmé par
le pilote puis remesuré sur tout le corpus au §4.37.g) : les `ListItem` vides ne
**perdent** pas de texte, ils le **fragmentent**. Chaque fragment est déjà un
élément du graphe. Les `b`, `c` et `d` ci-dessous sont corrigés en ce sens, et la
décision de réparer revenait au propriétaire sur les chiffres du §4.37.h : il a
tranché le 24 septembre 2026 pour l'**option (a)**, et la réparation sort du plan.

#### 4.36.a → MESURÉ, NON TRAITÉ — **trois ancrages du jeu de questions sur 44** portent sur un sommet à `text` vide

C'est le chiffre qui décide, et il est **non nul**. `element_id` vaut
`sha256(f"{filename}|{page_no}|{position_in_page}|{text[:50]}")[:10]`
(`src/docling_service/elements.py:216`) : réparer `item_text()` change
`text[:50]` pour ces éléments, donc **change leur `element_id`**, donc **tue
l'ancrage**. Le jeu de questions est un travail humain, et le contrat
(exigence 2) dit qu'un identifiant qui change rend la mesure historique
incomparable.

`mesuré` sur l'index vivant, les 44 ancrages de
`documentation/campagnes/2026-09-02-jeu-de-questions.yaml` relus dans le graphe :
**44 retrouvés, 0 absent, 41 à texte non vide, 3 à texte VIDE**. Les trois sont
des `ListItem`, et **aucun** n'est un `Code` — le jeu ne porte aucun ancrage
`code` (`Counter` des labels : 36 `text`, 8 `list_item`).

| `element_id` | section | document | `chunk_count` |
|---|---|---|---|
| `269b2e32d8` | Optimizing search quality | `htms/MLOps with Databricks/7. Foundation Models and Context Engineering.html` | 1 |
| `5558e561d7` | Querying and retrieval quality | idem | 2 |
| `e1ab19bc3b` | Serving Limitations | `htms/MLOps with Databricks/4. Model Serving： Architectures and Implementation.html` | 1 |

**Ce que la réparation leur ferait**, `mesuré` en simulant la correction sans la
committer — les trois textes sont bien retrouvés, et les identifiants bougent :

| ancien | nouveau | texte récupéré (début) |
|---|---|---|
| `269b2e32d8` | `64caa3e5b8` | « Add reranking . Databricks' built-in reranker is a great solution… » |
| `5558e561d7` | `c1daef2e4b` | « Databricks AI Search uses the HNSW algorithm for its approximate… » |
| `e1ab19bc3b` | `5134373b49` | « By default, each CPU model endpoint is allocated 4 GB of memory… » |

**La décision est celle du pilote**, pas du lot : réparer et réécrire ces trois
lignes du jeu, ou ne pas réparer. Les deux colonnes ci-dessus sont ce qu'il faut
pour trancher, et pour réécrire le jeu si le choix est de réparer.

#### 4.36.b → MESURÉ — le mécanisme du vide n'est **pas celui qui était annoncé**, et il vise **deux populations opposées**

Le mandat du lot posait que Docling émet des `CodeItem` **et** des `ListItem`
dont `.text` vaut `''` et qui sont **sans enfant**, `item_text()`
(`src/docling_service/elements.py:242-268`) rendant `''` par ses deux branches.
**La moitié de cette phrase est fausse, et c'est elle qui portait la
correction.**

`mesuré` le 23 septembre 2026, conversion réelle des 5 documents du jeu par le
chemin de production, en inspectant les descendants de chaque item vide :

```
code|VRAIMENT_VIDE             404     (aucun descendant porteur de texte)
list_item|RECUPERABLE           42     (le texte vit dans les ENFANTS)
```

- **les `ListItem` vides ONT des enfants**, `1` ou `2`, et ce sont eux qui
  portent le texte. `#/texts/55` rend
  `<inline><text>If</text><text>your code</text><text>determines what actions
  are taken, the system is not an agent.</text></inline>` par
  `export_to_doctags(doc)`. Docling coupe le texte d'un `<li>` en fragments
  *inline* dès qu'il porte du balisage (`<code>`, `<strong>`, un lien). **42 sur
  42 sont récupérables.** ~~Le graphe perd bien du texte~~ — **FAUX, corrigé par
  la reprise du lot 11** : `iterate_items()` descend dans les enfants, et **chaque
  fragment est DÉJÀ émis comme élément**. L'audit l'a mesuré sur les 42 (170
  descendants émis : 124 `text`, 31 `code`, 15 `list_item` ; `03b830cdeb` →
  `#/texts/82..90`) ; la reprise l'a remesuré sur **tout le corpus**, **202 sur
  202** (§4.37.g). Le texte n'est pas perdu, il est **FRAGMENTÉ** : le sommet de
  la puce est vide, et ses morceaux sont ses voisins de `sequence`. **Une
  réparation qui agrège les enfants dans la puce DUPLIQUE donc du texte** ;
- **les `Code` vides n'ont rien à récupérer.** Ce sont les **lignes blanches**
  entre deux lignes de code, chacune devenue son propre `CodeItem`. Le découpeur
  ne les « retrouve » pas : il les rend comme des clôtures vides — le chunk réel
  est `` ```\nfrom databricks.sdk import WorkspaceClient\n```\n```\n\n``` ``,
  et les clôtures vides sont exactement les items signalés. **404 sur 404 sont
  vraiment vides.**

**Conséquence : réparer les `Code` INVENTERAIT du texte**, en agrégeant ce qui
appartient aux voisins. C'est le « non prouvé » que le mandat demandait de
préférer à un « oui approximatif », et il ne vaut que pour cette moitié-là.

#### 4.36.c → MESURÉ — les **29** pertes sèches annoncées sont **37**, et **toutes** sont des `ListItem`

`mesuré` sur l'index vivant, les 1 564 sommets à `text` vide confrontés à
ChromaDB, `block_size` pris au **minimum** sur les chunks de l'élément :

| tag | vides / total | absents de ChromaDB | `block_size>1` avec texte (ambigu) | `block_size=1` avec texte (~~perte sèche prouvée~~ **perte de RATTACHEMENT**) |
|---|---|---|---|---|
| `Code` | 1 362 / 4 963 | 1 310 | 52 | **0** |
| `ListItem` | 202 / 1 748 | 118 | 47 | **37** |

Le total « avec texte » est **136**, et il reproduit exactement le 29 + 107 du
lot précédent. Seule la frontière prouvé/ambigu diffère — le critère de
`block_size` n'est pas le même. **Ce que le tableau ajoute, et qui manquait :
pas une seule perte prouvée n'est un `Code`.** Les deux mesures `b` et `c` se
recoupent donc sur la même conclusion, par deux chemins indépendants.

**CORRIGÉ PAR LA REPRISE DU LOT 11 : les 37 ne sont PAS des pertes de contenu.**
Ce sont des pertes de **RATTACHEMENT** : le sommet de la puce a un `text` vide
alors que le chunk ChromaDB ancré sur lui porte du texte — le texte de ses
fragments, que le graphe porte **aussi**, sous d'autres identifiants (§4.36.b
corrigé). Rien n'est absent du graphe ; ce qui manque, c'est le lien entre le
sommet que l'agent atteint par le chunk et le texte que ce chunk lui a servi.
Le décompte ChromaDB de tout le corpus, avec la définition de chaque compte, est
au §4.37.g.

#### 4.36.d → **le coût de la réparation, écrit avant la campagne** — 42 mesurés, **202 au plus** sur le corpus, et **zéro clé d'objet** — **INCOMPLET : il ne disait rien de la duplication**

**CE COÛT OMETTAIT LE RISQUE PRINCIPAL** (audit, point 3). La réparation qu'il
chiffre agrège les enfants dans la puce **en les gardant** : chaque caractère
agrégé est alors porté **deux fois** par le graphe. Ce paragraphe ne compte que
les identifiants déplacés. Le tableau des options, identifiants déplacés **et**
caractères dupliqués **et** ancrages morts, mesuré sur les 23 documents, est au
§4.37.h ; il remplace la borne `calculé` de 202 par une mesure.

`mesuré` en simulant la correction sur les 5 documents, deux parcours du **même**
document converti :

```
element_id déplacés par label : {'list_item': 42}
labels déplacés hors list_item : AUCUN, sur les cinq documents
PDF du corpus                  : 0 déplacé
```

- **le déplacement ne cascade pas.** `position_in_page` s'incrémente que
  l'élément porte du texte ou non (`elements.py:394-395`), et `page_no` ne
  dépend pas du texte : seuls bougent les éléments **dont le texte change**.
  C'est ce que confirme « AUCUN hors `list_item` » ;
- **la borne du corpus est 202**, le nombre de sommets `ListItem` à texte vide
  du `c`. Elle est `calculé` : 42 sur 42 récupérables sur l'échantillon, donc
  les 202 sont attendus déplacés. Les 1 362 `Code` ne bougent pas — il n'y a
  rien à leur rendre ;
- **aucune clé d'objet ne bouge**, et c'est prouvé deux fois. Les clés du PDF
  portent l'`element_id` (`images/<radical>/<element_id>_<label>.png`,
  `images.py:222`) mais ne sont produites que pour
  `VISUAL_LABELS = {picture, table, figure, graphic}` (`elements.py:40`,
  `extraction.py:938`) — `list_item` n'en est pas ; et `mesuré`, le PDF du
  corpus ne déplace **aucun** identifiant. Les clés du HTML ne portent pas
  d'`element_id`.

**Le garde qui manque** — « les deux stores disent la même chose du même
élément » — n'est **pas** écrit, parce que le `a` arrête le chantier avant lui.
Sa forme est acquise : il se pose **chez le producteur**, et il ne peut pas
exiger l'égalité **octet à octet**, ChromaDB portant la décoration markdown, la
puce de liste et l'agrégation du découpeur là où le graphe porte le texte nu. La
propriété testable est la plus faible des deux, et c'est celle du mandat : *un
élément dont ChromaDB porte du texte n'a pas un `text` vide dans le graphe.*
**Écrite telle quelle, cette propriété POUSSE à la duplication** (reprise du lot
11) : la satisfaire sur les puces vides, c'est leur donner le texte de fragments
que le graphe porte déjà. Elle n'est pas écrite non plus ici ; sa forme dépend de
l'option retenue au §4.37.h.

### 4.37 → la REPRISE du lot 11 — le harnais sait dire non (**a** à **f** TRAITÉS), et la décision des puces vides est **PRISE** sur ses chiffres (**g**, **h** ; deux libellés rectifiés par le §4.38.e)

L'audit du lot 11 a déclaré la branche **non fusionnable** sur deux bloquants,
tous deux confirmés par le pilote en lisant le code. Cette reprise les traite
(`a` à `f`) et remesure, **en lecture seule**, ce que la décision de réparer les
`ListItem` vides doit peser (`g`, `h`). `src/docling_service/` n'est **pas**
modifié : `item_text` est intact. Le compte est `calculé`,
`grep -c '^#### 4.37'` rend huit.

**Les deux gestes de campagne, et leur commande** — elle tourne dans l'image
d'extraction, le `src` monté étant celui de la branche mesurée (§4.27) :

```
docker run --rm --network rag_network \
  -v "$PWD/src":/app/src:ro -v "$PWD/scripts":/app/scripts:ro \
  -v "$PWD/documentation/campagnes":/campagnes:ro \
  -v <clone principal>/Datas:/corpus:ro -v <scratchpad>:/sp \
  -v /var/lib/docker/volumes/rag-ingestion-pipeline_docling_models/_data:/tmp/.cache:ro \
  --env-file <clone principal>/.env -e COMMIT_MESURE="$(git rev-parse HEAD)" \
  -e HOME=/tmp -e PYTHONPATH=/app -w /app rag-ingestion-pipeline-docling-service \
  python scripts/campagne/verifier-l-equivalence-des-identifiants.py \
    figer <dossier>                                      # AVANT la purge
    comparer /campagnes/2026-09-24-instantane-des-identifiants \
      [--deplacements-annonces <fichier>]                # APRÈS la réingestion
```

Les copies nettoyées des HTML sont attendues sous `<scratchpad>/cleaned/`,
produites avec un exportateur d'images **témoin** : `mesuré` le 24 septembre
2026, les 22 copies témoin sont **égales octet pour octet** aux 22 copies de
production de `Datas/.cleaned/` (SHA-256 comparés).

#### 4.37.a → TRAITÉ — **l'instantané** : l'après se compare à l'avant figé, plus au code qui l'a écrit

**Le défaut (audit, point 1, BLOQUANT).** Relancé après la campagne, le harnais
réextrayait avec le code X et comparait au graphe écrit par ce même code X. Il ne
pouvait voir qu'un non-déterminisme, jamais un déplacement.

**Le geste.** `figer` réextrait **tout le corpus** par le chemin de production,
prouve que les identifiants **émis** sont ceux du graphe, **puis seulement**
écrit un relevé par élément : identifiant émis, clé du document, `page_no`,
`position_in_page`, `text50`, label, `self_ref`. Le graphe ne stocke pas
`position_in_page` : l'instantané vient de l'**émission**, et il n'est écrit
qu'après la preuve. Au moindre rouge, rien n'est écrit. `comparer` confronte
l'émission du jour à **cet** instantané.

**L'instantané de la campagne**, `mesuré` le 24 septembre 2026 à 13:54 UTC,
`figer` au commit `a7ea049`, stores en lecture seule :

| | |
|---|---|
| emplacement | `documentation/campagnes/2026-09-24-instantane-des-identifiants/` |
| **empreinte** (SHA-256 du manifeste, qui porte celui de chaque fichier) | `e945893b1021e2f1aa3809434a889443ed9fb85e2a7e290cd329f077687f0f6d` |
| couverture | **23 documents sur 23**, **15 173 éléments** — le nombre d'arêtes `PARENT_OF` du graphe |
| preuve | émis == graphe pour chacun des 23 : 0 émis seul, 0 graphe seul |
| clés d'objet | 13 émises, les 13 que MinIO liste sous `images/<radical du PDF>/` |
| déterminisme | deux passages successifs : relevés et clés **identiques octet pour octet**, seule la date du manifeste diffère |
| durée | 82,4 s et 85,3 s (`/usr/bin/time`), le PDF en prend ~74 |
| `comparer`, le même jour | **0 déplacé, rc=0** ; avec un identifiant déclaré qui ne bouge pas, **rc=1** |

La couverture est **entière** et la borne est mesurée, non supposée : le GPU est
saturé par d'autres projets, mais la conversion tourne sur CPU (6,0 s pour le
plus gros HTML, 73,6 s pour le PDF, `mesuré` à l'ancien harnais le même jour).

**Le format, justifié.** Du **TSV sans guillemets**, un fichier par document.
Trois contraintes l'imposent, toutes `mesuré` :

- `check-added-large-files --maxkb=500` : l'instantané fait 1 016 Ko en tout, et
  son plus gros fichier **77 Ko** ;
- `detect-secrets` v1.5.0 voit un secret dans tout hexadécimal **entre
  guillemets** : le même identifiant en JSON rend rc=1, en TSV rc=0 ;
- `trailing-whitespace` réécrirait une ligne finissant par une espace : le
  label, jamais vide, est en **dernière** colonne, et chaque champ est échappé en
  ASCII (`json.dumps(…, ensure_ascii=True)`), donc aucune tabulation, aucun
  retour, aucun séparateur Unicode ne coupe une ligne. Au commit de l'instantané,
  aucun hook n'a réécrit un octet : le SHA-256 du manifeste committé est celui
  que `figer` a imprimé.

**Le faux vert n° 1 de l'audit est un test de la porte**, par le **vrai**
`_extract_flat`, seul le convertisseur Docling étant remplacé :
`TestLesFauxVertsDeLAudit::test_trois_listitem_qui_recoivent_du_texte_rougissent_apres_la_campagne`.
**Rouge d'abord** — `mesuré` le 24 septembre 2026, le script de l'auditeur rejoué
sur un `git archive 6beed44` : `IDENTIQUES 30`, `OK`, **rc=0**, alors que trois
identifiants ont disparu. **Vert ici** : `comparer` rend rc=1, `DEPLACES 3,
DECLARES 0`, attribution `{'text50': 3}`.

#### 4.37.b → TRAITÉ — **les identifiants comparés sont ceux que la production ÉMET**

**Le défaut (audit, point 2, BLOQUANT).** `reextraire()` jetait `element["id"]`
et le recalculait avec `compute_id` : une dérive au **site d'appel** lui était
invisible.

**Le geste.** Le relevé porte `element["id"]` tel que `persist` le reçoit ;
`compute_id` ne sert plus qu'à l'attribution. Une cinquième mutation du contrôle
négatif, `site_d_appel`, simule la dérive exacte de l'audit : les quatre entrées
intactes, l'identifiant émis calculé sur `.cleaned/<clé>`.

**Le faux vert n° 2 est un test de la porte** :
`test_une_production_qui_calcule_sur_cleaned_rougit_avant_la_campagne`. **Rouge
d'abord** sur `6beed44`, script de l'auditeur : côté production 0 identifiant sur
30 conforme au graphe, côté harnais `IDENTIQUES 30`, **rc=0**. **Vert ici** :
`figer` rend 1, `emis seul / graphe seul : 30 / 30`, et **n'écrit pas**
l'instantané. Le test exige la **raison** et pas seulement le `rc` : le contrôle
négatif rougit aussi ce scénario, par ricochet (la mutation `site_d_appel` y
devient nulle), et masquerait une confrontation au graphe qui ne garderait plus
rien — c'est un mutant qui l'a montré.

#### 4.37.c → TRAITÉ — **les déplacements s'annoncent**, et l'attribution est **exacte**

**rc=0 si et seulement si l'ensemble déplacé ÉGALE l'ensemble déclaré**
(`--deplacements-annonces`, un identifiant par ligne, `#` pour sa raison ; vide
par défaut). Quatre rouges : un déplacé non déclaré, un **déclaré qui ne bouge
pas** — sinon une réparation non appliquée passe en silence —, un identifiant
**apparu sans contrepartie**, et un identifiant **réassigné**. L'apparu n'est pas déclarable : la déclaration
porte sur l'instantané, et un élément ajouté force à le refiger plutôt qu'à
l'étendre en silence. C'est une borne voulue, écrite à `trancher`.

**L'attribution compare directement les quatre entrées** de la formule entre
l'avant et l'après, après appariement par `(self_ref, rang d'occurrence)` — le
PDF, converti par lots, répète ses `self_ref` d'un lot à l'autre. **L'heuristique
par jumeaux de `text50` est SUPPRIMÉE**, pas bornée : elle imputait la mutation
`filename` à `position_in_page` 60 fois sur 60 (audit, point 5). Sur le relevé
réel, chaque mutation est vue en totalité et imputée à son seul terme, sur les 23
documents.

**Le quatrième rouge n'était pas demandé, et c'est le chantier B qui l'a
montré.** Un identifiant présent des deux côtés peut désigner **un autre
élément** : une différence d'ensembles le compte comme identique. Ne plus émettre
les puces vides (option d du §4.37.h) décale leurs voisins, et une ligne de code
vide tombe à la position de la puce retirée — même clé, même page, même rang,
même `text50` `""`, **même identifiant**. `mesuré` sur les simulations : **490**
identifiants réassignés en (d), **231** en (c), 0 dans les autres options. Un
ancrage sur l'un d'eux glisserait vers un autre passage **sans un rouge**.
`comparer_les_releves` relève désormais les identifiants dont le label ou le
`self_ref` change, et `trancher` les rougit.

**Sa borne réelle, écrite au site** : l'attribution est aussi juste
que l'appariement, qui suppose que Docling rend le même arbre ; si Docling
change, le **compte** reste exact et l'attribution peut désigner des termes qui
n'ont pas bougé.

**Un faux rouge évité, et il était dans la règle du contrôle.** Muter
`position_in_page` de +1 fait tomber l'identifiant d'un élément sur celui de son
voisin quand les deux partagent leur `text50` — les lignes blanches d'un bloc de
code partagent `""` ; `page_no` +1 fait de même sur le PDF, d'une page à la
suivante. Le premier `figer` d'essai a rendu « NON VU » sur **13 contrôles de 12
documents** pour cette raison : 12 `position_in_page`, 1 `page_no` (le PDF). Le compte des mutés se fait désormais par
différence d'ensembles, et les **collisions** sont comptées à part.

#### 4.37.d → TRAITÉ — **les barrières sont posées à TOUS les sites** où une porte est liée

**Le défaut (audit, point 4).** `storage.py:16` et `extraction.py:48` importent
`get_writer` **par nom** : barrer `nebula.get_writer` dans `nebula` le laissait
vivant à deux sites sur trois. Deux mutants survivaient à 16 tests verts sur 16 —
le retrait de `nebula.get_writer` et celui de `vectors.get_collection`. **8 portes
effectives, pas 9.**

**Le geste.** `remplacer_partout` parcourt chaque module `src.*` chargé et
remplace tout attribut qui **est** l'original. Toute porte touchée est en outre
**journalisée**, parce qu'une levée peut être avalée par un `except Exception`
de la production — `crop_and_upload` et `ensure_bucket` en portent un.

**Le recompte**, `mesuré` au `figer` du 24 septembre 2026 : **9 portes, 11
sites**, toutes effectives.

| porte | sites |
|---|---|
| `nebula.get_writer` | `nebula`, `storage`, `extraction` — **3** |
| `nebula.NebulaWriter` | `nebula` — ajoutée : l'instancier directement contournait `get_writer` |
| `storage.persist` | `storage` — puis remplacée par la **capture** |
| `storage.forget_document`, `vectors.write_elements`, `vectors.delete_document`, `vectors.get_collection`, `images.upload_file` | leur module — 1 chacune |
| `images.get_client` | `images` — un **témoin**, pas une barrière (§4.37.e) |

`images.crop_and_upload` **n'est plus** une porte : la production tourne, et
son envoi passe par `get_client`.

**Le test demandé**, `TestLesBarrieres::test_aucune_porte_d_origine_ne_reste_liee_dans_un_module_src` :
après armement, il parcourt les modules `src.*` et rougit sur toute fonction
d'origine des quatre modules de stores encore liée quelque part, **hors d'une
liste de non-écrivains que le TEST tient lui-même**, chacun avec sa raison. Ce
n'est pas la liste du producteur, et c'est tout l'intérêt : une fonction ajoutée
à un module de store rougit le test tant que personne ne l'a classée. **Les deux
rouges demandés**, `mesuré` :

```
## A5 PORTES sans nebula.get_writer
   rc=1  2 failed, 52 passed
   ROUGE TestLesBarrieres::test_aucune_porte_d_origine_ne_reste_liee_dans_un_module_src
   ROUGE TestLesBarrieres::test_get_writer_est_barre_a_ses_trois_sites
## A5 PORTES sans vectors.get_collection
   rc=1  2 failed, 52 passed
   ROUGE TestLesBarrieres::test_aucune_porte_d_origine_ne_reste_liee_dans_un_module_src
   ROUGE TestLesBarrieres::test_la_production_appelee_par_son_module_leve
```

**Ce que les barrières ne couvrent pas, écrit pour que personne ne le
découvre** : une porte tenue ailleurs que dans un attribut de module — une
valeur par défaut, une fermeture, un dictionnaire — et les clients tiers
(`chromadb.HttpClient`, `Minio`, `ConnectionPool`) construits hors des quatre
modules. Le harnais s'en sert lui-même, **en lecture**, pour le graphe et le
listing MinIO.

#### 4.37.e → TRAITÉ — **le témoin MinIO descend d'une couche**, et ses clés sont confrontées au listing

**Le défaut (audit, point 7).** Le témoin remplaçait `crop_and_upload` par une
copie qui calculait la clé sans cropper : il en enregistrait une là où la
production aurait rendu `None` (zone vide, crop en échec), et ces clés n'étaient
jamais confrontées à MinIO, alors que la docstring promettait de « dire si une
réingestion a déplacé des clés d'objet ».

**Le choix : tenir la promesse, pas la retirer.** `crop_and_upload` de
**production** tourne en entier, crop compris ; seul `put_object` du client est
remplacé par un témoin qui enregistre la clé, et **lève** — journalisé — sur
toute autre méthode. Les cas `None` sont donc ceux de la production, par
construction. `figer` et `comparer` confrontent les clés enregistrées au
**listing** MinIO du préfixe du PDF, en lecture (`list_objects`). La raison du
choix : l'autre voie aurait retiré la seule mesure qui dise, après la campagne,
si une clé d'objet a bougé — et elles portent l'`element_id`. `mesuré` : 13
émises, 13 listées, égales.

**La borne** : les images des HTML sont envoyées par le **nettoyage**, sous des
clés sans `element_id` ; le harnais ne les voit pas et ne les confronte pas.

#### 4.37.f → TRAITÉ — **quatre `type: ignore` retirés**, et `scripts/campagne/` entre dans la porte

**Le défaut (audit, point 6).** Quatre `# type: ignore[assignment]`, lignes 109,
110, 156 et 157 du script, aucun justifié au site. `mesuré` sur `6beed44` depuis
son propre arbre, `mypy --strict --warn-unused-ignores` : **quatre `Unused "type:
ignore" comment`**, et les lignes 110 et 157 étaient redondantes.

**Le geste.** Les quatre affectations disparaissent au profit de
`remplacer_partout`, et avec elles les quatre `type: ignore`. Le script passe
`mypy --strict --warn-unused-ignores`. **Le coût de l'inclusion, mesuré** :
`mypy src/ scripts/campagne/` ne rougit sur **aucun** des trois scripts, et une
erreur de type déposée dans chacun est **vue** — un dossier au nom de module
invalide aurait pu être ignoré en silence. Il est donc **inclus** :
`make typecheck` vaut `mypy src/ scripts/campagne/`, 39 fichiers.

**Les mutants du producteur**, `mesuré` le 24 septembre 2026 sur une copie de
l'arbre : **33, zéro survivant**, deux d'entre eux gardant le rouge
« réassigné ». Le premier passage en laissait **trois**, et
chacun a corrigé un test, pas le producteur : un test d'empreinte qui altérait
l'en-tête et rougissait donc par le contrôle d'en-tête ; un test d'appariement qui
réparait l'élément dont la dernière occurrence tombait juste par chance ; et un
garde « émission vide » qu'aucun test ne pouvait isoler — il était redondant avec
le contrôle négatif, et il est **retiré**, la raison écrite au site.

#### 4.37.g → MESURÉ, lecture seule — sur **tout le corpus**, les 202 puces vides ont **tout** leur texte déjà dans le graphe, et ChromaDB **ne duplique pas**

**La sonde**, `mesuré` le 24 septembre 2026 : le chemin de production sur les
**23 documents**, barrières du harnais armées (journal vide en fin de run),
`persist` capturé **avec** le document Docling, chunks recalculés par
`vectors.build_chunks` sur ce document. Elle vit dans le scratchpad de la reprise
et **n'est pas versionnée** — elle devrait passer les règles `ANN` de ruff, et la
réécrire ferait une sonde différente de celle qui a produit ces chiffres ; son
empreinte est consignée : `sonde_b.py` SHA-256
`c7721a1944dd8989d298e1f4e2094cd65ee3b543de042f3e5e8127c27b6a9736`, analyse
`analyse_b.py`. **Deux contrôles de cohérence**, tous deux verts : la sonde
reproduit l'instantané du §4.37.a sur **23 documents sur 23**, et ses chunks sont
ceux de ChromaDB, **4 367 sur 4 367, identifiant ET texte**.

**B2 — combien de puces vides, et leur texte est-il déjà émis ?**

| compte | valeur | définition |
|---|---|---|
| `ListItem` à `text` vide | **202** | `label == list_item` et `item_text() == ""` ; l'instantané en compte autant (`text50 == ""`) — la borne `calculé` de 202 du §4.36.d était donc juste |
| … par format | **202 HTML**, **0 PDF** | sur 18 documents |
| … dont **TOUS** les descendants porteurs de texte sont déjà émis | **202 sur 202** | descendant = tout item atteint par `children`, puces imbriquées comprises (la définition de l'audit) ; porteur = `.text` non vide après `strip()` ; émis = son `self_ref` est celui d'un élément passé à `persist` |
| … dont au moins un descendant porteur **non** émis | **0** | |
| … sans aucun descendant porteur | **0** | aucune puce n'est vraiment vide |
| … avec une puce imbriquée **qui porte du texte** parmi leurs descendants | **14** | le libellé disait « avec une puce imbriquée » ; ce qui est compté exige que la puce imbriquée porte du texte. **21** puces ont une puce imbriquée parmi leurs descendants, porteuse ou non — `mesuré` le 24 septembre 2026, relecture du second audit (§4.38.e) |
| fragments | **727** : 546 `text`, 181 `code`, tous émis | descendants porteurs **sans entrer dans une puce imbriquée** — ce qu'une réparation agrégerait |
| caractères des fragments | **31 064** | somme de `len(item_text(fragment))` ; l'agrégat joint par des espaces en fait 31 589 |

**B3 — ChromaDB duplique-t-il déjà ?** **Non.** `mesuré` le même jour, lecture
seule (`HttpClient(...).get_collection("rag_documents").get()`, **jamais**
`vectors.get_collection`, qui fait `get_or_create`). Un chunk est « ancré » sur
un élément quand sa métadonnée `element_id` est l'identifiant de cet élément ;
« contenir » se juge après retrait des blancs, des accents graves, `*` et `_`,
sur les fragments d'au moins 4 caractères.

| compte | valeur | définition |
|---|---|---|
| C1 — puces vides portant au moins un chunk ancré sur elles | **84 sur 202**, 102 chunks | `block_size` de ces chunks : 1 → 46, 2 → 24, 3 → 13, 4 → 7, 5 → 5, 6 → 2, 7 → 4, 8 → 1 |
| C2 — parmi C1, puces dont les chunks contiennent le texte de tous leurs **descendants porteurs** | **78 sur 84** | le libellé disait « de tous leurs fragments » ; le compte porte sur les **descendants porteurs**, puces imbriquées comprises, et non sur les « fragments » au sens du §4.37.g, qui s'arrêtent à la puce imbriquée. Compté sur les fragments, il vaut **79 sur 84** — `mesuré` le 24 septembre 2026, relecture du second audit (§4.38.e). Les 6 autres (5 dans la lecture par fragments) : une puce longue que le découpeur coupe, sa première phrase partant dans un chunk ancré sur un élément **précédent** |
| C3 — fragments portant un chunk ancré sur **eux** | **3 sur 727** | `(optional)`, `)`, `Chapter 9` : un chunk qui commence au milieu d'une puce |
| C4 — fragments dont le texte est **à la fois** dans leur propre chunk et dans un chunk de leur puce | **0** | **la duplication, dans ChromaDB : nulle** |
| puces vides **sans** chunk à elles | **118** | leur texte est dans un chunk ancré sur un **autre** élément (`block_size > 1`) — **118 sur 118** ; absent de ChromaDB : **0** |

**Ce que cela dit.** ChromaDB porte le texte de chaque puce **une fois**, tantôt
sous l'identifiant de la puce (84), tantôt sous celui de l'élément qui ouvre le
chunk (118). Le graphe le porte **une fois** aussi, en fragments. Ce qui manque
n'est ni dans l'un ni dans l'autre : c'est le **lien**. Le sommet que l'agent
atteint par un chunk ancré sur une puce a un `text` vide, et ses fragments sont
ses **frères** sous la section, non ses enfants — la puce n'a aucun enfant dans le
graphe, `reference_id` rattachant tout élément non-titre au dernier titre.

**L'index, corrigé** (audit, point 7) : la phrase « aucun index de propriété » du
rapport du lot 11 est fausse. `mesuré` le même jour, `SHOW TAG INDEXES` rend
**un** index, `doc_index` sur `Document(filename)`, et **aucun** sur `Code` ni sur
`ListItem` : `MATCH (v:ListItem) WHERE v.ListItem.text == ""` est refusé,
`IndexNotFound`, là où le même filtre passe sur `Document`. D'où le filtrage en
Python de ces sondes, comme au §4.27.

#### 4.37.h → **TRANCHÉ le 24 septembre 2026 : option (a), on ne touche pas aux puces vides.** Les six options et leur coût sur les 23 documents

**LA DÉCISION.** Le 24 septembre 2026, le propriétaire a retenu **l'option (a) :
on ne touche pas aux puces vides.** La réparation **sort du plan**. Sa prémisse,
du contenu perdu, était fausse (§4.36.b corrigé, §4.37.g) ; le tableau ci-dessous
reste, comme **coût chiffré de ce qui a été écarté**.

**Les raisons, chacune citée pour ce qu'elle est.**

- le texte des puces **arrive déjà au prompt** par les fragments frères —
  `mesuré` côté `rag-agent-chat` (leur registre §4.67.b, commits `b59b2ad` et
  `26c8bf4`) : **20 mots sur 22** pour `1adfce548d`, **55 sur 63** pour
  `842a8884da`. Leurs deux questions dites « perdues » ne l'étaient donc pas :
  leur banc cherchait l'**identifiant** et non le **texte** ;
- **(f) les casse**, parce que `_get_children` ne lit **qu'un niveau** —
  `lu` dans `rag-agent-chat`, `graph_context.py:633` (leur §4.71) ;
- **(e)** met le texte **deux fois** au prompt ;
- **(b)**, **(c)** et **(d)** coûtent des ancrages ou dupliquent — colonnes du
  tableau.

Ce paragraphe donne les coûts ; il ne choisit plus, le choix est fait.

**Comment chaque option est simulée**, `mesuré` le 24 septembre 2026 : dans le
processus de la sonde du §4.37.g, par remplacement **en mémoire** —
`src/docling_service/` n'est ni modifié ni committé. Chaque option refait la
conversion des 23 documents par le chemin de production, barrières armées,
journal vide ; ses relevés sont confrontés à l'**instantané** du §4.37.a par
`comparer_les_releves`, la fonction même du harnais. Sondes : `sonde_b.py`
(`c7721a19…`) pour a à e, `sonde_b2.py` (`b01f9f87…`) pour f, qui relève en plus
`reference_id`, `ref_position` et `depth` et reproduit l'option a de la
première à l'identique ; analyses `analyse_b.py` (`882b1817…`) et
`analyse_reassignes.py` (`89f7e27e…`), toutes dans le scratchpad de la reprise.
Durée : 629 s pour b à e, 311 s pour a et f.

- **(a)** ne rien faire ;
- **(b)** donner à la puce le texte de ses fragments, joints par une espace, et
  **garder** les fragments ;
- **(c)** donner à la puce ce texte et **ne plus émettre** les fragments ;
- **(d)** ne plus émettre les puces vides ;
- **(e)** donner à la puce ce texte pour l'affichage, en calculant son
  identifiant sur le texte de Docling (vide) — l'identité et le texte se séparent ;
- **(f)** ne rien changer aux textes, et **rattacher** chaque fragment à sa puce :
  `reference_id` de la puce, `depth` + 1, `ref_position` recompté — trois
  champs qui n'entrent pas dans `compute_id`.

« Fragment » est le sens du §4.37.g : descendant porteur de texte, sans entrer
dans une puce imbriquée. Dans (c) et (d), seule la boucle d'extraction est
filtrée : le découpeur voit le document entier, comme aujourd'hui — c'est une
hypothèse de la simulation, et une réalisation qui filtrerait aussi le document
Docling donnerait d'autres chunks.

| option | identifiants déplacés (absents de l'après) | dont voisins décalés par `position_in_page` | **réassignés** (même id, autre élément) | apparus sans contrepartie | caractères dupliqués dans le graphe | ancrages touchés — nos 44 | ancrages touchés — jeu de l'agent, 130 | ChromaDB : chunks, textes, chunks ré-ancrés | ce que l'agent reçoit pour une puce |
|---|---|---|---|---|---|---|---|---|---|
| **(a)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 367, inchangés, 0 | un sommet à `text` vide ; ses 727 fragments sont ses **frères** sous la section ; le texte est dans un chunk ancré sur la puce (84) ou sur un autre élément (118) |
| **(b)** | **202**, tous `list_item`, tous imputés à `text50` | 0 | 0 | 0 | **31 064** | **3** | **2** | 4 367, inchangés, 102 | le sommet porte le texte agrégé, sous un **nouvel** identifiant ; le graphe le porte **deux fois** |
| **(c)** | **9 941** : 727 fragments disparus, 9 022 voisins, 192 puces (18 par `text50` seul, 174 par le rang et le texte) | 9 022 | **231** (dont 10 puces reprises par du code) | 167 | 0 | **31** (dont 1 réassigné) | **59** | 4 367, inchangés, **2 659** | le sommet porte le texte agrégé, sous un nouvel identifiant ; les fragments **n'existent plus** |
| **(d)** | **9 682** : 200 puces disparues, 9 482 décalés | 9 482 | **490** — dont **2** : l'identifiant de la puce retirée, **repris** par une ligne de code vide | 187 | 0 | **31** | **59** | **4 306** (−61), textes **changés**, **2 659** | la puce **n'existe plus** ; son texte reste en fragments |
| **(e)** | 0 | 0 | 0 | 0 | **31 064** | 0 | 0 | 4 367, inchangés, 0 | le sommet porte le texte agrégé, sous son **ancien** identifiant ; le graphe le porte **deux fois**, et `text[:50]` n'est plus ce qui entre dans l'identifiant |
| **(f)** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 367, inchangés, 0 | un sommet à `text` vide, mais ses 727 fragments deviennent ses **enfants** par `PARENT_OF` ; **2 568** éléments changent de structure : 727 de `reference_id` et de `depth`, 2 568 de `ref_position` |

**Les définitions.** *Déplacé* : identifiant de l'instantané absent de l'après.
*Voisin décalé* : déplacé qui n'est pas une puce vide et dont l'appariement
montre `position_in_page` changé. *Réassigné* : identifiant présent des deux côtés
dont le label ou le `self_ref` change (§4.37.c). *Apparu sans contrepartie* :
identifiant de l'après absent de l'instantané et non apparié à un déplacé.
*Caractères dupliqués* : somme des longueurs des fragments encore émis dont la
puce porte l'agrégat. *Ancrage touché* : ancrage déplacé **ou** réassigné — nos
44 sont ceux de `2026-09-02-jeu-de-questions.yaml`, et la dérivation que l'agent
en tient (`rag-agent-chat/tests/fixtures/jeu_de_questions_pipeline.yaml`) porte
**exactement les mêmes 44** ; le jeu de l'agent est
`rag-agent-chat/tests/fixtures/golden_qa_generated.yaml`, 130 `gold_element_ids`
distincts, lu depuis ce poste. **CE QUE « 130 SUR 130 PRÉSENTS DANS L'INSTANTANÉ »
NE CORROBORE PAS**, et il faut l'écrire : ces 130 ancrages sont **dérivés de
ChromaDB** par `scripts/generate_golden.py` — c'est le jeu **SILVER**, `reviewed:
false`. Ils viennent donc de la même émission que l'instantané ; les y
retrouver tous est une **tautologie**, pas une vérification. Leur recouvrement
avec nos 44 est de **2**. Pour mémoire, le pilote de l'agent compte **172**
ancrages distincts sur ses **deux** jeux — chaque compte est cité ici avec sa
définition, et les trois ne se comparent pas terme à terme. *Chunk
ré-ancré* : chunk de l'option a dont l'identifiant (`<ancre>#<rang>`) n'existe
plus. *Textes inchangés* : les textes des chunks, triés, sont égaux à ceux de
l'option a.

**CE QUE L'AUDIT A MESURÉ EN PLUS — HISTORIQUE**, consigné parce que le coût
écarté doit rester lisible, et non parce qu'il reste à décider. `mesuré` par le
second audit du lot 11, 24 septembre 2026 :

| option | déplacements **à identifiant constant** (champs hors `compute_id`) |
|---|---|
| **(c)** | 227 `reference_id`, 227 `ref_position`, 12 `label`, 2 `text` |
| **(d)** | 485 `reference_id`, 485 `ref_position`, 4 `depth`, 7 `label`, 3 `text` |
| **(e)** | **202 identifiants non redérivables de leur `text`**, sur **18**
documents. Le compteur qui le verrait, `id emis != formule` de
`_verifier_l_emission`, est **imprimé sans jamais rougir** : c'est une trace, pas
un garde. NON TRAITÉ — l'option (e) étant écartée, le compteur reste tel quel, et
le dire ici vaut mieux que le corriger sans besoin |

**Trois lectures que le tableau porte, et qui ne sont pas des recommandations.**

- **(c) et (d) cascadent**, ce que la réparation chiffrée au §4.36.d ne fait
  pas, à juste titre : elle ne retire rien. Retirer un élément décale le rang de tous ceux qui
  le suivent dans la page, et un chapitre HTML est **une seule page**. Près des
  deux tiers des 15 173 identifiants bougent.
- **Les deux ancrages du jeu de l'agent sur une puce vide** sont `1adfce548d` et
  `842a8884da`, en plus de nos trois (`269b2e32d8`, `5558e561d7`, `e1ab19bc3b`,
  §4.36.a). Le §4.36.a ne comptait que les nôtres.
- **(d) change ce que ChromaDB sert** : 61 chunks de moins, et des textes
  différents. **NON VÉRIFIÉ** : la cause — sans doute des chunks dont la seule
  référence connue était la puce, écartés par `resolve_anchors`.

**CE QUE L'AGENT MESURE CHEZ LUI**, cité comme tel et `mesuré` **par eux** : leurs
fenêtres comptent **46 places sur 1 751** occupées par des éléments **vides** —
**20 `code` vides**, qui rendent un bloc vide et un marqueur `[src:…]` qui ne cite
rien, et **26 puces vides**. Ils le **répareront chez eux**, en filtrant avant le
fenêtrage. Rien à faire de ce côté-ci : c'est la conséquence directe de l'option
(a), et elle se traite là où elle coûte.

**NON VÉRIFIÉ, pour toutes les options** : l'effet sur les réponses de l'agent.
Aucune campagne d'évaluation n'a tourné sur une option simulée ; les colonnes
disent ce que les stores porteraient, pas ce que l'agent en ferait.

### 4.38 → la SECONDE reprise du lot 11 — le faux vert **bloquant** est fermé (**a** à **f** TRAITÉS), et l'émiettement est **COMPTÉ** (**g** : mesure, AUCUNE correction). **Les **c**, **d** et **f** sont repris par le §4.39**

Le second audit a déclaré le lot **non fusionnable** pour **un seul** motif
bloquant, le **a** ci-dessous. Les deux faux verts du premier audit rougissent
toujours, l'ensemble déclaré tient dans ses quatre cas, l'instantané a été
vérifié indépendamment contre le graphe document par document, et aucun client
MinIO réel n'est construit : rien de cela n'a bougé.

**L'instantané n'a pas bougé non plus.**
`documentation/campagnes/2026-09-24-instantane-des-identifiants/` garde son
empreinte `e945893b1021e2f1aa3809434a889443ed9fb85e2a7e290cd329f077687f0f6d`,
octet pour octet — `mesuré` au début et à la fin de ce lot par
`sha256sum .../MANIFESTE.tsv`.

**Porte qualité**, `mesuré` le 24 septembre 2026 : `make all`, rc=0, **1 013
tests passés** (982 sur `3625816`), plus **14 mutations rejouées, 14 rouges**.

#### 4.38.a → TRAITÉ, et c'est ce qui bloquait la fusion — **la couverture ne se compare plus que dans un sens**

`_ecarts_de_couverture` ne comparait chaque paire que dans **un** sens (`a − b`
pour `a < b` en ordre alphabétique) : `instantane − corpus`, `instantane −
graphe` et `graphe − corpus` n'étaient **jamais** calculés. Puis `comparer`
faisait `if partition_key not in fige or partition_key not in corpus: continue`.

**Le faux vert, `mesuré` sur `3625816`** le 24 septembre 2026
(`uv run python` sur le monde factice des tests, rc du processus) :

| monde | rc sur `3625816` | rc après réparation |
|---|---|---|
| `/corpus` **VIDE**, instantané à 1 document | **0**, et `OK` — **aucun identifiant comparé** | **1** |
| instantané à 2 documents, corpus à **1** | **0**, et `OK` | **1** |
| graphe **vide**, corpus intact | 1 — déjà rouge par le sens `corpus − graphe` | 1 |

Le corpus arrive par un **montage**, et ce dépôt a déjà connu une purge qui
emportait 24 fichiers sur 25 (§4.34) : un montage vide ou amputé rendait donc
`OK`.

**Ce qui a été fait.** Les paires sont comparées **dans les deux sens**, comme la
docstring le promettait. Tout document de l'instantané qui n'a **pas** été
comparé est une **raison**, jamais un `continue` muet. La sortie porte
`DOCUMENTS COMPARES n / n de l'instantane`, et rougit s'ils diffèrent. Cinq
tests, dont **trois rouges d'abord** sur `3625816` — le troisième monde ci-dessus
était déjà rouge, son test est gardé contre un retour en arrière.

**Un garde qu'un autre garde couvre n'est pas tenu** : la raison
« n'ont PAS été comparés » **survivait** à son propre retrait, l'écart de
couverture rougissant déjà. Le test l'exige désormais **nommément** (mutation
`A1-b` de la table du §4.38.f).

#### 4.38.b → TRAITÉ — le garde « un journal de barrières non vide est un rouge » est tenu **des deux côtés**

Le garde existait dans `comparer`, mais **aucun test ne le tenait** : `mesuré`
par l'audit, son retrait dans `comparer` **seul** laissait 55 tests verts. Le
pendant de `test_une_barriere_touchee_est_rouge_meme_avalee`, côté `comparer`,
est écrit ; sous la mutation, il est le **seul** à rougir.

#### 4.38.c → TRAITÉ, puis **REPRIS par le §4.39.a** — l'empreinte devenait une MESURE, mais à un site que l'ARGUMENT désignait

**Rien n'interdisait de re-tautologiser le harnais.** `mesuré` par l'audit :
`figer` dans un dossier **neuf** après la campagne rend rc=0, puis `comparer`
contre ce nouvel instantané rend rc=0 aussi — le harnais comparait de nouveau le
code du jour à lui-même, le défaut même qui lui a donné sa forme (§4.37).

> **Le site choisi ci-dessous a été REPRIS par le §4.39.a** : il se déduisait du
> dossier passé en argument, et trois gestes suffisaient à le contourner. Le
> fichier `empreintes-des-instantanes.tsv` n'existe plus.

**Le site choisi, et pourquoi.**
`documentation/campagnes/empreintes-des-instantanes.tsv`, le **parent** du
dossier de l'instantané. Hors du dossier, et ce n'est pas un rangement : un
second instantané porte son **propre** manifeste, donc sa propre empreinte, et
une empreinte rangée à l'intérieur **se re-signerait elle-même**. Le parent est
versionné, revu au commit, et **monté avec** l'instantané
(`documentation/campagnes` → `/campagnes`), donc lisible dans le conteneur sans
montage de plus. Un dossier **absent** de la table est **refusé**, pas toléré :
c'est exactement le cas du second instantané qu'on viendrait d'écrire.

`comparer` rougit si l'empreinte diffère de celle qu'attend la table. Et
`figer` dans le **même** dossier rend désormais un **rc=1 avec un message**, là
où `FileExistsError` remontait nue — une trace d'appel n'est pas un verdict,
dans un script dont le code de sortie **est** le comportement.

#### 4.38.d → TRAITÉ, puis **RETIRÉ par le §4.39.b** — la dérivation AST a laissé passer quatre portes neuves sur cinq

> **CE PARAGRAPHE DÉCRIT UN DISPOSITIF QUI N'EXISTE PLUS.** Tout ce qu'il
> affirme au présent — les 22 porteurs, les trois classes « sans quatrième
> cas », les deux gardes contre les pièges de la mesure — a été **retiré** par
> le §4.39.b, après que le troisième audit lui a fait passer **quatre portes
> neuves sur cinq**. Il est conservé parce qu'un constat corrigé ne s'efface
> pas ; il ne décrit plus le code.

Le balayage des origines était borné à `MODULES = (nebula, vectors, storage,
images)`, une seconde liste en dur, non défendue. `mesuré` par l'audit : une
porte écrivante neuve déposée dans `extraction.py` **passait**, rc=0, 5 tests
verts.

**La dérivation.** Le test part de trois **semences** — les constructeurs de
client de store, `Minio`, `ConnectionPool`, `HttpClient` — et calcule par
**point fixe**, sur le texte de **tout** `src/docling_service/*.py`, l'ensemble
des fonctions qui **construisent ou reçoivent** un client : une fonction qui en
appelle une autre déjà porteuse l'est à son tour. Elle rend **22 porteurs**, là
où l'ancienne liste en balayait quatre modules.

Chacun des 22 est ensuite **barré**, ou **classé** avec sa raison, sans
quatrième cas : 8 portes plus le témoin MinIO ; 9 `NON_ECRIVAINS` — les chemins
de production que le harnais **appelle** et qui n'atteignent les stores que par
une porte barrée ; 4 `HORS_PROCESSUS`, les points d'entrée FastAPI de `main`,
dont le module ne s'importe pas sur l'hôte et dont un test **mesure** qu'ils ne
sont pas chargés dans le processus du harnais. Ils ne sont **pas sautés en
silence** : les omettre rougit.

**Deux gardes de plus, contre les pièges de la mesure.** Une semence qui ne sème
rien laisserait la dérivation vide et muette : le test exige que chaque semence
construise réellement un client — il a d'ailleurs rougi sur `PersistentClient`,
retiré depuis. Et une semence protège d'une porte neuve, non d'un **client**
neuf : un second test fige les SDK de store importés (`minio`, `nebula3`,
`chromadb`), de sorte que passer à une autre classe de client rougisse au lieu
d'aveugler la dérivation.

**Le rouge montré** : la porte neuve déposée dans `extraction.py` (mutation `A4`)
rend `des porteurs de client de store ne sont ni barrés ni classés :
['src.docling_service.extraction.archiver_le_document']`. `src/docling_service/`
n'est **pas** modifié par ce lot : la mutation est appliquée puis restaurée, et
le rejeu le vérifie par `git diff`.

#### 4.38.e → TRAITÉ — **sept garanties écrites** reçoivent leur test, et **deux libellés** du §4.37.g sont rectifiés

Sept mutants de l'audit **survivaient** à la porte : autant de phrases écrites
que rien ne tenait. Chacune a désormais son test, rouge sur le mutant et vert
sur le code (mutations `M31`, `M22`, `M14`, `M28`, `M32`, `M34`, `M35` du
§4.38.f) : les cinq champs du relevé lus par indexation et non `.get` — le seul
test portait sur `page_position` —, la clé d'objet **apparue** inattendue, le
nombre de lignes annoncé par le manifeste, le `format` de l'instantané, la
validation des éléments par la capture, `identiques` qui retranche les
réassignés, et l'empreinte de l'entrée convertie signalée devant un rouge.

Trois d'entre eux reçoivent en outre leur **contrepartie verte**, sans laquelle
le test passerait sur un garde inconditionnel : `self_ref` **tolère** l'absence,
à dessein ; une clé apparue **sous un déplacement déclaré** est verte ; une
entrée **inchangée** ne se signale pas.

**Les deux libellés du §4.37.g**, rectifiés sur place : « 14 puces avec une puce
imbriquée » est « avec une puce imbriquée **qui porte du texte** » — **21**
sinon ; et « C2 = 78, le texte de tous leurs **fragments** » est « de tous leurs
**descendants porteurs** » — **79** si l'on compte sur les fragments.

#### 4.38.f → TRAITÉ, puis **REPRIS par le §4.39.c** — la table se rejouait, mais en écrivant dans l'arbre de travail

Le défaut nommé au §4.35.e : les 33 mutations du premier passage n'étaient pas
versionnées, et l'audit n'a **pas pu** les rejouer. Une mutation qu'on ne peut
pas rejouer n'est pas une mesure, c'est une affirmation.

> **Le rejeu décrit ici écrivait dans l'arbre de travail**, et son verdict
> prenait un fichier cassé pour un rouge : voir le §4.39.c, qui l'a repris.

`tests/mutations/table-des-mutations.json` porte les **14** mutations de ce lot,
chacune avec **son site** (fichier + motif exact), **son remplacement** et **le
test censé rougir**. Les mutants de l'audit y sont entrés.
`scripts/rejouer-les-mutations.py` les applique une à une, lance le test visé,
**exige un rouge**, restaure, puis vérifie **par `git diff`** qu'il ne laisse
aucun fichier muté — un `finally` ne survit pas à un `SIGKILL`, et laisser un
fichier muté derrière soi, c'est livrer la mutation. Un motif qui n'apparaît pas
**exactement une fois** fait échouer le rejeu : une mutation qui ne mute rien
ressemble à un garde qui ne voit rien.

**Il entre dans la porte, et c'est une MESURE qui le décide.** Le chiffre écrit
ici était **faux** — « 34,2 s » pour une somme qui en faisait **35,4** (30,4 +
5,0), relevé par le troisième audit. Il a été **remesuré** après la réparation de
la troisième reprise, et il ne vit plus qu'à **un seul site, le §4.39.e**, que
le `Makefile` cite sans le répéter.

Le prix est tenu pour acceptable au regard de ce que le §4.35.e reprochait ; la
cible `mutations` du `Makefile` est séparée, donc retirable d'une ligne si
l'avis change.

#### 4.38.g → MESURÉ, lecture seule — **l'ÉMIETTEMENT compté sur l'instantané** : 742 éléments d'un seul caractère, dont 208 « . » et 121 « ) »

Docling découpe un `<li>` ou un paragraphe mis en forme (gras, lien, code en
ligne) en **plusieurs** éléments, parfois d'**un seul caractère**. Chacun coûte
une place de fenêtre et un marqueur `[src:…]` au prompt de l'agent. **On le
consigne et on le compte ; on ne le corrige pas**, parce que le corriger
déplacerait des milliers d'identifiants — c'est la même cascade que les options
(c) et (d) du §4.37.h, et la décision du 24 septembre 2026 est l'option (a).

**La commande**, `mesuré` le 24 septembre 2026, **depuis l'instantané versionné
et lui seul** — aucune conversion, aucun store, aucun client :

```
PYTHONPATH=. uv run python scripts/campagne/compter-l-emiettement.py \
    documentation/campagnes/2026-09-24-instantane-des-identifiants
```

**La borne de ces comptes, et elle est exacte.** L'instantané porte `text50`,
**tronqué à 50 caractères** : toute longueur **strictement inférieure à 50** y
est donc exacte, et une longueur de 50 signifie « 50 ou plus », qu'on ne sait
pas départager. **5 762** des 15 173 éléments sont dans ce cas. Tous les comptes
ci-dessous portent sur des longueurs **exactes** ; c'est pourquoi la tranche
haute s'arrête à 49. Les totaux se referment : 1 564 vides + 7 847 de 1 à 49
caractères + 5 762 tronqués = **15 173**, ce qu'un test vérifie.

**Les définitions, à côté des comptes.** *Vide* : `text50 == ""`, compté **à
part** — un élément sans texte n'est pas un texte court. *Tranche* : bornes
**inclusives** aux deux bouts, sur `len(text50)`. *Format* : l'extension de la
partition, `.html` ou `.pdf`, lue du manifeste. *Texte court fréquent* : le
`text50` **exact**, de 1 à 20 caractères, et ses occurrences sur les 23
documents.

**Par format** (23 documents, 15 173 éléments) :

| tranche | HTML | PDF | total |
|---|---|---|---|
| vide | 1 564 | 0 | **1 564** |
| 1 caractère | 742 | 0 | **742** |
| 2 à 5 | 838 | 17 | **855** |
| 6 à 20 | 3 414 | 142 | **3 556** |
| 21 à 49 | 2 632 | 62 | **2 694** |
| **moins de 50 (1 à 49)** | 7 626 | 221 | **7 847** |
| tous | 14 808 | 365 | **15 173** |

**Par label**, tous formats confondus :

| label | vide | 1 car. | 2-5 | 6-20 | 21-49 | < 50 | tous |
|---|---|---|---|---|---|---|---|
| `caption` | 0 | 0 | 0 | 0 | 1 | 1 | 201 |
| `code` | 1 362 | 186 | 233 | 1 411 | 837 | **2 667** | 4 963 |
| `list_item` | 202 | 0 | 24 | 355 | 386 | 765 | 1 748 |
| `picture` | 0 | 0 | 0 | 0 | 0 | 0 | 209 |
| `section_header` | 0 | 0 | 50 | 186 | 335 | 571 | 600 |
| `table` | 0 | 0 | 0 | 0 | 0 | 0 | 55 |
| `text` | 0 | **556** | 548 | 1 552 | 1 055 | **3 711** | 7 251 |
| `title` | 0 | 0 | 0 | 52 | 80 | 132 | 146 |

Le détail par label **et** par format est rendu par la même commande ; en deux
lignes : le PDF n'a **aucun** élément vide ni d'un seul caractère, et l'émiettement
est un phénomène **HTML**. Les **202** puces vides du §4.37.g s'y retrouvent
exactement, ligne `list_item` colonne « vide ».

**Les 20 textes courts les plus fréquents** (1 à 20 caractères) :

| rang | occurrences | long. | texte |
|---|---|---|---|
| 1 | **208** | 1 | `.` |
| 2 | **121** | 1 | `)` |
| 3 | 93 | 3 | `and` |
| 4 | 86 | 1 | `,` |
| 5 | 70 | 2 | `).` |
| 6 | 61 | 3 | `The` |
| 7 | 42 | 5 | `, and` |
| 8 | 42 | 4 | `Note` |
| 9 | 32 | 1 | `:` |
| 10 | 31 | 6 | `double` |
| 11 | 28 | 13 | `import mlflow` |
| 12 | 27 | 1 | `1` |
| 13 | 27 | 1 | `2` |
| 14 | 26 | 9 | `Chapter 5` |
| 15 | 26 | 14 | `databricks.yml` |
| 16 | 24 | 2 | `In` |
| 17 | 22 | 9 | `Chapter 9` |
| 18 | 21 | 1 | `6` |
| 19 | 21 | 9 | `Chapter 6` |
| 20 | 19 | 1 | `3` |

**Ce que cela dit, et ce que cela ne dit pas.** **742** éléments portent un seul
caractère, et les quatre premiers du classement — `.`, `)`, `,`, `).` — en font
**485** à eux seuls : ce sont des fins de phrase et des parenthèses fermantes
détachées du texte qu'elles terminent, exactement le phénomène décrit. **1 597**
éléments font 5 caractères ou moins sans être vides. **NON VÉRIFIÉ** : combien
de ces éléments entrent réellement dans une fenêtre de l'agent, et ce qu'ils y
coûtent — cela se mesure côté `rag-agent-chat`, sur leurs fenêtres, et le §4.37.h
en porte déjà un compte à eux (46 places sur 1 751).

**Ce qui n'a PAS été compté, et pourquoi.** Le nombre d'éléments par `<li>`
d'origine, et la reconstitution du paragraphe source : l'instantané ne porte ni
la hiérarchie (`parent`, `children`) ni le texte complet au-delà de 50
caractères. Les compter exigerait de **reconvertir** le corpus, donc de sortir de
la lecture seule ; ce n'est pas fait, et ce n'est pas estimé.

### 4.39 → la TROISIÈME reprise du lot 11 — les **deux** motifs bloquants sont fermés, et la preuve de non-écriture passe de la LECTURE DU CODE à l'EXÉCUTION

Le troisième audit a déclaré le lot **non fusionnable** pour deux motifs
bloquants : l'empreinte attendue se lisait à un site que l'**argument**
désignait (**a**), et la dérivation AST des barrières laissait passer **quatre
portes neuves sur cinq** (**b**). Ce qu'il a par ailleurs confirmé n'a pas
bougé : A1 est fermé contre les vrais stores, l'ensemble déclaré tient, le
chantier C est exact au dernier chiffre.

**L'instantané n'a pas bougé.**
`documentation/campagnes/2026-09-24-instantane-des-identifiants/` garde son
empreinte `e945893b1021e2f1aa3809434a889443ed9fb85e2a7e290cd329f077687f0f6d`,
octet pour octet — `mesuré` au début et à la fin de cette reprise par
`sha256sum .../MANIFESTE.tsv`. **Aucun document du corpus ne porte un `mtime`
du jour** : `find Datas -path 'Datas/.cleaned' -prune -o \( -name '*.pdf' -o
-name '*.html' \) -newermt "2026-09-24 00:00" -print` rend **0** sur **25**
fichiers. *(L'exclusion de `Datas/.cleaned/` n'est pas un détail : sans elle la
commande rend **47**, parce que ce répertoire porte 22 copies produites par
l'étape de nettoyage, qui ne sont pas le corpus. Corrigé le 25 septembre 2026,
§4.41.)*

**Porte qualité**, `mesuré` le 24 septembre 2026 : `make all`, rc=0, **1 053
tests passés** (1 013 sur `f717565`), plus **27 mutations rejouées, 27 rouges**
(14 sur `f717565`). **À l'issue de la quatrième reprise (§4.40) : 1 084 tests et
35 mutations, toutes rouges, rc=0.**

**Les huit comptes des stores, relevés au DÉBUT et à la FIN de la reprise**, en
lecture seule — `MATCH`/`GO` dans le graphe, `count()` par collection ChromaDB,
`list_objects` dans MinIO, jamais `SHOW STATS` (§4.27 n° 1) :

| compte | début | fin |
|---|---|---|
| sommets, tous tags | 15 196 | **15 196** |
| `Document` | 23 | **23** |
| `Paragraph` | 7 251 | **7 251** |
| `ListItem` | 1 748 | **1 748** |
| `Code` | 4 963 | **4 963** |
| arêtes `PARENT_OF` | 15 173 | **15 173** |
| chunks (ChromaDB) | 4 367 | **4 367** |
| objets (MinIO) | 212 | **212** |

Rien n'a bougé. Ce lot n'écrit dans aucun store, et c'est désormais une barrière
à l'exécution qui le tient (§4.39.b) et non une intention.

#### 4.39.a → TRAITÉ, bloquant — **l'empreinte attendue ne dépend plus de l'argument**, et le répertoire de campagne est FIXE

**Le faux vert, tel que l'audit l'a mesuré contre les vrais stores.**
`empreinte_attendue` lisait `dossier.parent / EMPREINTES` — donc le fichier
voisin du dossier qu'on lui **désignait**. Trois gestes suffisaient :
`figer /sp/bis/2026-09-24-instantane-des-identifiants` (rc=0), un `sha256sum`
et un `printf` dans `/sp/bis/empreintes-des-instantanes.tsv`, puis
`comparer /sp/bis/…` → **rc=0, `OK`, 23 / 23**. Le harnais était de nouveau
tautologique : il comparait le code du jour à un instantané écrit par le code du
jour, authentifié par une table écrite par la même main. La réparation du
§4.38.c avait déplacé le site sans le **fixer**.

**Le choix, et pourquoi celui-là.** Les trois options ouvertes étaient une
constante du module, un chemin résolu depuis le module, ou le refus de tout
dossier hors d'un répertoire de campagne fixe. **Seule la troisième fait rendre
1 aux trois gestes** — les deux premières ne ferment que le geste de
comparaison, et laissent `figer` écrire n'importe où. Elle est retenue, et
**combinée** à la première, parce qu'un montage en lecture seule est un choix
d'exécution et non une garantie :

1. `REPERTOIRE_DE_CAMPAGNE = Path(__file__).resolve().parents[1] /
   "documentation/campagnes"`, résolu depuis l'emplacement du **module**.
   `dossier_de_campagne` refuse tout dossier qui n'en est pas un **enfant
   direct** — un `…/campagnes/bis/instantané` porterait sa propre table voisine ;
2. `EMPREINTES_ATTENDUES`, un **dictionnaire du module**. Le fichier
   `empreintes-des-instantanes.tsv` est **supprimé** : un site canonique, pas
   deux.

**La borne restante s'écrit ici, et elle est voulue** : modifier une empreinte
ou inscrire un instantané exige un **commit sur `src/`**, revu comme du code.
`src/` est monté en lecture seule dans l'image d'extraction, et c'est lui qui
**est** le harnais.

**Le montage change, et c'est la conséquence du choix.**
`documentation/campagnes` était monté sur `/campagnes` ; il l'est désormais sur
`/app/documentation/campagnes`, là où le module le résout. Le geste canonique du
docstring de `verifier-l-equivalence-des-identifiants.py` est à jour.

**Les trois gestes de l'audit, remesurés DANS L'IMAGE**, 24 septembre 2026, rc du
processus :

| geste | sur `f717565` | après réparation |
|---|---|---|
| `figer /sp/bis/2026-09-24-instantane-des-identifiants` | **rc=0**, instantané écrit | **rc=1**, « hors du repertoire de campagne /app/documentation/campagnes », **rien n'est écrit** |
| `printf` dans `/sp/bis/empreintes-des-instantanes.tsv` | authentifiait | **la table voisine n'est plus lue du tout** |
| `comparer /sp/bis/2026-09-24-instantane-des-identifiants` | **rc=0**, `OK`, 23 / 23 | **rc=1**, même refus, **avant tout armement et toute connexion** |

**Et le geste légitime tient dans l'image**, même jour :
`comparer documentation/campagnes/2026-09-24-instantane-des-identifiants`
franchit le garde, lit la constante, arme **9 portes sur 11 sites** et **15
constructeurs de SDK**, interroge le graphe et le corpus par ses clients de
lecture, puis s'arrête sur `copie nettoyee manquante : /sp/cleaned/…` — la
campagne les produit, ce lot ne les fabrique pas. **NON VÉRIFIÉ** : la
comparaison complète des 23 documents contre les stores, faute des copies
nettoyées ; ce lot ne touche pas à la logique de comparaison, seulement à la
résolution du dossier.

#### 4.39.b → TRAITÉ, bloquant — **la barrière descend aux CONSTRUCTEURS des SDK**, et la dérivation AST est RETIRÉE

> **NOTE HISTORIQUE, relevée par le quatrième audit.** Le travail décrit
> ci-dessous est dans **`3113ead`**, et **non** dans `55b7214`. Les deux commits
> portent des titres qui ne décrivent pas leur contenu : `3113ead` porte tout le
> travail de la troisième reprise sous un titre qui n'en annonce qu'un tiers
> (« l'empreinte attendue cesse de dépendre du dossier qu'on désigne »), et
> `55b7214` annonce ce qu'il ne contient pas (« la barrière descend aux
> constructeurs des SDK »). Chercher cette barrière dans `55b7214` ne la trouve
> pas. Les commits ne se réécrivent pas — c'est la règle du chantier — donc la
> correction est **ici**, au registre.

**Ce que la dérivation laissait passer**, `mesuré` par l'audit : quatre des cinq
portes neuves — un alias d'import (`from minio import Minio as _M`), un
`getattr(minio, "Minio")(…)`, un client construit **au niveau du module**, et une
porte déposée dans `src/pipeline/`, hors du dossier balayé. Et ses quatre
`HORS_PROCESSUS` ne reposaient que sur l'absence de `fastapi` **sur l'hôte** :
dans l'image d'extraction, `src.docling_service.main` s'importe et les quatre
ressortent **liés**.

**Décision du pilote, 24 septembre 2026 : on ne rafistole pas l'analyse
statique.** Aucune analyse statique du Python n'est complète — `getattr` suffit
à la tromper — et chaque audit trouverait le trou suivant.

**La barrière est posée sur les constructeurs eux-mêmes**
(`barrer_les_sdk_de_store`). Deux gestes par constructeur, et il faut les deux…
sauf que **la mesure en a rendu un inutile** : un `setattr` explicite sur le
module du SDK figurait d'abord à côté du balayage de `sys.modules` ; le retirer
ne rougissait **aucune** des sept portes neuves, parce que le module du SDK est
lui-même dans `sys.modules`. Une ligne qu'aucune mutation ne tient est une ligne
qui ne garde rien : elle est partie. Reste **le balayage de tout `sys.modules`**,
qui re-lie l'objet d'origine partout où il est déjà nommé, alias compris, dans
n'importe quel paquet.

**Les constructeurs sont ÉNUMÉRÉS depuis le SDK installé, jamais de mémoire** —
une liste en dur se trompe en silence. Une règle par SDK, écrite à son site :

| module | règle | `mesuré` dans l'image, 24 septembre 2026 |
|---|---|---|
| `minio` | classes publiques qui **ne sont pas des exceptions** | `Minio`, `MinioAdmin` |
| `nebula3.gclient.net` | classes publiques en `…Pool`, plus `Connection` | `Connection`, `ConnectionPool` |
| `nebula3.gclient.net.SessionPool` | idem — `SessionPool` est une classe d'un **sous-module**, que le paquet n'expose pas | `SessionPool` |
| `chromadb` | **fonctions** publiques en `…Client` (les noms en `Client` qui sont des **classes** sont les interfaces abstraites) | `AdminClient`, `AsyncHttpClient`, `Client`, `CloudClient`, `EphemeralClient`, `HttpClient`, `PersistentClient` |
| `chromadb.api.client` | **classes** publiques en `…Client` — ajouté par le §4.40.f, parce que les noms de `chromadb` sont des fabriques, sans `__init__` à barrer | `AdminClient`, `Client`, `SharedSystemClient` |

**12 constructeurs barrés** au total à la troisième reprise, **15** depuis le
§4.40.f, `mesuré` dans l'image le 24 septembre 2026. Un SDK absent du processus est **nommé
absent**, jamais sauté en silence : sur l'hôte, `nebula3` et `chromadb` ne
s'importent pas, et le relevé le dit.

**Les portes neuves, mesurées DANS L'IMAGE d'extraction**, là où le harnais
tourne avec ses montages, rc du processus, 24 septembre 2026 : **0 / 12 lèvent
sur `f717565`**, **12 / 12 après réparation**. Les cinq de l'audit, plus sept
variantes de ce lot :

| # | porte | `f717565` | après |
|---|---|---|---|
| 1 | alias d'import **après** armement | passe | **lève** |
| 2 | alias d'import **avant** armement | passe | **lève** |
| 3 | `getattr(minio, "Minio")(…)` | passe | **lève** |
| 4 | client construit **au niveau du module**, importé après armement | passe | **lève** |
| 5 | porte déposée dans `src/pipeline` (`MinioImageExporter._get_client`) | passe | **lève** |
| 6 | `minio.MinioAdmin` | passe | **lève** |
| 7 | `importlib.import_module("minio").Minio(…)` | passe | **lève** |
| 8 | `nebula3` `ConnectionPool`, alias avant armement | passe | **lève** |
| 9 | `nebula3` `SessionPool` par `getattr` | passe | **lève** |
| 10 | `chromadb.HttpClient`, alias avant armement | passe | **lève** |
| 11 | `chromadb.Client` par `getattr` | passe | **lève** |
| 12 | `chromadb.PersistentClient`, que la production ne nomme nulle part | passe | **lève** |

Sept d'entre elles entrent dans la porte qualité de l'hôte
(`TestLesPortesNeuvesLevent`) : `minio` est le **seul** des trois SDK installé
hors conteneur, et un test qui exige un conteneur n'est pas un test de la porte.

**Les SEULS clients permis sont ceux de LECTURE, construits AVANT l'armement**,
et ils portent leur propre borne, parce qu'ils survivent à la barrière :

- la session Nebula est enveloppée dans `SessionEnLecture`, qui refuse toute
  requête dont un fragment ne commence pas par un verbe de lecture (`USE`,
  `MATCH`, `GO`, `LOOKUP`, `FETCH`, `SHOW`, `DESCRIBE`, `DESC`, `RETURN`,
  `YIELD`). **Les séparateurs sont les trois de `SEPARATEURS` — `;`, le tube
  `|` et le saut de ligne — et il en manquait DEUX** : c'est le défaut B3 du
  quatrième audit, traité au §4.40.c. **La borne est écrite au site, et elle
  est désormais VRAIE** : un séparateur à l'intérieur d'une chaîne citée compte
  pour un séparateur, donc le garde refuse **plus** que nécessaire, jamais
  moins — `mesuré` par un test, et non plus affirmé ;
- le client MinIO est enveloppé dans `LectureSeule`, qui ne laisse passer que
  `list_objects` et journalise tout le reste avant de lever.

**Les barrières par site restent**, comme seconde couche : 9 portes, 11 sites,
`mesuré` dans l'image. Le test qui les tient ne **dérive** plus rien — il part de
la liste **déclarée** `PORTES` — et **ne promet plus rien d'autre** que ce qu'il
mesure : que les portes nommées sont déliées partout.

**Ce que deviennent la dérivation, `NON_ECRIVAINS` et `HORS_PROCESSUS` :
RETIRÉS**, avec les trois tests qui en dépendaient. Ils promettaient une
exhaustivité (« aucun quatrième cas ») qu'ils ne tenaient pas, et **deux de
leurs classements étaient faux sans que personne le voie** :
`images.ensure_bucket` était donné pour un non-écrivain alors qu'il appelle
`make_bucket` ; et les raisons d'`extraction.extract` et d'`extraction._extract_pdf`
n'énuméraient que `persist`, `get_writer` et `crop_and_upload`, en **omettant
`storage.forget_document`**. Les corriger aurait conservé un dispositif dont la
décision du pilote dit qu'il ne peut pas être complété — ils sont nommés ici, et
retirés là-bas. `SEMENCES` disparaît avec eux. `SDK_DE_STORE` **reste**, avec un
rôle changé : il ne garde plus une dérivation, il nomme les SDK que la barrière
d'exécution couvre, et rougit si la production en importe un autre.

**La borne restante s'écrit ici**, et elle est RÉDUITE par le §4.40.f : un
client construit dans un **sous-processus**, ou par une bibliothèque tierce qui
parle à un store **hors de ces trois SDK** — un client S3 `boto3`, un driver
HTTP écrit à la main — n'est pas atteint. La barrière tient sur ce qui est
importé dans le processus du harnais. **Ce qui n'est plus une borne** : les
chemins de construction qui ne passent par aucun nom, que le seul rebondage
laissait passer ; voir le §4.40.f.

#### 4.39.c → TRAITÉ — **le rejeu ne touche plus JAMAIS l'arbre de travail**, et son verdict distingue un rouge d'un fichier cassé

**Trois défauts, tous mesurés par l'audit.** Le rejeu mutait les fichiers de
**production en place** : `extraction.py` restait muté **0,66 s** sur disque
pendant `make all` ; après un `SIGKILL` le fichier restait muté, et le lancement
suivant le prenait pour l'origine puis le « restaurait » **muté**. Le contrôle
final par `git diff` comparait l'arbre à l'**index**, donc laissait passer un
résidu **indexé** et rendait un faux « ECHEC » devant une modification légitime
non commitée. Et une mutation qui **cassait la syntaxe** passait pour « ROUGE »,
un rc non nul suffisant au verdict.

**Le rejeu se fait sur une COPIE JETABLE**, dans un répertoire temporaire.
`mesuré` le 24 septembre 2026 : **0,018 s** pour `src/`, `tests/`, `scripts/`,
`documentation/campagnes/` et `pyproject.toml`, contre **0,335 s** pour un
`git worktree add --detach`. La copie est retirée à la sortie ; **après un
`SIGKILL` elle survit** dans le répertoire temporaire du système, et c'est sans
conséquence : elle ne partage aucun fichier avec l'arbre, et le système la
nettoie. C'est exactement la raison pour laquelle la copie est préférée au
worktree, dont l'abandon laisserait une entrée dans `.git/worktrees` à purger.

**Le même environnement Python, et aucun `uv run` dans la copie**, `mesuré` :
le rejeu lance `sys.executable -m pytest` avec `cwd` sur la copie ; l'interpréte
est `…/.claude/worktrees/lot-11-rag-reprise-be3271/.venv/bin/python3`, celui du
parent, et la copie ne porte ni `.venv` ni `uv.lock` — rien à partir de quoi
`uv` créerait un environnement neuf.

**La sonde, mesurée de l'extérieur.** Un échantillonnage des `mtime` et des
tailles de `src/` et `tests/` toutes les 5 ms, `__pycache__` exclu, pendant
`make mutations` :

| | `f717565` | après réparation |
|---|---|---|
| échantillons / durée | 475 en 4,8 s | 1 375 en 12,6 s |
| fichiers touchés | **2** — `src/equivalence_des_identifiants.py` (465 événements), `src/docling_service/extraction.py` (272) | **aucun** |

Le script porte en outre **sa propre** sonde : il relève les `mtime` avant et
après, et rougit si l'un a bougé — **84 fichiers surveillés**, `mesuré` le
24 septembre 2026 par `empreinte_des_mtime(RACINE)`. Elle remplace le
`git diff`, et elle est elle-même tenue par une mutation (`A9-d`).

**Elle ne surveille QUE les sources, et c'est la réparation B1 du quatrième
audit.** Elle faisait un `rglob("*")` nu : **162** fichiers, dont **78** `.pyc`
— que l'interpréteur réécrit de lui-même. `mesuré` par l'audit : un
`python -c "import src.index_report"` lancé depuis l'arbre **pendant**
`make mutations` faisait rendre **2** à `make`, le rejeu se déclarant « ECHEC :
le rejeu a TOUCHE l'arbre de travail » alors qu'il n'avait touché que sa copie.
`__pycache__` est exclu par une clause sur `chemin.parts`, et le compte tombe
à **84** = 162 − 78. Un garde qui rougit sur ce qu'il ne garde pas finit par
être désarmé ; les deux sens sont tenus par un test, le `.pyc` touché ne
rougit plus et le `.py` touché rougit toujours.

**Le verdict exige les trois** : `rc == 1`, `failed` dans la dernière ligne, et
**aucun** `error`. Chacune des trois clauses a son cas de test qui la tient
seule — c'est ce qu'il a fallu pour que `A9-a`, `A9-b` et `A9-c` rougissent.
Une entrée de table qui **casse la syntaxe** fait désormais échouer le rejeu,
et c'est un test de bout en bout qui le montre.

`mutations` est ajouté à `.PHONY`.

#### 4.39.d → TRAITÉ — les quatre petits, et ce qu'ils ont coûté

**4a — `scripts/` entre dans `lint` et dans `typecheck`.**
`scripts/rejouer-les-mutations.py` était **exécuté** par `make all` sans être
contrôlé par elle. `mesuré` le 24 septembre 2026 : mettre **tout** `scripts/`
dans les deux cibles ne rougit **rien** — `ruff check src/ tests/ scripts/` :
`All checks passed!`, 6 fichiers dans `scripts/` ; `mypy src/ scripts/` :
`Success`, **40 → 42** fichiers. Les deux gardes cessent de diverger, comme pour
`tests/` au lot 4.

**4b — les deux mutants survivants de `compter-l-emiettement.py` meurent.**
Aucun chiffre par format ni par label du §4.38.g n'était tenu. Un **jeu d'essai**
à deux documents porte désormais la propriété **« aucun élément vide ni d'un
caractère dans les PDF »** : le HTML en porte un de chaque, le PDF aucun. Le
mutant `lo == 0` → `lo <= 1` fait passer la case « vide » du HTML de 1 à 2 et
rougit. Le PDF du jeu est rangé sous `livres/v1.2/`, un dossier **à point** : le
mutant `rsplit` → `split` y lit le format « 2/UN LIVRE.PDF », et le test vérifie
les colonnes **nommément**. Les deux entrent dans la table (`A10-a`, `A10-b`).

**4c — la clause `vu_du_graphe > 0` est TENUE, et non retirée.** Ce qu'elle
garde : un graphe qui porterait **déjà** les identifiants mutés rendrait
`emis_seul == 0`, et la mutation serait « vue » par le seul appariement, sans
qu'aucune confrontation au graphe l'ait confirmée. Le test construit ce monde-là
et exige la raison de la **mutation** ; son retrait la fait disparaître
(mutation `A8`).

**4e — la table versionnée passe de 14 à 27 mutations.** Chaque mutant survivant
de l'audit et chaque porte neuve y entre. Une entrée peut nommer **son** fichier
de test, parce que les gardes d'un script de campagne ne vivent pas dans le
fichier de test du harnais. L'entrée `A4` — la porte neuve déposée dans
`extraction.py` — **disparaît** avec la dérivation qu'elle tenait ; ce qu'elle
mesurait est repris, plus largement, par `A6-a` et `A6-b`, qui rougissent les
**sept** portes neuves d'un coup.

#### 4.39.e → **le prix du rejeu sur la porte**, son SEUL site

`mesuré` le 24 septembre 2026, deux exécutions consécutives chacune, sur le
worktree de la reprise :

| commande | durée |
|---|---|
| `make lint typecheck test format-check` (la porte **sans** le rejeu) | **33,5 s** puis **32,7 s** |
| `make all` (la porte **avec** le rejeu) | **45,9 s** puis **45,9 s** |

Soit **+13,2 s** pour **27** mutations, ou **+40 %**. Le chiffre du §4.38.f
(« 34,2 s », faux — la somme annoncée en faisait 35,4) est remplacé ; le
`Makefile` **cite ce paragraphe** au lieu de répéter le nombre, parce qu'un
nombre à deux sites finit par mentir à l'un des deux.

**Ce que le prix achète, et pourquoi il a triplé** : 13 mutations de plus, et
surtout des mutations dont le test **lance des sous-processus** — `A6-a` et
`A6-b` rejouent chacune les sept portes neuves dans sept processus neufs, soit
2,0 s pièce. C'est le coût d'une preuve à l'exécution ; la mesurer par lecture du
code coûtait moins et ne prouvait pas.

**À la quatrième reprise (§4.40), la table passe de 27 à 35 mutations.** Le
chiffre ci-dessus est donc périmé, et **le remesurer au niveau de `make` n'aurait
rien valu** : l'hôte portait ce jour-là une charge qui faisait varier `make all`
de **68,4 s** à **105,5 s** d'une exécution à la suivante. **La mesure est donc
prise là où elle est isolée** — le rejeu se chronomètre lui-même et imprime sa
durée. `mesuré` le 24 septembre 2026, trois exécutions consécutives de
`make mutations` : **19,3 s**, **17,3 s**, **19,3 s** pour **35** mutations,
toutes rouges. C'est **ce que le rejeu ajoute à la porte**, et c'est le seul
chiffre de ce paragraphe qui se compare d'une reprise à l'autre.


### 4.40 → la QUATRIÈME reprise du lot 11 — trois bloquants fermés, cinq non bloquants traités

Le quatrième audit confirme l'essentiel du §4.39 et nomme **trois** corrections
bloquantes et **cinq** non bloquantes. Toutes sont traitées ci-dessous. Les huit
comptes des stores, l'empreinte de l'instantané et les `mtime` du corpus sont
relevés au §4.39 (début) et ici (fin) : **rien n'a bougé**.

#### 4.40.a → BLOQUANT, TRAITÉ — la sonde des `mtime` surveillait les `.pyc`

Traité, et le détail est écrit au §4.39.c, qui porte la sonde : `rglob("*")` sans
exclusion surveillait **162** fichiers dont **78** `.pyc`, que l'interpréteur
réécrit de lui-même. `mesuré` par l'audit : un `python -c "import
src.index_report"` lancé depuis l'arbre **pendant** `make mutations` faisait
rendre **2** à `make`. `__pycache__` est exclu ; le compte tombe à **84**.

#### 4.40.b → BLOQUANT, TRAITÉ — le garde des SDK passe de l'INTERDICTION à l'AUTORISATION

**Le défaut, et il est de PRIORITÉ D'OPÉRATEURS.**
`importe & set(SDK_DE_STORE) ^ set(SDK_DE_STORE)` vaut `SDK_DE_STORE - importe`,
parce que `&` lie plus fort que `^`. Le garde ne pouvait donc voir qu'un SDK
**disparu**, jamais un SDK **neuf**. La constante de `src/` n'était lue par aucun
site et le test en portait sa propre copie en dur. Deux mutants y survivaient,
`mesurés` par l'audit : **S1**, un `import boto3` ajouté à `storage.py`, et
**S2**, la constante vidée.

**La réparation est la POLARITÉ.** Une liste d'interdictions ne dit rien de ce
qu'elle ne connaît pas — et c'est exactement ce qu'on lui demande de voir.
`src/equivalence_des_identifiants.py` publie désormais **deux classes** :
`SDK_DE_STORE` (couverts par la barrière des constructeurs) et `PAS_UN_STORE`
(**14** dépendances, chacune avec sa raison au site). Le test énumère par l'AST
**tous** les modules tiers de premier niveau importés par `src/` — hors
bibliothèque standard, hors `src` — et exige que chacun soit classé, **dans les
deux sens**. `mesuré` le 24 septembre 2026 : **17** dépendances tierces, 3 + 14.

**`requests` porte la borne de la classe `PAS_UN_STORE`, écrite au site** : un
client HTTP générique **peut** écrire dans un store par son API REST, sans
passer par aucun SDK. Il est classé sur l'usage qu'en fait `src/` aujourd'hui,
pas sur une impossibilité. Ce sont les portes de `src.docling_service` qui le
couvrent, en seconde couche.

**Les trois mutants, rc du processus, `mesuré` le 24 septembre 2026 :**

| mutant | sur `55b7214` | ici |
|---|---|---|
| `S1` — `import boto3` ajouté à `storage.py` | **SURVIT** (`1 passed`) | **ROUGE** |
| `S2` — la classification vidée | **SURVIT** (`1 passed`) | **ROUGE** |
| `S3` — un SDK **déclaré** que `src/` n'importe pas | (le cas n'existait pas) | **ROUGE** |

#### 4.40.c → BLOQUANT, TRAITÉ — la session de lecture laissait passer les écritures composées

**Le défaut.** `SessionEnLecture.execute` ne découpait la requête que sur `;`.
nGQL compose aussi par le **tube** `|`, qui passe le résultat d'une lecture à une
**écriture**, et par le simple **saut de ligne**. `mesuré` sur une session
factice, 24 septembre 2026 : **12 formes** passaient, dont
`GO … | DELETE VERTEX $-.d`, `SHOW SPACES | DROP SPACE $-.Name` et
`YIELD "x" AS d | DELETE VERTEX $-.d`. L'audit en avait nommé 8 ; les deux formes
par **saut de ligne** ont été mesurées ici, et ce sont elles qui mettent le saut
de ligne parmi les séparateurs. **Le commentaire du site affirmait que le garde
« refuserait plus, JAMAIS moins » : il refusait moins.**

**La réparation.** Les trois séparateurs sont une constante, `SEPARATEURS`, et le
test paramétré reçoit les **12** formes. **Jamais aucune n'a été envoyée à un
vrai Nebula** : elles tournent toutes contre une session factice.

**La borne est désormais MESURÉE, et non affirmée** : un séparateur à l'intérieur
d'une chaîne citée compte pour un séparateur, donc
`MATCH (d:Document) WHERE d.Document.source_path == "a|b" RETURN d;` — qui ne
fait que **lire** — est refusée. C'est le sens acceptable. L'autre sens tient par
un argument, écrit au site : découper ne fait qu'**ajouter** des fragments, donc
des exigences, et le premier fragment commence toujours à la position 0.

**Les requêtes réelles du harnais passent toujours**, et le test ne les recopie
plus à la main : il les **forme** avec les mêmes constantes et les mêmes
f-strings que `Graphe.__init__`, `Graphe.documents` et `Graphe.ids`, sur les
**23** `element_id` de l'instantané versionné. `mesuré` le 24 septembre 2026 :
aucun des 23 identifiants ne porte de séparateur.

#### 4.40.d → NON BLOQUANT, TRAITÉ — `format` et `format-check` voient `scripts/`

**C'est le défaut D7, une troisième fois.** `lint` et `typecheck` avaient pris
`scripts/` au point 4a ; ces deux cibles étaient restées à `src/ tests/`.
`mesuré` le 24 septembre 2026, **rc du processus** et non derrière un tube, sur
un `scripts/` portant un fichier mal formé : `ruff format --check src/ tests/`
rend **0**, la même commande avec `scripts/` rend **1**, et `make format-check`
rend **2** là où il rendait **0**. Sur l'arbre propre : **84** fichiers déjà
formatés, rc=0.

#### 4.40.e → NON BLOQUANT, TRAITÉ — `LectureSeule` écrit dans le journal que quelqu'un lit

`LectureSeule` tenait son **propre** `self._journal`, que personne ne lisait,
quand `SessionEnLecture` écrivait déjà dans le journal **partagé**. Une écriture
MinIO refusée par l'enveloppe, puis **avalée** par la production, ne devenait
donc aucun rouge — alors que `figer` et `comparer` rougissent sur le journal
d'armement. L'enveloppe le reçoit à la construction. Le mutant `N1` de l'audit —
le retrait de l'`append` — rougit désormais son test (entrée `N2` de la table).

#### 4.40.f → NON BLOQUANT, TRAITÉ — la barrière descend à la CLASSE

**Ce que le rebondage des NOMS laissait passer.** `mesuré` le 24 septembre 2026
sur `minio`, hors conteneur, **10 chemins de construction** :

| # | chemin | sur `55b7214` | ici |
|---|---|---|---|
| 1 | nom direct `Minio(…)` | LÈVE | **LÈVE** |
| 2 | sous-classe de `Minio` | **ÉCHAPPE** | **LÈVE** |
| 3 | dictionnaire rempli avant l'armement | **ÉCHAPPE** | **LÈVE** |
| 4 | attribut de classe | **ÉCHAPPE** | **LÈVE** |
| 5 | argument par défaut | **ÉCHAPPE** | **LÈVE** |
| 6 | fermeture capturée avant l'armement | **ÉCHAPPE** | **LÈVE** |
| 7 | `partial` capturé avant l'armement | **ÉCHAPPE** | **LÈVE** |
| 8 | `type(client)(…)` | **ÉCHAPPE** | **LÈVE** |
| 9 | `client.__class__(…)` | **ÉCHAPPE** | **LÈVE** |
| 10 | import à neuf après l'armement | LÈVE | **LÈVE** |

**8 sur 10 échappaient** — l'audit en nommait 7, en comptant la fermeture et le
`partial` ensemble. **Tous les huit passent par la CLASSE, aucun par le nom** :
c'est pourquoi la barrière y descend, en posant la levée sur son `__init__`.
Le rebondage des noms **reste**, en seconde couche.

**Les clients de LECTURE survivent, et c'est le contrôle négatif** : ils sont
construits **avant** l'armement, donc leur `__init__` a déjà tourné ; une levée
posée sur `__init__` n'empêche que les constructions **à venir**.

**`mesuré` DANS L'IMAGE**, 24 septembre 2026, les trois SDK ensemble :

- **15** constructeurs barrés (12 avant), dont **8 classes** dont l'`__init__`
  lève : `minio` 2, `nebula3` 3, `chromadb.api.client` 3 ;
- les **10** chemins lèvent, et `chromadb.HttpClient` comme
  `chromadb.api.client.Client` lèvent tous deux ;
- les clients de lecture **lisent encore** : **212** objets MinIO listés et
  **23** `Document` lus, après l'armement ;
- **aucun pool `nebula3` n'a eu à reconstruire de connexion** en cours de route,
  ni pendant cette mesure ni pendant la comparaison complète.

**`chromadb` a demandé un choix, et il est mesuré.** Ses noms publics sont des
**fabriques** — des fonctions, sans `__init__` à barrer. Les classes concrètes
qu'elles construisent vivent dans `chromadb.api.client`, et la barrière y
descend par une règle **étroite** : le suffixe `Client`, soit **3 classes sur 20
noms publics** (chromadb 0.6.3). `_classes_hors_exception` y prendrait
`Collection`, `Settings` et `System` — ce dont la **lecture** a besoin — et
casserait le harnais au lieu de le garder. **La borne s'écrit ici** : les **7**
fabriques de `chromadb` restent tenues par le seul rebondage des noms, et la
raison est **RENDUE** dans `ArmementDesSdk.sans_classe`, imprimée par le script,
plutôt que tue.

#### 4.40.g → NON BLOQUANT, TRAITÉ — un instantané non inscrit est refusé AVANT la connexion

`EmpreinteInattendueError` se levait **après** la connexion au graphe et
**après** l'armement des barrières, et remontait en **trace d'appel**. Elle
rejoint le garde du répertoire de campagne, en tête de `main()`, comme
`FileExistsError` rend déjà un verdict propre à `figer`. `figer` n'y est pas
soumis : son instantané n'existe pas encore, donc son empreinte ne peut pas être
attendue.

`mesuré` le 24 septembre 2026 sur l'hôte, `comparer` d'un dossier non inscrit :
avant, **rc=1** sur un `ModuleNotFoundError: No module named 'nebula3'` levé par
`Graphe` — **le rc ne distinguait pas le refus du harnais d'un plantage à la
connexion** ; après, **rc=1**, le message du refus, aucune trace, et ni la
connexion ni l'armement n'ont eu lieu.

#### 4.40.h → NON BLOQUANT, TRAITÉ — les quatre bornes que le registre devait écrire

**1. Les deux enveloppes protègent de l'accident, pas de l'intention.**
`LectureSeule` laisse `._client` atteignable et `SessionEnLecture` laisse
`._session` atteignable ; l'un et l'autre rendent l'objet **nu**, sur lequel
toute méthode et toute requête passent. Un nom préfixé d'un souligné est une
**convention, pas une serrure**. C'est acceptable contre une écriture
**accidentelle**, et ça ne vaut rien contre une écriture **délibérée** : ce sont
la barrière des constructeurs et celle des portes qui tiennent devant un
appelant décidé. **La borne est écrite aux deux docstrings**, et ici.

**2. La liste des bornes, après le §4.40.f.** Ce qui reste hors de portée de la
barrière : un client construit dans un **sous-processus** ; une bibliothèque
tierce qui parle à un store **hors des trois SDK** (un `boto3`, un driver HTTP
écrit à la main — et c'est la raison pour laquelle `requests` est classé au
§4.40.b avec sa borne) ; et les **7 fabriques `chromadb`**, tenues par le seul
rebondage des noms. **Ce qui n'en est plus une** : les huit chemins de
construction qui ne passent par aucun nom.

**3. `figer` écrit sous n'importe quel nom à l'intérieur du répertoire de
campagne.** `dossier_de_campagne` ne contrôle qu'une chose : que le dossier soit
un **enfant direct** de `documentation/campagnes`. Le **nom** est libre, et
`figer` y écrira. Ce n'est **pas** `figer` qui rattrape, c'est `comparer` : il
exige que le nom figure dans `EMPREINTES_ATTENDUES`, une **constante de `src/`**,
donc un **commit revu comme du code**. Un instantané frauduleusement figé sous un
nom neuf n'est comparable par personne — `mesuré` au §4.40.g, rc=1. La borne
utile s'écrit donc ainsi : **le répertoire de campagne n'est pas en écriture
seule ; c'est la constante qui authentifie, pas l'emplacement.**

**4. Une copie jetable abandonnée par un `SIGKILL` reste dans `/tmp`.** Le rejeu
des mutations travaille sur une copie jetable dans le répertoire temporaire du
système, retirée à la sortie normale. Après un `SIGKILL`, **elle survit** — et
elle porte alors une **source mutée**, celle de la mutation en cours. Elle est
**hors de tout montage** : aucun conteneur ne la voit, et elle ne partage aucun
fichier avec l'arbre de travail, donc elle ne peut ni être ingérée ni être prise
pour l'origine au lancement suivant — c'était le défaut de la version d'avant le
§4.39.c, qui mutait en place. **Ce qu'elle coûte** : de l'espace disque jusqu'au
prochain nettoyage de `/tmp`, et un fichier de code muté lisible par qui lit
`/tmp`. Ce n'est pas rattrapé, et c'est **accepté** ici plutôt que tu.


### 4.41 → OUVERT APRÈS FUSION — les cinq points non bloquants que la vérification finale a laissés

**Le lot 11 est fusionné dans `main` le 25 septembre 2026** (`--no-ff`,
`2918ccc`, 20 commits, arbre `1ff7d1e`). La vérification finale qui l'a déclaré
fusionnable n'a rien trouvé de bloquant, mais elle a laissé **cinq** constats.
Ils sont inscrits ici parce qu'ils survivent à la fusion : aucun n'est traité.

**a — 25 septembre 2026 — la borne ChromaDB du §4.40.f et du §4.40.h.2 est
écrite FAUSSE, dans le sens prudent.** Les deux paragraphes annoncent les
**7 fabriques `chromadb`** comme « tenues par le seul rebondage des noms ». La
mesure dit l'inverse : les 7 fabriques **capturées avant l'armement** lèvent,
**9 essais sur 9**, et elles sont tenues par **chacune des deux couches prise
séparément**. La borne écrite est donc plus pessimiste que la barrière réelle.
Un registre qui sous-promet reste un registre qui se trompe : à corriger aux
deux sites.

**b — 25 septembre 2026 — deux gardes n'ont pas d'entrée dans la table des
mutations.** `B1` (l'exclusion de `__pycache__`, §4.40.a) et `N1` (la portée de
`format-check`, §4.40.d) sont des comportements livrés et testés, mais
`tests/mutations/table-des-mutations.json` ne porte **aucune mutation** qui les
exerce. Les 35 mutations rouges de la porte ne disent donc rien de ces deux
lignes-là.

**c — 25 septembre 2026 — `A6-b` n'exerce aucune référence capturée avant
l'armement.** La mutation porte son nom d'un cas — la référence prise **avant**
que la barrière ne soit armée — qu'elle ne construit pas. Elle est rouge, et
elle est rouge pour une autre raison que celle que son intitulé annonce.

**d — 25 septembre 2026 — la couverture de `chromadb.api.async_client` est
FORTUITE.** `AsyncClient` n'est atteint que par **héritage de
`SharedSystemClient`**, qui est le nom réellement rebondi. Aucun test ne tient
cette couverture : elle tombe le jour où `chromadb` change sa hiérarchie, et
rien ne rougira.

**e — 25 septembre 2026 — « 3 classes sur 20 noms publics » doit se lire « 3 sur
20 CLASSES publiques ».** Le module en expose **39 noms publics** mesurés, dont
20 classes. La phrase est écrite à **deux sites**, et elle compare un numérateur
de classes à un dénominateur de noms.

**Et la commande de comptage du corpus, corrigée ici même.** Le §4.40 la citait
sans exclusion : `find Datas \( -name '*.pdf' -o -name '*.html' \)` rend **47**,
parce que `Datas/.cleaned/` porte **22 copies produites** par l'étape de
nettoyage. Le corpus en compte **25**. La commande juste écarte `.cleaned` —
`find Datas -path 'Datas/.cleaned' -prune -o \( -name '*.pdf' -o -name '*.html'
\) -print` —, et c'est elle qui est désormais au §4.40. `mesuré` le 25 septembre
2026 : 47 sans l'exclusion, 25 avec, 22 dans `.cleaned`, et **0** fichier du
corpus portant un `mtime` postérieur au 24 septembre 2026.


### 4.42 → CONSIGNÉ par la DEUXIÈME campagne de référence — deux constats, et deux constats d'AVANT qui se ferment

La campagne du 25 septembre 2026 — purge des trois stores et du HTML nettoyé,
réingestion complète par le code de `main` sans aucun changement du code
d'extraction — est au site canonique
[`documentation/campagnes/2026-09-25-deuxieme-campagne-de-reference.md`](campagnes/2026-09-25-deuxieme-campagne-de-reference.md).

**Son résultat tient en une ligne, et il est celui qu'on attendait :
`DEPLACES 0`.** `comparer` contre l'instantané versionné rend
`DOCUMENTS COMPARES 23 / 23`, `rc=0`, aucun déplacement déclaré ni constaté. Les
huit comptes, l'empreinte des 212 clés d'objet MinIO, les sorties de
`verify_contract` et d'`index_report` **ligne pour ligne**, le texte des 44
ancrages et les quatre valeurs de rappel sont **identiques** avant et après. La
décision (a) du 24 septembre — on ne touche pas aux puces vides — laissait
l'extraction en l'état ; la réingestion le confirme par la mesure.

**DEUX constats de ce registre se ferment par cette campagne, et c'est un geste
de pilote, pas de branche.**

- **§4.32.a.** Le lot 8 écrivait : « Ce qui n'est pas prouvé, et qui ne pouvait
  pas l'être : qu'un run réellement créé par ce chemin aille au bout. Le premier
  geste de réingestion reste donc à faire sous les yeux de quelqu'un. » **Il est
  fait.** `mesuré` le 25 septembre 2026 : marqueur `reingerer:2026-09-25-campagne-2`
  posé sur les curseurs de `livres_html_sensor` et `pdfs_sensor`, tick à 03:43:43
  et 03:44:10, **22 + 1 = 23 runs CRÉÉS** — et le compte de runs le confirme par
  un second chemin, **958 → 981**, soit exactement +23. Les 23 sont allés au
  bout : **23 `SUCCESS`, 0 échec, 0 reprise**. Les clés de run portent
  l'étiquette et non le `mtime`
  (`livres_html_<partition>_reingestion_2026-09-25-campagne-2`, `mesuré` sur le
  tag `dagster/run_key`), ce qui est exactement ce que le lot 8 a livré. **Le
  silence ne s'est pas produit.**
- **§4.28.c, et le §7 de la première campagne** — « l'exigence 5 du contrat n'est
  PAS ÉPROUVÉE ». **Elle l'est.** Le service de l'agent tourne sur ce poste
  (`rag-agent-api`, `healthy`, `AGENT_SERVICE_URL=http://agent-api:8000` rend
  **200** sur `/health`, `mesuré` le 25 septembre 2026), `agent_reindex_sensor`
  est parti **seul** à 03:50:41 — 24 s après la fin du dernier run d'ingestion —
  et son run rend `ok — 4367 chunks indexes`. Le garde du §4.15 a tenu
  **13 ticks `SKIPPED` consécutifs**, chacun nommant le run qui bloque. **Réserve
  qui reste** : ce qui est éprouvé est que l'appel part, aboutit et réussit en fin
  d'ingestion. Que l'index BM25 d'en face serve effectivement ces 4 367 chunks est
  une propriété de l'AUTRE dépôt, et aucune requête n'a été posée à l'agent.

#### 4.42.a La CLI Dagster POSE un curseur et ne sait pas le LIRE

`dagster sensor cursor <NOM>` n'offre que `--set` et `--delete` (`mesuré` le
25 septembre 2026, `dagster sensor cursor --help`). **Il n'existe aucun mode
lecture**, et la sous-commande sans option ne rend pas la valeur.

**Pourquoi ce n'est pas qu'une gêne d'ergonomie.** Le geste de réingestion du
lot 8 *est* une écriture de curseur, et c'est le seul déclencheur de la
réingestion. Un opérateur peut donc le **poser** par une commande officielle,
mais il ne peut ni **vérifier ce qu'il y a avant de l'écraser**, ni **constater
que le marqueur a été consommé**, sans sortir de la CLI :

```python
from dagster import DagsterInstance
for s in DagsterInstance.get().all_instigator_state():
    print(s.instigator_name, s.status.value, s.instigator_data.cursor)
```

C'est la voie qu'emploie déjà le §3.1 de la première campagne, et celle que la
deuxième a dû employer quatre fois. **Elle n'est écrite nulle part dans le
dépôt** : ni dans le `README`, ni au-dessus de `PREFIXE_REINGESTION`, qui décrit
pourtant le geste en soixante lignes et ne dit jamais comment relire ce qu'on
vient d'écrire.

**La forme du remède, si le pilote veut le fermer** : une ligne de plus dans le
bloc au-dessus de `PREFIXE_REINGESTION` et dans la section « Ré-ingérer
proprement » du `README`, donnant le geste de lecture à côté du geste
d'écriture. Ce n'est pas du code : c'est la moitié manquante d'une procédure
documentée. *(Le §4.33.d note déjà que les trois copies de la prose du geste de
réingestion ne sont tenues par rien — un quatrième site ne s'ajoute pas sans y
penser.)*

#### 4.42.b L'empreinte des clés d'objet MinIO circule SANS SA RECETTE

Le témoin `c91f5be6e24fbcba5f4a744119bf8da65fed44b7ecac79cce0ae1b027ed0b994`
authentifie l'état du bucket : non pas le *nombre* d'objets, mais **l'ensemble
des 212 clés**, à la clé près. C'est un bon témoin — chaque clé de crop porte un
`element_id` dans son nom, donc l'égalité de l'empreinte est une preuve de
non-déplacement **indépendante de `comparer`**.

**Mais aucun site du dépôt ne disait comment il se calcule.** `mesuré` le
25 septembre 2026, **avant** que la campagne n'écrive quoi que ce soit :
`grep -rn 'c91f5be6'` sur `d22a153` rendait le **vide** — ni dans `src/`, ni
dans `scripts/`, ni dans `documentation/`, ni dans l'instantané.

*(La mesure se rejoue sur le COMMIT et non sur l'arbre, parce que **ce constat
l'a lui-même périmée** : la campagne écrit désormais l'empreinte dans **deux**
fichiers, et un `grep` lancé sur l'arbre les trouve. C'est le §4.31.B1 — « cinq
renvois `mesuré` que le lot a rendus faux LUI-MÊME » — et il se ferme en datant
la mesure de son commit : `git grep 'c91f5be6' d22a153` rend **le vide, rc=1**,
tandis que `grep -rc` sur l'arbre rend **4 lignes ici et 6 au compte rendu**.)*

La deuxième campagne a donc dû **identifier la recette par mesure**, en
calculant quatre variantes plausibles sur la même liste triée :

| Variante | Empreinte |
|---|---|
| lignes jointes par `\n`, **avec `\n` final** | **`c91f5be6…0994`** — c'est celle-ci |
| lignes jointes par `\n`, sans `\n` final | `d1e98913…` |
| concaténation nue | `56b2cf3c…` |
| séparateur `\0` | `e2fb462f…` |

**Une empreinte sans sa recette n'est pas un témoin, c'est un chiffre.** Le
suivant qui la remesurera a une chance sur quatre de la reproduire du premier
coup, et trois chances sur quatre de conclure à une dérive qui n'existe pas.
C'est le mode de panne exact que ce chantier traque : un rouge fabriqué par
l'instrument, sur un système sain.

**Ce que ce constat n'est pas.** Ce n'est pas un reproche à l'instantané, qui
porte bien, lui, sa propre empreinte et sa propre recette — `cles-d-objet.tsv`
et son `sha256` dans le manifeste, tous deux produits et relus par
`src/equivalence_des_identifiants.py`. Les **13** clés qu'il porte sont les
crops du PDF, pas les **212** objets du bucket : les deux témoins ne comptent pas
la même chose, et c'est précisément pourquoi le second a besoin de sa recette
écrite quelque part.

**La forme du remède** : la recette à côté de l'empreinte, partout où l'empreinte
apparaît — et, mieux, un geste versionné qui la rende, sur le modèle des scripts
de `scripts/campagne/`. La deuxième campagne l'a écrite à son §1.2 ; elle n'y est
pas *gardée*.


### 4.43 → CONSIGNÉ par la BASCULE vers SeaweedFS — la décision du propriétaire, exécutée et mesurée

**SeaweedFS remplace MinIO.** La solution a été **retenue par le propriétaire du
chantier en début de semaine du 21 septembre 2026** ; elle est **en service
depuis le 25 septembre 2026**. Ce registre ne rouvre pas le choix : il consigne
ce qui a été mesuré en l'exécutant.

Les deux sites canoniques sont
[`documentation/campagnes/2026-09-25-bascule-seaweedfs.md`](campagnes/2026-09-25-bascule-seaweedfs.md)
— les huit critères d'essai, la procédure de bascule et le retour arrière — et
[`documentation/campagnes/2026-09-25-deuxieme-campagne-de-reference.md`](campagnes/2026-09-25-deuxieme-campagne-de-reference.md),
dont les huit comptes servent d'attendus.

**Ce qui a été mesuré le 25 septembre 2026, après la bascule réelle :**

| Témoin | Avant, sur MinIO | Après, sur SeaweedFS |
|---|---|---|
| sommets, `Document` compris | 15 196 | **15 196** |
| sommets `Document` / `Paragraph` / `ListItem` / `Code` | 23 / 7 251 / 1 748 / 4 963 | **identiques** |
| arêtes `PARENT_OF` | 15 173 | **15 173** |
| chunks ChromaDB | 4 367 | **4 367** |
| objets dans le bucket `documents` | 212 | **212** |
| **empreinte des 212 clés** | `c91f5be6…0994` | **`c91f5be6…0994`** |
| `comparer` contre l'instantané | 23 / 23, `DEPLACES 0`, `rc=0` | **23 / 23, `DEPLACES 0`, `rc=0`** |

Et le témoin propre à la bascule : les **212** sommets porteurs d'une
`minio_url` la portent **tous** sous `http://seaweedfs:8333/documents/`,
**zéro** occurrence de `minio:9000` dans le graphe comme dans les 22 copies
nettoyées de `Datas/.cleaned/`.

**La réingestion a été faite par le capteur, jamais à la main** : marqueur
`reingerer:2026-09-25-bascule-seaweedfs` posé sur `livres_html_sensor` et
`pdfs_sensor`, **22 + 1 = 23 runs créés**, tous `SUCCESS`, puis le run
`agent_reindex_job` parti seul et rendant `ok — 4367 chunks indexes`. Le compte
de runs le confirme par un second chemin : **982 → 1 005**, soit exactement
+23, puis 1 006 avec la réindexation.

**MinIO n'a été ni arrêté, ni recréé, ni purgé, et rien n'y a été écrit.** Il
est **conservé, debout, avec ses 212 objets** : c'est le retour arrière, et il
le restera tant que le pilote ne dira pas de le retirer. `mesuré` après la
bascule : mêmes 212 objets, même empreinte, `StartedAt` et `RestartCount`
inchangés, et **aucun objet modifié après 03:50:00 UTC** — l'empreinte des 212
couples `(date de modification, clé)` vaut `8a73f1a6…e771` avant comme après.
La purge a d'ailleurs annoncé **0 objet supprimé**, ce qui est le signal que
c'est bien SeaweedFS qu'elle visait ; un 212 aurait voulu dire qu'elle venait de
purger MinIO.

#### 4.43.a Les 886 `FAILURE` de l'historique : un seul job, une seule cause, cinq fenêtres closes

L'historique Dagster porte **886 runs `FAILURE`**, et ils faisaient peur sans
rien dire. Ils sont caractérisés, `mesuré` le 25 septembre 2026 sur les
`run_records` et les événements `STEP_FAILURE` de l'instance :

- **tous les 886 sont des `agent_reindex_job`** — aucun run d'ingestion n'a
  jamais échoué sur ce poste ;
- **une seule cause, 886 fois sur 886** : `DagsterExecutionStepExecutionError`
  dont la cause est une **`ReindexError`** sur le `POST /reindex`, c'est-à-dire
  une `ConnectionError` vers un service d'agent **absent** du poste ;
- **cinq fenêtres**, et rien en dehors :

| Fenêtre | Échecs | De | À |
|---|---|---|---|
| 1 | **68** | 31 août 16:06 | 31 août 16:39 |
| 2 | **498** | 2 septembre 05:33 | 2 septembre 09:43 |
| 3 | **9** | 2 septembre 12:52 | 2 septembre 12:56 |
| 4 | **59** | 2 septembre 13:03 | 2 septembre 13:32 |
| 5 | **252** | 3 septembre 06:31 | 3 septembre 08:37 |

68 + 498 + 9 + 59 + 252 = **886**, et la somme se ferme. **Aucun échec depuis le
3 septembre 2026 08:37 UTC.**

**La découpe en fenêtres porte son seuil, sans quoi elle ne se rejoue pas** : la
coupure est un **écart de plus de 300 s** entre deux créations consécutives. À
600 s ou 900 s, les fenêtres 3 et 4 fusionnent et l'on n'en compte plus que
quatre — 68 / 498 / 68 / 252. Le seuil n'est pas neutre, et l'écrire est la
moitié du chiffre.

**Les fenêtres 1 et 5 ne sont documentées nulle part ailleurs**, et c'est le
sens de ce constat. Le §4.28.c parle de **67 `ReindexError`** relevés le 2
septembre — c'est un instantané pris au milieu de la fenêtre 2, pas son total.
Les 68 échecs du 31 août et les 252 du 3 septembre n'ont **aucun site** : ce
paragraphe est le premier.

**Ce que cela ferme, et ce que cela ne ferme pas.** Cela ferme la crainte d'un
défaut d'ingestion latent : il n'y en a pas, l'ingestion n'a jamais échoué. Cela
ne ferme pas le **§4.15** — un service d'agent absent fait échouer la
réindexation run après run, toutes les 30 s, sans délai de garde ni alerte, et
c'est exactement ce que ces cinq fenêtres racontent.

#### 4.43.b La recette de l'empreinte des clés, **des deux côtés** — et la clause qui n'est pas éprouvée

Le §4.42.b demandait que l'empreinte circule avec sa recette. La voici, et elle
se lit **des deux côtés** :

> Les clés d'objet **distinctes** (`set`), triées par `sorted()` de Python,
> jointes par `"\n"`, **avec un `"\n"` final**, encodées en **UTF-8**,
> condensées en **SHA-256**, rendues en hexadécimal minuscule.

```python
cles = sorted({o.object_name for o in client.list_objects(bucket, recursive=True)})
empreinte = hashlib.sha256(("\n".join(cles) + "\n").encode("utf-8")).hexdigest()
```

**Mais les deux côtés ne partent pas de la même liste, et c'est le point.**

| Qui | D'où viennent les clés |
|---|---|
| `rag-agent-chat` | des **`minio_url` du GRAPHE**, dont il retire le préfixe |
| ce dépôt (campagnes, sondes) | du **BUCKET**, par `list_objects` |

**Elles s'accordent parce que les deux ensembles sont égaux** — 212 clés de part
et d'autre, et la bascule vient de le remesurer — **et non parce que la recette
serait la même par construction**. Si un objet existait dans le bucket sans
sommet correspondant, ou l'inverse, les deux empreintes divergeraient et aucune
des deux ne serait fausse. **L'égalité est un fait mesuré, pas une propriété.**

**Et la clause « triée » n'est pas éprouvée.** `list_objects` rend déjà ses clés
en ordre lexicographique — c'est le comportement de l'API S3, et MinIO comme
SeaweedFS s'y tiennent. Le `sorted()` de la recette ne change donc rien sur ce
corpus, et **aucune mesure ne distingue « trié » de « dans l'ordre rendu »**.
Elle tient du côté du graphe, où l'ordre n'a aucune raison d'être celui-là ;
côté bucket, elle est **inerte, et donc non éprouvée**. Un jour où une
passerelle rendrait ses clés dans un autre ordre, c'est cette clause qui
sauverait le témoin — et personne n'aurait de mesure pour dire qu'elle marche.

#### 4.43.c Le défaut à fermer : `MINIO_*` configure le serveur MinIO **et** authentifie auprès de SeaweedFS

**C'est le défaut réel que la bascule met en lumière, et il reste ouvert.**
`MINIO_ROOT_USER` et `MINIO_ROOT_PASSWORD` sont lues par **deux** consommateurs
qui n'ont rien à voir :

- le service `minio` de `docker-compose.yml`, qui s'en **configure lui-même** ;
- `DoclingSettings`, qui s'en **authentifie** auprès de ce que `MINIO_ENDPOINT`
  désigne — aujourd'hui `seaweedfs:8333`.

**Conséquence immédiate, et elle a dicté toute la procédure de bascule** : le
`.env` porte désormais le jeu SeaweedFS sous ces deux noms, si bien que
**recréer le conteneur `minio` changerait ses identifiants** et rendrait le
retour arrière impossible. `minio` n'a donc **jamais** été recréé, et un
`docker compose up -d` **nu** — sans nom de service — le recréerait, puisqu'il
recrée tout ce dont la configuration a changé. La règle « on nomme les
services » n'est pas une précaution de style ici : c'est ce qui sépare une
bascule d'une perte du retour arrière.

**La forme du remède** : un nom neutre — `OBJECT_STORE_ENDPOINT`,
`OBJECT_STORE_ACCESS_KEY`, `OBJECT_STORE_SECRET_KEY`, `OBJECT_STORE_BUCKET` —
pour l'**accès client**, et des variables distinctes pour la **configuration du
serveur** MinIO tant qu'il est conservé. Ce n'est pas un renommage cosmétique :
c'est la séparation de deux rôles qu'une seule variable tient aujourd'hui. Le
lot est à part parce que `MINIO_ENDPOINT`, `MINIO_ROOT_USER`,
`MINIO_ROOT_PASSWORD` et `MINIO_BUCKET` sont le **contrat avec
`rag-agent-chat`**, qui vit dans un autre dépôt : le renommage se coordonne avec
son pilote, il ne se décrète pas ici.

*(Deux effets cosmétiques du même défaut, à emporter dans ce lot : la ligne de
journal `Bucket MinIO 'documents' pret.` parle désormais de SeaweedFS, et la
sortie de `wipe_stores` titre encore `--- MinIO ---`. Le message porte le nom de
la bibliothèque `minio-py`, pas celui du serveur.)*

## 5. Ouvert — le code mort, et la doctrine qu'il fait mentir

### 5.1 → traité par le lot 5 — cinq symboles morts retirés, et le sixième était CONTOURNÉ

**Le constat, tel qu'il était ouvert.** `settings.chunk_size` (450) et
`settings.chunk_overlap` (75), `chunk_text` et `DEFAULT_CHUNK_SIZE` /
`DEFAULT_CHUNK_OVERLAP`, `chunk_ids` : **aucun appelant en production**. Seuls
les tests les exerçaient. Le découpage réel est
`HybridChunker(tokenizer=..., max_tokens=modele.max_seq_length)`, construit par
`vectors.get_chunker`. Le débat « 900 contre 450 » était donc vide — **les deux
étaient faux** — et `services/docling.md` présentait `CHUNK_SIZE=900` /
`CHUNK_OVERLAP=150` comme des variables d'environnement effectives, alors
qu'elles ne faisaient rien. Le commentaire de `settings.py` justifiait 450 par
une mesure qui documentait une constante morte.

**Ce que le lot 5 a fait, et ce paragraphe décrivait encore l'état d'AVANT.**
Cinq symboles sont retirés — `chunk_size`, `chunk_overlap`, `chunk_text`,
`DEFAULT_CHUNK_SIZE`, `DEFAULT_CHUNK_OVERLAP` — et le motif est écrit à leur
place, dans `settings.py`, pour que le débat ne se rouvre pas. `services/docling.md`
ne les annonce plus. `mesuré` le 2 septembre 2026,
`grep -rni 'chunk_size\|chunk_overlap\|chunk_text\|DEFAULT_CHUNK' src/ tests/`
rend **quatre lignes, toutes des commentaires** qui disent pourquoi ces symboles
sont partis — `settings.py`, `vectors.py`, `chunking.py` et
`tests/unit/test_dagster_yaml.py`. Aucune n'est du code. *(Le `-i` n'est pas un
détail : sans lui, le commentaire de `settings.py`, qui écrit `CHUNK_SIZE` en
capitales, ne sort pas — et ce paragraphe l'avait d'abord compté à un site au
lieu de quatre.)*

**Le sixième n'était pas mort, il était CONTOURNÉ.** `chunk_ids` n'avait aucun
appelant, mais `vectors.build_chunks` reconstruisait la **même** forme par une
expression en ligne — le seul site que la production exécute, et **le seul que
rien ne gardait**. La fonction devient `chunk_id`, unitaire, et l'appelant la
traverse. Voir §4.30.b pour la leçon, et **§4.31.B3 pour la conséquence, que ce
registre avait d'abord écrite fausse**.

### 5.2 → traité par le lot 5 — le module part en entier, son nom mentait aussi

Seul `has_content` est importé (`vectors.py:28`, `index_report.py:21`).
`build_blocks`, `Block`, `_family`, `PROSE_LABELS`, `CODE_LABELS` n'ont aucun
appelant. Le docstring du module (l.9-13) énonce « **fusionner plutôt que
jeter** » avec deux garde-fous de section — or la production **jette** :
`vectors.py:138` écarte tout chunk plus court que `min_chunk_chars`.

Le même docstring affirme que `HybridChunker` « n'a pas de `min_tokens` : les
fragments isolés y survivent » — et c'est précisément `HybridChunker` qui a
remplacé `build_blocks`. `documentation/base_vectorielle.md:20` affirme quant à
lui que les fragments isolés « sont absorbés dans leur paragraphe d'origine ».
Les deux ne peuvent pas être vrais.

### 5.3 → traité par le lot 3, et c'était devenu une condition, pas un choix

`VERTEX_PROPERTIES` et `DOCUMENT_PROPERTIES` étaient déclarés dans `ngql.py`
sans jamais être importés, et `DOCUMENT_PROPERTIES` y comptait **3** champs
contre **7** dans `nebula.py`. Un lecteur qui ouvrait `ngql.py` lisait un schéma
périmé.

**Ce constat était rangé au lot 5, et le lot 3 l'a pris — voici l'argument.**
Ajouter `depth` au schéma (§4.11) sans toucher au doublon aurait porté à **deux**
le nombre de définitions fausses dans le fichier même où l'on vient de changer
le schéma. Une constante morte qui décrit faussement ce qu'on vient de modifier
n'est pas du code mort : c'est un piège, et c'est exactement la famille de
défaut que le lot 3 existe pour fermer.

Le sens de la déduplication est **l'inverse** de celui qu'on attendrait : c'est
la définition de `nebula.py` qui disparaît, et celle de `ngql.py` qui devient
canonique. `ngql.py` est le seul des deux modules « sans dépendance externe »,
donc le seul testable sans graphd — et c'est ce qui permet aux gardes de §4.11
d'exister comme tests unitaires plutôt que comme intentions.

### 5.4 → FERMÉ par la réparation du lot 3 — les quatre fichiers sont format-propres, et `make all` rend 0

**Et le commit qui l'a fermé a créé deux affirmations fausses dans le même geste.**
`mesuré` par le pilote le 1er septembre 2026, après fusion : `9d2e341` a étendu
`format` et `format-check` à `src/ tests/` — le bon geste, celui qui ferme l'angle
mort D7 — mais le `README.md` a gardé une table décrivant `ruff format src/`, et un
« 66 files already formatted » là où la mesure rend **67**. Corrigé sur `main` par
le pilote, sans troisième tour de réparation : la porte était verte et le juge
passé.

**Ce que ça dit du lot 5**, qui s'appelle « la documentation contre le code » : son
gibier naît dans les commits qui font **bien** leur travail. C'est là que personne
ne relit la phrase qui décrivait l'état d'avant. Ni le lot ni son audit ne l'ont
vu, et le diff faisait 25 lignes de `README.md`.

**Le constat, tel qu'il était ouvert.** `ruff format --check src/` signalait
**3 fichiers** sur `main` — `extraction.py:412`, `:442`, `:479` ;
`language.py:136-140` ; `matter.py:134-137` — plus un **quatrième dans un angle
mort**, `tests/unit/test_wipe_stores.py`, préexistant sur `main` : `make
format-check` était **borné à `src/`** et ne le signalait jamais, `make format`
ne le réparait pas, mais le hook `ruff-format --check` **bloquait** tout commit
qui le touchait, sans issue automatique. Ce sont des lignes tenant dans les 100
colonnes mais pliées à la main.

**Ce qui a fermé le constat, et en trois temps.** Le report était rangé au lot 2,
puis au lot 5 quand le lot 2 a disparu, au motif que reformater `extraction.py`
noierait le diff du lot qui le réécrit. Deux arguments ont eu raison de ce motif :

1. **le lot 3 a reformaté `extraction.py` et `matter.py`**, en écarts déclarés,
   parce que le hook refuse tout commit qui les touche et que les gardes de §4.21
   et §4.14 y vivent. Coût `mesuré` : **9** et **4** lignes
   (`git show --numstat --format= 23055cb 27c3c22`) ;
2. **le report des deux derniers supposait que personne n'y toucherait**, alors
   que le lot 4 vise `extraction.py` quatre fois (§4.1, §4.6, §4.7, §4.22) : le
   report se serait heurté au même mur. La réparation du lot 3 a donc reformaté
   `language.py` et `tests/unit/test_wipe_stores.py` dans un commit de style
   seul. Coût `mesuré` : **7** lignes — 3 ajoutées, 4 retirées.

**Coût total : 20 lignes de diff, sur trois commits de style.** Le récit d'un
« reformatage massif » était surdimensionné de bout en bout, et il instruisait
chaque conversation à venir de l'accepter sans remesurer. Le chiffre de 16 lignes
sur 1 221 qui vivait ici — mesuré pour les trois fichiers de `src/` avec `ruff`
0.11.8 et le `pyproject.toml` du dépôt, sans lequel `ruff` retombe sur 88
colonnes — était juste ; c'est le mot « massif » qui n'a jamais rien mesuré.

**Ce que la fermeture obtient, et c'est le motif réel.** `make all` rend **0**.
L'exception « rc=2 est le rouge attendu » — qui vivait dans chaque prompt du
chantier depuis le lot 0b, que chaque conversation redécouvrait, et qui a déjà
**masqué un vrai rouge une fois** — n'existe plus. Un `rc` non nul est désormais
un défaut, sans exception à connaître.

`mesuré` sur la pointe de la réparation du lot 3 :
`uv run ruff format --check src/ tests/` → « 66 files already formatted »,
`rc=0` ; `make all` → `rc=0`.

**Et l'angle mort est fermé par la portée, pas par le nettoyage.** Reformater les
quatre fichiers rend le dépôt propre **aujourd'hui** ; cela ne garde rien. La
divergence des deux portées — `make format-check` sur `src/`, le hook sur tout ce
qui est indexé — **était** le défaut, et c'est elle qui a produit l'angle mort
D7. `make format` et `make format-check` portent désormais sur `src/ tests/`,
donc les deux gardes voient la même chose. Sans ce second geste,
`test_wipe_stores.py` pouvait redériver en silence et rebloquer le commit suivant
qui le touche : *un garde-fou qui repose sur la mémoire du suivant n'est pas un
garde-fou.* C'est un écart au périmètre de la réparation, déclaré, et il était
déjà proposé au registre — « étendre `format-check` à `tests/` fermerait cet
angle mort d'un geste », consigné par la seconde réparation du lot 0b.

**Toute phrase de ce dépôt qui disait « trois fichiers » parlait de la portée de
`make format-check`, jamais de l'état du dépôt.** Le lot 0b avait clos cette
énumération sur une portée qui n'était plus celle du garde qu'il installait :
c'était une phrase d'exhaustivité. Elle est sans objet désormais — les deux
portées coïncident, et le compte est **zéro**.

### 5.6 Trois `except Exception` sans justification écrite au site

`wipe_stores.py:107`, `:115` et `:126` (branche `…restore-5e9fa1`, commit
`50fcb44`) attrapent `Exception` nu, journalisent et poursuivent, sans une
ligne qui dise pourquoi la largeur est voulue. La règle du dépôt l'exige au
site, et §4.7 relève exactement le même défaut dans `cleaning.py:486-489`.

Le cas est ici moins grave qu'en 4.7 : la conséquence est portée par
`wipe_stores.py:135-138`, qui accumule les stores en échec et sort en 1 — une
purge partielle ne passe donc pas pour une purge réussie. Ce qui manque est la
phrase, pas le garde-fou. À traiter avec 4.7, d'une seule main.


---

### 5.7 → TRANCHÉ par le lot 5 — la branche RESTE, et la mesure tranche mieux que l'argument

La branche qui rend `"ECHEC — …"` n'est plus atteinte en production : l'asset
lève avant de publier ses métadonnées (§8). Seuls les tests unitaires de
`reindex.py` l'exercent.

Le développeur de la réparation l'a rendue morte, l'a dit, et ne l'a pas
retirée — argument retenu : `request_reindex` est une fonction publique dont le
contrat est « ne lève jamais, dit ce qui s'est passé », et amputer son objet de
retour parce que son unique appelant d'aujourd'hui lève d'abord la coupleraient
à ce consommateur. À trancher avec §5.1 et §5.2, dans le lot du code mort.

### 5.8 → VÉRIFIÉ par le lot 5, non traité — divergence permanente et assumée

Il contient la phrase d'exhaustivité « la seule obligation que le contrat
impose au pipeline », corrigée depuis dans le docstring de `reindex.py` (§8).
Le commit n'a **pas** été réécrit : sa porte qualité a été prouvée verte, et la
règle du chantier interdit de réécrire pour un gain cosmétique.

Il existe donc une divergence permanente entre ce message et le code. C'est le
prix connu de la règle, il est assumé, et il est écrit ici pour que personne ne
le redécouvre comme un défaut.

## 6. Ouvert — ce que la documentation affirme et que le code ne fait pas

| # | Affirmation | Preuve du contraire | Sévérité |
|---|---|---|---|
| 6.1 | ~~`docling.md` : `CHUNK_SIZE=900`, `CHUNK_OVERLAP=150`~~ | **✅ lot 5** — variables mortes retirées du code ET de la table ; le motif est écrit au site pour que le débat ne se rouvre pas | haute |
| 6.2 | ~~`chromadb.md` et `llm_integration_plan.md` : fenêtre de **256** tokens~~ | **✅ lot 5** — c'est **128**, et le renvoi de ce constat était faux : *aucun* `settings.py` ne porte ce chiffre, la fenêtre est `modele.max_seq_length` lue au runtime. Annoncer 256 laissait croire à une fenêtre configurable qui n'existe pas | moyenne |
| 6.3 | ~~`chromadb.md` énumère les métadonnées~~ | **✅ lot 5** — il en manquait **cinq** et non quatre : le constat oubliait `page_no_end`, ajoutée par le lot 4. Traité aux **quatre** sites (13/18, 9/18, 15/18, 17/18 clés), et les énumérations qui ne portaient aucun rôle sont **retirées** au profit d'un renvoi à `ChunkMetadata` | haute |
| 6.4 | ~~« un vecteur par **bloc** »~~ | **✅ lot 5** — deux sites, plus la description du regroupement qui décrivait l'algorithme disparu | basse |
| 6.5 | ~~fragments isolés « absorbés dans leur paragraphe »~~ | **✅ lot 5** — la production **jette**, et le rejet est **borné** au chunk seul de son élément depuis le lot 4 : écrire « jette » sans la borne aurait créé le défaut d'à côté | moyenne |
| 6.6 | ~~`llm_integration_plan.md` prescrit `cross-encoder/ms-marco-MiniLM-L6-v2`~~ | **✅ lot 5, côté DOCUMENT** — la prescription est **retirée plutôt que remplacée** : choisir un reranker multilingue est une décision de l'autre dépôt, appuyée sur une campagne. Ce document devait cesser de prescrire ce qui a déjà échoué. Le défaut est **inerte** tant que le corpus est entièrement anglais (§1), et il se réveille au premier document non anglais ou à la première question française sur un passage anglais — ce que l'embedder multilingue rend précisément possible | haute |
| 6.7 | ~~`docling.md` : « Ressources : GPU NVIDIA (CUDA 12.1) »~~ | **✅ lot 5** — n'était fermé qu'**à moitié** : trois autres affirmations du même fichier supposaient un GPU (« seul service avec accès GPU », « FastAPI + CUDA 12.1 », « la conversion sature déjà le GPU »). La nuance juste est écrite : l'image embarque les wheels CUDA, elle n'**exige** pas de GPU | haute |
| 6.8 | ~~`docling.md` énumère les modules « sans dépendance externe »~~ | **✅ lot 5, corrigé par sa réparation** — ils sont **quatorze** sur 18, et non onze ; les quatre qui portent une dépendance de niveau module sont `extraction.py` (`bs4`), `images.py` (`minio`), `main.py` (`fastapi`) et `settings.py` (`pydantic_settings`). Le compte de onze **niait le déverrouillage des lots 3 et 4** — celui sur lequel reposent `test_vectors.py` et `test_nebula.py`. Le critère du balayage est écrit au site et rejoué par un test : §4.31.B2 | basse |
| 6.9 | ~~`README.md`, section Volumétrie : mesurée sur 42 documents~~ | **✅ lot 5** — remplacée par la mesure de l'index vivant, avec deux réserves (les 13 objets MinIO ne sont pas représentatifs, la chaîne d'images HTML étant rompue ; une taille de répertoire n'est pas une mesure de contenu) et **aucune extrapolation**. **Le renvoi de ce constat a roté DEUX fois** : `:317` → `:365` → la section est en `:404`. Voir §6.17 | moyenne |
| 6.10 | ~~chiffres de découpage et de bruit~~ | **✅ lot 5** — **conservés** avec leur périmètre plutôt que supprimés : ils documentent la décision prise à l'époque, et l'effacer laisserait le choix sans motif. Détail mesuré : la comparaison porte sur *Practical MLOps*, **absent du corpus** — les deux titres actuels s'en approchent, d'où la réserve écrite au site | moyenne |
| 6.11 | ~~`CHANGEMENTS.md` : 759 arêtes, 13 220 chemins~~ | **✅ lot 5** — même traitement que §6.10, et la réserve dit ce que le corpus actuel a mesuré à la place (§3.2). Le 0/0 côté agent n'est pas une contradiction : il mesurait un graphe produit par autre chose que ce code | haute |
| 6.12 | `Dockerfile.docling` installe torch depuis l'index CUDA 12.1 | **OUVERT — consigné par le lot 5 avec son motif, écrit au site.** Changer l'index change l'**image**, donc demande une reconstruction et une réingestion pour vérifier que l'extraction et l'encodage rendent les mêmes résultats : un chantier avec sa campagne de validation, hors du périmètre « documentation contre code ». Le coût est écrit dans `services/docling.md` (10,4 Go) | moyenne |
| 6.13 | ~~divergence de nommage du volume de cache~~ | **✅ lot 5 — SANS OBJET, et c'est une mesure** : `rag_hf_cache` et `rag_models_cache` n'apparaissent **nulle part** dans le dépôt. Écrit comme sans objet dans `services/docling.md` pour que personne ne le redécouvre comme un défaut | basse |
| 6.14 | ~~`README.md` : « le modèle n'est entraîné que sur de l'anglais »~~ | **✅ lot 5** — et le vestige vivait à **trois** sites, non deux : ce constat et §6.15 en nomment deux, le troisième est `src/docling_service/language.py`, le module dont la langue **est** le sujet. L'ancre morte était citée **deux** fois (README **et** `CHANGEMENTS.md`). Balayage complet : **0 renvoi interne mort** dans les documents livrés | haute |
| 6.15 | ~~`schemas.py` : « le modèle actuel n'étant entraîné que sur de l'anglais »~~ | **✅ lot 5** — dans le fichier qui **est** le contrat. Le motif est **remplacé** et non seulement retiré : la clé `language` sert à filtrer sur demande et à dire à l'utilisateur la langue de la source. Une clé sans motif invite le lot suivant à la croire morte, ce qui est arrivé à `chunk_ids` (§5.1) | haute |

---

### 6.16 → MOITIÉ faite par le lot 5, et il RESTE OUVERT — la seconde moitié est dans l'autre dépôt

L'exigence 4 est **tenue** sur l'échantillon du lot 1 : `sequence` est présente
sur **2 285 arêtes sur 2 285**, et l'ordre de lecture est prouvé — trié par
`sequence`, `page_no` ne décroît **jamais**, 0 inversion sur les trois documents
(`mesuré`). C'est un compteur global au document (`DocumentAccumulator._global_order`),
et il **survit aux lots de pages** du PDF.

Trois réserves qu'aucun document ne porte, et dont l'agent peut se tromper :

1. **`sequence` repart à 0 dans chaque document.** Elle n'est donc pas
   globalement monotone : tout « avant / après » doit être **borné au document**.
2. **Elle n'est pas contiguë sous un parent, par construction.** Mesuré **par le
   lot 1, sur 3 documents et 2 285 arêtes** : 44 des 185 parents ont des
   `sequence` non contiguës, et **44 sur 44** sont exactement expliqués par la
   taille du sous-arbre du frère précédent. Ce n'est pas un défaut — c'est un
   ordre de lecture global, pas un rang sous le parent. *(Remesuré sur le corpus
   complet — 15 173 arêtes, 763 parents, 167 non contigus — au site canonique.)*
3. **Le plus grand écart entre deux `sequence` consécutives d'un même parent vaut
   994**, c'est-à-dire une **différence** de 994 et **993 valeurs
   intercalaires** — les deux lectures ne donnent pas le même nombre, et aucune
   des deux n'était écrite. Un agent qui implémente « la fenêtre d'éléments »
   comme « les enfants de P dont `sequence ∈ [s−k, s+k]` » rendra
   **silencieusement moins** d'éléments que demandé ; un agent qui lit la
   contiguïté comme un indice d'intégrité conclura à une perte.

**Le site canonique des trois chiffres est le docstring de
`verify_contract.inversions_de_page`**, où ils sont remesurés sur le corpus
complet. Les mentions d'ici y renvoient.

**Le garde existe désormais — écrit par le lot 3 avec §4.4.** La propriété que
le lot 1 avait d'abord conclue — « aucun parent ne porte deux fois la même
valeur » — est l'**unicité sous un parent**, et non l'ordre exigé : une
numérotation aléatoire distincte par parent passerait ce test. Le garde écrit
est le second : `page_no` ne décroît pas dans l'ordre des `sequence`, borné au
document. `verify_contract.inversions_de_page` le vérifie sur la **totalité** des
arêtes — **0 inversion sur 15 173**, corpus complet, `mesuré` le 31 août 2026 —
et les trois réserves ci-dessus sont écrites à son site, parce que deux d'entre
elles interdisent des contrôles qu'on serait tenté d'écrire à la place.

**Restent à écrire au contrat côté agent**, ce que le lot 3 ne peut pas faire
d'ici : les réserves 1 à 3 concernent la façon dont l'agent LIT `sequence`, et
sa documentation vit dans l'autre dépôt.

### 6.18 → traité par le lot 5 — et il manquait une erreur de plus que ce constat n'en annonçait

Le lot 3 a mis à jour `documentation/services/nebulagraph.md` et
`documentation/llm_integration_plan.md` sur le seul point que son code rendait
faux — les tags d'élément gagnent `depth`. **Il a laissé les erreurs
préexistantes du même bloc**, périmètre strict, et les voici pour le lot 5
(`mesuré` le 31 août 2026 par `DESCRIBE TAG Document;` et `DESC SPACE rag_space;`
sur `rag_space`) :

| Site | Ce qu'il dit | Mesuré |
|---|---|---|
| `services/nebulagraph.md:24` | `vid_type=FIXED_STRING(64)` | **256** — `ngql.py` porte `VID_MAX_BYTES = 256`, et le commentaire y explique pourquoi 64 ne suffisait pas |
| `services/nebulagraph.md:26` | `CREATE TAG Document(filename string, type_file string)` | **7** propriétés : `filename`, `type_file`, `total_pages`, `collection`, `source_path`, `language`, `content_hash` |
| `llm_integration_plan.md:298` | `Document \| filename: string, type_file: string` | les mêmes 7 |

C'est la même famille que §6.3 : une énumération close que personne n'a
rouverte. `source_path` y manque des deux côtés, et c'est **l'exigence 3 du
contrat** — l'identité d'un document.

### 6.17 → traité par le lot 5 — et sa propre liste de « renvois vérifiés justes » avait ROTÉ

| Site | Ce qu'il dit | Mesuré |
|---|---|---|
| §2 de ce registre | « 1 PDF de 73 pages » sous l'étiquette **`mesuré`** | **71** — corrigé |
| §6.9 de ce registre | renvoi `README.md:317` | ligne réelle **365** — corrigé le 31 août 2026, **et roté depuis** : la section est en `:404`. Le renvoi désigne désormais la SECTION (« README.md, section Volumétrie ») et non une ligne |
| §3.2 (avant fermeture) | renvoi `extraction.py:370-373` | c'est la fin de `_detect_document_language` ; le vrai site est `extraction.py:320` + `ranking.py:130-148` — corrigé |
| §3.4 | renvoi `vectors.py:199-203` | c'est la boucle d'`upsert` ; le vrai site est `vectors.py:186-192` — corrigé |
| `pilotage_du_chantier.md` §2.2 | « 73 pages », deux sites | **71** |
| `pilotage_du_chantier.md` §5.1 | `main = 528748d` | la pointe bouge à chaque commit : le SHA a été retiré au profit de la commande qui la mesure |

**Cette section listait sept renvois « vérifiés justes et laissés tels quels ».
Remesurés par le lot 5 le 2 septembre 2026, DEUX le sont encore.** C'est le
résultat le plus instructif de tout le §6, et il porte sur la méthode plutôt que
sur les faits :

| Renvoi, tel qu'il était déclaré juste | État mesuré le 2 septembre 2026 |
|---|---|
| `ranking.py:56-71` — `docling_parent_rank` | **juste**, c'est bien le corps de la fonction |
| `ranking.py:83-84` — `docling_level_rank` | **juste** |
| `extraction.py:335-337` | **dérivé** — pointe désormais un *docstring* sur `minio_url`, plus le code de propagation |
| `index_report.py:75-84` | **dérivé** — pointe le bloc `Returns:`, plus la mesure |
| `nebula.py:49` — `VERTEX_PROPERTIES` | **PÉRIMÉ** — une parenthèse fermante seule. Le symbole ne vit plus dans ce fichier depuis le lot 3 (§5.3) |
| `nebula.py:160` — `last_visual_id` | **PÉRIMÉ** — une ligne vide |
| `schemas.py:94-95` | juste au moment de la mesure, et **corrigé depuis** par le lot 5 (§6.15) |

**Et le renvoi de §6.9 a roté DEUX fois.** Cette même section l'avait corrigé de
`README.md:317` vers `:365`. La section Volumétrie est aujourd'hui en `:404`.

**La leçon, et elle vaut plus que les sept lignes.** Un renvoi `fichier:ligne`
est une mesure dont la provenance comprend la **révision**, exactement comme le
« 56 files already formatted » du F2 : un nombre exact, mesuré, et périmé par le
commit qui le porte. Re-vérifier une liste de renvois ne la stabilise pas — elle
recommence à pourrir au commit suivant, et ce §6.17 en est la preuve par
lui-même, en trois jours.

**Le geste durable est de désigner un SYMBOLE et non une ligne** — `ngql.
VERTEX_PROPERTIES`, `vectors.get_chunker`, `ChunkMetadata.depth` — parce qu'un
symbole se déplace avec son code et qu'un `grep` le retrouve. Les renvois que le
lot 5 a écrits le sont sous cette forme, et les chiffres qu'il a consolidés
portent le nom de leur site canonique plutôt que sa ligne.

*(Les quatre renvois périmés ci-dessus ne sont **pas** corrigés en `fichier:ligne`
neuf : ce serait refaire le défaut à trois jours près. Ils sont remplacés par le
nom du symbole dans le corps des constats concernés.)*

---

## 7. Ouvert — fond et état de l'art

### 7.1 La vraie limite du découpage est le modèle, pas le découpeur

`paraphrase-multilingual-MiniLM-L12-v2` plafonne à **128 tokens**
(`settings.py:45`, `mesuré` indirectement par la médiane de 91 tokens rapportée
en `CHANGEMENTS.md:110`). Le RAG de 2026 travaille couramment sur 200 à 512
tokens, et les techniques qui dominent — *late chunking*, *contextual
retrieval* — supposent des fenêtres de 512 à 8 192. Le plafond de 128 est donc
structurel, imposé par le contrat, et non un défaut de `HybridChunker`.

Changer de modèle (`bge-m3`, `multilingual-e5-large`, `Qwen3-Embedding`) impose
une réingestion complète et ne se décide pas sans campagne comparative
appariée. **Ce n'est pas le moment** — mais c'est la question à rouvrir dès que
la première campagne de référence existe.

### 7.2 Les figures sans légende restent muettes

`nebula.py:183` ne relie que les `Caption` déjà présents dans le document. Une
figure sans légende est introuvable en recherche sémantique et impossible à
juger pertinente par le modèle, qui n'en voit qu'un marqueur. L'état de l'art :
une description générée par un VLM à l'ingestion, indexée dans ChromaDB. C'est
un chantier, pas un correctif.

---

## 8. Traité

Un constat fermé se déplace ici avec le commit qui l'a fermé, il ne s'efface
pas.

**Le lot 6 a été FUSIONNÉ dans `main` le 3 septembre 2026** par la fusion
`--no-ff` `69a6786` : 4 commits de campagne, puis **15 de réparation** exigés par
le pilote après l'audit indépendant. `499ecb2` est **intact** comme ancêtre — zéro
réécriture, **zéro ligne de `src/`**. C'est le **dernier lot du plan**.

Le conflit unique du registre a été résolu par le pilote dans le sens qui garde
l'insertion du lot **et** la date corrigée : une résolution naïve réintroduisait
la date fausse que ce lot avait lui-même trouvée (§4.32.d). Les quatre juges de sa
réparation passent, remesurés — 81 ticks dont 12 `SKIPPED`, la commande citée ne
produit pas les agrégats donc ils portent `calculé`, `grep -c '^#### 4.32'` rend
4, et l'exigence 5 est « non éprouvée » avec son motif. `make all` rend **0** sur
la fusion résolue, **884 tests**, balayage de graines **26/26 vertes**, corpus
intact à l'octet.

**LE PLAN EST ÉPUISÉ, et la suite est décidée** : on s'arrête au bord de ce dépôt,
et la passation vers `rag-agent-chat` vit à
[`etat_des_lieux.md`](etat_des_lieux.md). L'ordre de ce qui monte au plan est au
§7.0 bis du mandat — **§4.32.a en tête, devant §4.29.i**, sur la cotation relevée
par l'audit du lot 6.

**La campagne, telle qu'elle a été menée le 2 septembre 2026**, sur la branche
`claude/session-c608cd`. Il ne ferme aucun constat : il
**mesure** ce que les cinq lots précédents avaient fermé, sur un index produit
par le code de `main`, et il en verse **quatre** neufs au §4.32. Son compte rendu
est à son site canonique,
[`documentation/campagnes/2026-09-02-premiere-campagne-de-reference.md`](campagnes/2026-09-02-premiere-campagne-de-reference.md) ;
le jeu de 30 questions est à côté, en YAML pour la raison mesurée du §3.6 bis.

Ce que la campagne **confirme par la mesure**, et qui n'était jusque-là qu'annoncé :

- **§3.5 est entièrement fermé** — 199 images HTML sur 199 portent leur
  `minio_url`, contre 0 sur 199 mesurés par le lot 1 sur le producteur, et les
  199 objets sont dans le bucket, référencés, sans orphelin ni manquant ;
- **§4.28.a est fermé et son effet est attribué** — les éléments au jeu de
  chunks troué passent de 2 à 0, les chunks de 4 365 à **4 367** exactement, et
  les deux chunks retrouvés sont `aa3de10738` index 4 et `eb52c4ec8f` index 3,
  tous deux `label=code`, ce qui explique au chiffre près le seul mouvement des
  labels d'`index_report` — `code` de 973 à 975 ;
- **§4.29.e est fermé des deux côtés** — la colonne `page_no_end` existe *et* les
  données la portent : 0 sommet sur 15 173 à `NULL`, contre 15 173 sur 15 173
  avant. Sa clé entre dans les métadonnées ChromaDB ;
- **§4.15 est observé en vol pour la première fois, et le garde n'a aucun
  trou** — **12 ticks `SKIPPED` consécutifs**, de 12:56:43 à 13:02:28, chacun
  nommant le garde et le run d'ingestion qui bloque, l'un avec son âge. Les deux
  runs de réindexation créés à l'intérieur de la fenêtre d'ingestion le sont
  **entre les deux vagues**, où aucun run d'ingestion n'était non terminal :
  c'est le capteur qui a raison, pas la fenêtre qui a un trou ;
- **§3.4 est reproduit à l'identique sur un index neuf** — 137 chunks tronqués,
  3,1 %, médiane 95, maximum 149 tokens ;
- **§3.2 est confirmé à pleine portée** — **un** document reste plat sur 23.

Et ce qu'elle **ne** peut pas mesurer est écrit au même titre : l'**exigence 5 du
contrat n'est PAS ÉPROUVÉE** et n'est pas déclarée tenue — `rag-agent-chat` ne
**tourne** pas ici, et les runs de réindexation échouent tous sur `ReindexError`.
Le déclenchement, lui, est mesuré. **Le dépôt, en revanche, EXISTE sur ce poste**
(`/home/ubuntu/RAG/rag-agent-chat`), son `docker-compose.yml` déclare le service
`agent-api` sur `rag_network` — l'hôte même qu'`AGENT_SERVICE_URL` attend — et il
lui manque son `.env` (`mesuré`). La non-épreuve est donc un **choix de
périmètre** — autre dépôt, service non audité — et non une impossibilité de
poste : c'est écrit au §7 du compte rendu.

**Le lot 5 a été FUSIONNÉ dans `main` le 2 septembre 2026** par la fusion
`--no-ff` `d8c67c5` : douze commits de livraison, puis **dix-huit de réparation**
exigés par le pilote après l'audit indépendant. `e5103cf` est **intact** comme
ancêtre — zéro réécriture. `make all` à **0** sur chacun des trente, balayage de
graines **26/26** sur chacun, corpus intact à l'octet.

**Le pilote a remesuré avant de trancher** (`mesuré` le 2 septembre 2026) : le
juge de sa réparation — un `DESCRIBE` en échec relu comme « colonne présente » —
rend `rc=1` et **3 rouges**, là où il laissait la suite **entièrement verte** ;
`sed -n '230p'` ne porte plus le renvoi et les cinq sites nomment le symbole ; le
balayage AST rend **14** modules sans dépendance et **4** porteurs,
indépendamment ; `delete_document` supprime par `source_path` et **jamais par
id**. Sur le résultat de la fusion d'essai : `rc=0`, **865 tests**, 73 fichiers
formatés, balayage **26/26 vertes**.

**Et il n'était pas cosmétique** : trois de ses constats étaient des défauts de
comportement, dont un qui **rompait le contrat** — deux sites décidaient du nom du
sous-répertoire nettoyé, rien ne gardait leur accord, et l'`element_id` d'un
chapitre changeait. `chunk_ids` n'était pas mort mais **contourné**. La fenêtre du
modèle n'était gardée par rien. Ses quatre bloquants étaient, quatre fois, la
famille qu'il existe pour fermer, commise par lui. Mandat §5.1 sexies.

Il ferme §4.29.a, §4.29.b, §4.29.c, §4.29.e, §4.29.g, §5.1,
§5.2, §5.7 *(tranché : la branche RESTE)*, §6.1 à §6.11, §6.13 à §6.15, §6.17,
§6.18, et **la moitié faisable de §6.16**. Il vérifie §5.8 et §4.29.h — deux
divergences permanentes et assumées, non touchées. Il consigne §4.29.d, §4.29.f,
§4.29.i et §6.12 avec leur motif, et verse **onze constats neufs au §4.30**.

**Ce qu'il n'a pas fait, délibérément, et le pilote l'a fait après fusion** : il
n'a pas réécrit le plan de lots ni le §7 du mandat. Le §4.28.e pose la règle — « il n'appartient pas à une branche de
réécrire le plan » — et elle vaut ici. Le seul chiffre du mandat qu'il a touché est
le nombre de fichiers que `mypy` annonce au §2.4, que son code fait passer de 36 à
35 : la règle « documentation dans le même commit que le code » l'imposait, et il
a été **retiré** au profit de la commande qui le mesure.

**Le lot 4 a été fusionné dans `main` le 2 septembre 2026** par la fusion
`--no-ff` `79cd2bc` : 14 commits de livraison, puis 11 de réparation exigés par le
pilote après l'audit indépendant. `e9ebe43` est **intact** comme ancêtre de
`a845736` — zéro réécriture, vérifié avant fusion. Il ferme §3.5, §4.1, §4.2,
§4.3, §4.6, §4.7, §4.10, §4.15, §4.17, §4.19, §4.22, §4.25, §4.28.a à §4.28.d et
§5.6, et laisse **neuf constats au §4.29**.

Les neuf juges de sa réparation ont été rejoués par le pilote et rougissent tous :
le containment de la purge désarmé (9 rouges), l'âge du run bloqué, le compteur du
§4.22 rendu inerte à son site d'appel, le `page_no_end` des chunks mis à 0, les
deux contrôles de `verify_contract`, et un septième module rendu inimportable.
`make all` rend **0** sur le résultat de la fusion d'essai, **857 tests**, balayage
de graines **26/26 vertes**, corpus intact à l'octet.

**Le lot 3 a été fusionné dans `main` le 1er septembre 2026** par la fusion
`--no-ff` `4e28594` : 11 commits de livraison, puis 6 de réparation exigés par le
pilote après l'audit indépendant. Les 11 SHA d'origine sont **intacts** —
`22c782e` est ancêtre de `7eb0922`, zéro réécriture, vérifié avant fusion. Il
ferme §3.4, §4.4, §4.5, §4.11, §4.14, §4.21, §4.23, §4.24, §5.3 et §5.4, et laisse
**deux mutations survivantes** (§4.12, §4.28.d) et **cinq constats** au lot 4
(§4.28). Le juge de sa réparation, remesuré par le pilote : la mutation « groupes
anonymes comptés comme des titres » (`ranking.py:68` → `if True`) rend
`test_non_platitude.py` **rouge**, là où elle le laissait vert avant réparation.
`make all` rend **0** sur `main`, 708 tests, balayage de graines **26/26 vertes**.

Le lot 0 a été fusionné dans `main` le 29 août 2026 par la fusion `--no-ff`
`b59bf38` : 8 commits de livraison, puis 6 de réparation exigés par le pilote
après l'audit indépendant. Tous les commits cités sont désormais dans `main`.

### La réparation du lot 0 — six points, exigés avant fusion

L'audit indépendant a jugé le lot bon dans sa conception et a trouvé six
défauts à ses bords. Le pilote a refusé de les reporter au registre : deux
étaient des tests de quelques lignes dans des fichiers que le lot possédait
déjà, et le premier était une régression.

**1 → `33841c9` — une réindexation échouée n'est plus perdue.** C'était le seul
défaut de comportement, et une **régression** : sur `main`, un agent
momentanément injoignable recevait **une tentative par document ingéré**,
dont la dernière pouvait aboutir ; le lot livré lui en donnait **une seule**. Le curseur du sensor avançait à
l'**émission** de la demande, et le `run_key` déterministe
(`reindex-<storage_id>`) interdisait toute reprise — un `run_key` consommé
l'est pour toujours, Dagster le cherche dans tout l'historique. Remettre le
curseur à zéro ne rattrapait rien.

La correction retenue, et le pilote a lu ses alternatives : **le sensor ne
tient plus aucun état.** `update_cursor` a disparu du module. Il compare deux
*faits* lus dans l'historique des runs — le repère de la dernière ingestion
réussie, et celui de la dernière **réindexation réussie** — et le `run_key`
porte la rafale *et* la tentative. L'asset **lève** quand l'appel a été tenté
et n'a pas abouti ; une URL vide ne lève pas, un appel non tenté n'est pas un
appel échoué. Les trois propriétés du contrat sont tenues : une ingestion reste
verte quoi qu'il advienne de l'agent, un échec est retenté **indéfiniment**, et
un échec **rougit son run** — donc apparaît dans les filtres et les alertes,
là où « une métadonnée dans un run vert » ne le faisait pas.

La règle « ne jamais lever » a été rouverte à bon droit : elle venait de
`factory.py`, où une reprise signifiait reconvertir des centaines de pages ;
dans son propre run, une reprise coûte **un appel HTTP**. Le motif a disparu
avec le déménagement.

Prix assumé et consigné : un agent arrêté deux heures produit des runs rouges
pendant deux heures, un par tick. Le levier est `minimum_interval_seconds`
(30 s). Alternatives écartées et argumentées : garder un curseur mais l'avancer
au succès (un état que rien ne réconcilie avec la réalité), une `RetryPolicy`
bornée (**toute reprise bornée réintroduit la perte**), `run_key=None` (aurait
supprimé la seule protection contre deux évaluations concurrentes).

**2 → `bb74750` — le sensor est livré armé, et c'est prouvé.** `default_status=
DefaultSensorStatus.RUNNING` n'était gardé par rien : la retirer laissait 508
tests verts et rendait **tout le lot inerte au déploiement**. Un troisième test
tient les deux autres honnêtes — un sensor témoin déclaré sans le champ ne doit
**pas** être armé —, sans quoi ils resteraient vrais si Dagster changeait sa
valeur par défaut.

**3 → `1c002f2` — les deux moitiés du titre de `7d587b0`, enfin gardées.**
`tests/unit/test_wipe_stores.py` n'importait que les trois fonctions d'aide : `main()`
n'avait **aucun** test, et c'est là que vivent la purge MinIO et le
`sys.exit(1)` sur purge partielle. Testé en **sous-processus**, et l'argument
est bon : le comportement en cause *est* le code de sortie, ce qu'un
`docker compose exec` remonte et ce qu'un `&&` lit. Un import laisserait
attraper `SystemExit` — prouver qu'un objet a été levé, pas que la commande
échoue. Seconde raison, suffisante seule : boucher `chromadb`/`nebula3` dans
`sys.modules` laisserait les bouchons derrière soi et rendrait l'ordre des
tests significatif.

**4 → `3603492` — le `max()` sur plusieurs sources.** `max(reperes)` n'était
gardé par rien : le harnais appelait `build_reindex` avec **un** nom de job,
alors que `sources.yaml` en déclare **trois**. La configuration réellement
livrée n'était testée nulle part.

**5 → `46969bb` — « la seule obligation » corrigée.** `reindex.py` affirmait
être la seule obligation du contrat ; le §0 en énonce **cinq**, et l'exigence 1
est implémentée par `98bb20d`, du même lot. La correction ne recopie pas la
liste — ce serait la même faute d'un cran plus loin : elle dit ce que le module
porte, donne un contre-exemple vérifiable et renvoie ici. Le message de commit
de `3eb5aef`, lui, garde l'affirmation fausse : §5.8.

**6 → `4e3345c` — le chiffre 21 retiré.** Il vivait dans du **code de
production** sans étiquette et ne correspondait à aucun corpus connu. Retiré
plutôt qu'étiqueté, l'argument étant gardé : il ne dépend d'aucun corpus.

**Mesures de la réparation** (`mesuré`) : `make all` vert sur chacun des 6
commits — 508 / 508 / 511 / 521 / 532 / **535** —, balayage de graines
**156/156**, et le compte du README juste **dans chaque commit qui le change**.
Neuf mutations déclarées ; le pilote en a rejoué **huit de ses mains, toutes
rouges**.

**Les commits cités ci-dessous** sont ceux de la livraison initiale du lot.

### 5.5 → traité par le lot 0b — les hooks `pre-commit` sont installés

`.pre-commit-config.yaml` déclarait `ruff`, `ruff-format`, `detect-secrets`,
`trailing-whitespace` et `check-yaml`, et **rien ne les exécutait** : le
framework n'était installé nulle part. `.git/hooks/pre-commit` ne portait que le
contrôle d'identité d'auteur.

**L'arbitrage retenu : le contrôle d'identité devient un hook `repo: local`**, et
son `entry` pointe le script versionné `scripts/git-hooks/pre-commit`. Le fichier
`.git/hooks/pre-commit` — qui ne peut héberger qu'un script — est rendu au
framework, et l'installation tient en un geste :
`make install && uv run pre-commit install`.

La propriété qui fait tenir l'arbitrage : les deux voies d'installation
exécutent **les mêmes octets**. La liste blanche d'adresses n'a qu'un site,
`ADRESSES_AUTORISEES` dans le script versionné, donc elle ne peut pas diverger.
Le mandat §2.1 reste vrai, et il a été réécrit dans le même commit pour donner
les deux voies et dire laquelle prendre.

Écartées, et pourquoi :

- **chaîner à la main dans `.git/hooks/pre-commit`** (identité, puis
  `exec pre-commit run`) : c'est réécrire à la main ce que `pre-commit install`
  génère, dans un fichier **non versionné** — donc un garde-fou qui n'existe
  que sur le poste de celui qui l'a écrit. C'est exactement le défaut que §5.5
  ferme ;
- **`core.hooksPath` vers un dossier versionné** : `pre-commit` refuse
  d'installer quand `core.hooksPath` est positionné, et la valeur est partagée
  par tous les arbres de travail ;
- **déplacer l'identité vers `pre-push` ou `commit-msg`** pour libérer
  `pre-commit` : `pre-push` est trop tard — le commit porte déjà la mauvaise
  adresse, et c'est la réécriture d'historique qui coûte cher. Inutile de toute
  façon : `stages: [pre-commit]` conserve exactement le moment de déclenchement.

**Deux réglages sans lesquels le hook serait creux.** `always_run: true` :
un hook dont la liste de fichiers filtrée est **vide** est *sauté* par le
framework, et le contrôle d'identité ne dépend d'aucun fichier ;
`always_run` rétablit la parité. Et `pass_filenames: false`, le script ne lisant
pas d'arguments mais `git var GIT_AUTHOR_IDENT`.

**Ce paragraphe portait « c'est là la SEULE faiblesse de la voie framework face
au script brut ». C'était faux, et cette phrase a caché la régression R1 pendant
tout le lot.** Il y en avait une seconde, plus large : le hook généré ouvre sa
configuration en chemin **relatif**, donc le contrôle ne valait plus que pour
les arbres de travail dont la configuration le porte. Une phrase d'exhaustivité
clôt une énumération que personne ne rouvre — c'est la leçon du chantier, et
elle s'est appliquée au document qui l'énonce. Voir « R1 » ci-dessous.

**Prouvé par mutation, sur un clone frais** (`mesuré`, 31 août 2026). Le cas
atteignable est le commit sans fichier éligible, `git commit --allow-empty` :

| Configuration | Commit vide portant `…@aosis.net` |
|---|---|
| `always_run: true` (livré) | **refusé**, `rc=1`, « COMMIT REFUSÉ » |
| `always_run` retiré | **accepté**, `rc=0` — le hook affiche « (no files to check) Skipped » et le commit part avec l'adresse professionnelle |

C'est exactement le sinistre d'origine, à un réglage de configuration près.

**`ruff-format` est passé à `--check`.** Sans cela, le premier développeur à
toucher une ligne de `extraction.py` aurait vu le hook reformater le fichier
entier et emporté dans son commit les trois plis réservés au lot 2 (§5.4) : le
défaut que le lot 0b ferme dans `make all`, revenu par la porte du hook. C'est un
écart au fichier tel qu'il était déclaré, assumé et argumenté au site.

### R1 → traitée par la réparation du lot 0b — le contrôle d'identité était devenu conditionnel à la branche

**C'était une régression, et de la famille de défaut qui a coûté un dépôt
entier.** Le lot 0b, tel qu'il avait été livré, a fermé une porte et en a
entrouvert une autre sans l'écrire.

Le mécanisme, en trois lignes :

- **avant** le lot, `.git/hooks/pre-commit` portait le script d'identité. Ce
  fichier vit **hors** de l'arbre de travail : le contrôle valait pour toute
  branche, tout commit détaché, tout `git bisect` ;
- **après** le lot, le contrôle vivait dans `.pre-commit-config.yaml`, un
  fichier **de l'arbre de travail**, et le hook généré l'ouvre en chemin
  **relatif** (`--config=.pre-commit-config.yaml`) ;
- donc tout arbre dont la configuration ne porte pas le hook était désarmé, **en
  silence**. Sur les **111** commits de `main` (`a005172`), **aucun** ne la porte
  (`mesuré` le 31 août 2026 :
  `for c in $(git rev-list a005172); do git show "$c:.pre-commit-config.yaml" | grep -q identite-auteur; done`).

**Mesuré, dans un clone frais monté par `pre-commit install` seul, arbre sorti à
`298c77e`** (31 août 2026) :

```bash
GIT_AUTHOR_EMAIL=florian.horellou@aosis.net \
GIT_COMMITTER_EMAIL=florian.horellou@aosis.net \
git commit --allow-empty -m essai
```

→ `rc=0`, commit **créé**, auteur **et** committer `@aosis.net`. Le hook du
framework tourne bel et bien, et son rapport ne contient **aucune** ligne
d'identité.

**C'est la leçon « une règle survit à son motif », appliquée à un fichier qui
déménage.** La propriété « inconditionnel » du contrôle d'identité ne venait pas
du script : elle venait de l'**endroit** où il vivait. Le script a changé de
place, la propriété est morte dans le déménagement, et rien ne l'a notée — pas
même le développeur qui a écrit, dans le même lot, que le mandat §2.1 devait
rester vrai. La phrase d'exhaustivité du §5.5 ci-dessus a fermé la porte à
double tour.

#### Ce qui a été retenu, et pourquoi pas seulement de la documentation

La réparation documentaire proposée par l'audit — au mandat §2.1, inverser
l'ordre : copie manuelle **d'abord**, `pre-commit install` ensuite, jamais `-f`
— **est correcte et elle est retenue**. Elle laisse `pre-commit` en « migration
mode » et conserve le script en `pre-commit.legacy`, la seule couche indépendante
de la branche. Mesuré : sous ce montage, dans un arbre à `298c77e`, le commit
`@aosis.net` est **refusé**, `rc=1`, HEAD inchangé.

**Elle ne suffisait pas, et pour une raison mesurée plutôt que rhétorique.**
`pre-commit install` **suggère lui-même** le geste qui détruit la couche, dans sa
propre sortie : « `Use -f to use only pre-commit.` ». Une consigne documentaire
qui contredit l'outil qu'elle pilote perd, et elle perd en silence : `-f` ne
produit aucune erreur, seulement l'absence d'une protection. L'inversion de
l'ordre non plus. Une porte dont la seule preuve est une phrase dans un fichier
de 900 lignes n'est pas une porte.

**Ce qui a donc été livré, en plus :**

1. `scripts/installer-les-garde-fous.sh`, versionné, qui fait les deux gestes
   dans l'ordre, ne passe jamais `-f`, et **vérifie son propre résultat** —
   `.git/hooks/<type>` doit être le hook du framework, `<type>.legacy` doit être
   octet pour octet le script d'identité — en sortant en erreur avec la cause
   probable sinon ;
2. `make install` l'appelle. L'installation redevient **un seul geste**, ce qui
   rend vraie la phrase d'exhaustivité que la cible `install` portait déjà
   (« la seule étape d'installation de la porte qualité »), et qui était devenue
   fausse avec le lot 0b ;
3. `tests/unit/test_installation_des_garde_fous.py`, qui **prouve la propriété**
   au lieu de la documenter : un dépôt jetable dont la configuration ne déclare
   pas le contrôle d'identité, armé par le script livré, refuse le commit
   `@aosis.net` — en auteur seul, en committer seul, et sur les deux — et accepte
   une adresse de la liste blanche.

**Écarté, et pourquoi.** `prepare-commit-msg` est le seul point d'accroche commun
à `git commit`, `git revert`, `git cherry-pick` **et** `git merge` (`mesuré`,
mouchards posés sur chaque hook). Il aurait donc pu couvrir d'un geste tout ce
que `pre-commit` laisse passer. Il est écarté sur deux mesures :

- lors d'un `git cherry-pick`, `git var GIT_AUTHOR_IDENT` y rend l'identité
  **locale**, pas celle du commit produit. Mesuré : un commit dont l'auteur est
  `@aosis.net`, cueilli depuis un arbre configuré en `@gmail.com`, se présente au
  hook comme `@gmail.com` et passe. Le contrôle serait **vert sur le défaut** —
  exactement le garde qu'on croit avoir ;
- un refus depuis `prepare-commit-msg` laisse l'arbre sale : mesuré sur
  `git merge --no-ff`, `MERGE_HEAD` reste **présent**, la fusion est en cours
  et il faut un `git merge --abort` ; sur `git revert`, neuf fichiers modifiés
  restent dans l'arbre sans qu'aucun état de git ne le signale.

### D1 → traitée par la réparation du lot 0b — les commits de FUSION n'étaient couverts par rien

Ce n'était **pas** une régression du lot 0b : le script brut avait le même trou.
Mais le geste suivant du chantier est `git merge --no-ff`, et ce commit-là part
sur GitHub, où la liste des contributeurs ne se défait pas.

`pre-commit install` n'installe que le type `pre-commit`. Mesuré le 31 août 2026,
mouchards posés sur chaque hook de `.git/hooks`, ce que chaque geste déclenche :

| Geste | `pre-commit` | `prepare-commit-msg` | `commit-msg` | `pre-merge-commit` |
|---|---|---|---|---|
| `git commit` | oui | oui | oui | — |
| `git commit --amend` | oui | oui | oui | — |
| `git merge --no-ff` | **non** | oui | oui | **oui** |
| `git revert --no-edit` | **non** | oui | **non** | — |
| `git cherry-pick` | **non** | oui | **non** | — |

Mesuré, dans un clone monté selon le lot tel qu'il avait été livré :
`git merge --no-ff` avec `GIT_AUTHOR_EMAIL` et `GIT_COMMITTER_EMAIL` en
`@aosis.net` → `rc=0`, commit de fusion **créé**, auteur et committer
`@aosis.net`, et **aucun hook n'a tourné** — la sortie de `git merge` ne porte
aucune bannière du framework.

**Fermé des deux côtés**, parce qu'une moitié seule aurait été creuse :

- `scripts/installer-les-garde-fous.sh` installe les deux types
  (`--hook-type pre-commit --hook-type pre-merge-commit`) **et** pose la copie
  manuelle sur les deux, donc `pre-merge-commit.legacy` couvre les arbres dont la
  configuration ne porte pas le hook. Sans cette seconde moitié, la fusion serait
  gardée sur la branche du lot et nulle part ailleurs — exactement le défaut R1,
  revenu par la porte de la fusion ;
- `.pre-commit-config.yaml` déclare `default_install_hook_types: [pre-commit,
  pre-merge-commit]` et `stages: [pre-commit, pre-merge-commit]` sur le hook
  d'identité. La clé ne sert qu'à un `pre-commit install` tapé à la main : le
  script passe les types explicitement, l'installation ne devant rien à la
  branche sortie.

Prouvé par mutation sur un **vrai** `git merge`, dans
`tests/unit/test_installation_des_garde_fous.py::TestLesCommitsDeFusionSontCouverts`,
avec son témoin — une fusion portant une adresse de la liste blanche doit passer,
sans quoi le test serait vrai d'un montage qui refuse toute fusion.

**Reste ouvert, et borné : `git revert`, `git cherry-pick`, `git rebase`.** Le
seul point d'accroche commun est `prepare-commit-msg`, et il est écarté sur
mesure — voir R1 ci-dessus, « Écarté, et pourquoi » : il y voit l'identité
**locale**, donc il serait vert sur le défaut, et son refus laisse l'arbre sale.
La fermeture honnête est un hook `pre-push`. **À trancher par le pilote** : le
registre §5.5 avait écarté `pre-push` au motif qu'il est « trop tard, le commit
porte déjà la mauvaise adresse » — vrai, mais ce qui coûte cher n'est pas le
commit local, c'est le **push**, et réécrire un historique non poussé est
gratuit. L'argument mérite d'être rouvert ; il l'est ici, pas tranché.

### C → traitée par la réparation du lot 0b — les hooks contre le corpus versionné

**Ce constat n'est pas né du lot 0b, mais c'est sa fusion qui le rendait
vivant.** Pendant que le lot travaillait, une autre conversation a poussé
`a005172` sur `main` — « data: versionner le corpus, il fait partie de l'identité
du projet » : `Datas/htms/` et `Datas/pdfs/` sortent du `.gitignore`, 25 fichiers,
**55 Mo** (`mesuré`, `du -sh Datas` sur le résultat de la fusion d'essai). Le lot
0b installe la porte. Les deux ensemble donnent un arbre rouge, et c'est
exactement le cas que le mandat §7 fait mesurer : deux branches vertes peuvent
donner un arbre rouge.

Mesuré sur le résultat d'une fusion d'essai `--no-ff` avec `a005172`,
**0 conflit** :

| Fait | Mesure |
|---|---|
| `detect-secrets` refuse le corpus | `rc=1`, deux `Hex High Entropy String` — `Datas/htms/MLOps with Databricks/3. MLflow for Traditional ML.html:94` et `…/4. Model Serving： Architectures and Implementation.html:330`. Faux positifs |
| les hooks d'hygiène écrivent dedans | **24 fichiers sur 25**, **240 lignes** — 216 pour `trailing-whitespace`, 24 pour `end-of-file-fixer` |
| `check-added-large-files` interdit d'étendre | un fichier déjà suivi qu'on modifie : `rc=0`. Un chapitre **nouveau** de 661 ko : `rc=1`, refusé |
| fichiers suivis au-dessus du seuil de 500 ko | **25** |

**Le deuxième fait est le plus grave, et il ne se voit pas.** On ne peut pas
poser de `# pragma: allowlist secret` sur les deux détections : le **contenu** du
fichier entre dans le calcul de `element_id` (contrat, exigences 2 et 3). Et pour
les hooks qui écrivent, le geste naturel — `git add` puis recommit — fait entrer
le fichier **altéré**, au-delà de ce que l'humain a écrit, **sans aucune
erreur**. C'est le sinistre du mandat §2.2 appliqué au contenu au lieu du nom :
deux postes dont les fichiers diffèrent d'un caractère produisent des
identifiants différents, donc des campagnes incomparables, et rien ne le signale.

#### Ce qui a été retenu, et l'hypothèse écartée

**L'hypothèse du pilote — `exclude` sur `detect-secrets` seul — était
insuffisante, et l'audit l'a réfutée** : elle laisse ouvertes les deux autres
familles, dont celle qui écrit. **Retenu : un `exclude: '^Datas/'` au niveau
RACINE**, et non par hook.

La raison est celle du lot tout entier. `pre-commit` applique les motifs
`files`/`exclude` de la racine à la liste de fichiers **avant** de la distribuer
aux hooks : un seul site couvre donc les quatre hooks fautifs **et tous ceux
qu'on ajoutera**. Un `exclude` par hook aurait demandé de se souvenir de le
reporter sur le hook suivant — un garde-fou qui repose sur la mémoire du suivant
n'est pas un garde-fou.

Gardé par `tests/unit/test_hooks_contre_le_corpus.py`, qui reproduit le filtrage
de `pre-commit` (`re.search` du motif sur le chemin) et asserte le motif livré.
Il porte son témoin : un motif trop large — `'.'` — désarmerait la porte entière
en restant vert sur les deux autres tests. Quatre mutations, quatre rouges
ciblés : `'^Datas'` (sans barre, emporte `Datastore/`), `'Datas/'` (sans ancre,
emporte `src/Datas/`), `'^Datas/htms/'` (laisse le PDF dehors), `'.'`.

#### La conséquence du point 3, écrite là où le prochain la lira

Le constat « le corpus ne peut plus être étendu » demandait une réponse, pas
seulement une correction. **Le geste est écrit au `README.md`, section « Le
corpus est hors de portée des hooks, et voici comment l'étendre » :** c'est un
`git add` ordinaire, sans `--no-verify`, sans seuil à relever, sans exception à
ajouter — et c'est précisément l'effet voulu de l'exclusion. Les deux seules
réserves y sont écrites : **ne renommer aucun fichier** (`source_path` entre dans
`element_id`), et les bornes de GitHub (avertissement à 50 Mo par fichier, refus
à 100 Mo — sans objet aujourd'hui, mais **pas de loin** : voir F1 plus bas, le
« moins de 1 Mo » écrit ici était faux d'un facteur 6).

**Ce que l'exclusion coûte, assumé et écrit au site :** un secret réel déposé
sous `Datas/` ne serait pas vu par `detect-secrets`. Accepté — le corpus est une
capture de documentation publique, et l'alternative consiste à altérer les
données de mesure du chantier. La borne est étroite : ce chemin-là, et lui seul.

### La réserve du pilote sur `.env` et `detect-secrets` — CONFIRMÉE

Le §5.5 disait que `detect-secrets` « n'a jamais tourné en garde-fou sur un dépôt
dont le `.env` porte les mots de passe MinIO et PostgreSQL ». La première moitié
était vraie. **La seconde induisait en erreur, et le raisonnement du pilote est
confirmé par la mesure** (31 août 2026) :

- un hook `pre-commit` ne voit que les fichiers **indexés** ;
- `.env` est ignoré (`git check-ignore -v .env` → `.gitignore:2`) et **non
  suivi** (`git ls-files --error-unmatch .env` → échec). Il n'est donc jamais
  indexé, et **installer le hook ne le fera jamais scanner** ;
- `docker-compose.yml` ne porte **aucun** secret en clair : les sept sites
  concernés passent tous par une interpolation `${…}` (`mesuré`,
  `grep -nE "PASSWORD|SECRET|ROOT_USER|_KEY" docker-compose.yml`).

Le gain réel est donc **ailleurs, et il est réel** : empêcher qu'un secret parte
un jour dans un fichier **versionné**. C'est une protection prospective, pas la
découverte d'un secret déjà présent. Écrit comme tel au `README.md` pour que
personne ne la survende.

### La baseline `detect-secrets` — supprimée, et pourquoi

Les deux faits avancés par le pilote sont **confirmés**, et le second est pire
que « non vérifié » : `.secrets.baseline` portait `generated_at`
`2026-04-30T00:15:52Z` (quatre mois) et une seule entrée,
`tests/unit/test_settings.py:44`, `Secret Keyword`, `is_verified: false`.

**Cette entrée était un fantôme.** Elle désignait
une assertion sur `minio_root_password` comparée à une valeur d'essai, ligne
**supprimée le 11 juin 2026** par `b157e84` : le fichier ne compte plus que 36 lignes, il n'a donc pas
de ligne 44, et il ne contient aucun secret (`mesuré`). La baseline mentait
depuis deux mois et demi.

**L'argument accessoire « et elle était `is_verified: false` » est FAUX, et il est
retiré.** En sémantique `detect-secrets`, `is_verified` signifie « vérifié contre
le **service réel** » par un plugin de vérification ; le champ d'audit humain est
`is_secret`. Un `is_verified: false` est donc la valeur normale de presque toute
entrée de baseline, et n'indique aucun pourrissement. **La preuve du fantôme
reste entière** — elle tient à la ligne 44 disparue, mesurée — mais elle tenait
seule, et cet argument-là ne lui ajoutait rien.

Et elle ne mentait pas passivement. Mesuré : `detect-secrets-hook --baseline
.secrets.baseline tests/unit/test_settings.py` **réécrit la baseline** et sort en
**3** — « Please `git add .secrets.baseline` ». Le premier commit touchant ce
fichier aurait donc été refusé pour une raison sans rapport avec lui.

**Tranché : la baseline est supprimée, et `--baseline` retiré des `args`.** Une
baseline est un état que rien ne réconcilie avec le code, indexé par des numéros
de ligne et des hachages qui dérivent tous les deux — c'est la leçon « ne rien
écrire est plus robuste que bien écrire » appliquée à la lettre, et le fantôme en
est la preuve mesurée. Les faux positifs se déclarent désormais **au site**, par
`# pragma: allowlist secret` avec sa justification : un pragma est relu dans le
diff et **meurt avec la ligne qu'il annote**, là où une entrée de baseline lui
survit.

**Ce que `detect-secrets` a trouvé, en tournant vraiment** (`mesuré`, scan de
tous les fichiers versionnés) : **trois** détections, toutes fausses.

| Site | Détection | Verdict |
|---|---|---|
| `.secrets.baseline:130` | `Hex High Entropy String`, `Secret Keyword` | le hachage **de la baseline elle-même**. Ne se produit qu'en scan direct : le hook exclut son propre fichier. Disparu avec la baseline |
| `src/pipeline/reindex.py` | `Secret Keyword` | la constante `API_KEY_HEADER`, dont la valeur est un **nom** d'en-tête HTTP et non une clé. Pragma posé |
| `tests/unit/test_reindex.py` | `Secret Keyword` | l'argument `api_key` d'un test, dont la valeur d'essai est le mot « secret » lui-même. Pragma posé |

**Aucun secret réel n'a été trouvé.** Et les deux faux positifs **bloquaient**
tout commit touchant ces deux fichiers : le garde-fou, tel qu'il était déclaré,
était non seulement inactif mais ininstallable en l'état.

Piège mesuré au passage, et consigné parce qu'il se reproduira : le plugin
`Secret Keyword` **déduplique par hachage** dans un fichier. Poser le pragma sur
la première occurrence a fait apparaître une seconde ligne portant la même
valeur, jusque-là masquée. Un scan après correction n'est pas une politesse.

Second piège : `.secrets.baseline` ne se terminait pas par un saut de ligne, si
bien que `end-of-file-fixer` la réécrivait, ce qui faisait ensuite échouer
`detect-secrets` sur « your baseline file is unstaged ». Deux hooks du même
fichier se défaisaient mutuellement le travail. Sans objet désormais.

### 5.4, première moitié → traitée par le lot 0b — la porte constate au lieu d'écrire

`make all` avait `format` pour première cible, c'est-à-dire `ruff format src/`,
qui **écrit** : la porte réécrivait trois fichiers avant de les contrôler. Une
porte qualité qui écrit dans le dépôt qu'elle contrôle ne contrôle rien — elle
rend vrai ce qu'elle allait vérifier.

Le coût réel n'était pas le reformatage, c'était la **manipulation à se
rappeler** : révoquer `git checkout -- src/` avant chaque commit. Le développeur
de la réparation du lot 0 l'a fait six fois parce qu'il le savait ; le suivant ne
l'aurait pas su et aurait livré du reformatage sans rapport avec son sujet, dans
un commit que personne n'aurait relu pour ça.

`format` (écrit, geste volontaire) et `format-check` (constate) sont désormais
deux cibles distinctes, et c'est `format-check` qui entre dans `all`. Vérifié par
mutation : avec `format` dans `all`, `make all` laisse trois fichiers modifiés
dans l'arbre ; avec `format-check`, l'arbre est intact après la porte
(`mesuré`, 31 août 2026).

`format-check` passe **en dernier** dans `all`. L'ordre ne change pas le verdict
de la porte — elle est rouge dans les deux cas — seulement ce qu'un humain
apprend avant qu'elle ne s'arrête. Placé en premier, il aurait privé tous les
lots à venir du signal de `lint`, `typecheck` et `test` sur `main`, pour les
mois où le rouge de formatage reste ouvert. C'est un écart au « une ligne » que
le registre annonçait, et il est assumé.

Reste ouvert, et détaché : les trois fichiers eux-mêmes (§5.4 ci-dessus, lot 2).

### 4.18 → traité par le lot 0b — les sensors d'ingestion sont livrés armés

`factory.py:335` déclare `default_status=DefaultSensorStatus.RUNNING` sur
**chaque** sensor de source, et rien ne le gardait : retirer la ligne laissait
**535 tests verts** (`mesuré`, 31 août 2026 — suite entière moins la nouvelle
classe, sous mutation). Tout le pipeline était donc livrable à l'arrêt en
silence.

Le garde est décliné de celui du sensor de réindexation
(`bb74750`) dans `tests/unit/test_factory.py::TestLesSensorsDIngestionSontLivresArmes`,
avec les trois précautions qui le rendent non creux :

- il asserte sur l'objet **produit** — `build_source(...).sensor` — et sur celui
  que `definitions.py` **livre** réellement, jamais sur la présence du mot dans
  la source ;
- il boucle sur **toutes** les sources de `sources.yaml`, et **chacun des deux
  tests qui bouclent porte sa propre borne, EN LIGNE**, sur la collection qu'il
  parcourt. C'est la leçon de `3603492` : un harnais qui n'appelle la fabrique
  qu'avec une source laisse les autres sans garde. La borne est **inférieure** et
  non une égalité, pour qu'une quatrième source soit couverte d'office sans
  qu'une phrase d'exhaustivité ne l'interdise ;

  **La livraison initiale avait mis cette borne dans un test à part, et ce test
  ne gardait rien.** Il appelait `load_sources()` de son côté, donc il
  n'observait jamais le harnais des deux autres : `mesuré` le 31 août 2026,
  forcer ce harnais à une liste vide **et** retirer l'assertion en ligne laissait
  **551 tests VERTS**. Il était vert des deux côtés du défaut. Sa couverture
  marginale est de surcroît **nulle** — `mesuré` : `load_sources()` rendu vide
  globalement rougit 10 tests, dont
  `test_sources.py::TestDefaultSourcesFile::test_loads_and_validates`, qui
  asserte exactement les mêmes trois noms. Le test a donc été **retiré** par la
  réparation, et l'assertion en ligne renforcée d'un compte
  (`len(sources) >= 3`) vers un ensemble de **noms**
  (`{s.name for s in sources} >= SOURCES_ATTENDUES`), strictement plus fort : un
  compte reste vert si une source est renommée pendant qu'une autre est ajoutée.
  C'est la leçon « un test qui choisit lui-même son cas doit prouver qu'il l'a
  atteint », et cette preuve doit vivre **là où le cas est choisi**. Le garde du
  lot tient après retrait : la mutation de `default_status` dans `factory.py`
  rougit toujours les deux tests qui bouclent (`mesuré`) ;
- un sensor témoin déclaré **sans** le champ ne doit pas être armé, sans quoi
  les assertions resteraient vraies si Dagster changeait sa valeur par défaut.
  Dagster livre bien `STOPPED` par défaut (`mesuré` sous mutation).

### Les affirmations que le lot 0b avait rendues fausses → corrigées par sa réparation

Le lot 0b a édité en profondeur le `README.md`, le `Makefile`, le mandat et ce
registre. Neuf affirmations en sont sorties fausses ou surdimensionnées. Elles
entrent dans le périmètre de la réparation parce que la règle du dépôt est
« documentation dans le même commit que son code », et parce que ce chantier ne
traque rien d'autre que l'écart entre ce que la documentation affirme et ce que le
code fait.

| Réf | L'affirmation | Ce que la mesure dit | Où c'est corrigé |
|---|---|---|---|
| **D2** | README : les hooks qui écrivent « montrent leur diff » | **faux.** `--show-diff-on-failure` n'est activé nulle part, et **aucune clé** de `.pre-commit-config.yaml` ne peut l'activer — c'est un drapeau de ligne de commande. La sortie se limite à `files were modified by this hook` puis `Fixing <fichier>` (`mesuré`) | README : la phrase est corrigée, et les deux commandes qui montrent le diff sont données |
| **D3** | README : `check-added-large-files` = « aucun fichier > 500 ko » | **faux.** Seuls les fichiers **ajoutés** sont contrôlés ; un fichier déjà suivi qu'on modifie passe quelle que soit sa taille, et le dépôt post-fusion en porte **25** au-dessus du seuil (`mesuré`) | README, tableau des hooks — ligne détachée de `check-yaml` |
| **D4** | Makefile : « `uv sync` … c'est la **seule** étape d'installation de la porte qualité » | **rendue fausse par le lot**, qui en avait fait deux. Redevenue **vraie** : `make install` arme aussi les hooks | Makefile, cible `install` — voir R1 |
| **D7** | README, mandat §2.4, ce registre §5.4 : « trois fichiers » non format-propres | **faux.** Il y en avait **quatre** : `tests/unit/test_wipe_stores.py`, préexistant sur `main`, invisible à `make format-check` (borné à `src/`), non réparé par `make format`, mais **bloqué** par le hook `ruff-format --check`. **Sans objet depuis la réparation du lot 3** : les quatre sont reformatés, les deux portées coïncident sur `src/ tests/`, et le compte est zéro (§5.4) | §5.4 ci-dessus, plus README et mandat §2.4 |
| **D8** | « reformatage massif » qui « noierait le lot 2 » | **surdimensionné.** `mesuré` : **16 lignes** de diff sur **1 221**, à cinq endroits, dont quatre replis de ligne (le « 1 213, quatre endroits » de cette ligne était lui-même imprécis — voir F2 plus bas). La décision de ne pas reformater reste bonne — pour la **lisibilité** du lot 2, pas pour un volume | §5.4 ci-dessus : le récit est remplacé par la mesure |
| **D9** | README : « le dépôt en portait **2** » pragmas | **faux.** Il y en a **3** — `src/pipeline/reindex.py:69`, `tests/unit/test_reindex.py:91` et `:92` (`mesuré`). La troisième est née du piège de déduplication décrit plus haut, et n'avait pas été recomptée | README, avec la commande de comptage |
| **D10** | `is_verified: false` lu comme un signe de pourrissement de la baseline | **faux.** En sémantique `detect-secrets`, `is_verified` signifie « vérifié contre le **service réel** » ; le champ d'audit humain est `is_secret`. C'est la valeur normale de presque toute entrée. **La preuve du fantôme reste entière** — la ligne 44 disparue — mais elle tenait seule | `.pre-commit-config.yaml` et ce registre, aux deux sites |
| **H8** | mandat §6 et §7 : le lot 0b justifié par « un dépôt dont le `.env` porte les mots de passe » | **survente.** Un hook `pre-commit` ne voit que les fichiers **indexés**, `.env` est ignoré et non suivi, donc l'installer ne le fera **jamais** scanner. Le lot avait corrigé cette survente au README et à `SECURITY.md`, **pas au mandat** — le texte le plus copié du chantier | mandat §6 et §7 |
| **H9** | mandat §2.1 : « l'identité, dans chaque arbre de travail » | **faux.** `extensions.worktreeConfig` n'est pas activé, donc `git config user.email` écrit dans `.git/config`, **partagé** : `mesuré`, les quatre arbres de travail lisent le même fichier. Une fois suffit | mandat §2.1, dans le tableau des portées |

### La seconde réparation du lot 0b — les neuf points

La réparation du lot 0b a elle-même été auditée. Les trois bloquants qu'elle
avait fermés — contrôle d'identité inconditionnel, commits de fusion couverts,
corpus soustrait aux hooks — ont été prouvés fermés **deux fois
indépendamment** et ne sont pas rouverts ici. Restaient neuf points, presque tous
documentaires. Ce qui suit les consigne un par un.

#### F3 → le geste canonique du README cassait le jour de la fusion

Le README donnait, pour rescanner tout le dépôt versionné, `git ls-files -z |
xargs -0 … detect-secrets-hook`, précédé de « **Il ne doit rien rendre** ». Deux
sections plus bas, le même fichier annonce que le corpus porte deux faux positifs
`Hex High Entropy String`. **Les deux sections se contredisaient**, et c'est celle
qui promet le vert que le prochain développeur exécute.

`mesuré` le 31 août 2026 **sur le résultat d'une fusion d'essai `--no-ff` avec
`a005172`** (0 conflit) : `rc=123`, deux détections, aux deux emplacements
annoncés — `Datas/htms/MLOps with Databricks/3. MLflow for Traditional ML.html:94`
et `…/4. Model Serving： Architectures and Implementation.html:330`.

La cause est exactement le sujet du lot : `detect-secrets-hook` est appelé **en
direct**, pas par le framework, donc l'`exclude: '^Datas/'` de la racine — que
seul `pre-commit` applique — ne le filtre pas.

**Tranché : c'est la commande qui porte l'exclusion**, `git ls-files -z --
':!Datas/'`, et la phrase « il ne doit rien rendre » est **conservée** parce
qu'elle redevient vraie (`mesuré` sur le même arbre : aucune sortie, `rc=0`, 99
fichiers scannés). L'autre issue — garder la commande et écrire « elle rend deux
détections attendues » — a été écartée : un geste de contrôle dont le vert
attendu est « deux erreurs » ne se relit pas, et la troisième détection réelle
passerait inaperçue.

**Le défaut était invisible depuis la branche**, `Datas/` n'y étant pas versionné :
`git ls-files` ne le nomme pas, et la commande est verte pour une raison qui
disparaît à la fusion. C'est le cas d'école du mandat §7 — deux branches vertes,
un arbre rouge — et il ne se voit qu'en mesurant sur le résultat de la fusion.

**Deux pièges consignés au README au passage**, tous deux mesurés : `xargs`
traduit l'échec du programme qu'il appelle en **123** et jamais en 1, donc un
contrôle écrit `rc = 1` serait vert sur le défaut ; et le code de retour d'un
`cmd | tail` est celui de `tail`.

**Reste ouvert, et petit :** le `:!Datas/` du README et l'`exclude: '^Datas/'` de
`.pre-commit-config.yaml` disent la même chose à deux endroits. Le second est
gardé par `tests/unit/test_hooks_contre_le_corpus.py`, le premier ne l'est pas —
aucun test ne lit le README. C'est la même famille que F7 ci-dessous.

#### F4 et « rien à se rappeler » → le §2.1 du mandat, le texte le plus copié

Deux affirmations fausses vivaient dans la section que le pilote colle dans
**chaque** prompt.

**« Si `uv` manque sur le poste, le script s'exécute seul. »** `mesuré` le
31 août 2026, clone frais,
`env PATH=/usr/bin:/bin sh scripts/installer-les-garde-fous.sh` : **`rc=1`**, et
seules les **deux copies du contrôle d'identité** sont posées —
`.git/hooks/pre-commit` et `.git/hooks/pre-merge-commit`, tous deux le script
d'identité, **aucun** hook du framework, **aucun** `.legacy`. Le script est
honnête sur sa sortie d'erreur (« `uv: not found` », puis « le contrôle
d'identité est copié et actif ; les hooks du framework ne le sont pas ») : c'est
la phrase du mandat qui mentait, pas le code. Un montage à moitié armé est le
pire des trois états — il ressemble au bon.

**« Il n'y a rien d'autre à taper, rien à faire dans un ordre, rien à se
rappeler. »** Il y a **trois** choses, et elles sont désormais numérotées au
§2.1 : `git config user.email` (que la même section demande deux paragraphes plus
bas), relancer `make install` après toute édition de la liste blanche (F13), et
relancer `make install` si le `.venv` visé par le hook disparaît (F6).

C'est la troisième **phrase d'exhaustivité** de ce lot, après « c'est là la SEULE
faiblesse » (qui a caché R1) et « trois fichiers » (D7). Elles se ressemblent
toutes : elles closent une énumération que personne ne rouvre. La liste des trois
gestes est donc écrite **comme ouverte**, avec la consigne d'y ajouter la
quatrième plutôt que de la garder.

#### F6 → l'armement fige un chemin absolu, et rien ne le disait

`pre-commit install` écrit dans le hook généré une ligne
`INSTALL_PYTHON=<interpréteur de l'arbre d'où l'installation a été lancée>`, et
`.git/hooks` est **partagé par tout le clone**. Le dépôt réel pointe aujourd'hui
le `.venv` de l'arbre de travail **temporaire** du lot 0b (`mesuré`,
`grep INSTALL_PYTHON .git/hooks/pre-commit`). Or le mandat §7 prescrit de
supprimer la branche après fusion, donc son arbre.

`mesuré` le 31 août 2026, dans un clone armé par le script livré dont on fait
ensuite disparaître le chemin visé, `PATH` sans `pre-commit` (`which pre-commit`
→ `rc=1` sur ce poste) : le commit est **refusé**, `rc=1`, **HEAD inchangé**, sur
le seul message « `` `pre-commit` not found.  Did you forget to activate your
virtualenv? `` ». Il ne nomme ni le chemin disparu, ni `make install`. Et le
repli `elif command -v pre-commit` du hook généré ne rattrape rien ici, puisque
`pre-commit` n'est pas au PATH.

**C'est fail-closed, donc sans danger pour l'historique** : rien ne part avec une
mauvaise adresse, tout s'arrête. Le défaut était de ne pas être **écrit**. Il
l'est désormais au mandat §2.1 — dans le tableau des portées et dans la liste des
trois gestes — et au `README.md`, section des garde-fous.

**Proposé et NON retenu dans ce diff, à trancher par le pilote.** Rendre le hook
lui-même robuste demanderait d'éditer `.git/hooks/<type>`, un fichier **non
versionné** que `pre-commit install` réécrit : c'est exactement l'anti-patron que
§5.5 avait écarté. La piste qui tient debout est ailleurs, dans
`scripts/installer-les-garde-fous.sh`, qui calcule déjà `--git-common-dir` :
**comparer `git rev-parse --git-dir` et `--git-common-dir`**, et avertir — ou
refuser — quand l'installation est lancée depuis un arbre de travail secondaire,
puisqu'elle grave alors dans le clone entier un chemin qui mourra avec cet arbre.
C'est trois lignes, c'est la doctrine du lot (« un garde-fou qui repose sur la
mémoire du suivant n'est pas un garde-fou »), et le mandat de cette réparation
demandait de le **proposer**, pas de le faire. Il est proposé.

**Conséquence immédiate, pour le pilote :** à l'étape 5 du §7 — « supprimer la
branche, local **et** distant » — s'ajoute « puis relancer `make install` depuis
le clone principal ». Ce n'est pas écrit dans le §7 : ce lot n'y touche pas.

#### F13 → la liste blanche d'adresses a DEUX sites au runtime

Le `README.md` et le mandat §2.1 affirmaient « la liste blanche d'adresses n'a
qu'un site et ne peut pas diverger ». C'est vrai du **dépôt versionné**, et faux
du **montage armé** : `<type>.legacy` est une copie **figée à l'installation**,
là où le hook `repo: local` relit le script versionné à chaque commit.

`mesuré` le 31 août 2026, clone frais armé par le script livré, édition
**commitée** de `ADRESSES_AUTORISEES`, dans les deux sens :

| Édition | Mesure |
|---|---|
| **ajouter** `essai@exemple.test` | commit suivant portant cette adresse : `« Identite d'auteur autorisee ... Passed »` **puis** `pre-commit.legacy` refuse — `rc=1`, HEAD inchangé, et le message énumère l'**ancienne** liste |
| **retirer** `florian_horellou@laposte.net` | commit suivant portant cette adresse : la couche `repo: local` refuse — `rc=1`, HEAD inchangé |

**Fail-closed dans les deux sens** : friction, jamais exposition. C'est pourquoi
le montage n'est **pas** changé — la copie figée **est** la propriété qui rend le
contrôle inconditionnel, et la rendre dynamique la reprendrait. Seule
l'affirmation est corrigée, aux deux sites, avec le geste : **relancer
`make install` après toute édition de `ADRESSES_AUTORISEES`**.

Consigné au passage, parce que c'est ce qu'un lecteur verra : dans ce cas précis,
le message de refus **énumère l'ancienne liste**, donc il paraît contredire le
fichier qu'on vient d'éditer. C'est le seul cas où cela se produit.

#### F8 → l'installeur pouvait annoncer un montage qu'il n'avait pas fait

**C'est la forme exacte du défaut que ce lot traque, dans le garde-fou de ce
lot.** La boucle de **vérification** de `scripts/installer-les-garde-fous.sh`
itérait la **même** variable `TYPES` que la boucle d'**armement**. Une boucle sur
une liste vide vérifie zéro chose, et la vérification est vraie.

`mesuré` le 31 août 2026, sur le script tel qu'il était livré, avec `TYPES=""` :
`rc=0`, le message « `Garde-fous armes dans …/.git/hooks :` » suivi d'une liste
**vide**, et **zéro** fichier `.legacy` créé. Le framework, lui, restait
installé : sans `--hook-type`, `pre-commit install` retombe sur
`default_install_hook_types` de la configuration. Le montage avait donc
**exactement l'air du bon**, amputé de la seule couche indépendante de l'arbre de
travail — celle dont la perte a coûté au lot 0b sa fusion au premier tour (R1).

**Fermé par quatre lignes de shell** — un refus si `TYPES` est vide, avant tout
armement — **et gardé par un test**, `TestLeScriptConstateSonPropreResultat::
test_un_installeur_dont_la_liste_de_types_est_vide_est_refuse`, qui mute le
script **livré**. Avant ce test, la propriété n'était attrapée que **par effet de
bord** : la suite rougissait parce que les commits d'essai passaient, pas parce
que quoi que ce soit observait le montage.

Le test porte sa propre borne, en ligne : il asserte que la substitution a
**changé** le texte du script. Sans elle, une réécriture de la ligne `TYPES`
rendrait la mutation inopérante et le test resterait vert sans rien garder — la
leçon « un test qui choisit lui-même son cas doit prouver qu'il l'a atteint ».

##### La même forme, dans le hook d'identité — consignée, NON corrigée

`scripts/git-hooks/pre-commit` porte `for adresse in $email $committer`, non
protégé. Si les deux variables sont vides, la boucle ne tourne pas, et le hook
est vert. `mesuré` le 31 août 2026, clone armé par le script livré :

```bash
env GIT_AUTHOR_EMAIL= GIT_COMMITTER_EMAIL= EMAIL= git commit -m "essai adresse vide"
```

→ `rc=0`, **commit créé**, `auteur=<>` et `committer=<>`, les deux couches du
contrôle affichant « Passed ».

**Non corrigé, délibérément**, et c'est la décision du pilote : vider
`GIT_AUTHOR_EMAIL` est un geste volontaire, au même rang que `--no-verify`, que
le hook documente lui-même comme la sortie de secours. La réserve à garder, pour
que la ligne ne soit pas lue plus grave qu'elle n'est : une adresse **vide** n'est
pas une adresse **professionnelle**, donc ce chemin ne rejoue pas le sinistre
d'origine — il produit un commit que GitHub n'attribue à personne. C'est la
**forme** qui est la leçon, pas la conséquence.

**La leçon, écrite ici pour être relue :** en `sh`, `for x in $liste` sur une
liste vide est un no-op silencieux, et tout compteur d'erreurs initialisé à `0`
en sort inchangé. Chaque fois qu'une boucle **vérifie**, il faut se demander ce
qu'elle rend quand elle ne tourne pas — et le rendre impossible, pas le
documenter.

#### F11 / C6 → le garde du corpus n'avait aucun modèle de la clé `files`

`tests/unit/test_hooks_contre_le_corpus.py` ne lisait que `config.get("exclude")`.
Or `pre-commit` filtre la liste de fichiers par **deux** clés de racine : un
fichier est vu par les hooks si `re.search(files, chemin)` **et** non
`re.search(exclude, chemin)`. `files` vaut `''` par défaut, ce qui matche tout —
et c'est pour cela que son absence ne se remarquait pas.

**Deux mutations survivaient** (`mesuré` le 31 août 2026, suite entière **verte à
550** dans les deux cas) :

| Mutation | Ce qu'elle fait | Ce que les tests disaient |
|---|---|---|
| ajouter `files: '^Datas/'` à la **racine** | les **sept** hooks basés fichiers rendent « no files to check » et un `.py` volontairement sale se commite en `rc=0` (`mesuré` bout en bout, mutation **commitée**, dans un clone armé) | **550 verts** |
| `exclude: '^Datas/\|^scripts/'` | soustrait à **tous** les hooks `scripts/git-hooks/pre-commit` — le contrôle d'identité lui-même — et `scripts/installer-les-garde-fous.sh` | **550 verts** |

La première est la plus large : elle désarme la porte **entière** en laissant
l'`exclude` livré intact, donc en restant verte sur les trois tests du fichier.
La seconde passait parce que la liste témoin `CHEMINS_A_GARDER_SOUS_CONTROLE` ne
portait **aucun** chemin sous `scripts/`.

**Fermées par assertion, et chacune prouvée par mutation :**

- le témoin — renommé `test_le_reste_du_depot_reste_sous_controle`, son ancien nom
  `test_l_exclusion_n_emporte_rien_d_autre` ne décrivant plus ce qu'il fait —
  modélise désormais **les deux clés**, par un `_sous_controle(chemin)` qui
  reproduit le filtrage réel de `pre-commit` ;
- la liste témoin gagne `scripts/git-hooks/pre-commit` et
  `scripts/installer-les-garde-fous.sh`.

Mutation A rougit sur `files « ^Datas/ », exclude « ^Datas/ »` avec sept chemins
nommés ; mutation B sur les deux scripts, et eux seuls. La configuration remise,
les trois tests repassent au vert.

**Relevé au passage, et il compte :** sous la mutation A, `identite-auteur` est le
seul hook qui **tourne encore** — « Passed » — parce qu'il porte `always_run:
true`. Ce réglage, posé pour le commit sans fichier éligible (registre §5.5), se
révèle être aussi ce qui met le contrôle d'identité hors de portée d'un `files`
mal posé. Ce n'est pas une raison de relâcher le témoin : les sept autres hooks,
eux, tombent.

#### F5 → le harnais de test écrivait des hooks hors de son bac à sable

`tests/unit/test_installation_des_garde_fous.py` purge explicitement `GIT_DIR` et
`GIT_WORK_TREE` dans `_git()`, pour que les commits d'essai aillent bien au dépôt
jetable. Mais le **seul** sous-processus du fichier qui **écrit** des hooks —
celui qui exécute l'installeur — ne les purgeait pas.

`mesuré` le 31 août 2026, avec un `GIT_DIR` dans l'environnement de `pytest` :
l'installeur résout `--git-common-dir` sur le dépôt **désigné**, et **quatre**
fichiers y partent — `pre-commit`, `pre-commit.legacy`, `pre-merge-commit`,
`pre-merge-commit.legacy`. Les tests **rougissent** (6 échecs sur 9) : ce n'était
donc pas un faux vert, et c'est la seule raison pour laquelle ce défaut n'a rien
cassé. Mais le harnais écrivait dans **la ressource même que ce lot protège**, et
il l'aurait trouvée déjà armée.

**Fermé par deux `pop`**, les mêmes que `_git()` — et **gardé** par
`TestLeHarnaisResteDansSonBacASable::
test_git_dir_dans_l_environnement_ne_deporte_pas_les_hooks`, qui **désigne** un
dépôt par `GIT_DIR`, lance le harnais, et exige que ce dépôt ressorte intact. Il
porte son témoin — le harnais doit avoir armé **son** bac à sable — sans quoi il
serait vert d'un harnais qui n'installe rien nulle part.

Contrôle d'après-correction, `mesuré` : la même suite, relancée sous `GIT_DIR`,
passe **11/11** et le dépôt désigné ne reçoit **aucun** hook. Avant, elle rendait
6 échecs et 4 fichiers.

**La leçon, et elle est déjà au mandat sous une autre forme :** un harnais de test
peut effacer ce qu'il doit observer — celui-ci pouvait *armer* ce qu'il doit
observer. Quand un fichier de test purge une variable d'environnement à un
endroit, la question n'est pas « pourquoi ici », c'est « **où encore** ».

#### F1 et F2 → deux chiffres faux dans le commit qui corrigeait les chiffres

**F1 — « le plus gros fichier du corpus pèse aujourd'hui moins de 1 Mo ».** C'est
la phrase sur laquelle le `README.md` concluait que les bornes de GitHub ne se
posent pas. Elle est **fausse d'un facteur 6**. `mesuré` le 31 août 2026 **sur le
résultat de la fusion d'essai `--no-ff` avec `a005172`** :

```bash
git ls-files -z -- Datas | xargs -0 stat -c '%s %n'
```

*(Pas de `-I{}` : `xargs -I` change le découpage et n'insère rien si le motif
n'est pas répété en argument — cette commande, écrite d'abord avec `-I{}` sans
`"{}"` derrière, rendait « `stat: missing operand` » vingt-cinq fois. Le `-0`
seul suffit, et il est ce qui compte : les noms du corpus portent des espaces et
un deux-points pleine chasse.)*

| Mesure | Valeur |
|---|---|
| plus gros fichier | **6 362 475 o** — `Datas/htms/Practical MLflow for Generative AI on Databricks/8. Deploying a GenAI Application with MLflow.html` |
| plus petit fichier | **671 707 o** — `…/Practical MLflow…/Preface.html` |
| au-dessus de 1 Mo | **19 sur 25** |
| total | 57 381 999 o, soit les 55 Mo de `du -sh Datas` |

**La conclusion survit, la marge non.** Elle est de **8×** face à l'avertissement
à 50 Mo, pas de 50×. Corrigé aux **deux** sites : `README.md` et ce registre.

**F2 — « 4 files would be reformatted, 56 files already formatted ».** Le chiffre
est **58**, remesuré sur cette révision. Et son défaut n'est pas d'être faux :
**56 est une valeur juste, mesurée sur le mauvais arbre.** `mesuré` par
`git archive 6f554e8 | tar -x` puis `ruff format --check src/ tests/` :
« 4 files would be reformatted, **56** files already formatted » à `6f554e8` —
c'est-à-dire **avant** que la réparation n'ajoute ses deux fichiers de tests.
Le commit qui modifie l'arbre citait donc une mesure prise sur l'arbre d'avant.
Corrigé aux **trois** sites : `README.md`, mandat §2.4, ce registre §5.4.

**C'est cette forme-là qu'il faut retenir**, pas les deux chiffres : *un nombre
mesuré, exact, et périmé par le commit qui le porte*. Un `mesuré` n'est pas une
étiquette de véracité, c'est une étiquette de **provenance** — et une provenance
comprend l'arbre, pas seulement la commande et la date.

##### Le balayage de provenance qu'ils ont rendu nécessaire

Tous les chiffres du diff `6f554e8..566eb35` ont été repassés. Deux autres
portaient le même défaut, plus petits, et ils sont corrigés dans le même commit :

| Chiffre | Écrit | Mesuré | Ce qui n'allait pas |
|---|---|---|---|
| dénominateur du coût de reformatage | « 16 lignes sur **1 213** » | **1 221** | `wc -l` pris sur l'arbre **d'après** `ruff format`. Un diff ne se rapporte pas au tas qu'il a produit : 1 221 − 8 = 1 213, et l'écart **est** le diff lui-même |
| nombre d'endroits reformatés | « **quatre**, tous des replis de ligne » | **cinq**, dont quatre replis | le cinquième est un doublon de ligne vide dans `_extract_pdf`, sans addition en face. `git diff -U0 \| grep -c '^@@'` → 5 |

Les six autres ont été **reconfirmés justes**, avec leur commande :
`3 files would be reformatted, 33 files already formatted` (`src/` seul) ;
**111** commits de `main` dont **aucun** ne déclare `identite-auteur` (boucle
`git show <c>:.pre-commit-config.yaml`) ; **3** pragmas porteurs
(`grep -rn 'pragma: allowlist secret' --include='*.py'`) ; **25** fichiers et
**55 Mo** de corpus (`git ls-files -- Datas`, `du -sh Datas`) ; **16 lignes** de
diff, 4 ajoutées et 12 supprimées (`git diff --numstat`) ; et le compte de tests
du `README.md`, remesuré à chaque commit de cette réparation.

**Un piège de mesure trouvé au passage, et consigné parce qu'il se reproduira :**
`ruff format` sur un arbre extrait **sans** le `pyproject.toml` du dépôt retombe
sur ses 88 colonnes par défaut au lieu des 100 déclarées, et rend alors
« 2 files reformatted » et **66** lignes de diff au lieu de 3 et 16. Un
reformatage se mesure **avec la configuration du dépôt**, jamais sur les fichiers
seuls.

#### Le « `make` n'est pas installé » du §2.4 — supprimé par `9f5a78c`, et pourquoi

Le mandat portait, en §2.4 : « **`make` n'est pas installé sur le poste de
développement, et il n'y a pas les droits pour l'y mettre** (`mesuré`, 31 août
2026). Chaque conversation le redécouvre ; ce n'est pas un incident, c'est
l'environnement. » C'est **faux sur ce poste** : GNU Make 4.4.1, `/usr/bin/make`,
et `make install` rend 0 dans un clone frais (`mesuré`, 31 août 2026,
indépendamment par le pilote et par l'auditeur). Le deuxième commit du lot 0b,
`9f5a78c`, l'a remplacé par « la présence de `make` est un fait de POSTE :
mesure-la, ne la lis pas ici », avec les deux mesures contradictoires citées côte
à côte. **C'était le bon geste**, et la suppression survit à la fusion sans
conflit — `main` n'a pas retouché ce paragraphe depuis.

**Deux réserves du mandat de cette réparation sont ici renversées, et il faut le
dire :**

- « **sans le déclarer** » — non. `9f5a78c` le déclare dans son message de
  commit, en propres termes : « Corrige aussi le mandat §2.4 sur un point qui
  n'est pas le mien mais qui vivait dans le même paragraphe : "make n'est pas
  installé" y était écrit comme un fait du chantier alors que c'est un fait de
  POSTE. » Et le paragraphe de remplacement le déclare **au site**. Ce qui
  manquait n'était pas la déclaration : c'était **la trace au registre**, qui ne
  porte cette correction dans aucune de ses tables — ni dans « Les affirmations
  que le lot 0b avait rendues fausses » (D2 à H9), ni ailleurs. Elle y est
  désormais ;
- « **le §2.4 fusionné n'aura plus de repli pour un poste sans `make`** » — non
  plus. `9f5a78c` a conservé le repli, et l'a même corrigé du défaut qui aurait
  compté : la recette de `main` commençait par `uv run ruff format src/`, qui
  **écrit** dans l'arbre — c'est précisément ce que ce lot interdit à la cible
  `all` — et la recette de la branche est passée à `ruff format --check src/`,
  en dernière position.

**Mais le repli était faux pour une autre raison, et celle-là est réelle.** Il
prétend remplacer `make install && make all` ; il ne portait que `uv sync`,
c'est-à-dire la **première** ligne de la cible `install`, pas la **seconde** —
`sh scripts/installer-les-garde-fous.sh`, celle que ce lot ajoute et sur laquelle
tout le reste repose. Un poste sans `make` suivant cette recette se retrouvait
donc **sans aucun garde-fou** : ni contrôle d'identité, ni `detect-secrets`.
C'est le défaut du lot 0b tout entier, revenu par la porte de sa propre recette
de repli.

`mesuré` le 31 août 2026, clone frais : après le repli tel qu'il était écrit,
`.git/hooks` ne porte **aucun** hook ; après le repli corrigé, les **quatre**
attendus, et la suite rend `lint=0`, `typecheck=0`, `test=0`, `format-check=1`
— le rouge d'alors. Le repli du §2.4 porte désormais la ligne manquante.
*(`format-check` rend **0** depuis la réparation du lot 3 — §5.4. La mesure
ci-dessus est conservée telle quelle : elle décrit le clone frais du 31 août
2026.)*

#### Trouvé par la SECONDE réparation, et NON traité — consigné, pas corrigé

Décision du pilote, pour arrêter la spirale : ce qui suit est **consigné et non
corrigé**. Le périmètre de cette réparation était les neuf points ci-dessus.

##### F7 — la seule ligne dont dépend tout le reste n'est gardée par aucun test

`Makefile`, cible `install`, seconde ligne :
`sh scripts/installer-les-garde-fous.sh`. **Tout ce que ce lot installe dépend
d'elle, et rien ne la garde.** `mesuré` le 31 août 2026 : la retirer laisse
**552 tests verts** ; et `grep -rn Makefile tests/` ne rend **rien** — aucun test
de ce dépôt ne lit le `Makefile`.

C'est la forme la plus pure du défaut que le lot traque : la porte est prouvée,
le garde est prouvé, et **l'interrupteur qui les allume ne l'est pas**. Les onze
tests de `test_installation_des_garde_fous.py` exécutent le script **directement**,
jamais par la cible qui le lance en vrai.

**Pourquoi ce n'est pas fermé ici.** Le garde honnête serait un test qui lance
`make install` dans un dépôt jetable et constate les quatre hooks. Il coûte un
`uv sync` complet par exécution — plusieurs minutes, et le réseau — dans une
suite qui tourne en 9 secondes et ne sort jamais du disque. La variante bon
marché — lire le `Makefile` et asserter que la cible `install` contient la chaîne
`installer-les-garde-fous.sh` — est un test sur du **texte**, pas sur un
comportement : il resterait vert si le script était renommé, déplacé, ou rendu
non exécutable. Aucune des deux ne vaut d'être livrée sans que le pilote
tranche ce qu'il accepte de payer. **À trancher.**

##### Douze mutations survivantes sur l'installeur et la configuration

Le mandat de cette réparation demandait de consigner « **I5, I8, C8, C9, C10** —
cinq mutations survivantes relevées par l'auditeur ». **Ces références n'ont pas
pu être retrouvées** : le rapport d'audit ne vit ni dans le dépôt, ni dans aucun
arbre de travail (`mesuré`). Recopier cinq étiquettes dont j'ignore le contenu
aurait produit un registre qui cite des preuves qu'il n'a pas. **Le balayage a
donc été refait de zéro**, et il en rend douze, chacune `mesuré`e — suite entière
verte, **552** — sur le code **livré**, mutation appliquée puis révoquée :

| Réf | Mutation | Ce qu'elle emporte |
|---|---|---|
| **C-a** | retirer `always_run: true` du hook `identite-auteur` | le contrôle d'identité redevient **sauté** sur un commit sans fichier éligible. C'est le sinistre d'origine à un réglage près — et le §5.5 en donne une table « prouvé par mutation » qui est une **mesure à la main**, pas un garde |
| **C-b** | retirer `stages: [pre-commit, pre-merge-commit]` | la couche framework cesse de couvrir les commits de fusion |
| **C-c** | retirer `pass_filenames: false` | le script reçoit une liste de fichiers qu'il ne lit pas — inerte aujourd'hui, piège demain |
| **C-d** | `ruff-format` sans `--check` | **le hook se remet à RÉÉCRIRE l'arbre indexé.** C'est le défaut que le lot ferme dans `make all`, revenu par la porte du hook — et rien ne le voit |
| **C-e** | retirer `default_install_hook_types` | un `pre-commit install` tapé à la main n'installe plus que `pre-commit` |
| **C-f** | retirer **entièrement** le dépôt `detect-secrets` | le garde-fou dont l'absence justifiait le lot entier disparaît |
| **C-g** | `check-added-large-files` sans `--maxkb=500` | le seuil retombe au défaut de l'outil |
| **I-a** | affaiblir `grep -q 'generated by pre-commit'` en `grep -q ''` | la moitié « le framework est bien là » de la vérification devient décorative |
| **I-b** | `erreurs=1` → `erreurs=0` dans cette même branche | idem, par l'autre bout |
| **I-c** | `--git-common-dir` → `--git-dir` | l'installation depuis un **arbre de travail secondaire** arme `.git/worktrees/<nom>/hooks`, que git n'exécute pas. **Le harnais ne peut pas l'atteindre** : il monte un dépôt simple, où les deux valeurs sont identiques |
| **I-d** | retirer le `chmod +x` | la copie manuelle n'est plus exécutable ; `pre-commit install` ne la déplace donc plus en `.legacy` |
| **I-e** | retirer la garde « `$identite` introuvable » | le message de cause probable disparaît (`set -eu` arrête quand même) |

**Trois d'entre elles méritent d'être lues comme des constats, pas comme des
trous de couverture :** C-a et C-d rouvrent chacune un défaut que ce lot a fermé
ailleurs, et I-c est un cas que le harnais actuel **ne peut pas** atteindre —
fermer celui-là demande un dépôt d'essai avec un `git worktree`, ce qui est un
harnais différent, pas une assertion de plus.

##### Six affirmations imprécises — références non retrouvées

Le mandat listait « **F15, F16, F17, F18, F19, F20** — six affirmations
imprécises ou périmées ». Comme ci-dessus, **leur contenu n'a pas pu être
retrouvé**. Ce qui a été trouvé par relecture est corrigé plus haut (F1, F2, plus
les deux du balayage de provenance) ou consigné ici. **Si le pilote détient ces
six références, elles restent à verser.**

##### Les gestes que rien ne couvre — et un qui l'est, contre l'attente

`git revert`, `git cherry-pick` et `git rebase` créent des commits qu'aucun hook
ne voit. Rien de neuf : c'est écrit sous R1 et D1, avec le motif du rejet de
`prepare-commit-msg` (il y voit l'identité **locale**, il serait donc vert sur le
défaut ; et son refus laisse l'arbre sale).

**Ce qui est neuf, et mesuré le 31 août 2026 :** une **fusion AVEC conflit** est
**couverte**, et pas par le hook qu'on croit. `pre-merge-commit` ne tourne que
lorsque la fusion s'auto-commite ; une fusion conflictuelle s'achève par un
`git commit`, donc par le hook **`pre-commit`**. Mesuré dans un clone armé, sur
un vrai conflit de contenu résolu à la main, avec `@aosis.net` en auteur et en
committer : `rc=1`, **HEAD inchangé**, les **deux** couches refusant —
`pre-commit.legacy` d'abord, puis `identite-auteur` du framework (« Failed »).

À noter au passage, parce que cela vaudra pour d'autres hooks : `pre-commit`
affiche alors « `[INFO] Checking merge-conflict files only.` » et restreint sa
liste de fichiers. Le contrôle d'identité y survit **grâce à `always_run: true`**
— voir C-a ci-dessus.

Les tables de couverture du `README.md` et du mandat §2.1 ne sont pas **fausses**
(« `git merge --no-ff` → oui ») mais elles nomment un seul mécanisme là où il y
en a deux. Non corrigé : hors périmètre.

##### `pre-push` — le constat est rouvert, et il n'est pas tranché

L'auditeur rouvre l'argument contre le §5.5, et **le pilote le trouve fort sans
le trancher dans ce lot** : « ce qui est irréversible n'est pas le commit local,
c'est le **push** ». Le §5.5 avait écarté `pre-push` au motif qu'il est « trop
tard, le commit porte déjà la mauvaise adresse » — c'est vrai, mais réécrire un
historique **non poussé** est gratuit, là où la liste des contributeurs GitHub,
une fois constituée, ne se défait pas. C'est exactement le sinistre d'origine.

**La réserve de l'auditeur, à ne pas perdre :** `pre-push` **ne couvrirait pas**
les commits locaux d'un `git bisect`, ni ceux qu'on ne pousse jamais. Ce serait
donc un filet **en plus** des deux couches, pas à leur place.

**Constat ouvert.** Il ferme d'un geste les trois lignes « non » des tables de
couverture — `revert`, `cherry-pick`, `rebase` — ce qu'aucune autre piste ne
fait.

##### `_run_legacy` et la montée de git — à surveiller

Toute la réparation R1 tient sur la couche `<type>.legacy`, c'est-à-dire sur
`_run_legacy` de `pre-commit`. Ce code porte, dans la version installée
(`pre-commit` 4.6.2,
`.venv/…/pre_commit/commands/hook_impl.py:36`) :

```python
    if hook_dir is None:  # git 2.54+ hooks
        return 0, stdin
```

Autrement dit : **quand `hook_dir` est absent, la couche `.legacy` n'est pas
exécutée du tout**, et `_run_legacy` rend 0. Le hook généré aujourd'hui passe
toujours `--hook-dir "$HERE"`, et le poste est en **git 2.53.0** (`mesuré`), donc
la branche est morte ici. Elle ne le restera pas : son commentaire annonce
explicitement le mécanisme de hooks de git 2.54+.

**Ce qu'il faut faire, et quand.** À la première montée de git ou de
`pre-commit`, remesurer que le commit `@aosis.net` est toujours refusé **dans un
arbre dont `.pre-commit-config.yaml` ne déclare pas le contrôle** — c'est
exactement ce que `tests/unit/test_installation_des_garde_fous.py` fait, donc la
suite le dira. C'est le seul endroit du dépôt où une montée de version d'outil
peut désarmer R1 en silence.

##### `test_wipe_stores.py` — le quatrième fichier, dans son angle mort

Rappel, sans changement : `tests/unit/test_wipe_stores.py` n'est pas
format-propre, `make format-check` est borné à `src/` et ne le voit pas,
`make format` ne le répare pas, et le hook `ruff-format --check` **bloque** tout
commit qui le touche. Le geste reste
`uv run ruff format tests/unit/test_wipe_stores.py`, dans le commit qui touche ce
fichier et nulle part ailleurs. Détail complet au §5.4.

### Trouvé par la réparation du lot 0b, et NON traité

- **`git revert`, `git cherry-pick`, `git rebase` créent des commits qu'aucun
  hook ne voit** (`mesuré`, mouchards posés sur chaque hook de `.git/hooks`). Le
  seul point d'accroche commun, `prepare-commit-msg`, est écarté sur mesure : il
  y voit l'identité **locale** et non celle du commit produit — il serait vert
  sur le défaut — et son refus laisse l'arbre sale. **La fermeture honnête est un
  hook `pre-push`, et elle est à trancher par le pilote.** Le §5.5 avait écarté
  `pre-push` au motif qu'il est « trop tard, le commit porte déjà la mauvaise
  adresse ». C'est vrai, mais ce qui est irréversible n'est pas le commit local,
  c'est le **push** : la liste des contributeurs GitHub, une fois constituée, ne
  se défait pas, tandis que réécrire un historique non poussé est gratuit.
  L'argument mérite d'être rouvert. Il ne l'a pas été dans le diff : hors
  périmètre.
- **Quatre fichiers de documentation portent des blancs de fin** —
  `documentation/base_vectorielle.md` (3 lignes),
  `documentation/graphe_connaissances.md` (9), `documentation/orchestration.md`
  (1), `documentation/stockage_objets.md` (1), soit **14 lignes** (`mesuré` sur le
  résultat de la fusion d'essai). Ce n'est **pas** un défaut : le hook
  `trailing-whitespace` les corrigera au premier commit qui les touche, ce qui est
  exactement son travail — contrairement au corpus, un document *doit* être
  normalisé. C'est consigné pour qu'un développeur qui voit ces quatre fichiers
  modifiés dans son `git status` sache d'où ils viennent et ne les révoque pas.
- **`make format-check` est borné à `src/` alors que le hook `ruff-format` voit
  tout ce qui est indexé.** Les deux portées divergent, et c'est la cause de
  l'angle mort D7. Étendre `format-check` à `tests/` rendrait `make all` rouge
  d'un quatrième fichier et **fermerait cet angle mort d'un geste** — mais cela
  demande de reformater `test_wipe_stores.py`, ce que le mandat de la réparation
  interdit explicitement. À trancher avec §5.4.
  **→ RETENU et fait par la réparation du lot 3** : le fichier est reformaté,
  `make format` et `make format-check` portent sur `src/ tests/`, et `make all`
  rend 0. La piste était juste, et c'est le reformatage qui la débloquait.

### 3.6 → traité par `eaa8a8e` — la porte qualité est reproductible

`[dependency-groups] dev` déclaré dans `pyproject.toml`, épinglé comme les
dépendances de production, `ruff` à la version du hook `.pre-commit-config.yaml`.
`requirements-dev.txt` supprimé : il n'était référencé que par une ligne du
README, aucune image ne l'installait, et quatre des douze outils qu'il déclarait
n'avaient aucun utilisateur (`httpx`, `pytest-mock`, `pytest-asyncio` — aucun
test ne les importe — et `pydantic-settings`, déjà dépendance de production).
Le `Makefile` appelle chaque outil derrière `uv run` et gagne une cible
`install` : la séquence tient en `make install && make all`, sans activation
d'environnement.

Restait ouvert et détaché de ce constat : §5.4 et §5.5, tous deux traités par
le lot 0b — sauf les fichiers non format-propres eux-mêmes, qui restent au §5.4
ouvert. Ils sont **quatre**, dont trois pour le lot 2 : voir §5.4, c'est son site
canonique.

### « mypy rouge dès le premier commit » → traité par `98bb20d`

Corrigé **à la source**, sans `type: ignore` ni assouplissement : `main.py` et
`index_report.py` lisent `get_embedding_model` dans `embedding.py`, son module
source, et non par réexport implicite depuis `vectors.py`. La correction est
repliée dans le commit qui introduisait l'erreur — sans quoi la branche aurait
gardé cinq commits rouges. Mutation vérifiée : remettre l'import depuis
`vectors` rend `mypy --strict` rouge.

### 3.1 → traité par `a3ad1f4` — `POST /reindex` une fois par rafale

L'appel quitte `factory._record_metadata`. Il vit dans `src/pipeline/reindex_job.py` :
un asset `agent/lexical_index`, son job `agent_reindex_job`, et un sensor qui
l'arme quand **aucun run d'ingestion n'est en vol** (statuts non terminaux,
`QUEUED` compris) **et** qu'au moins un a réussi depuis la dernière
réindexation, repérée par un curseur. Le nombre d'appels ne suit plus le nombre
de documents : un appel par rafale au lieu d'un appel par partition.

Options écartées, argumentées dans le docstring du module : un asset aval se
matérialiserait dans le run de la partition et ne ferait que déplacer le défaut ;
un `run_status_sensor` sur SUCCESS se déclenche lui aussi une fois par run et
demanderait la même garde pour un harnais de test plus lourd ; un asset check
vérifie, il n'agit pas.

Limite consignée plutôt que découverte : un corpus déposé en goutte-à-goutte
est une suite de rafales, donc une suite de réindexations. C'est le
comportement voulu, ce n'est pas « une seule fois » dans l'absolu.

Le garde qui manquait : les tests assertent un **nombre**, depuis le côté qui
le produit, pour 1, 3 et 12 documents — un test « l'appel a lieu » était vert
des deux côtés du défaut. Treize mutations du code livré ont été vérifiées
rouges. Détail dans `tests/unit/test_reindex_job.py`.

### « 407 tests verts » → traité par `390ce8a`

Le dépôt ne portait **aucun** compte de tests : le 407 vivait hors du dépôt. Il
en a désormais un seul, dans `README.md` section Tests, avec sa commande, sa
date et son étiquette `mesuré` — **508** —, et la consigne d'y renvoyer plutôt
que de le recopier.
