# Deuxième campagne de référence — 25 septembre 2026

> **Archive datée, non réécrite.** Compte rendu de mesure du 25 septembre 2026. L'état en service est décrit par [`livraison.md`](../livraison.md).

Ce fichier est le **compte rendu mesuré** de la deuxième campagne de référence du
pipeline d'ingestion : purge des trois stores et du HTML nettoyé, réingestion
complète du corpus par le code de `main` **sans aucun changement du code
d'extraction**, puis mesure.

Sa compagne est la
[première campagne](2026-09-02-premiere-campagne-de-reference.md), dont il
reprend la forme, les instruments et les réserves. **Les réserves de la première
valent ici sans être réécrites** : trente questions ne suffisent pas à arbitrer
un réglage, et le rappel mesuré est un plancher dense, non le rappel du système.

**Ce que cette campagne est, et ce qu'elle n'est pas.** Le code d'extraction n'a
pas changé depuis l'instantané du 24 septembre 2026 — décision (a) du pilote, on
ne touche pas aux puces vides (registre §4.37.h). C'est donc un **test de
reproductibilité** : purger puis réécrire par le même code doit rendre le même
index. Ce n'est **pas** une mesure de qualité, ni un arbitrage.

Toute valeur porte son étiquette `mesuré`, `calculé` ou `NON VÉRIFIÉ`, sa
commande et son heure. Les heures sont UTC, le 25 septembre 2026.

**Le poste** (`mesuré`, `docker compose ps`, 03:31 UTC) : pile Compose
`rag-ingestion-pipeline`, **dix** services debout, montés depuis le clone
principal. C'est un service de plus que la première campagne, et **c'est le fait
de poste qui change tout au §5** : le démon Dagster tourne.

---

## 0. Le verdict, en trois lignes

- **La purge est faite**, `rc=0`, et ses quatre volets sont mesurés avant et
  après (§2).
- **La réingestion est complète** : **23 partitions sur 23**, **23 runs
  `SUCCESS`**, **zéro échec**, **zéro reprise**, créés par le **capteur** et non
  à la main (§3).
- **`DÉPLACÉS = 0`.** `comparer` contre l'instantané versionné rend
  `DOCUMENTS COMPARES 23 / 23`, `DEPLACES 0`, **`rc=0`** (§4.2).

**Et les huit comptes, l'empreinte des clés MinIO, `verify_contract`,
`index_report`, les 44 ancrages et les quatre valeurs de rappel sont identiques
à l'octet ou au dixième de point près, avant et après.** La reproductibilité
attendue est constatée sur **tous** les témoins relevés.

---

## 1. Étape 0 — l'état d'avant, et les conditions d'arrêt une par une

Le mandat pose des conditions d'arrêt : si une seule n'est pas remplie, on
s'arrête **avant** la purge. Voici les onze, chacune avec sa mesure.

| # | Condition | Mesuré le 25 septembre 2026 | Verdict |
|---|---|---|---|
| 1 | branche de campagne depuis `main`, `main` = `d22a153` ou descendant | branche `claude/campagne-2-purge-reingestion-08b58a`, partie de `d22a153` ; `main` = `origin/main` = **`d22a153`** | **remplie** |
| 2 | clone principal propre et sur `main` | `git status --porcelain` rend **`?? .claude/`** et rien d'autre ; branche `main` | **remplie** |
| 3 | les conteneurs servent le `src` de `main` | `docker inspect` : `docling-service`, `dagster-daemon` et `dagster-webserver` montent tous `/home/ubuntu/RAG/rag-ingestion-pipeline/src`, c'est-à-dire le clone principal, qui est sur `main` | **remplie** |
| 4 | dix services debout | `graphd`, `metad`, `storaged`, `chromadb`, `minio`, `nebula-studio`, `postgres-dagster`, `dagster-webserver`, `dagster-daemon`, `docling-service` (`healthy`) — **10** | **remplie** |
| 5 | démon Dagster debout, quatre capteurs armés | `dagster-daemon` `Up 16 hours` ; les **quatre** capteurs à `DECLARED_IN_CODE`, **et le fait qui le prouve est le tick** : chacun est évalué toutes les 30 s (relevé à 03:32, trois ticks consécutifs par capteur) | **remplie** |
| 6 | aucun run en cours | `RunsFilter(statuses=non terminaux)` rend **0** | **remplie** |
| 7 | nombre de runs | **958**, dont 72 `SUCCESS` et 886 `FAILURE` — la valeur du dernier relevé, au run près | **remplie** |
| 8 | les huit comptes | tous égaux aux valeurs attendues — table ci-dessous | **remplie** |
| 9 | empreinte des clés MinIO | **`c91f5be6…0994`** | **remplie** |
| 10 | empreinte de l'instantané | `sha256sum MANIFESTE.tsv` rend **`e945893b…0f6d`** | **remplie** |
| 11 | attestation d'avant par `comparer` | `rc=0`, **23 / 23**, `DEPLACES 0` (§1.3) | **remplie** |

**Les onze sont remplies. La purge a donc eu lieu.**

### 1.1 Les huit comptes d'avant, et la commande qui les rend

`mesuré` à 03:34 UTC, dans l'image d'extraction, `src` de `main` monté en
lecture seule (geste du registre §4.27) :

```bash
docker run --rm --network rag_network \
  -v "$MAIN/src":/app/src:ro -v "$SP/sondes":/sondes:ro -v "$SP/sortie":/sortie \
  --env-file "$MAIN/.env" -e HOME=/tmp -e PYTHONPATH=/app -w /app \
  rag-ingestion-pipeline-docling-service python /sondes/huit_comptes.py
```

**Le compte de sommets est fait par `MATCH … RETURN count(n)`, tag par tag, et
jamais par `SHOW STATS`**, qui rend 0 sur un space peuplé (§4.27 n° 1).

| Compte | Attendu par le mandat | Mesuré avant | Verdict |
|---|---|---|---|
| sommets, tous tags confondus, **`Document` compris** | 15 196 | **15 196** | égal |
| sommets `Document` | 23 | **23** | égal |
| sommets `Paragraph` | 7 251 | **7 251** | égal |
| sommets `ListItem` | 1 748 | **1 748** | égal |
| sommets `Code` | 4 963 | **4 963** | égal |
| arêtes `PARENT_OF` | 15 173 | **15 173** | égal |
| chunks ChromaDB | 4 367 | **4 367** | égal |
| objets MinIO | 212 | **212** | égal |

**Les deux chiffres de sommets se citent avec leur définition, et le mandat le
prescrit** : **15 196** sommets `Document` compris, **15 173** sans — et 15 173
est aussi le nombre d'arêtes `PARENT_OF`, ce qui n'est pas un hasard (chaque
sommet non racine a exactement un parent).

Les quatre tags que le mandat ne demande pas, relevés parce qu'ils entrent dans
la somme (`mesuré`) : `Caption` **201**, `Picture` **209**, `SectionHeader`
**746**, `Table` **55** ; `Footnote`, `Formula`, `PageFooter`, `PageHeader` :
**0** chacun. Arêtes `LINKED_TO` : **201**.

### 1.2 L'empreinte des clés MinIO — et sa recette, qui n'était écrite nulle part

`mesuré` : **212** objets, et l'empreinte du mandat est **reproduite** :

```
c91f5be6e24fbcba5f4a744119bf8da65fed44b7ecac79cce0ae1b027ed0b994
```

**La recette n'était écrite nulle part dans le dépôt**, et elle a donc été
**identifiée par mesure**, en calculant les quatre variantes plausibles sur la
même liste. **La mesure porte sur le COMMIT, non sur l'arbre d'aujourd'hui, et
c'est délibéré** : ce paragraphe-ci a périmé sa propre sonde en écrivant
l'empreinte. `mesuré` : `git grep 'c91f5be6' d22a153` rend **le vide**, `rc=1`
du processus — aucun fichier de `main` ne la porte ; le même motif cherché sur
cet arbre rend **deux** fichiers, ce compte rendu et le registre, tous deux
écrits par la campagne. Une seule variante concorde, et c'est celle-ci :

> SHA-256 de la liste des clés d'objet **triée**, **jointes par `\n`**, **avec
> un `\n` final**.

Les trois autres, données pour que personne ne recommence le tri
(`calculé`, même liste) : sans `\n` final `d1e98913…`, concaténation nue
`56b2cf3c…`, séparateur `\0` `e2fb462f…`. **Écrire la recette à côté de
l'empreinte est le sujet** : une empreinte sans sa recette n'est pas
reproductible, et c'est un constat que cette campagne laisse au registre
(§4.42.b).

Répartition des 212 clés (`mesuré`, sur la liste) : **199** sous
`images/html/…` — les images des chapitres HTML — et **13** sous
`images/Hands-On_RAG_for_Production_ER_-_Ofer_Mendelevitch/…` — les crops du
PDF. La somme se ferme.

### 1.3 L'attestation d'avant — `comparer` contre les vrais stores

C'est la condition la plus coûteuse, et la plus importante : elle établit que
l'instrument rend `rc=0` **sur l'index d'avant**, donc qu'un rouge après la
réingestion serait imputable à la réingestion et non à l'instrument.

`mesuré` de **03:37:37 à 03:39:00** UTC (83 s), `rc=0` du **processus**, lu sans
aucun tube :

```bash
docker run --rm --network rag_network \
  -v "$W/src":/app/src:ro -v "$W/scripts":/app/scripts:ro \
  -v "$W/documentation/campagnes":/app/documentation/campagnes:ro \
  -v "$MAIN/Datas":/corpus:ro \
  -v "$SP/sp-comparer":/sp \
  -v "$MAIN/Datas/.cleaned":/sp/cleaned:ro \
  -v /var/lib/docker/volumes/rag-ingestion-pipeline_docling_models/_data:/tmp/.cache:ro \
  --env-file "$MAIN/.env" -e COMMIT_MESURE="$(git rev-parse HEAD)" \
  -e HOME=/tmp -e PYTHONPATH=/app -w /app \
  rag-ingestion-pipeline-docling-service \
  python scripts/campagne/verifier-l-equivalence-des-identifiants.py \
    comparer documentation/campagnes/2026-09-24-instantane-des-identifiants
```

Les copies nettoyées **de production** — `Datas/.cleaned/`, **22** fichiers —
sont montées **en lecture seule** sous `/sp/cleaned`, qui est l'emplacement que
`reextraire` attend. Ce sont elles que le pipeline convertit pour un HTML, et
non la source. Le montage est `:ro` : le harnais ne peut pas les altérer, et
l'attestation ne peut donc pas se fabriquer son propre sujet.

Sortie (extrait, les trois dernières lignes) :

```
INSTANTANE e945893b1021e2f1aa3809434a889443ed9fb85e2a7e290cd329f077687f0f6d
DOCUMENTS COMPARES 23 / 23 de l'instantane
DEPLACES 0, DECLARES 0
ATTRIBUTION (exacte, par appariement) : {}
OK : l'ensemble deplace est exactement l'ensemble declare.
```

### 1.4 Le corpus d'avant

`mesuré` :

| | |
|---|---|
| fichiers du corpus, **`Datas/.cleaned/` EXCLU** | **25** — 24 HTML, 1 PDF |
| empreinte de la liste | **`b66441820e9b8d3114d5dafa0d5c6d461c427b3e770fb2c0e584e947df5f508e`** |
| fichiers versionnés sous `Datas` | 25 |
| `mtime` distincts, corpus entier | **deux** : `1788184102` et `1788184103`, soit le **31 août 2026 13:48:23** |
| fichier au `mtime` récent | **aucun** |
| fichiers dans `Datas/.cleaned/` | 22 |

La commande de comptage **exclut `.cleaned`**, et c'est le piège du §4.41 : sans
l'exclusion elle rend **47**.

```bash
find Datas -path 'Datas/.cleaned' -prune -o \( -name '*.pdf' -o -name '*.html' \) -print | wc -l
git ls-files -z -- Datas | xargs -0 sha256sum | sort | sha256sum
```

L'empreinte est **celle de la première campagne**, au caractère près : le corpus
n'a pas bougé d'un octet en vingt-trois jours.

### 1.5 Le job du capteur HTML matérialise BIEN `cleaned_html` — le geste du §2.3 n'est pas nécessaire

Le mandat demande de lire la définition du job avant de purger, parce que la
première campagne a dû matérialiser `cleaned_html` à part, hors capteur (§2.3 de
la première), et qu'il fallait savoir si le geste restait dû.

**Il ne l'est pas, et c'est mesuré sur la code location VIVANTE, pas seulement
lu dans le source** — la distinction compte, `define_asset_job` ne résolvant sa
sélection qu'à la construction du repository :

```python
from src.pipeline.definitions import defs
for j in defs.get_repository_def().get_all_jobs():
    print(j.name, sorted(k.to_user_string() for k in j.asset_layer.executable_asset_keys))
```

`mesuré` à 03:41 UTC, dans le conteneur `dagster-webserver` :

| Job | Assets matérialisés |
|---|---|
| **`livres_html_job`** | **`livres_html/cleaned_html`** *et* `livres_html/extracted_document` |
| `pdfs_job` | `pdfs/extracted_document` |
| `markdown_job` | `markdown/extracted_document` |
| `agent_reindex_job` | `agent/lexical_index` |

`livres_html_job` porte donc **les deux** assets, et il est celui que
`livres_html_sensor` déclenche. Le run d'une partition HTML régénère sa copie
nettoyée **et** re-téléverse ses images vers MinIO, dans le même run.

**Pourquoi la première campagne a dû le faire à part, et ce n'était donc pas un
défaut du job** : son démon était **arrêté**, et son §2.3 a matérialisé l'asset
partition par partition avant de lancer les runs. Le geste était une
conséquence de l'état du poste, pas une lacune du job. **Prédiction posée AVANT
la purge, et vérifiée après (§2.3) : `Datas/.cleaned/` doit se repeupler à 22
fichiers et le bucket à 212 objets par les seuls runs du capteur.**

### 1.6 La commande qui pose un curseur, et celle qui le lit — l'une existe, l'autre pas

**Poser** : la commande est
`dagster sensor cursor <NOM> --set <VALEUR> -w src/workspace.yaml`, et son aide
en ligne la décrit mot pour mot — « Set the cursor value for an existing
sensor ».

**Lire : il n'y a pas de commande.** `dagster sensor cursor --help` n'offre que
`--set` et `--delete` ; **il n'existe aucun mode lecture**, et invoquer la
sous-commande sans option ne rend pas la valeur. Le mandat prévoyait
« `dagster sensor cursor` sans `--set`, ou l'équivalent » : c'est **l'équivalent**
qui a servi, et il n'est pas dans la CLI :

```python
from dagster import DagsterInstance
for s in DagsterInstance.get().all_instigator_state():
    print(s.instigator_name, s.status.value, s.instigator_data.cursor)
```

C'est la voie qu'emploie déjà le §3.1 de la première campagne. **C'est un
constat, et il part au registre (§4.42.a)** : le geste de réingestion du lot 8
se pose par une commande officielle et se **relit** par un script maison.

### 1.7 Les curseurs d'avant

`mesuré` à 03:33 UTC :

| Capteur | Statut | Curseur |
|---|---|---|
| `livres_html_sensor` | `DECLARED_IN_CODE` | JSON, **22 entrées**, `mtime` du 31 août |
| `pdfs_sensor` | `DECLARED_IN_CODE` | JSON, **1 entrée**, `mtime` du 31 août |
| `markdown_sensor` | `DECLARED_IN_CODE` | **vide** (`None`) |
| `agent_reindex_sensor` | `DECLARED_IN_CODE` | **vide** (`None`) |

22 + 1 = **23**, soit exactement les 23 partitions. Les 25 fichiers du corpus
moins les **deux** `Index.html` que `matter.is_front_back_matter` écarte.

Le relevé intégral, `mtime` par `mtime`, est conservé hors du dépôt ; ce qui
compte pour la suite est qu'il est **identique** après la campagne (§5.3).

### 1.8 Les mesures d'avant — instruments et index

`verify_contract`, `mesuré` à 03:40 UTC, geste du §4.27, **`rc=1`** :

```
chunks examines                : 4367
element_id au mauvais format   : 0
element_id != graph_node_id    : 0
cles de metadonnees manquantes : aucune
ids de chunk suffixes en #n    : 976
chunks sans source_path        : 0
chunk_index hors de chunk_count: 0
elements au jeu de chunks troue: 0
modele des vecteurs            : paraphrase-multilingual-MiniLM-L12-v2
aretes PARENT_OF examinees     : 15173
aretes sans sequence           : 0
inversions de page dans l'ordre: 0
sommets sans depth             : 0/15173
sommets sans page_no_end       : 0/15173
colonnes du tag Document       : 7, manquantes aucune
sommets visuels sans minio_url : 52/264
ancres presentes dans le graphe : 3750/3750

ANOMALIE : 52 sommets visuels sur 264 sans minio_url
```

Le `rc=1` est **attendu** : ce sont les 52 tables HTML du §4.32.b, que le
producteur exclut par construction. `verify_contract` ne peut pas rendre 0 sur
ce corpus, et la première campagne l'a déjà établi.

`index_report`, `mesuré` à 03:41 UTC, `rc=0` : **4 367** chunks, **23**
documents, médiane **299** caractères, **137** chunks tronqués (3,1 %),
`text` 2 604 / `code` 975 / `list_item` 484 / `table` 196 / `caption` 108,
**4 367** `en`. Les valeurs de la première campagne, toutes.

`verifier-le-jeu-de-questions.py`, `mesuré` à 03:36 UTC, **`rc=0`**, lu **sans
tube** :

```
index interroge           : 4367 chunks
chunks annonces par le jeu: 4367
ancrages a verifier       : 44

Jeu valide : les 44 ancrages concordent avec l'index, champ par champ.
```

**Et le texte des 44 ancrages a été relevé, pas seulement leur présence** — le
mandat demande « les 44 ancrages distincts présents, **avec leur texte** ». Une
sonde de lecture seule a extrait, pour chacun, son texte intégral, sa longueur,
son `label`, son `section_title` et son `source_path`, et en a tiré une
empreinte de contrôle (`mesuré`) :

```
EMPREINTE DES 44 ANCRAGES : 11c4e1b325732ca6ce273dd08bfaba038473afa3b54b72d5649ff69cfd96611d
```

définie comme le SHA-256 des 44 lignes `element_id<TAB>sha256(texte)`, triées
par `element_id`, jointes par `\n`, avec `\n` final. **Aucun n'est absent.**

**Correction.** Cette phrase disait « les 44 sont `label=text` », et elle est
fausse. `mesuré` sur les métadonnées de l'index, `label` par `element_id` :
**36** sont `label=text` et **8** sont `label=list_item` — `269b2e32d8`,
`347b2e3799`, `5558e561d7`, `d5948cc70d`, `d913ef3b4f`, `e1ab19bc3b`,
`e74bcf1706` et `eda4f1e10c`. 36 + 8 = 44, et la somme se ferme. Ce qui était
mesuré est la **présence** des 44 et leur **texte** ; leur `label` ne l'était
pas, et il avait été supposé uniforme. L'empreinte des 44 ancrages ne change
pas : elle ne porte que l'`element_id` et le condensat du texte.

### 1.9 Le rappel d'avant, et le commit qui ajoute k = 50

**Le commit vient AVANT la mesure d'avant**, comme le mandat le prescrit, pour
que l'avant et l'après portent les mêmes `k`.

`scripts/campagne/mesurer-le-rappel-vectoriel.py` prenait ses `k` d'un argument
de ligne de commande **dont le défaut était le littéral `["5", "10", "20"]`**.
Le défaut passe à `["5", "10", "20", "50"]` — commit **`9f21b38`**, un fichier,
**+10 / −2**, aucune ligne de `src/`. Le motif est écrit au site : laisser 50 à
la ligne de commande le rendait facultatif des deux côtés, donc oubliable d'un
seul.

**Porte qualité sur ce commit**, `mesuré` dans l'arbre de travail de la
campagne, `make all` écrit dans un fichier et son `rc` lu directement, **jamais
derrière un tube**, et **aucun `-q` ajouté** :

| | |
|---|---|
| `make all` | **rc=0** |
| tests | **1 084 passed** |
| `mypy` | « no issues found in **42** source files » |
| mutations | **35 rejouées, 35 rouges**, « arbre de travail intact, 84 fichiers surveillés » |
| `ruff format --check src/ tests/ scripts/` | **84 files already formatted** |
| hooks au commit | les **huit** ont tourné et sont passés ; **aucun `--no-verify`** |

*(L'arbre de travail a reçu `uv sync` seul et **jamais** `make install` : le §12
de la première campagne dit pourquoi — `make install` graverait dans le
`.git/hooks` partagé un interpréteur qui mourrait avec cet arbre.)*

Rappel d'avant, `mesuré` à 03:37 UTC, `rc=0`, contre les **4 367** chunks. **La
sortie du script est ce qui est `mesuré`** — 30 lignes JSON, une par question ;
les agrégats ci-dessous en sont **dérivés**, et la dérivation est celle de la
première campagne, réécrite ici pour que la table se rejoue :

| Valeur | Dérivation, sur les **26** questions à réponse |
|---|---|
| **micro@k** | `somme(trouves@k) / somme(attendus)` |
| **macro@k** | `moyenne(rappel@k)`, chaque question pesant 1 |
| **au moins un@k** | `compte(au_moins_un@k vrai) / 26` |

| k | micro (`calculé`) | macro (`calculé`) | au moins un (`calculé`) |
|---|---|---|---|
| 5 | 26 / 47 = **55,3 %** | 61,5 % | 20 / 26 = 76,9 % |
| 10 | 29 / 47 = **61,7 %** | 66,0 % | 20 / 26 = 76,9 % |
| 20 | 34 / 47 = **72,3 %** | 72,4 % | 21 / 26 = 80,8 % |
| **50** | 38 / 47 = **80,9 %** | 78,8 % | 22 / 26 = 84,6 % |

**Les trois premières lignes sont, au dixième de point, celles de la première
campagne** — 55,3 / 61,7 / 72,3 en micro. L'index d'avant est donc bien celui
que la première campagne a laissé, et ce n'est pas une hypothèse.

**Les dénominateurs se citent avec leur définition**, le mandat le prescrit :
**44** ancrages **distincts**, **47** avec répétitions — c'est 47 qui est le
dénominateur du rappel micro, deux questions pouvant citer le même passage.

---

## 2. Étape 1 — la purge

### 2.1 Ce que la purge touche, lu dans le code AVANT de la lancer

`src/wipe_stores.py`, `main()` : **quatre** volets, et le quatrième est celui
qui écrit sur disque.

| Volet | Ce qu'il fait | Ce qu'il touche |
|---|---|---|
| ChromaDB | `client.delete_collection("rag_documents")` | la collection |
| MinIO | `remove_object` un par un sur tout le bucket | les objets, pas le bucket |
| NebulaGraph | `DROP SPACE IF EXISTS rag_space` | le space |
| HTML nettoyé | `shutil.rmtree` sur `cleaned_root(source_dir)` | `Datas/.cleaned/` |

**Le corpus n'est pas une cible, et deux gardes l'établissent** (`purge_cleaned`,
lot 9) : la cible doit être **strictement contenue** dans `source_dir` —
`base not in cible.parents` refuse l'égalité — **et** doit être
`cleaned_root(base)` ou l'un de ses descendants. C'est le second garde qui ferme
le §4.29.a, où `CLEANED_SUBDIR=htms` passait le containment et emportait **24
des 25 fichiers** du corpus versionné. `CLEANED_SUBDIR` n'est plus un réglage :
c'est la constante `".cleaned"`.

**Le montage de `Datas` doit être en ÉCRITURE**, et c'est la conséquence directe
du quatrième volet : `rmtree` ne peut pas tourner sur un montage `:ro`. C'est le
seul geste de toute la campagne qui monte le corpus en écriture, et il est
encadré par les deux gardes ci-dessus. `source_dir` vaut
`/opt/dagster/app/Datas` (`PipelineSettings`), donc c'est **là** que `Datas` est
monté, et pas ailleurs.

### 2.2 Le geste, et sa sortie

`mesuré`, **03:42:07 → 03:42:09** UTC, **2 s**, `rc=0` :

```bash
docker run --rm --network rag_network \
  -v "$MAIN/src":/app/src:ro \
  -v "$MAIN/Datas":/opt/dagster/app/Datas \
  --env-file "$MAIN/.env" -e HOME=/tmp -e PYTHONPATH=/app -w /app \
  rag-ingestion-pipeline-docling-service python -m src.wipe_stores
```

```
--- ChromaDB ---
collection rag_documents supprimee

--- MinIO ---
212 objets supprimes du bucket documents

--- NebulaGraph ---
space rag_space supprime

--- HTML nettoye ---
22 fichiers retires de /opt/dagster/app/Datas/.cleaned

Redemarrer docling-service pour recreer le schema.
```

**Les quatre volets ont réussi, et les quatre comptes concordent avec l'avant** :
212 objets supprimés pour 212 relevés, 22 fichiers retirés pour 22 relevés.

### 2.3 Le redémarrage prescrit, et son effet mesuré sur le schéma

`docker compose restart docling-service`, **03:42:22 → 03:42:24**, `rc=0`,
`healthy` en **26 s**. C'est le **seul** redémarrage de toute la campagne.

Il n'est pas facultatif : la purge a joué `DROP SPACE`, et `init_schema()` ne
tourne **qu'au démarrage** du service — son docstring le dit, et la dernière
ligne de sortie de `wipe_stores` le répète.

`mesuré`, journal du service :

```
03:42:25 INFO [src.docling_service.images] Bucket MinIO 'documents' pret.
03:42:48 INFO [src.docling_service.nebula] Schema semantique NebulaGraph pret.
```

État du schéma après, `mesuré` par `SHOW SPACES` puis `DESCRIBE TAG` sur les 12
tags :

| | |
|---|---|
| `SHOW SPACES` | **`['rag_space']`** — recréé |
| tags | **12** : les 11 tags d'élément plus `Document` |
| colonnes par tag d'élément | **6** partout (`label`, `page_no`, `text`, `minio_url`, `depth`, `page_no_end`) |
| colonnes de `Document` | **7** |
| **colonnes manquantes, tous tags** | **0** |
| types d'arête | `PARENT_OF`, `LINKED_TO` |

Cette fois par `CREATE TAG` et non par `ALTER` : le space venait d'être détruit.

### 2.4 L'état après la purge

`mesuré` à 03:43 UTC, même sonde qu'au §1.1 :

| Poste | Avant | Après la purge |
|---|---|---|
| collections ChromaDB | `['rag_documents']` | **`[]` — zéro collection**, pas une collection vide |
| `rag_space` | peuplé | **recréé et VIDE** — les 12 tags rendent **0** chacun, `PARENT_OF` **0**, `LINKED_TO` **0** |
| objets MinIO | 212 | **0** ; le bucket `documents` existe toujours |
| `Datas/.cleaned/` | 22 fichiers | **absent** — `ls` rend `No such file or directory` |

**Le corpus est identique à l'octet**, `mesuré` immédiatement après la purge :

| | |
|---|---|
| empreinte | **`b664418…f508e`** — la même qu'au §1.4 |
| `git status --porcelain -- Datas` | **vide** |
| fichiers, `.cleaned` exclu | **25** |
| `mtime` distincts | **les deux mêmes**, `1788184102` et `1788184103` |

**Et aucun run n'a été créé par la purge** : **958** runs avant, **958** après
(`mesuré`, 03:43 UTC). C'était à vérifier — retirer `.cleaned/` ne touche aucun
`mtime` du corpus, donc n'arme aucun capteur, et la mesure le confirme plutôt
que de le supposer.

**Le Postgres de Dagster n'a PAS été purgé** : ni les runs — les 958 sont là —
ni les curseurs, qui portent toujours les `mtime` du 31 août. C'est une
condition du geste de réingestion, pas un oubli : le §4.26 raconte ce qu'un
Postgres reparti vierge a coûté, et le §4.32.a pourquoi la forme de la clé
nominale en dépend.

---

## 3. Étape 2 — la réingestion, par le geste du lot 8

### 3.1 Où le marqueur est posé, et où il ne l'est pas

Trois sources sont déclarées dans `sources.yaml` : `livres_html`, `pdfs`,
`markdown`. Le marqueur est posé sur **deux**.

| Capteur | Fichiers dans sa source | Marqueur posé ? | Motif |
|---|---|---|---|
| `livres_html_sensor` | **22** (24 HTML moins les deux `Index.html` écartés) | **oui** | la source porte des fichiers à réingérer |
| `pdfs_sensor` | **1** | **oui** | idem |
| `markdown_sensor` | **0** — `Datas/mds` **n'existe pas** (`mesuré`, `ls`) | **non** | voir ci-dessous |
| `agent_reindex_sensor` | — | **non** | ce n'est pas un capteur de fichiers ; il part tout seul en fin d'ingestion |

**Ce qui a été fait pour la source vide, et pourquoi.** `markdown_sensor` n'a
**pas** reçu de marqueur. Le geste aurait été inoffensif — le code prévoit
explicitement le cas, la condition `or etiquette` de `_build_sensor` existant
pour qu'un marqueur posé sur une source au corpus vide soit **consommé** au lieu
d'être rejoué à chaque tick — mais il aurait été **sans effet et sans objet** :
zéro fichier, donc zéro partition, donc zéro run. Poser un marqueur là aurait
écrit un curseur JSON `{}` à la place d'un curseur vide, c'est-à-dire aurait
changé l'état de Dagster pour rien. **La règle retenue : on ne pose le marqueur
que sur les capteurs dont la source porte des fichiers**, ce que le mandat
formule déjà.

### 3.2 Le geste

`mesuré`, **03:43:40** et **03:43:44** UTC, `rc=0` chacun :

```bash
docker compose exec -T -w /opt/dagster/app -e PYTHONPATH=/opt/dagster/app \
  dagster-webserver dagster sensor cursor livres_html_sensor \
    --set 'reingerer:2026-09-25-campagne-2' -w src/workspace.yaml
```

```
Set cursor state for sensor livres_html_sensor to "reingerer:2026-09-25-campagne-2"
Set cursor state for sensor pdfs_sensor        to "reingerer:2026-09-25-campagne-2"
```

### 3.3 Le tick — et c'est ici que le §4.32.a se referme, sous les yeux de quelqu'un

**Le silence du §4.32.a ne s'est PAS produit.** `mesuré` sur les ticks
enregistrés par Dagster :

| Capteur | Tick | Statut | **Runs CRÉÉS** | `skip_reason` |
|---|---|---|---|---|
| `livres_html_sensor` | **03:43:43** | **`SUCCESS`** | **22** | `None` |
| `pdfs_sensor` | **03:44:10** | **`SUCCESS`** | **1** | `None` |

**22 + 1 = 23 runs créés, pour 23 demandes.** Et le compte de runs le confirme
par un second chemin, indépendant du tick : **958 → 981**, soit **exactement
+23** (`mesuré`, 03:44:31).

**C'est le premier geste de réingestion réellement exercé**, et c'est ce que le
lot 8 disait ne pas pouvoir prouver. Le registre §4.32.a l'écrit noir sur
blanc : « Ce qui n'est pas prouvé, et qui ne pouvait pas l'être : qu'un run
réellement créé par ce chemin aille au bout. Le premier geste de réingestion
reste donc à faire sous les yeux de quelqu'un. » **C'est fait, et les 23 runs
sont allés au bout.**

**La clé de run porte l'étiquette, et non le `mtime`** — c'est ce qui la rend
neuve pour Dagster, et c'est mesuré sur les runs eux-mêmes, pas déduit du code
(`mesuré`, tag `dagster/run_key`) :

```
livres_html_htms/MLOps with Databricks/1. MLOps Principles and Components.html_reingestion_2026-09-25-campagne-2
```

La forme est exactement `{source}_{partition}_reingestion_{etiquette}`, celle
que `TestLaCleDeReingestionNePorteQueLEtiquette` fige. Aucun `mtime` du corpus
n'a été touché pour l'obtenir.

### 3.4 Les 23 runs, un par un

`mesuré`, lu dans les `run_records` de l'instance Dagster.
`max_concurrent_runs: 2` (`dagster.yaml`) : deux runs en vol, les autres en
file.

| Départ UTC | Job | Statut | Durée | Reprises | Partition |
|---|---|---|---|---|---|
| 03:43:50 | `livres_html_job` | `SUCCESS` | 21,5 s | **0** | `MLOps with Databricks/1. MLOps Principles and Components` |
| 03:43:54 | `livres_html_job` | `SUCCESS` | 21,0 s | **0** | `MLOps with Databricks/10. AI Governance` |
| 03:44:15 | `livres_html_job` | `SUCCESS` | 22,1 s | **0** | `MLOps with Databricks/2. Developing on Databricks` |
| 03:44:20 | `livres_html_job` | `SUCCESS` | 36,9 s | **0** | `MLOps with Databricks/3. MLflow for Traditional ML` |
| 03:44:40 | `livres_html_job` | `SUCCESS` | 21,4 s | **0** | `MLOps with Databricks/4. Model Serving：Architectures and Implementation` |
| 03:45:00 | `livres_html_job` | `SUCCESS` | 22,5 s | **0** | `MLOps with Databricks/5. Machine Learning Model Deployment` |
| 03:45:06 | `livres_html_job` | `SUCCESS` | 36,5 s | **0** | `MLOps with Databricks/6. Monitoring ML Applications` |
| 03:45:26 | `livres_html_job` | `SUCCESS` | 22,4 s | **0** | `MLOps with Databricks/7. Foundation Models and Context Engineering` |
| 03:45:47 | `livres_html_job` | `SUCCESS` | 22,1 s | **0** | `MLOps with Databricks/8. MLflow for GenAI` |
| 03:45:52 | `livres_html_job` | `SUCCESS` | 37,2 s | **0** | `MLOps with Databricks/9. Deploying in Monitoring LLM-Based Systems` |
| 03:46:12 | `livres_html_job` | `SUCCESS` | **9,1 s** | **0** | `MLOps with Databricks/Preface` |
| 03:46:28 | `livres_html_job` | `SUCCESS` | 13,7 s | **0** | `Practical MLflow…/1. Introduction to MLflow for GenAI on Databricks` |
| 03:46:33 | `livres_html_job` | `SUCCESS` | 12,9 s | **0** | `Practical MLflow…/10. Unifying GenAI Systems with MLflow` |
| 03:46:48 | `livres_html_job` | `SUCCESS` | 13,1 s | **0** | `Practical MLflow…/2. End-to-End GenAI Application Lifecycle with MLflow` |
| 03:46:53 | `livres_html_job` | `SUCCESS` | 36,2 s | **0** | `Practical MLflow…/3. Prompt Engineering with MLflow` |
| 03:47:09 | `livres_html_job` | `SUCCESS` | 13,0 s | **0** | `Practical MLflow…/4. Building and Versioning a Tool-Calling Agent` |
| 03:47:29 | `livres_html_job` | `SUCCESS` | 21,8 s | **0** | `Practical MLflow…/5. MLflow Tracing for GenAI Application Observability` |
| 03:47:34 | `livres_html_job` | `SUCCESS` | 36,4 s | **0** | `Practical MLflow…/6. Evaluating GenAI Applications with MLflow` |
| 03:47:54 | `livres_html_job` | `SUCCESS` | 21,2 s | **0** | `Practical MLflow…/7. Advanced Agents and Tools` |
| 03:48:15 | `livres_html_job` | `SUCCESS` | 21,5 s | **0** | `Practical MLflow…/8. Deploying a GenAI Application with MLflow` |
| 03:48:20 | `livres_html_job` | `SUCCESS` | 13,3 s | **0** | `Practical MLflow…/9. Production Monitoring with MLflow` |
| 03:48:41 | `livres_html_job` | `SUCCESS` | **96,1 s** | **0** | `Practical MLflow…/Preface` |
| 03:48:43 | `pdfs_job` | `SUCCESS` | 93,1 s | **0** | `pdfs/Hands-On_RAG_for_Production_ER_-_Ofer_Mendelevitch.pdf` |

| | |
|---|---|
| runs | **23**, dont **23 `SUCCESS`** et **0 échec** |
| reprises automatiques | **0** sur 23 |
| durée par run | min **9,1 s**, médiane **21,8 s**, max **96,1 s** |
| somme des durées | **665,1 s** (`calculé` — somme des 23 `end − start`) |
| durée **murale** | **387,3 s** (`calculé` — `max(end) − min(start)`), de 03:43:50,081 à 03:50:17,395 |
| créations | de 03:43:46,558 à 03:44:11,613, soit **25 s** pour créer les 23 |

**Aucun run en échec, donc aucune relance de partition, donc aucun écart à
déclarer de ce côté.** La clause du mandat sur les échecs n'a pas eu à jouer, et
aucune purge supplémentaire n'a eu lieu.

**Une observation qui n'est pas une anomalie, et qu'il faut écrire pour qu'elle
ne se lise pas comme telle.** Le `Preface` de *Practical MLflow* met **96,1 s**
là où celui de *MLOps with Databricks* met **9,1 s** — un facteur dix sur deux
documents de même nature. La cause n'est pas mesurée ici ; ce qui **est**
mesuré, c'est que le run est `SUCCESS`, sans reprise, et que son document rend
au `comparer` les **127** éléments de l'instantané, identiques (§4.2). **Le
contenu produit est donc le bon** ; seule la durée détonne. `NON VÉRIFIÉ` : la
cause de l'écart de durée.

### 3.5 `cleaned_html` a bien été refait par le capteur — la prédiction du §1.5 se vérifie

**Le geste du §2.3 de la première campagne n'a PAS été fait, et n'avait pas à
l'être.** `mesuré` après la réingestion, sans aucune matérialisation manuelle :

| | après la purge | après les 23 runs |
|---|---|---|
| fichiers dans `Datas/.cleaned/` | **0** (répertoire absent) | **22** |
| objets dans le bucket `documents` | **0** | **212** |
| dont images HTML | 0 | **199** |
| dont crops du PDF | 0 | **13** |

Les 22 copies nettoyées et les 199 images sont revenues **par les seuls runs du
capteur**, ce que le §1.5 avait prédit en lisant la définition du job **avant**
la purge. C'est un écart **en moins** par rapport à la première campagne, et il
est déclaré au §6 à sa taille exacte.

### 3.6 Le déclenchement du `POST /reindex` — l'exigence 5 est ÉPROUVÉE, pour la première fois

`agent_reindex_sensor` est parti **tout seul**, et il n'a pas été forcé.

`mesuré`, run **`f0e37ba9`**, démarré à **03:50:48** UTC, **`SUCCESS`**, avec
ses deux métadonnées :

```
reindex        = ok — 4367 chunks indexes
chunks_indexed = 4367
```

C'est mot pour mot la valeur que le mandat annonçait, et **4 367** est le compte
de chunks de l'index réingéré.

**Ce qui rend cela possible ici et ne l'était pas à la première campagne est un
fait de POSTE, et il doit être écrit comme tel** : le service **`rag-agent-api`
tourne** — `Up 3 hours (healthy)` — et `AGENT_SERVICE_URL=http://agent-api:8000`
répond **200** sur `/health` (`mesuré`, 03:42 UTC). La première campagne
écrivait que l'exigence 5 « n'est pas éprouvée » parce que le service ne
tournait sur aucun conteneur du poste. **Elle l'est désormais.**

**Et le garde du §4.15 a été observé en vol, avec sa raison à chaque tick.**
`mesuré`, ticks d'`agent_reindex_sensor` dans la fenêtre 03:43 → 03:53 :
**19 ticks**, et les trois familles se ferment — **1 + 13 + 4 + 1 = 19** :

| Ticks | Compte | Ce qu'ils disent |
|---|---|---|
| `SKIPPED` avant le geste (03:43:23) | **1** | « Rien de nouveau n'a ete ingere depuis la derniere reindexation reussie. » |
| `SKIPPED` **consécutifs** de **03:43:59 à 03:50:10** | **13** | chacun **nomme le garde et le run qui bloque** : « Ingestion en cours (`<job>`) : la reindexation attend qu'elle retombe. Le run `…` est en QUEUED ». Le job nommé est `livres_html_job` au premier tick et `pdfs_job` aux **12** suivants — voir la correction en fin de §3.6 |
| `SUCCESS` à **03:50:41** | **1** | le run de réindexation, créé **24 s** après la fin du dernier run d'ingestion (03:50:17,4) |
| `SKIPPED` après (03:51:11 → 03:52:46) | **4** | « Rien de nouveau… » — l'index est à jour |

**Le trou recouvre ici toute la fenêtre d'ingestion**, contrairement à la
première campagne où deux runs de réindexation étaient partis à l'intérieur —
et la raison est mesurable : l'ingestion est partie **en une seule vague**, les
23 runs créés en 25 secondes, sans le trou de 64 s que la première campagne
avait entre sa partition d'essai et les 22 autres.

**Une précision sur ce que le garde nomme, et une correction.** Cette phrase
disait « les 13 ticks bloqués citent `pdfs_job` », et elle est fausse : ils sont
**12 sur 13**. `mesuré` sur les ticks enregistrés, le **premier** de la série,
à **03:43:59**, cite `livres_html_job` et le run **`b3d62067`**, alors en
`QUEUED` — c'est-à-dire le tout premier des 22 runs HTML, et non le run du PDF.
Les **12** suivants, de 03:44:30 à 03:50:10, citent bien `pdfs_job` et le run
`ff4429ce`. Le garde nomme le run en vol le plus ancien, et celui-ci change au
fil de la vague ; il se trouve qu'après 03:44:30 c'est le run du PDF, mis en
file le premier et exécuté le dernier, qui le reste jusqu'au bout.

`pdfs_job` est donc cité alors que son run n'a **démarré** qu'à 03:48:43 : le
garde compte un run **`QUEUED`** comme « en vol », et c'est correct — un run en file va
s'exécuter, et réindexer avant lui indexerait un état incomplet. Le message dit
d'ailleurs « est en QUEUED », il ne prétend pas qu'il tourne.

---

## 4. Étape 3 — les mesures d'après, en regard d'avant

### 4.1 Les huit comptes et l'empreinte MinIO

`mesuré` à 03:51 UTC, **même sonde, même commande qu'au §1.1**.

| Compte | Attendu | Avant | **Après** | Écart |
|---|---|---|---|---|
| sommets, `Document` compris | 15 196 | 15 196 | **15 196** | **0** |
| sommets `Document` | 23 | 23 | **23** | **0** |
| sommets `Paragraph` | 7 251 | 7 251 | **7 251** | **0** |
| sommets `ListItem` | 1 748 | 1 748 | **1 748** | **0** |
| sommets `Code` | 4 963 | 4 963 | **4 963** | **0** |
| arêtes `PARENT_OF` | 15 173 | 15 173 | **15 173** | **0** |
| chunks ChromaDB | 4 367 | 4 367 | **4 367** | **0** |
| objets MinIO | 212 | 212 | **212** | **0** |

Et les quatre tags hors mandat, également identiques : `Caption` **201**,
`Picture` **209**, `SectionHeader` **746**, `Table` **55** ; `LINKED_TO`
**201**. Les quatre tags vides le sont restés.

**Empreinte des clés d'objet MinIO**, même recette qu'au §1.2 :

```
c91f5be6e24fbcba5f4a744119bf8da65fed44b7ecac79cce0ae1b027ed0b994
```

**Identique.** Ce n'est pas seulement le *nombre* d'objets qui se reproduit :
c'est **l'ensemble des 212 clés, à la clé près et au tri près**. Or chaque clé
de crop du PDF porte un `element_id` dans son nom
(`images/<radical>/<element_id>_<label>.png`), donc cette égalité est une preuve
de plus, indépendante de `comparer`, que les identifiants n'ont pas bougé.

Le modèle inscrit sur la collection est **`paraphrase-multilingual-MiniLM-L12-v2`**
avant comme après.

### 4.2 `comparer` contre l'instantané versionné — le verdict de la campagne

`mesuré` de **03:52:44 à 03:54:09** UTC (85 s), `rc=0` du **processus**, lu sans
tube. **Commande strictement identique à celle du §1.3** ; seuls les stores et
les copies nettoyées ont changé, et les copies sont celles que les 23 runs
viennent de **régénérer**, montées `:ro`.

```
INSTANTANE e945893b1021e2f1aa3809434a889443ed9fb85e2a7e290cd329f077687f0f6d
DOCUMENTS COMPARES 23 / 23 de l'instantane
DEPLACES 0, DECLARES 0
ATTRIBUTION (exacte, par appariement) : {}
OK : l'ensemble deplace est exactement l'ensemble declare.
```

| | |
|---|---|
| `rc` du processus | **0** |
| `DOCUMENTS COMPARES` | **23 / 23** |
| `DEPLACES` | **0** |
| `DECLARES` | **0** — **aucun déplacement n'a été annoncé**, ni avant ni après |
| `L'ENTREE CONVERTIE A CHANGE` | **aucune occurrence** — les 23 `sha256_de_l_entree` de l'instantané valent toujours |
| `apparus sans contrepartie` | **0** sur les 23 documents |
| `reassignes` | **0** sur les 23 documents |

**Aucun déplacement n'a été déclaré pour faire passer l'instrument au vert**, et
il n'y avait rien à déclarer : `--deplacements-annonces` n'a pas été employé, le
fichier n'existe pas, et `DECLARES 0` le dit dans la sortie.

**Les copies nettoyées régénérées rendent les mêmes empreintes d'entrée que
celles du 24 septembre.** C'est un résultat en soi : `cleaning.py` est
déterministe sur ce corpus, ses 22 sorties sont octet pour octet celles qui ont
servi à figer l'instantané. Si elles avaient changé, le harnais l'aurait dit —
c'est précisément ce que la colonne `sha256_de_l_entree` existe pour distinguer.

**Les contrôles négatifs ont tourné, et ils sont ce qui empêche ce vert d'être
creux.** Pour chaque document, cinq mutations du calcul d'identifiant —
`filename`, `page_no`, `position_in_page`, `site_d_appel`, `text50` — et chacune
doit déplacer les identifiants qu'elle touche, sans quoi le `0 déplacé` ne
prouverait rien. Sur le PDF (`mesuré`) : 365 / 295 / 361 / 365 / 198 mutés,
**0 mal attribué**, tous **hors graphe** — « vu » sur les cinq.

### 4.3 `verify_contract` et `index_report`

`mesuré` à 03:55 UTC, geste du §4.27, **`rc=1`** pour le premier et **`rc=0`**
pour le second — les deux `rc` sont ceux des processus.

**La sortie de `verify_contract` est IDENTIQUE, ligne pour ligne, à celle
d'avant** (`mesuré` : `diff` des deux sorties rend le vide). Les dix-sept
compteurs valent donc ce que le §1.8 donne, et en regard de la **première
campagne** :

| Ligne | 1ʳᵉ campagne (2 sept.) | Avant (25 sept.) | **Après** |
|---|---|---|---|
| chunks examinés | 4 367 | 4 367 | **4 367** |
| `element_id` au mauvais format | 0 | 0 | **0** |
| `element_id` != `graph_node_id` | 0 | 0 | **0** |
| clés de métadonnées manquantes | aucune | aucune | **aucune** |
| ids de chunk suffixés en `#n` | 976 | 976 | **976** |
| éléments au jeu de chunks troué | 0 | 0 | **0** |
| arêtes `PARENT_OF` examinées | 15 173 | 15 173 | **15 173** |
| arêtes sans `sequence` | 0 | 0 | **0** |
| inversions de page dans l'ordre | 0 | 0 | **0** |
| sommets sans `depth` | 0 / 15 173 | 0 / 15 173 | **0 / 15 173** |
| sommets sans `page_no_end` | 0 / 15 173 | 0 / 15 173 | **0 / 15 173** |
| colonnes du tag `Document` | 7, aucune manquante | idem | **idem** |
| **sommets visuels sans `minio_url`** | **52 / 264** | **52 / 264** | **52 / 264** |
| ancres présentes dans le graphe | 3 750 / 3 750 | 3 750 / 3 750 | **3 750 / 3 750** |
| `rc` | 1 | 1 | **1** |

**Le `rc=1` est le §4.32.b, et rien d'autre.** Les 52 sont, à 52 sur 52, des
tables HTML que `extraction.propager_les_url_dimages` exclut délibérément et que
`verify_contract._lire_les_urls_visuelles` compte quand même. L'instrument ne
peut pas rendre 0 sur ce corpus, la première campagne l'a établi, et **une
réingestion n'y change rien — ce qui est exactement la prédiction du constat**.

**La sortie d'`index_report` est elle aussi IDENTIQUE, ligne pour ligne**
(`mesuré`, `diff` vide), donc égale à celle de la première campagne sur les
seize postes qu'elle rend : 4 367 chunks, 23 documents, 1 sans caractère
alphanumérique, 21 de moins de 40 caractères, médiane 299 / moyenne 303 /
extrêmes 8–683, éléments fusionnés médiane 2 maximum 18, fenêtre 128 tokens,
**137** chunks tronqués (3,1 %) tokens médiane 95 maximum 149, profondeurs
4 / 5 / 8 / 5 / **1 document plat**, 4 367 `en`, et `text` 2 604 / `code` **975**
/ `list_item` 484 / `table` 196 / `caption` 108.

**`section_header` vaut toujours 0** dans la répartition par label : aucun titre
n'est jamais un chunk (§4.24).

### 4.4 Les 44 ancrages du jeu de questions

`verifier-le-jeu-de-questions.py`, `mesuré` à 03:54 UTC, **`rc=0`**, lu sans
tube :

```
index interroge           : 4367 chunks
chunks annonces par le jeu: 4367
ancrages a verifier       : 44

Jeu valide : les 44 ancrages concordent avec l'index, champ par champ.
```

**Et le texte est le même, ce qui est plus fort que « présent ».** La sonde du
§1.8 a été rejouée à l'identique, et les deux relevés sont comparés par `diff` :

| Comparaison | Résultat |
|---|---|
| les 44 lignes `element_id` / longueur / `sha256(texte)` / `label` | **`diff` vide — identique** |
| le relevé complet : **texte intégral**, `section_title`, `source_path`, nombre d'occurrences | **`diff` vide — identique** |
| empreinte des 44 ancrages | **`11c4e1b3…611d`** avant, **`11c4e1b3…611d`** après |

**Les 44 ancrages sont présents, distincts, et portent le même texte
qu'avant** — le mandat demandait exactement cela.

Le chiffre se cite avec sa définition : **44** ancrages **distincts**, **47**
avec répétitions.

### 4.5 Le rappel vectoriel, aux quatre `k`

`mesuré` à 03:55 UTC, `rc=0`, contre les **4 367** chunks, **même script, même
commit `9f21b38`, mêmes quatre `k`** qu'au §1.9. Les agrégats sont `calculé`,
par la dérivation écrite au §1.9.

| k | micro — avant | **micro — après** | macro — avant | **macro — après** | au moins un — avant | **après** |
|---|---|---|---|---|---|---|
| 5 | 26/47 = 55,3 % | **26/47 = 55,3 %** | 61,5 % | **61,5 %** | 20/26 = 76,9 % | **20/26 = 76,9 %** |
| 10 | 29/47 = 61,7 % | **29/47 = 61,7 %** | 66,0 % | **66,0 %** | 20/26 = 76,9 % | **20/26 = 76,9 %** |
| 20 | 34/47 = 72,3 % | **34/47 = 72,3 %** | 72,4 % | **72,4 %** | 21/26 = 80,8 % | **21/26 = 80,8 %** |
| **50** | 38/47 = 80,9 % | **38/47 = 80,9 %** | 78,8 % | **78,8 %** | 22/26 = 84,6 % | **22/26 = 84,6 %** |

**Les définitions, à côté des comptes, parce qu'un rappel sans son dénominateur
ne se compare pas :**

- **rappel micro à k** — `somme des ancrages retrouvés dans les k premiers` ÷
  `somme des ancrages attendus`, sur les **26** questions à réponse. Dénominateur
  **47** : les ancrages **avec répétitions**, une question pouvant citer un
  passage qu'une autre cite aussi. Chaque *ancrage* pèse 1 ;
- **rappel macro à k** — moyenne, sur les mêmes 26 questions, du rapport
  `retrouvés ÷ attendus` de **chaque question**. Chaque *question* pèse 1, quel
  que soit son nombre d'ancrages ;
- **au moins un à k** — nombre de questions dont **au moins un** ancrage revient
  dans les k premiers, ÷ **26**. Ni micro ni macro : c'est le compte des
  questions non muettes ;
- les **4** questions `sans_reponse` n'ont **pas** de rappel — 0 ancrage, donc
  aucun dénominateur — et sont exclues des trois.

**En regard de la première campagne** (2 septembre 2026) :

| k | 1ʳᵉ campagne, micro | Avant (25 sept.) | **Après (25 sept.)** |
|---|---|---|---|
| 5 | **55,3 %** | 55,3 % | **55,3 %** |
| 10 | **61,7 %** | 61,7 % | **61,7 %** |
| 20 | **72,3 %** | 72,3 % | **72,3 %** |
| 50 | *non mesuré* | 80,9 % | **80,9 %** |

**Les trois valeurs de la première campagne se reproduisent exactement, et la
quatrième est neuve.** `k = 50` n'existait pas le 2 septembre : il n'y a donc
rien à mettre en regard, et l'écrire est plus honnête que de comparer à un
chiffre absent.

Par strate, à k = 10 puis à k = 50 (`calculé`, **identique avant et après**,
`diff` des agrégats vide) :

| Strate | n | micro @10 | au moins un @10 | micro @50 | au moins un @50 |
|---|---|---|---|---|---|
| `simple` | 8 | **8 / 8 = 100 %** | **8 / 8** | **8 / 8 = 100 %** | **8 / 8** |
| `multi_passages` | 12 | 18 / 31 = 58,1 % | 10 / 12 | **27 / 31 = 87,1 %** | **12 / 12** |
| `reformulee` | 2 | 2 / 3 = 66,7 % | 1 / 2 | 2 / 3 = 66,7 % | 1 / 2 |
| `de_suivi` | 4 | 1 / 5 = 20,0 % | 1 / 4 | 1 / 5 = 20,0 % | 1 / 4 |

**Ce que `k = 50` apporte, et ce qu'il n'apporte pas.** Il ne bouge **que** la
strate `multi_passages`, qui passe de 58,1 % à 87,1 % en micro et atteint
**12 / 12** en « au moins un ». Les trois autres strates sont **exactement**
identiques à k = 10 : le plancher `simple` est déjà saturé à k = 5, et les
questions `de_suivi` et `reformulee` qui échouent échouent **à tout k testé** —
leur ancrage n'est pas au-delà du vingtième voisin, il n'est nulle part dans les
cinquante. **Ce n'est donc pas un argument pour élargir `k`** : trente questions
n'arbitrent pas un réglage, et la réserve de la première campagne tient mot pour
mot.

Les distances L2 du premier voisin sont identiques question par question, aux
quatre décimales (`mesuré` : le `diff` du relevé par question est vide) — par
exemple `q15` à **6,1064**, `q26` à **20,0067**.

### 4.6 Le corpus, et le compte de runs

**Le corpus est identique à l'octet**, `mesuré` à 03:56 UTC, après tous les
gestes :

| | |
|---|---|
| empreinte | **`b664418…f508e`** — identique à l'avant et à la première campagne |
| `git status --porcelain -- Datas` | **vide** |
| fichiers, `.cleaned` exclu | **25** |
| `mtime` distincts | **les deux mêmes** — aucun fichier touché |

**Les runs, un par un** (`mesuré`, `inst.get_runs_count`) :

| Moment | Runs | Δ | Ce qui les a créés |
|---|---|---|---|
| avant tout geste, 03:33 | **958** | — | l'histoire du poste |
| après la purge, 03:43 | **958** | **+0** | **rien** — la purge ne crée aucun run |
| après le tick des capteurs, 03:44 | **981** | **+23** | les 23 partitions demandées par les deux capteurs |
| état final, 03:56 | **982** | **+1** | le run de réindexation `f0e37ba9` |

**982 = 958 + 23 + 1**, et le compte se ferme sans reste. Par statut :
**96 `SUCCESS`** (72 + 23 + 1) et **886 `FAILURE`** — **le compte d'échecs n'a
pas bougé d'une unité**. **0** run non terminal.

**Les curseurs sont revenus exactement à leur valeur d'avant** (`mesuré`,
`diff` du relevé complet) : `livres_html_sensor` 22 entrées, `pdfs_sensor` 1,
les deux autres vides, **et les `mtime` inscrits sont les mêmes qu'avant la
campagne**, au chiffre près. Le marqueur a été consommé par son tick, et le
curseur JSON reconstruit porte les `mtime` d'un corpus qui n'a pas bougé.

---

## 5. Les écarts au mandat, à leur taille exacte

Trois, et aucun n'est un écart de périmètre.

**Écart 1 — le geste du §2.3 n'a PAS été fait, et c'est un écart EN MOINS.** Le
mandat le prévoyait conditionnellement : « Si `cleaned_html` n'est pas dans le
job du capteur (étape 0), fais le geste du §2.3 ». La condition a été **levée
avant la purge** par lecture de la code location vivante (§1.5) : `livres_html_job`
matérialise `cleaned_html`. Le geste n'a donc pas eu lieu, et la prédiction qui
en découlait a été vérifiée après (§3.5) — 22 copies nettoyées et 199 images
revenues par les seuls runs du capteur. **Taille exacte : zéro
`dagster asset materialize` lancé, là où la première campagne en a lancé 22.**

**Écart 2 — `markdown_sensor` n'a pas reçu de marqueur.** Le mandat demande de
poser le marqueur « sur le curseur de chaque capteur de fichiers **dont la
source a des fichiers** », et de dire ce qui est fait pour une source vide.
`Datas/mds` n'existe pas : zéro fichier. Le marqueur n'a pas été posé, le motif
est au §3.1. **Taille exacte : un capteur sur trois sans marqueur, zéro
partition perdue** — il n'y en avait aucune à demander.

**Écart 3 — j'ai livré du code, un commit d'une ligne utile.** Le mandat
l'autorise explicitement pour `k = 50` et le borne à `scripts/campagne/` : c'est
`9f21b38`, **un fichier, +10 / −2**. `git diff main..HEAD --stat -- src/` et
`-- Datas` rendent tous deux le **vide**. **Taille exacte : une constante de
défaut et son commentaire de motif ; aucune ligne de production, aucun test
désactivé, aucune règle relâchée.**

**Et une précision qui n'est pas un écart mais que le mandat demande de dire.**
Le mandat prescrivait de vérifier la commande de lecture d'un curseur
« `dagster sensor cursor` sans `--set`, ou l'équivalent ». **Le premier terme de
l'alternative n'existe pas** : la CLI n'a pas de mode lecture. C'est
l'équivalent qui a servi, et le constat part au registre (§4.42.a).

---

## 6. NON VÉRIFIÉ

Une réserve écrite vaut mieux qu'une conclusion tirée.

**La cause de l'écart de durée entre les deux `Preface`** — 96,1 s contre
9,1 s — n'est pas mesurée. Ce qui l'est : le run est `SUCCESS` sans reprise, et
son document rend au `comparer` ses 127 éléments identiques à l'instantané.

**L'index BM25 reconstruit chez l'agent n'est pas vérifié de ce côté-ci.** Ce
qui est mesuré est que `POST /reindex` a été émis, que l'agent a répondu, et que
sa réponse dit `ok — 4367 chunks indexes`. **Que son index lexical serve
effectivement ces 4 367 chunks est une propriété de l'autre dépôt**, et aucune
requête n'a été posée à l'agent pour l'éprouver. L'exigence 5 est tenue au sens
du contrat — l'appel part et réussit en fin d'ingestion ; elle n'est pas éprouvée
au sens de l'agent.

**L'égalité des ENSEMBLES d'`element_id` est prouvée ici, et c'est neuf — mais
sa portée est celle de l'instantané.** `comparer` confronte l'émission de la
production aux **23 relevés versionnés du 24 septembre**, pas à l'index
d'avant-purge. Ce qui est établi : le code de `main` réémet, document par
document, exactement les identifiants que l'instantané porte. Ce qui ne l'est
pas par ce chemin : que l'index d'avant-purge portât lui-même exactement cet
ensemble — c'est l'attestation d'avant (§1.3) qui le dit, et elle le dit par le
même instrument.

**Le rappel reste un plancher dense.** Ni BM25, ni le graphe, ni le reranker, ni
l'abstention. La réserve du §6.4 de la première campagne vaut intégralement.

**Les strates à petit n ne sont pas mesurées, elles sont échantillonnées.**
`reformulee` compte n = 2, et ses deux questions éprouvent deux axes
différents — reformulation monolingue et translinguistique — donc **n = 1 par
axe**. Le « 66,7 % » de la ligne agrège une question qui échoue et une qui
réussit.

**La qualité des trente questions n'est garantie par rien d'automatique**, et
les questions pièges restent reportées au second tour.

**Le profil de reproductibilité n'est établi que sur UNE réingestion.** Tous les
témoins concordent, mais une seule répétition ne distingue pas « déterministe »
de « stable ce jour-là ». C'est une réserve de méthode, pas un doute sur un
chiffre.

---

## 7. L'état dans lequel la pile est laissée

`mesuré` le 25 septembre 2026 à 03:56 UTC.

**Les dix services sont debout**, dans le projet Compose
`rag-ingestion-pipeline`, montés depuis le clone principal : `graphd`, `metad`,
`storaged`, `chromadb`, `minio`, `nebula-studio`, `postgres-dagster`,
`dagster-webserver`, `dagster-daemon`, `docling-service` (`healthy`, redémarré
**une** fois par cette campagne). **La pile n'est pas démontée.**

**Le démon Dagster tourne toujours, et il n'a pas été arrêté.** C'est la
différence avec la première campagne, qui l'avait arrêté pour cesser de produire
un run rouge toutes les 30 secondes. Ici, `agent_reindex_sensor` **saute**
proprement — « Rien de nouveau n'a ete ingere depuis la derniere reindexation
reussie » — parce que l'agent tourne et que la réindexation a réussi. **Aucun
run rouge n'est produit par le temps qui passe**, et il n'y avait donc aucun
motif de l'arrêter. Le mandat l'interdisait par ailleurs.

**L'index laissé au poste** :

| | |
|---|---|
| chunks ChromaDB | **4 367** |
| sommets | **15 196** (`Document` compris) |
| arêtes `PARENT_OF` | **15 173** |
| arêtes `LINKED_TO` | **201** |
| documents | **23** |
| objets MinIO | **212**, empreinte `c91f5be6…0994` |
| `Datas/.cleaned/` | **22** fichiers, régénérés |
| modèle inscrit | `paraphrase-multilingual-MiniLM-L12-v2` |
| `verify_contract` | **`rc=1`**, une seule anomalie : les 52 tables HTML (§4.32.b) |
| runs Dagster | **982**, dont 96 `SUCCESS` et 886 `FAILURE`, **0** non terminal |
| curseurs | revenus à l'identique : 22 / 1 / vide / vide |

**Le corpus est intact à l'octet**, empreinte `b664418…f508e`, `mtime`
inchangés, `git status -- Datas` vide.

**Ce qui subsiste et ne relève pas de cette campagne** : les seize arbres de
travail sous `.claude/worktrees/`, dont plusieurs sont morts et que git ne
connaît plus. Le `git status` du clone principal ne rend que `?? .claude/`, comme
avant la campagne.

**Les sondes de mesure de cette campagne vivent HORS de l'arbre**, dans le
scratchpad de session, et pas une n'a été laissée non versionnée dans le dépôt.
C'est la doctrine du §10 de la première campagne, et son motif : un script de
mesure est **versionné** s'il doit être rejoué, **hors de l'arbre** s'il est
jetable ; « non versionné dans l'arbre » n'est pas une destination. Les
instruments rejouables de cette campagne sont ceux que `main` porte déjà —
`scripts/campagne/*.py`, `src/verify_contract.py`, `src/index_report.py`.

---

## 8. Ce que la campagne laisse au registre

**Deux** constats neufs, mesurés, hors du diff — périmètre strict. Ils vivent au
registre §4.42.

- **§4.42.a** — la CLI Dagster **pose** un curseur (`dagster sensor cursor
  --set`) mais ne sait pas le **lire**. Le geste de réingestion du lot 8 se
  vérifie donc par un script maison, et un opérateur qui voudrait contrôler son
  marqueur avant de le poser n'a aucune commande officielle pour le faire ;
- **§4.42.b** — l'empreinte des clés d'objet MinIO circule **sans sa recette**.
  Aucun site du dépôt ne dit comment `c91f5be6…` se calcule ; il a fallu
  l'identifier par mesure, en essayant quatre variantes. Une empreinte sans sa
  recette n'est pas un témoin, c'est un chiffre.

**Et deux constats du registre changent d'état par cette campagne, ce qui est un
geste de pilote et non de branche** :

- **§4.32.a** — le lot 8 écrivait « le premier geste de réingestion reste à
  faire sous les yeux de quelqu'un ». **Il est fait** : 23 demandes, 23 runs
  créés, 23 `SUCCESS`, `skip_reason=None` sans perte ;
- **§4.28.c** et le §7 de la première campagne — « l'exigence 5 n'est pas
  éprouvée ». **Elle l'est**, le service de l'agent tournant sur ce poste.

---

## 9. Les pièges de mesure, et comment ils ont été pris

Ils sont écrits parce que le mandat les nomme d'avance et qu'un piège annoncé se
commet quand même.

**Le `rc` est celui du PROCESSUS, jamais derrière un tube.** Les six codes de
retour qui décident de quelque chose — les deux `comparer`, les deux
`verify_contract`, les deux `verifier-le-jeu-de-questions` — sont lus
immédiatement après le `docker run`, la sortie étant redirigée vers un fichier.
Aucun `| grep`, aucun `| tail` entre la commande et son `rc`. C'est le piège F3,
commis puis corrigé au §11 de la première campagne.

**Aucun `-q` n'a été ajouté** à `make all` : `addopts` en porte déjà un, et
`-qq` supprimerait la ligne `N passed` — celle-là même qui est rapportée.

**Le corpus est compté en excluant `Datas/.cleaned/`.** Sans l'exclusion la
commande rend **47** au lieu de 25 (§4.41).

**`SHOW STATS` n'a pas servi.** Les seize comptes de sommets et d'arêtes
viennent de `MATCH … RETURN count(…)`, tag par tag et type d'arête par type
d'arête. `SHOW STATS` rend 0 sur un space peuplé (§4.27 n° 1).

**`image_exporter=None` n'a pas été employé.** `comparer` passe le témoin MinIO
inerte du harnais, jamais `None`, qui supprimerait l'attribut `src` et
fabriquerait une fausse dérive.

**Les chiffres partagés portent leur définition** : 15 196 ou 15 173 selon que
`Document` compte, 44 ou 47 selon que les ancrages sont distincts ou répétés.
Les deux paires sont écrites côte à côte partout où elles apparaissent.

**Le silence du §4.32.a a été cherché, pas supposé.** Des demandes de capteur
sans runs créés ne se voient qu'en **comptant les runs**, et le compte a été
pris avant le geste (958), juste après (981) et à la fin (982). C'est pour cela
que le §4.6 donne le compte en quatre temps plutôt qu'en deux.

**Et un piège de conclusion, qui est le vrai risque de cette campagne-ci.** Tous
les témoins concordent. Une campagne dont tout est vert est celle où l'on relit
le moins ses instruments — c'est le motif pour lequel les contrôles négatifs du
§4.2 sont rapportés avec leurs chiffres, et pour lequel l'attestation d'avant
(§1.3) a été payée : sans elle, un `comparer` vert après la réingestion ne
distinguerait pas « rien n'a bougé » de « l'instrument ne voit rien ».
