# Première campagne de référence — 2 septembre 2026

> **Archive datée, non réécrite.** Compte rendu de mesure du 2 septembre 2026. L'état en service est décrit par [`livraison.md`](../livraison.md).

Ce fichier est le **compte rendu mesuré** de la première campagne de référence du
pipeline d'ingestion : la réingestion complète du corpus par le code de `main`,
le verdict des deux instruments dessus, et le jeu de trente questions écrit
contre l'index qui en sort.

> **RÉSERVE, ET ELLE VIENT AVANT LES CHIFFRES.** Cette campagne est un
> **contrôle de bon fonctionnement, pas une décision d'architecture**. Trente
> questions suffisent à prouver que la chaîne marche de bout en bout et à voir un
> défaut grossier. **Elles ne suffisent pas à arbitrer un réglage** : un écart de
> deux points est du bruit. Aucun chiffre de ce fichier ne doit servir à choisir
> un `k`, un seuil, un modèle ou une pondération. Le registre, section 1, le dit
> avant nous ; c'est la ligne que la première campagne d'un système finit
> toujours par franchir, et c'est pour cela qu'elle est écrite ici en tête.

Toute valeur porte son étiquette `mesuré`, `calculé` ou `supposé`, sa commande et
sa date.

> **ET CETTE PHRASE ÉTAIT UNE PROMESSE QUE LE FICHIER NE TENAIT PAS.** `mesuré`
> le 3 septembre 2026 sur la version livrée : `` `mesuré` `` y apparaît **31
> fois**, `` `calculé` `` **une seule** et `` `supposé` `` **une seule** — les
> deux dernières dans cette phrase-ci. **Aucune valeur du compte rendu n'était
> donc jamais étiquetée `calculé` ni `supposé`**, alors que les pourcentages, les
> sommes de durées et la durée murale le sont par définition : ils sont dérivés
> de valeurs mesurées, pas relevés par une commande. Une étiquette qu'on annonce
> et qu'on n'emploie jamais est une phrase d'exhaustivité de plus. Les valeurs
> dérivées portent désormais `calculé` **et leur dérivation**, au §3.3 et au
> §6.4. Le poste : GNU Make 4.4.1, `uv` 0.11.28, pile Compose
`rag-ingestion-pipeline`, neuf services debout plus le daemon démarré par cette
campagne (`mesuré`, `docker compose ps`).

**Une correction de date, en préalable.** Le mandat et le registre datent la
fusion du lot 5 et les mesures de leur §7.2 du **3 septembre 2026**. Le commit de
fusion `d8c67c5` porte `2026-09-02 12:29:51 +0000` en auteur **et** en committer,
et l'horloge du poste rendait `2026-09-02 12:40 UTC` au début de cette campagne
(`mesuré`, `git log -1 --format='%ai %ci' main` et `date -u`). Toutes les mesures
de ce fichier sont donc datées du **2 septembre 2026**.

---

## 1. L'état du poste, remesuré et non lu

Le §7.2 du mandat décrit cinq points d'état de poste et prescrit de les
remesurer. Voici les cinq, `mesuré` le 2 septembre 2026 avant tout geste.

| Point du §7.2 | Ce qu'il annonçait | Mesuré |
|---|---|---|
| `dagster-daemon` arrêté | arrêté | **vrai** — `Exited (0) 3 hours ago` (`docker compose ps -a`) |
| index vivant du code du lot 3 | 4 365 chunks, 15 196 sommets, 15 374 arêtes, 23 documents, 13 objets MinIO | **4 365 / 15 196 / 15 173 `PARENT_OF` / 23 / 13**. Les deux chiffres d'arêtes sont justes et ne comptent pas la même chose, et c'est **mesuré** : 15 173 `PARENT_OF` **plus 201 `LINKED_TO` font exactement 15 374**. Le mandat donne le total, `verify_contract` examine les `PARENT_OF` seules |
| `verify_contract` sort en 1 sur **quatre** anomalies | quatre | **vrai, et les quatre sont exactement celles annoncées** |
| `verify_data` / `verify_contract` ne tournent pas côté hôte | vrai | non rejoué : le geste du §4.27 a été employé d'emblée |
| répertoire mort `lot-1-observation-b12761` | subsiste, 484 Mo | **subsiste** — non touché, il ne relève pas de ce lot |

Les quatre anomalies de départ, `mesuré` le 2 septembre 2026 par
`docker run … -v "$PWD/src":/app/src:ro … python -m src.verify_contract`
(le geste du registre §4.27, qui monte le `src` de la branche et non celui du
clone principal) :

```
cles de metadonnees manquantes : ['page_no_end']
elements au jeu de chunks troue: 2
sommets sans page_no_end       : 15173/15173
sommets visuels sans minio_url : 251/264
```

`rc=1`. Le `src` de cette branche est **identique** à celui de `main` à cet
instant (`git diff main..HEAD --stat -- src/` rend le vide), donc la précaution
du §4.27 ne changeait rien ici — et c'est précisément pourquoi il faut la
mesurer plutôt que la supposer.

Porte qualité avant tout geste, `mesuré` : `make all` → **rc=0**, 865 tests,
`mypy` « no issues found in 35 source files », « 73 files already formatted ».

Corpus, `mesuré` : 25 fichiers, 57 381 999 octets, et l'empreinte de la liste
`git ls-files -z -- Datas | xargs -0 sha256sum | sort` vaut
`b66441820e9b8d3114d5dafa0d5c6d461c427b3e770fb2c0e584e947df5f508e`. Les deux
arbres — le clone principal, que Docker monte, et l'arbre de travail de ce lot —
portent **le même corpus à l'octet**. Cette empreinte est le témoin de
non-modification rejoué après chaque geste de la campagne.

---

## 2. Étape 0 — les trois gestes, et l'effet de chacun

Un geste dont on ne mesure pas l'effet n'a pas eu lieu. Voici les trois, avec ce
que chacun a réellement changé.

### 2.1 Geste 1 — redémarrer `docling-service` : effet mesuré NUL sur le schéma

`docker compose restart docling-service`, 12:42:05 → 12:42:37 UTC, `rc=0`,
`healthy` en ~40 s. `init_schema()` a joué : le journal porte
`12:42:32,575 INFO [src.docling_service.nebula] Schema semantique NebulaGraph pret.`
et `GET /health` rend **200** avec `graph_ready: true`, `objects_ready: true`,
`models_ready: true`.

**L'effet sur le schéma est nul, et c'est le résultat.** `DESCRIBE TAG` sur les
**11** tags d'élément plus `Document`, avant et après, rend la même chose
(`mesuré`) : les 11 tags portent leurs **6** colonnes — `label`, `page_no`,
`text`, `minio_url`, `depth`, `page_no_end` — et `Document` ses **7**, avec
**0 colonne manquante sur les 12 tags**. Le poste était déjà dans le second des
deux états que `anomalie_de_colonne` distingue : schéma migré, données vides. La
consigne « redémarrer avant de réingérer » ne périme pas pour autant — elle est
sans coût quand le schéma est à jour, et c'est la seule des deux choses qui vaille
d'être apprise par cœur.

### 2.2 Geste 2 — `wipe_stores` purge QUATRE choses, et la quatrième est celle qui compte

`python -m src.wipe_stores` dans l'image d'extraction, avec **le `src` de cette
branche** et `Datas` monté en écriture. `rc=0`, et sa sortie titre les quatre :

```
collection rag_documents supprimee
13 objets supprimes du bucket documents
space rag_space supprime
22 fichiers retires de /opt/dagster/app/Datas/.cleaned
```

État **avant** le geste, `mesuré` : `Datas/.cleaned/` porte **22** fichiers,
2,4 Mo, et son HTML référence **199** URL `http://minio:9000/…` — alors que le
bucket n'en porte que **13** objets, tous des crops du PDF. **Les 199 images
référencées par le HTML nettoyé n'existaient pas.** C'est le §4.28.b, reproduit
au chiffre près.

État **après** le geste, `mesuré` : `Datas/.cleaned/` **n'existe plus** (0
fichier), ChromaDB porte **0** collection, NebulaGraph **0** space, le bucket
existe et porte **0** objet. Corpus **intact à l'octet** — même empreinte, `git
status --porcelain -- Datas` vide.

**Un quatrième geste, prescrit par `wipe_stores` lui-même, a suivi** :
`docker compose restart docling-service`, parce que la purge a joué
`DROP SPACE` et que `init_schema()` ne tourne qu'au démarrage du service — son
docstring le dit, et sa dernière ligne de sortie le répète. `mesuré` après ce
redémarrage : `SHOW SPACES` rend `rag_space`, et les 11 tags d'élément portent
leurs 6 colonnes, cette fois par `CREATE TAG` et non par `ALTER`. Ce n'est pas un
écart au §7.2 : c'est la complétion du geste 2, et le §7.2 ne la nomme pas.

### 2.3 Geste 3 — l'asset `cleaned_html`, seul chemin qui re-téléverse les images

Le daemon étant arrêté, l'asset a été matérialisé partition par partition, hors
capteur :

```bash
dagster asset materialize -f src/pipeline/definitions.py \
  --select 'livres_html/cleaned_html' --partition "<clé de partition>"
```

**22 partitions sur 22, `rc=0` chacune** (`mesuré`, 12:46:07 → 12:49:55 UTC).

Effet mesuré, et il se ferme sans résidu :

| | avant le geste 3 | après |
|---|---|---|
| fichiers dans `Datas/.cleaned/` | 0 | **22** |
| URL MinIO distinctes référencées par le HTML nettoyé | 0 | **199** |
| objets dans le bucket `documents` | 0 | **199** |
| URL référencées **et** présentes | — | **199** |
| URL référencées **absentes** du bucket | — | **0** |
| objets présents **non** référencés | — | **0** |

La première partition a été mesurée seule avant d'étendre aux 21 autres : 1
fichier, 4 URL référencées, **4** objets dans le bucket. Corpus intact à l'octet
après le geste.

**Ce geste est ce qui rend la réparation du lot 4 opérante.** `extraction.
propager_les_url_dimages` lit les URL **dans le HTML nettoyé**, où
`cleaning.py` les a écrites, puis les pose sur les éléments `picture` par
correspondance positionnelle, gardée par un refus. Sans `.cleaned/` à jour, il
n'y a rien à lire.

---

## 3. Étape 1 — la réingestion, et pourquoi démarrer le daemon n'a PAS suffi

### 3.1 Le fait qui contredit le mandat, et sa cause mesurée

Le mandat écrit : « Le daemon est arrêté et les capteurs sont livrés armés : le
démarrer déclenche l'ingestion. » **C'est faux sur ce poste, et la cause est
mesurée.**

Le Postgres de Dagster a **survécu** — il n'est pas reparti vierge comme au
lot 3 (§7.1). Ses curseurs portaient donc les mtimes de l'ingestion du 31 août :
`livres_html_sensor` **22 entrées**, `pdfs_sensor` **1** (`mesuré`,
`instance.all_instigator_state()`). Et les mtimes du corpus n'ont pas bougé —
identiques **au microseconde près** :

```
1788184102.942725  Datas/htms/MLOps with Databricks/1. MLOps Principles and Components.html
1788184102.942725  ← curseur
```

Les curseurs des deux capteurs porteurs ont donc été **vidés délibérément** —
acte daté 12:51:41 UTC, `dagster sensor cursor --delete`, vérifié à 0 entrée pour
les quatre capteurs — puis le daemon a été **démarré**, acte daté
**12:51:57.765 UTC**, `docker compose up -d dagster-daemon`, `rc=0`.

**Et l'ingestion ne s'est toujours pas déclenchée.** La cause est dans le tick,
et elle est mesurée sur l'objet que Dagster enregistre :

| Capteur | premier tick après démarrage | `run_keys` demandées | runs créés | `skip_reason` |
|---|---|---|---|---|
| `livres_html_sensor` | 12:52:02.534 UTC | **22** | **0** | **`None`** |
| `pdfs_sensor` | 12:52:01.822 UTC | **1** | **0** | **`None`** |
| les deux, ticks suivants | 12:52:33 et après | 0 | 0 | « Sensor function returned an empty result » |

Le capteur a bien construit ses **23** demandes de run — et le curseur, revenu à
22 et 1 entrées, le prouve par un second chemin : il n'est réécrit que dans la
branche qui ajoute une demande. **Dagster en a créé zéro, et n'a donné aucune
raison.**

**La cause est le `run_key`.** `factory.py`, `file_sensor` :
`run_key=f"{source.name}_{partition_key}_{mtime}"`. Ces 23 clés avaient été
consommées le 31 août avec **les mêmes mtimes**, et Dagster cherche un `run_key`
consommé dans **tout** l'historique, sans borne de temps. C'est **mot pour mot**
le défaut que la réparation du lot 0 a fermé dans `reindex_job.py` — registre
§8 : « Une clé d'idempotence déterministe interdit la reprise… le geste de
récupération naturel — remettre le curseur à zéro — ne rattrapait rien » — et il
est **intact dans le capteur d'ingestion**, où il n'était consigné nulle part.
Voir le registre §4.32.a, ouvert par cette campagne.

### 3.2 Ce qui a été fait à la place, déclaré comme écart

Les 23 partitions ont été lancées explicitement, par le **vrai** coordinateur de
runs et le vrai lanceur :

```bash
dagster job launch -w src/workspace.yaml -j livres_html_job \
  --tags '{"dagster/partition": "<clé de partition>"}'
```

**23 lancements, `rc=0` chacun** (`mesuré`). Ce qui est exercé : tout le chemin
d'ingestion du code de `main` — `cleaned_html` → `extracted_document` → service
Docling → les trois stores → le capteur de réindexation. Ce qui ne l'est pas : la
**création** du run par le capteur, que Dagster refuse. L'écart est écrit au §7
de ce fichier, à sa taille exacte.

### 3.3 Le temps, les partitions, et ce qui a rougi

`mesuré` le 2 septembre 2026, lu dans les `run_records` de l'instance Dagster :

| | |
|---|---|
| runs d'ingestion | **23**, dont **23 `SUCCESS`** et 0 échec |
| dont `livres_html_job` | 22 |
| dont `pdfs_job` | 1 |
| durée par run | min **8,8 s**, médiane **21,3 s**, max **93,1 s** (le PDF) |
| somme des durées | **556,4 s** (`calculé` — somme des 23 `end_time − start_time`) |
| durée **murale** de l'ingestion | **451,2 s** (`calculé` — `max(end_time) − min(start_time)`), de 12:55:24 à 13:02:55 UTC |
| plafond de parallélisme | `max_concurrent_runs: 2` (`dagster.yaml`) |

**Ce qui a rougi, et c'est un seul objet : `agent_reindex_job`.** Un run par
tick de 30 s, **tous en échec**, tous sur `ReindexError` levée dans
`reindex_job.lexical_index`. La cause est mesurée et n'est pas un défaut de ce
dépôt : `AGENT_SERVICE_URL=http://agent-api:8000` et **le service
`rag-agent-chat` ne tourne pas sur ce poste** — il n'apparaît dans aucun
conteneur. C'est l'exigence 5 du contrat, et le §7 de ce fichier dit pourquoi
elle n'est **pas éprouvée** ici — le §7 dit le motif, et ce n'est pas une
impossibilité. Le compte de ces runs **croît tant que le
daemon tourne** : il valait **49** au moment de la mesure ci-dessous, ce qui est
un état de poste et non un résultat. Le §10 dit dans quel état la pile est
laissée.

**Et le garde du §4.15 a été observé en vol pour la première fois — il n'a AUCUN
trou, et la preuve directe vit dans le capteur lui-même.** Ce paragraphe a
d'abord prouvé le garde par un **trou entre les départs de runs** de
réindexation, ce qui est une preuve circonstancielle : un trou dit qu'aucun run
n'est parti, jamais pourquoi. Le capteur, lui, écrit sa raison à chaque tick, et
c'est cette preuve-là qui est rapportée ici.

`mesuré` le **3 septembre 2026** — la date de la mesure, non celle des ticks,
qui sont du 2 — par `instance.get_ticks(...)` sur `agent_reindex_sensor`,
**81 ticks** dans la fenêtre 12:40 → 13:40 UTC, et les trois familles se
ferment : **68 + 12 + 1 = 81**.

| Ticks | Compte | Ce qu'ils disent |
|---|---|---|
| `SKIPPED` **consécutifs**, de **12:56:43 à 13:02:28** | **12** | chacun porte un `skip_reason` qui **nomme le garde et le run qui bloque** — « Ingestion en cours (`pdfs_job`) : la reindexation attend qu'elle retombe. Le run `13019b18…` est en STARTED depuis **66 s**. » Les trois derniers donnent l'âge du run : 2 s, 33 s, 66 s |
| `SUCCESS` | **68** | un run de réindexation créé à chacun — ce sont les 68 runs du §10 |
| `SKIPPED` **à `skip_reason = None`**, à **13:32:31** | **1** | le dernier tick, à l'instant où le daemon est arrêté (§10). Il n'appartient pas au garde |

**Et l'ingestion a été lancée en DEUX vagues, ce qui explique le reste**
(`mesuré`, `create_timestamp` et `start_time` des 23 runs) : une **partition
d'essai** créée à 12:55:18, démarrée à 12:55:24, **terminée à 12:55:33** ; puis
les **22 autres** créées à partir de **12:56:37**. Entre les deux, **aucun run
d'ingestion non terminal pendant 64 secondes** — de 12:55:33 à 12:56:37.

C'est pourquoi **deux runs de réindexation ont été créés à l'intérieur de la
fenêtre d'ingestion** — ticks `SUCCESS` à **12:55:43** et **12:56:13** — et c'est
le garde qui a **raison** : il n'y avait à ces instants-là rien à attendre. La
phrase que ce paragraphe portait — « le trou recouvre **exactement** la fenêtre
d'ingestion » — était donc fausse, et elle prêtait au garde un périmètre qu'il
n'a pas eu : le trou entre départs va de **12:56:21 à 13:03:04**, soit **403
secondes**, et il **commence 57 secondes après** l'ouverture de la fenêtre
(12:55:24). La réindexation a repris **9 secondes** après la fin du dernier run
d'ingestion.

Deux décorations de ce paragraphe étaient fausses, et elles sont corrigées :
**une** seconde et non trois séparent la création du premier run d'ingestion
(12:55:18) du départ du run de réindexation qui l'enjambe (12:55:19) ; et **49**
était un compte de **runs**, non de ticks — les ticks de la fenêtre sont **81**.
*(Le compte de runs croît d'un toutes les 30 secondes tant que le daemon
tourne ; c'est un état de poste, pas un résultat.)*

Deux compteurs du registre se reproduisent **au chiffre près** dans le journal du
service, sur le PDF :

- « **39 titres sur 87 (45 %)** ont reçu le rang de REPLI et non un rang mesuré :
  le document ne classe que **3** niveaux » — §4.21, identique ;
- « **18 éléments** enjambent une frontière de page : leur `page_no` est la page
  d'entrée, `page_no_end` la page de sortie » — le compteur du §4.22, désormais
  peuplé.

Corpus **intact à l'octet** après l'ingestion (même empreinte, `git status` vide).

---

## 4. Étape 2 — `verify_contract` : trois anomalies fermées, une survit

`mesuré` le 2 septembre 2026 à 13:03:47 UTC, geste du §4.27 :

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

`rc=1`.

### 4.1 Les trois qui se ferment

| Anomalie | avant | après |
|---|---|---|
| clé `page_no_end` absente des métadonnées ChromaDB | `['page_no_end']` | **aucune** |
| éléments au jeu de chunks troué | **2** | **0** |
| sommets sans `page_no_end` | **15 173 / 15 173** | **0 / 15 173** |

Et le jeu de chunks passe de **4 365 à 4 367**, exactement la prédiction du
§4.28.a. **L'attribution des deux chunks retrouvés est mesurée, pas déduite** :

```
aa3de10738 label=code chunk_count=7 presents=[0,1,2,3,4,5,6]  (il manquait l'index 4)
eb52c4ec8f label=code chunk_count=4 presents=[0,1,2,3]        (il manquait l'index 3)
```

Les deux sont `label=code`, ce qui explique au chiffre près le seul mouvement de
la répartition par label d'`index_report` : `code` passe de **973** (§4.24) à
**975**, tous les autres labels inchangés.

### 4.2 Celle qui survit — et sa cause n'est pas le passé

**52 sommets visuels sur 264 n'ont pas de `minio_url`.** Le décompte se ferme
sans résidu (`mesuré`, remontée des chaînes `PARENT_OF` côté client, le §4.30.j
interdisant un `WHERE` sur une propriété d'arête) :

| origine | tag | avec URL | sans URL |
|---|---|---|---|
| HTML | `Picture` | **199** | **0** |
| HTML | `Table` | 0 | **52** |
| PDF | `Picture` | **10** | 0 |
| PDF | `Table` | **3** | 0 |
| | **total** | **212** | **52** |

**La chaîne d'images HTML du §3.5 est entièrement fermée** : 199 images sur 199
portent leur URL, contre 0 sur 199 mesurés par le lot 1 sur le producteur.

**Les 52 restants sont, à 52 sur 52, des tables HTML — et aucune ingestion ne
pourra jamais les pourvoir.** *(`mesuré` le 3 septembre 2026 sur le graphe :
55 sommets `Table`, 3 avec URL — les trois du PDF —, 52 sans, et les 52 textes
sans URL commencent tous par `|`. Réserve à ne pas perdre : **2 des 3 tables du
PDF commencent aussi par `|`**, donc le `|` n'est pas ce qui discrimine — c'est
le chemin d'origine.)* La cause est un désaccord entre deux sites du code
livré, et l'un des deux l'écrit noir sur blanc :

- `extraction.propager_les_url_dimages` **exclut délibérément** les tables, et son
  docstring dit pourquoi : « Seuls les `picture` sont ciblés, et non tous les
  éléments visuels : un `table` est visuel mais n'est pas une `<img>` du HTML. Le
  compter décalerait toutes les URL. » Une table HTML est rendue par Docling en
  Markdown — les 52 textes commencent tous par `|` — il n'y a **aucune image à
  téléverser** ;
- `verify_contract._lire_les_urls_visuelles` lit `minio_url` « sur tous les
  sommets `Picture` **et** `Table` » et compte l'absence comme une anomalie.

**Conséquence, et il faut l'écrire : `verify_contract` ne peut pas rendre 0 sur ce
corpus**, quoi qu'on ingère. L'attente du mandat — « les quatre doivent se
fermer » — est inatteignable pour la quatrième. Ce n'est ni une ingestion
incomplète, ni une régression : c'est un instrument qui compte une catégorie que
son producteur exclut par construction. **Consigné et non corrigé** — périmètre
strict, et l'arbitrage appartient au pilote : registre §4.32.b.

---

## 5. Étape 3 — `index_report`

`mesuré` le 2 septembre 2026 à 13:05:14 UTC, geste du §4.27, `rc=0`.

| Poste | Valeur |
|---|---|
| chunks indexés | **4 367** |
| documents distincts | **23** |
| sans caractère alphanumérique | **1** (0,0 %) |
| moins de 40 caractères | **21** (0,5 %) |
| taille des chunks | médiane **299**, moyenne 303, min/max **8 / 683** |
| éléments fusionnés par chunk | médiane **2**, maximum **18** |
| modèle | `paraphrase-multilingual-MiniLM-L12-v2`, fenêtre **128** tokens |
| mesure de troncature sur | texte **encodé**, titre de section compris |
| chunks tronqués par le modèle | **137** (3,1 %), tokens médiane **95**, max **149** |
| profondeur de hiérarchie | niveau 5 : **4** documents ; 4 : **5** ; 3 : **8** ; 2 : **5** ; **1 : 1 document — reste plat** |
| langue | **4 367 `en`** |
| labels | `text` 2 604, `code` **975**, `list_item` 484, `table` 196, `caption` 108 |

Trois lectures méritent d'être relevées.

**La troncature est reproduite à l'identique sur un index neuf** : 137 chunks,
3,1 %, médiane 95, maximum 149 — les quatre valeurs du registre §3.4, mesurées
là sur l'index du lot 3. L'instrument est stable et le corpus n'a pas bougé.

**Le chapitre plat est unique, et il est là.** `1 document au niveau 1 — restes
plats`, sur 23. C'est le §3.2 confirmé à pleine portée du corpus : 22 documents
s'imbriquent, un est plat.

**`section_header` n'apparaît pas dans la répartition par label** — il vaut 0.
C'est la charge utile du §4.24, intacte : aucun titre n'est jamais un chunk, donc
l'agent ne peut lire le niveau d'un titre que dans le graphe.

---

## 6. Étape 4 — les trente questions

### 6.1 Ce qui a été échantillonné, et ce qui ne l'a pas été

**On échantillonne les questions, JAMAIS le corpus.** Les 23 documents sont
ingérés et les 30 questions sont cherchées contre les **4 367** chunks. Grosse
meule de foin, échantillon d'aiguilles.

Les questions sont tirées de **deux chapitres par ouvrage plus une section
d'environ cinq pages du PDF**, comme la spécification le prescrit :

| Source échantillonnée | `element_id` cités |
|---|---|
| `MLOps with Databricks/4. Model Serving：Architectures and Implementation.html` | 15 |
| `MLOps with Databricks/7. Foundation Models and Context Engineering.html` | 12 |
| `Practical MLflow…/6. Evaluating GenAI Applications with MLflow.html` | 8 |
| `Practical MLflow…/8. Deploying a GenAI Application with MLflow.html` | 8 |
| `pdfs/Hands-On_RAG_for_Production…pdf`, **pages 41 à 45** | 4 |

Le motif du choix : le chapitre 4 et le chapitre 8 traitent tous deux du
déploiement et du service de modèles dans les deux ouvrages — ce sont les
« sosies plausibles » que le **mandat** §4 annonce comme voulus ; le chapitre 7 est
le plus profondément imbriqué du corpus ; et les pages 41–45 du PDF
(« Response Quality and Reduced Hallucinations » et ses quatre raisons, plus
« High Latency ») sont voisines thématiquement des deux, ce qui rend possibles des
questions **inter-documents**.

Les chapitres ont été **lus dans le store**, pas de mémoire : le texte de chaque
chunk avec son `element_id`, son `label`, son `depth` et son `section_title`, par
`collection.get(where={"source_path": …})`.

### 6.2 Le jeu, et sa conformité à la spécification

Le jeu vit dans
[`2026-09-02-jeu-de-questions.yaml`](2026-09-02-jeu-de-questions.yaml).

**Il est en YAML et non en JSON, l'arbitrage est bon — et le motif que ce
paragraphe donnait n'était pas le vrai.** Écrit d'abord en JSON, il a fait
**refuser le commit**. `rc=1`, `HEAD` inchangé : le garde a fait son travail.
Aucun `--no-verify`, aucune baseline, aucune règle relâchée. C'est l'arbitrage
déjà pris au registre §3.6 bis pour `tests/fixtures/arbres_docling.yaml`.

**Mais le YAML ne passe PAS parce que ses faux positifs y sont déclarés.**
`mesuré` le 3 septembre 2026, `detect-secrets-hook` v1.5.0, sur le **même
contenu** rendu dans les deux formats :

| Fichier | `rc` | détections |
|---|---|---|
| le contenu en **JSON** | **1** | **11** « Hex High Entropy String » — 1 empreinte + **10 `element_id`** |
| le **YAML livré** | **0** | 0 |
| le **YAML privé de son unique pragma** | **1** | **1** — l'empreinte, et **elle seule** |

La troisième ligne est celle qui tranche : sans le pragma, le YAML ne rend
**qu'une** détection. **Les dix `element_id` ne sont jamais détectés en YAML.**

**La cause mesurée est une propriété du transformateur YAML de `detect-secrets`,
et c'est plus étroit que « YAML n'est pas scanné »** : il rend les **valeurs de
mapping** et **pas les éléments de séquence**. Vérifié sur un fichier d'essai de
trois chaînes hexadécimales — deux en éléments de liste, une en valeur de
mapping — **YAML : 1 détection** (la valeur de mapping) ; **le même contenu en
JSON : 3**. Or les `element_id` de ce jeu vivent en **éléments de séquence**
(`element_ids:` puis `- 3af1392862`), et l'empreinte en **valeur de mapping**.

**Conséquence sur ce que l'en-tête du fichier affirmait :** il parlait des
« pragmas » au **pluriel** comme couvrant les `element_id`. Il n'y a **qu'un
seul** pragma, sur l'empreinte (`grep -c 'pragma: allowlist secret'` rend 2, dont
**une occurrence en prose** dans l'en-tête). **Dix des onze faux positifs ne sont
déclarés nulle part — parce que rien ne le demande.** L'en-tête est corrigé.

Bénéfice de plus, gratuit et inchangé : le hook `check-yaml` valide ce fichier à
chaque commit, ce que le JSON n'avait pas.

| Strate | Attendu (registre §1) | Livré |
|---|---|---|
| multi-passages, 2 ou 3 sections différentes | 12 | **12** |
| simple, un passage | 8 | **8** |
| sans réponse | 4 | **4** |
| de suivi, avec `chat_history` | 4 | **4** |
| reformulée | 2 | **2** |
| | **30** | **30** |

`mesuré` : **44 `element_id` distincts**, tous au format `^[a-f0-9]{10}$`, tous
présents dans l'index, et les 12 multi-passages couvrent **2 ou 3 sections
distinctes** chacune — dont deux qui franchissent une frontière de **document**.
Les questions pièges sont **reportées au second tour**, comme la spécification le
prescrit : c'est la strate où un modèle écrit le plus facilement un faux piège, et
elle demande une relecture humaine.

**Les quatre questions sans réponse sont vérifiées sans réponse, par deux voies.**
Une question « sans réponse » qui aurait une réponse punirait une abstention
correcte — elle mesurerait l'inverse de ce qu'elle prétend. `mesuré` sur les 4 367
chunks : balayage lexical des termes discriminants, puis lecture des cinq plus
proches voisins vectoriels.

**Le critère du balayage, parce qu'un balayage dont le critère n'est pas écrit
n'est pas reproductible** : recherche d'une expression régulière, **en minuscules
et sur mot entier**, dans le texte des 4 367 chunks rendus par
`collection.get(include=["documents"])`.

*(La ligne de `q23` donnait comme terme discriminant « **un F1 chiffré associé à
arXiv** ». **Ce n'est pas un terme, c'est un jugement** — et c'était la seule des
quatre lignes qu'un tiers ne pouvait pas rejouer depuis le texte. Elle est
remplacée par le balayage, qui la **confirme** : `mesuré` le 3 septembre 2026,
**97** chunks nomment arXiv, **aucun d'eux** ne porte `f1` ni `f-score`, donc
aucun ne porte de score chiffré. Le fait tenait ; c'est sa preuve qui n'était pas
rejouable. Réserve honnête : le compte de `f-score` que l'audit indépendant
annonçait — 6 — ne se reproduit sous aucune des variantes essayées ici
(`\bf-score\b`, `\bf[- ]?scores?\b`, `\bf1[- ]score\b` rendent **3**) ; le
chiffre écrit ci-dessus est le mien, avec son critère.)*

| Question | terme discriminant | porteurs |
|---|---|---|
| prix horaire en USD d'un `CU_8` en `eu-west-1` | `usd`, `eu-west` | **0**, **0** |
| contrôleur d'ingress Kubernetes de Model Serving | `ingress`, `nginx`, `istio`, `traefik` | **0** partout |
| F1-score atteint par l'arXiv Curator | `\bf1\b`, `\bf-score\b`, `arxiv` | **4**, **3**, **97** — et **0** chunk arXiv portant l'un des deux |
| nombre de pages du manuel Samsung | `samsung … page` | **0** |

Et leurs plus proches voisins sont **précisément les passages plausibles** — la
table des coûts Databricks, les sections de l'arXiv Curator, et pour la
quatrième le passage même qui mentionne le manuel Samsung comme exemple de donnée
manquante. C'est le piège que l'abstention doit franchir, et il est mesuré.

**Une conséquence à consigner, qui n'est pas un défaut : le corpus est
entièrement anglais** — `index_report` rend **4 367 chunks `en`** sur 4 367. La
mesure translinguistique est donc coupée en deux : « question française →
document anglais » reste possible, l'inverse disparaît. Le jeu échantillonne la
moitié survivante avec **une** question, `q30`, en français sur un passage
anglais. **À n = 1, cet axe est échantillonné, pas mesuré** : c'est une réserve,
pas un résultat.

### 6.3 Ce qui garde le jeu, et ce qui ne le garde pas

Deux objets, et **aucun ne remplace l'autre**. La distinction est le sujet, parce
qu'un jeu de questions ne rougit pas tout seul : il devient faux en silence.

**`tests/unit/test_jeu_de_questions.py` garde la FORME** — 19 tests, dans
`make test`. Les effectifs attendus y sont écrits en **littéraux** tirés du
registre §1 : les dériver du fichier rendrait chaque assertion vraie par
construction, le motif des treize gardes creux de ce chantier.

**`scripts/campagne/verifier-le-jeu-de-questions.py` garde la PROVENANCE** — il
relit chaque ancrage dans l'index vivant, champ par champ, et sort en **1** au
premier désaccord. Il n'est pas un test parce qu'il ne peut pas l'être :
`chromadb` n'appartient pas aux dépendances du dépôt, et un test qui l'importerait
ne serait collectable sur aucun poste sans l'image d'extraction.

`mesuré` sur l'index de la campagne : **`rc=0`, les 44 ancrages concordent, champ
par champ.**

> **ET AUCUNE PORTE NE L'APPELLE — c'est un garde réel que rien ne déclenche.**
> `mesuré` le 3 septembre 2026 :
>
> ```bash
> grep -rn 'verifier-le-jeu-de-questions' Makefile .pre-commit-config.yaml >   pyproject.toml $(git ls-files '*.sh')      # rc=1, aucune occurrence
> ```
>
> **La justification ci-dessus explique pourquoi ce n'est pas un TEST ; elle
> n'explique ni pourquoi ce n'est pas une cible `make`, ni pourquoi ce n'est pas
> une ligne de procédure d'avant-campagne.** Or ces deux-là ne demandent pas
> `chromadb` dans le venv du dépôt : une cible `make` peut lancer le geste du
> §4.27, exactement comme la campagne l'a fait.
>
> **Ce que l'état actuel coûte, et c'est précisément ce que le script existe pour
> empêcher :** le jour où le corpus est renommé ou réingéré, les `element_id`
> changent, le jeu de questions devient faux — et **`make all` reste vert**. Le
> jeu ne rougit pas ; il devient faux en silence, ce que ce §6.3 annonce en tête
> et que le montage ne referme qu'à moitié.
>
> **À trancher avec le §4.32.c du registre : c'est la même décision de portée** —
> ce que la porte qualité de ce dépôt accepte de couvrir. Elle n'appartient pas à
> une campagne de mesure, et elle est écrite là pour le pilote.

**Les deux moitiés sont prouvées par mutation du fichier livré**, texte vérifié
changé à chaque fois et empreinte restaurée après chacune. Onze mutations
rougissent les gardes de forme, et **la douzième les laisse entièrement verts** —
c'est elle qui prouve que la frontière annoncée est la vraie :

| Mutation du jeu livré | `test_jeu_de_questions.py` | script de provenance |
|---|---|---|
| une question change de strate | **rouge**, 2 tests | — |
| une `sans_reponse` porte un ancrage | **rouge**, 1 | — |
| une `simple` perd son ancrage | **rouge**, 3 | — |
| un `element_id` à 9 hexadécimaux | **rouge**, 1 | — |
| une multi-passages sur UNE seule section | **rouge**, 1 | — |
| une `de_suivi` perd son historique | **rouge**, 2 | — |
| plus aucune question française | **rouge**, 1 | — |
| le périmètre déclaré dépasse le réel | **rouge**, 1 | — |
| un doublon d'ancrage dans une question | **rouge**, 4 | — |
| le fichier certifie ses propres effectifs | **rouge**, 3 | — |
| le jeu est **vide** (témoin de creux) | **rouge**, 5 | — |
| **un ancrage désigne la mauvaise section** | **VERT, 0 rouge** | **rc=1**, cause nommée |
| le volume d'index annoncé est faux | non couvert | **rc=1** |
| un ancrage désigne un `element_id` inexistant | non couvert | **rc=1** |
| *témoin — aucune mutation* | vert, 19 tests | **rc=0** |

*(Le `rc` du script est lu **sans pipe**. Une première mesure le lisait derrière
un `grep`, qui rendait `0` sur les trois rouges : c'est le piège F3 du registre —
« le code de retour d'un `cmd | tail` est celui de `tail` » — et il a été commis
puis corrigé ici.)*

### 6.4 Le rappel vectoriel brut — ce qu'il mesure, et ce qu'il ne mesure pas

`mesuré` le 2 septembre 2026 par
`scripts/campagne/mesurer-le-rappel-vectoriel.py`, `rc=0`, contre les **4 367**
chunks — **et cette étiquette porte sur la SORTIE du script, pas sur les agrégats
qui en sont tirés** : voir l'encadré ci-dessous. La question est encodée **exactement comme la production encode** :
`get_embedding_model().encode(...)` sans normalisation, la collection ne déclarant
pas `hnsw:space` — ChromaDB retombe donc sur `l2` (§4.29.f).

> **LES AGRÉGATS DE CETTE SECTION SONT `calculé`, ET ILS ÉTAIENT DONNÉS `mesuré`
> SOUS UNE COMMANDE QUI NE LES PRODUIT PAS.** `mesuré` le 3 septembre 2026 : la
> commande citée ci-dessus rend `rc=0` et **610 lignes de JSON — une entrée par
> question**, et **aucune** des valeurs des deux tables qui suivent n'y figure.
> Le script imprime `trouves@k`, `rappel@k` et `au_moins_un@k` **par question** ;
> il n'imprime ni micro, ni macro, ni « au moins un », ni la table par strate.
> Un chiffre présenté `mesuré` sous une commande citée qui ne le rend pas est un
> chiffre que personne ne peut rejouer.
>
> **Ce qui est `mesuré` est la sortie du script** ; ce qui suit en est **dérivé**,
> et voici la dérivation, sur les seules questions à réponse — 26 sur 30, les 4
> `sans_reponse` n'ayant pas de rappel :
>
> | Valeur | Dérivation depuis les lignes du script |
> |---|---|
> | **rappel micro** à `k` | `somme(trouves@k) / somme(attendus)` sur les 26 lignes |
> | **rappel macro** à `k` | `moyenne(rappel@k)` sur les 26 lignes — chaque question pèse 1, quel que soit son nombre d'ancrages |
> | **au moins un** à `k` | `compte(au_moins_un@k vrai) / 26` |
> | **table par strate** | les mêmes deux premières formules, restreintes aux lignes d'une strate |
>
> Les valeurs elles-mêmes sont **inchangées** : elles ont été redérivées de la
> sortie du script le 3 septembre 2026 et concordent au dixième de point près.
> Ce qui change est l'étiquette et l'écriture de la dérivation — sans quoi la
> table n'est pas rejouable, et c'est la seule chose qui la rendait fausse.

**Ce que cette mesure NE couvre pas, et il faut le lire avant les chiffres :** ni
BM25, ni la reconstruction par le graphe, ni le reranker, ni l'abstention. Tout
cela vit dans `rag-agent-chat`. C'est un **plancher dense**, mesuré de ce côté-ci
de la frontière.

Toutes les valeurs des deux tables qui suivent sont `calculé` — dérivées comme
ci-dessus de la sortie `mesuré`e du script.

| k | rappel micro (`calculé`) | rappel macro (`calculé`) | au moins un passage (`calculé`) |
|---|---|---|---|
| 5 | **26 / 47 = 55,3 %** | 61,5 % | **20 / 26 = 76,9 %** |
| 10 | **29 / 47 = 61,7 %** | 66,0 % | 20 / 26 = 76,9 % |
| 20 | **34 / 47 = 72,3 %** | 72,4 % | **21 / 26 = 80,8 %** |

*(26 questions à réponse sur 30 ; les 4 sans réponse n'ont pas de rappel.)*

Par strate, à k = 10 :

| Strate | n | rappel micro (`calculé`) | au moins un (`calculé`) |
|---|---|---|---|
| simple | 8 | **8 / 8 = 100 %** | **8 / 8** |
| multi-passages | 12 | 18 / 31 = 58,1 % | 10 / 12 |
| reformulée | 2 | 2 / 3 = 66,7 % | 1 / 2 |
| de suivi | 4 | **1 / 5 = 20,0 %** | 1 / 4 |

**Trois lectures, et aucune n'est une conclusion de réglage.**

**Le plancher de contrôle tient : 8 sur 8, à k = 5.** C'est ce que la strate
`simple` existe pour dire, et c'est la preuve que la chaîne fonctionne de bout en
bout — le texte est extrait, découpé, encodé, indexé avec ses métadonnées, et
retrouvé par une question posée dans d'autres mots que le passage.

**Le 20 % des questions de suivi n'est pas un défaut de l'index : c'est le
périmètre de la mesure — et c'est désormais MESURÉ, alors que ce paragraphe
l'affirmait.** Le script encode la question **seule**, sans son `chat_history` —
« Et laquelle des trois demande un identifiant de plus dans la charge ? » ne
porte, hors contexte, presque aucun signal. La résolution de l'antécédent est le
travail de l'agent.

**L'affirmation a été éprouvée, et elle tient.** `mesuré` le 3 septembre 2026,
même index, même modèle, même `k` = 10, **seule l'entrée change** — la question
seule contre `chat_history` concaténé + question :

| | question seule | historique + question |
|---|---|---|
| rappel micro de la strate `de_suivi` | **1 / 5 = 20,0 %** | **3 / 5 = 60,0 %** |
| distance L2 du 1er voisin, `q26` | 20,01 | **7,56** |
| distance L2 du 1er voisin, `q27` | 15,68 | **4,13** |
| distance L2 du 1er voisin, `q28` | 15,94 | **9,12** |

Le rappel triple et les trois distances s'effondrent : le signal manquant était
bien l'antécédent, et il est bien dans l'historique. *(`q25` reste à 0/2 dans les
deux cas — l'historique ne suffit pas partout, et c'est une réserve, pas une
infirmation.)*

**Et c'est le point, plus que le chiffre.** Ce paragraphe affirmait « c'est le
périmètre de la mesure » **sans étiquette**, alors que rien ne l'avait éprouvé :
c'était un `supposé` présenté comme une explication. La conclusion était juste —
ce qui est exactement ce qui rend la faute difficile à voir, et c'est la leçon la
plus chère de ce chantier, payée au §3.2 puis au §4.28.e : **étiquette `supposé`
tout ce qui n'a pas été mesuré, même quand ta conclusion te paraît sûre.** Ici la
mesure existait pour trois lignes de script ; elle n'avait pas été faite.

Ce chiffre dit donc que la strate est **dure comme prévu, pour la raison
prévue**, pas que quelque chose est cassé.

**La question française rend 2 sur 2 dans les cinq premiers.** `q30`, posée en
français sur un passage anglais dont elle ne partage aucun mot, retrouve ses deux
ancrages. La moitié survivante de la mesure translinguistique fonctionne — **à
n = 1**, ce qui est un échantillon et non une mesure.

**Et la même réserve vaut pour l'autre moitié de cette strate, ce que ce compte
rendu n'écrivait que d'un côté.** La strate `reformulee` compte **n = 2**, et ses
deux questions n'éprouvent pas le même axe : `q29` est une **reformulation**
monolingue — même langue que le passage, vocabulaire délibérément disjoint — et
`q30` est **translinguistique**. Chaque axe est donc à **n = 1**, et le
« 2 / 3 = 66,7 % » de la ligne `reformulee` agrège deux choses différentes : `q29`
rend 0 / 1, `q30` rend 2 / 2.

**Aucun des deux axes n'est mesuré ; les deux sont échantillonnés.** Le compte
rendu appliquait cette réserve à l'axe translinguistique et la taisait pour la
reformulation — or c'est le même n, et le même argument. Un lecteur pressé
lirait « la reformulation rend 66,7 % » comme un résultat de strate ; c'est une
question qui échoue et une qui réussit, sur deux axes distincts.

**Une observation qu'il faut écrire sans en tirer de réglage.** La distance L2 du
premier voisin, `mesuré` : questions à réponse, min **6,11**, médiane **9,72**,
max **20,01** ; questions sans réponse, **8,73**, **11,44**, **13,11**, **14,86**.
**Les deux plages se recouvrent largement.** Sur cet échantillon, la distance
brute du premier voisin dense ne sépare donc pas « répondable » de « non
répondable ». C'est un fait mesuré sur 30 questions, et ce n'est **pas** un
argument pour ou contre un seuil : trente questions ne suffisent pas à en
dimensionner un.

---

## 7. Ce que la campagne n'a PAS pu mesurer

Une réserve écrite vaut mieux qu'une conclusion tirée.

**L'exigence 5 du contrat — `POST /reindex` en fin de pipeline — n'est PAS
ÉPROUVÉE par cette campagne, et elle n'est pas déclarée tenue. Elle n'est pas
pour autant inéprouvable sur ce poste, et ce paragraphe l'écrivait.** `mesuré`
le 3 septembre 2026, trois commandes :

```bash
ls /home/ubuntu/RAG/rag-agent-chat                       # rc=0 — le depot EXISTE
grep -n 'agent-api' /home/ubuntu/RAG/rag-agent-chat/docker-compose.yml
test -e /home/ubuntu/RAG/rag-agent-chat/.env             # rc=1 — pas de .env
```

Le dépôt `rag-agent-chat` **est présent sur ce poste** ; son `docker-compose.yml`
déclare un service **`agent-api`** raccroché à `rag_network` en `external: true`
— c'est-à-dire **exactement l'hôte qu'`AGENT_SERVICE_URL=http://agent-api:8000`
attend** — et il **n'a pas de `.env`**, seulement un `.env.example`.

**Le motif de la non-épreuve est donc un choix de périmètre, pas une
impossibilité** : monter la pile d'un **autre dépôt**, en lui fabriquant le
`.env` qui lui manque, pour éprouver une exigence depuis celui-ci, dépasse le
mandat de cette campagne et engagerait un service que personne n'a audité. La
décision est de ne pas le faire, et elle est écrite ici plutôt que déguisée en
fatalité. **Ce qui reste vrai sans réserve : l'exigence n'est pas tenue par
cette campagne**, et le prochain qui voudra l'éprouver sait maintenant ce qu'il
lui manque — un `.env` dans l'autre dépôt, et la décision de l'y mettre.

`mesuré` : les **49**
runs `agent_reindex_job` de la fenêtre de campagne ont **tous** échoué sur
`ReindexError`, parce que `AGENT_SERVICE_URL=http://agent-api:8000` désigne un
service qui ne tourne pas — `rag-agent-chat` n'existe dans aucun conteneur du
poste. Ce qui **est** mesuré, et qui n'est pas rien : le déclenchement fonctionne
— le capteur arme le job, et il **saute tant qu'un run d'ingestion est en vol**,
en nommant à chaque tick le garde et le run qui bloque : **12 ticks `SKIPPED`
consécutifs**, de 12:56:43 à 13:02:28 (§4.15, observé en vol pour la première
fois, §3.3), et
l'échec **rougit son run** au lieu de se perdre dans une métadonnée verte, ce qui
était la charge utile de la réparation du lot 0. Ce qui n'est pas mesuré est la
seule chose qui compte pour l'agent : que l'index BM25 d'en face ait été
reconstruit.

**La création du run par le capteur d'ingestion n'a pas pu être exercée**, et la
cause est le `run_key` déterministe du §3.1. Ce que la campagne a exercé du
capteur : le balayage du glob, l'écartement des deux `Index.html` par
`matter.is_front_back_matter` (visible au journal du daemon), la gestion du
curseur, et la construction des 23 demandes. Ce qu'elle n'a pas exercé : leur
transformation en runs.

**La qualité des trente questions n'est garantie par rien d'automatique.** Les
gardes tiennent leur forme et leur provenance ; qu'une question soit dure et
qu'une réponse attendue soit juste demande une relecture humaine. C'est le motif
même pour lequel la spécification reporte les questions pièges au second tour, et
il vaut aussi pour les cinq strates livrées.

**L'ablation du graphe n'est pas mesurée, et ce n'était pas le mandat.** La
contrainte d'ordre 6 du contrat est désormais **levée** — la profondeur réelle du
graphe est constatée : 22 documents sur 23 s'imbriquent, `depth` atteint 5, et
`index_report` en donne la distribution. L'ablation elle-même se mesure côté
agent, avec le jeu que cette campagne livre.

**La contrainte 7 — le coût en fenêtre de contexte d'un fil d'Ariane réel — n'est
pas mesurée ici** : les chiffres du contrat (34 caractères sans fil d'Ariane, 134
à deux niveaux, 275 à cinq) sont `mesuré`s **côté agent**, et c'est là qu'ils se
remesurent.

**Le rappel mesuré est un plancher dense**, non le rappel du système : §6.4.

---

## 8. Les écarts au mandat, à leur taille exacte

Trois, et aucun n'est un écart de périmètre.

**Écart 1 — les curseurs des capteurs ont été vidés, et le daemon n'a pas suffi
à déclencher l'ingestion.** Le mandat annonce « le démarrer déclenche
l'ingestion » ; c'est faux sur ce poste et la cause est mesurée (§3.1). J'ai vidé
les curseurs des deux capteurs porteurs — **état Dagster, jamais le corpus** —
puis démarré le daemon comme acte daté. Cela n'a toujours pas suffi, et les 23
partitions ont été lancées par `dagster job launch` avec le tag de partition.
**Taille exacte : la création du run par le capteur n'est pas exercée ; tout le
reste du chemin l'est.** Le corpus n'a pas été touché — j'ai écarté d'emblée le
geste qui aurait « marché » : un `touch` sur les 23 fichiers.

**Le motif que je donnais — « le mtime est ce que le capteur lit » — est le plus
faible des trois.** Les deux autres valent d'être écrits, parce que ce sont eux
qui font de ce refus la bonne décision et non seulement une obéissance :

1. **un `touch` est invisible à git ET à mon propre témoin de non-modification.**
   L'empreinte que cette campagne rejoue après chaque geste porte sur le
   **contenu** (`git ls-files -z -- Datas | xargs -0 sha256sum | sort`), et
   `git status` ne voit pas davantage un changement de `mtime`. C'est donc
   **exactement la mutation du corpus qu'un audit ne peut pas voir** : j'aurais
   pu la commettre, la déclarer, et personne n'aurait eu de moyen de la vérifier
   — ni de la défaire ;
2. **toucher aurait masqué §4.32.a pour un TROISIÈME lot d'affilée.** Le défaut
   ne se voit que lorsqu'on réingère un corpus **dont les `mtime` n'ont pas
   bougé**. Au lot 3 il était caché par un Postgres reparti vierge ; un `touch`
   ici l'aurait caché par des `mtime` neufs, et la phrase du mandat « le démarrer
   déclenche l'ingestion » aurait survécu un lot de plus, cette fois avec une
   campagne de référence pour la corroborer.

Le mandat interdit de modifier le corpus ; ces deux raisons disent **pourquoi**
l'interdiction est bonne ici, et elles auraient suffi seules.

**Écart 2 — un quatrième geste s'est ajouté aux trois du §7.2** : un second
redémarrage de `docling-service` après la purge, parce que `wipe_stores` joue
`DROP SPACE` et que `init_schema()` ne tourne qu'au démarrage. Ce n'est pas mon
invention : le docstring de `wipe_stores` le prescrit et sa dernière ligne de
sortie le répète. **Taille exacte : un `docker compose restart`, mesuré avant et
après.**

**Écart 3 — j'ai livré du code, ce que le mandat n'annonçait pas.** Le lot 6 est
décrit comme produisant « un récit et non du code ». Il livre en plus **19
tests**, **deux scripts** et **un artefact de données**. Le motif : un jeu de
questions ne rougit pas tout seul, et le mandat exige que « tout garde neuf
rougisse à la mutation du code livré ». Sans garde, la spécification du registre
§1 resterait une phrase d'exhaustivité dans un document — exactement ce que le
lot 5 a passé trente commits à fermer. **Taille exacte : 4 fichiers neufs,
aucune ligne de `src/` touchée** (`git diff main..HEAD --stat -- src/` rend le
vide).

---

## 9. Ce que la campagne laisse au registre

**Quatre** constats neufs, mesurés, **hors du diff** — périmètre strict.

*(Cette section annonçait **trois** constats — deux nommés, un « troisième point,
plus petit » — alors que le registre en porte **quatre**. Le manquant était
`§4.32.d`, les neuf dates fausses. Un résumé qui ne compte pas ce que sa source
porte est la famille de dénombrement que ce chantier traque, et elle se corrige
en recomptant : le juge est ci-dessous.)*

- **§4.32.a** — le `run_key` déterministe du capteur d'ingestion interdit toute
  réingestion d'un fichier non modifié, et la remise à zéro du curseur ne
  rattrape rien. Sévérité : il rend le geste « réingérer le corpus » impossible
  par le chemin nominal, et il est **silencieux** — `skip_reason=None`, 22 runs
  perdus sans un mot.
- **§4.32.b** — `verify_contract` compte les `Table` parmi les sommets visuels
  alors que le producteur exclut les tables par construction et l'écrit à son
  site. Il ne peut donc pas rendre 0 sur ce corpus.
- **§4.32.c** — `make lint` et `make format-check` portent sur `src/ tests/` et
  **ne voient pas `scripts/`**, alors que le hook `ruff` voit tout ce qui est
  indexé. C'est la divergence de portée de la famille D7, une nouvelle fois, et
  ce lot y ajoute deux fichiers. Les deux scripts livrés passent `ruff check` et
  `ruff format --check` — `mesuré` — et la porte ne le dira pas à ma place.
- **§4.32.d** — tout le lot 5 est daté du 3 septembre 2026 dans les deux
  documents de gouvernance, **neuf mentions**, et aucun commit du dépôt ne porte
  cette date. Inerte — aucune décision n'en dépend — et corriger la date d'un lot
  fusionné est un geste de pilote, pas de branche.

**Le juge de ce compte est une mesure**, et il doit égaler le nombre annoncé
ci-dessus :

```bash
grep -c '^#### 4.32' documentation/axes_amelioration.md
```

`mesuré` le 3 septembre 2026 : **4**.

---

## 10. L'état dans lequel la pile est laissée

`mesuré` le 2 septembre 2026 à 13:32 UTC, `docker compose ps -a`.

**Les neuf services sont debout**, dans le projet Compose
`rag-ingestion-pipeline`, monté depuis le clone principal : `graphd`, `metad`,
`storaged`, `chromadb`, `minio`, `nebula-studio`, `postgres-dagster`,
`dagster-webserver`, `docling-service` (celui-ci `healthy`, redémarré deux fois
par cette campagne). Aucun bind mount ne pointe vers un arbre de travail. La
pile n'est **pas** démontée.

**`dagster-daemon` est arrêté, et c'est un acte déclaré.** Il a été démarré à
12:51:57 UTC pour l'étape 1 — le seul lot qui en a le droit — et arrêté à
13:32:31 UTC, `rc=0`, **aucun run en vol au moment de l'arrêt** (91 runs depuis
le démarrage, tous terminaux : 23 `SUCCESS` d'ingestion et **68** `FAILURE` de
réindexation). Le motif de l'arrêt est mesuré et il est double : chaque tick de
30 s produit un run rouge de plus, et à 68 en quarante minutes l'historique de
runs cesse d'être lisible pour le lot suivant ; et l'index redevient à l'abri
d'un tick. Le §4.31.N du registre note qu'un daemon laissé tourner quatre heures
avait déjà dû être arrêté par le pilote pour protéger l'antécédent.

**L'index laissé au poste**, `mesuré` après l'arrêt du daemon :

| | |
|---|---|
| chunks ChromaDB | **4 367** |
| sommets | **15 196** |
| arêtes `PARENT_OF` | **15 173** |
| arêtes `LINKED_TO` (légende → illustration) | **201** |
| arêtes, toutes | **15 374** |
| documents | **23** |
| objets MinIO | **212** |
| sommets `Paragraph` | 7 251, dont **0** à `page_no_end` NULL |
| modèle inscrit sur la collection | `paraphrase-multilingual-MiniLM-L12-v2` |
| `verify_contract` | **`rc=1`**, une seule anomalie : les 52 tables HTML (§4.2) |

**Une stabilité mesurée qui mérite d'être relevée.** La réingestion complète —
purge des quatre stores puis réécriture par le même code — rend **exactement**
les mêmes comptes structurels que l'index d'avant : 15 196 sommets, 15 173
arêtes, 3 750 ancres, 7 251 `Paragraph`. Seul le jeu de *chunks* a bougé, de
4 365 à 4 367, et pour la cause connue. **Ce que cela établit, à sa taille
exacte :** les comptes sont identiques, et **deux** `element_id` nommés au
registre §4.28.a depuis l'ancien index — `aa3de10738` et `eb52c4ec8f` — sont
présents dans le nouveau. L'égalité des **ensembles** de 3 750 identifiants
n'est **pas** mesurée : elle demanderait un instantané de l'ancien ensemble, qui
n'a pas été pris avant la purge. C'est deux identifiants prouvés, pas 3 750, et
l'écrire autrement serait la faute du §4.28.e.

**Ce qui subsiste et ne relève pas de ce lot** : le répertoire mort
`.claude/worktrees/lot-1-observation-b12761`, 484 Mo, que git ne connaît plus et
que rien n'ancre — il se retire en `sudo` à l'occasion. Et un arbre de travail
dédié au balayage de graines, `/home/ubuntu/RAG/lot6-graines`, en `HEAD` détaché,
**sans `make install`** (`uv sync` seul, §9), à retirer avec la branche.

**Et un troisième objet, que cette section aurait dû déclarer et ne déclarait
pas : `runs.py`.** C'était mon script de mesure des `run_records` de l'instance
Dagster — celui dont sortent les durées, les partitions et la chronologie du
§3.3. Je l'avais laissé **non versionné à la racine du clone principal**, où il
salissait le `git status` de `main` pour le suivant. Le pilote l'a lu, puis
**déplacé hors du dépôt** — il ne l'a pas supprimé —, et le `git status` du clone
principal est propre depuis (`mesuré` le 3 septembre 2026 : plus de `runs.py` à
la racine, `git status --porcelain` ne rend que `?? .claude/`).

**La forme est ce qu'il faut retenir, et elle vaut plus que l'objet.** Un script
de mesure a deux destinations légitimes : **versionné** s'il doit être rejoué —
c'est le cas des deux scripts de `scripts/campagne/`, et le registre §10 du
mandat dit pourquoi : « une mesure qui décide du plan doit laisser un artefact
rejouable » — ou **hors de l'arbre** s'il est jetable. La troisième, « non
versionné dans l'arbre », n'en est pas une : elle laisse au suivant un
`git status` sale qu'il n'a pas les moyens d'interpréter, et elle rend la mesure
ni rejouable ni absente.

---

## 11. Deux pièges de mesure rencontrés, et la façon dont ils ont été pris

Ils ne sont pas des défauts du dépôt : ce sont deux erreurs de ma main, corrigées
avant d'entrer dans un chiffre. Elles sont écrites parce que la seconde est un
piège que le registre nomme déjà, et que je l'ai commise quand même.

**1 — un `rc` lu derrière un `grep`.** La première mesure du code de sortie de
`verifier-le-jeu-de-questions.py` sous mutation le lisait derrière un
`| grep -v telemetry`. Elle rendait **`rc=0` sur les trois mutations qui
échouent**, parce que `${PIPESTATUS[0]}` après l'appel d'une fonction dont la
dernière commande est un `grep` rend le statut du `grep`. C'est le piège **F3**
du registre — « le code de retour d'un `cmd | tail` est celui de `tail` » — et
c'est ce que le mandat interdit en une ligne : *ne filtre pas la sortie d'une
porte*. Remesuré sans aucun tube, la sortie redirigée vers un fichier : `rc=1`
sur les trois, `rc=0` sur le témoin. **Le chiffre faux n'est jamais entré dans ce
fichier**, mais il avait été affiché.

**2 — un faux rouge fabriqué par ma propre sonde.** Le harnais du balayage de
graines écrit le journal de chaque graine puis **le supprime si elle est verte**.
Un `ls` lancé pendant le balayage a donc trouvé un journal — celui de la graine
**en cours** — et je l'ai lu comme un rouge. Le fichier avait disparu deux
secondes plus tard. *Un harnais de mesure peut muter ce qu'il observe*, et une
sonde qui l'observe pendant qu'il tourne peut lire un état transitoire pour un
résultat. Le seul signal fiable est la ligne de bilan écrite **après** la boucle,
et c'est elle qui est rapportée au §12 de ce fichier.

---

## 12. La porte qualité et le balayage de graines, commit par commit

`mesuré` du 2 septembre 2026 13:31:22 UTC au 14:03:17 UTC, **dans un arbre de
travail dédié** — `/home/ubuntu/RAG/lot6-graines`, en `HEAD` détaché, `uv sync`
seul et **jamais** `make install`, le §2.1 du mandat gravant sinon dans
`.git/hooks` partagé un interpréteur qui mourrait avec cet arbre.

L'arbre est basculé **une fois, avant** les mesures de chaque commit, et jamais
pendant : un audit s'est fabriqué un faux rouge en basculant le sien pendant que
son balayage tournait. La propreté de l'arbre est constatée **avant et après**
chaque commit, parce qu'un rouge sur un arbre sale ne prouve rien.

Les 26 graines — **la graine 0**, qui désactive la randomisation du hachage et
est donc un cas distinct, **plus 25 aléatoires** tirées une seule fois et
gardées identiques pour les trois commits, ce qui rend les trois colonnes
comparables.

| Commit | arbre sale avant | `make all` | tests | `mypy` | format | graines | arbre sale après |
|---|---|---|---|---|---|---|---|
| `6f81c8e` le jeu de questions et ses gardes | **0** | **rc=0** | **884** | 35 fichiers, 0 erreur | 74 formatés | **26 / 26 vertes** | **0** |
| `d5f4bc4` le compte rendu et le script de rappel | **0** | **rc=0** | **884** | idem | 74 | **26 / 26 vertes** | **0** |
| `4d366f7` le registre | **0** | **rc=0** | **884** | idem | 74 | **26 / 26 vertes** | **0** |

**78 exécutions de la suite sous graine, 78 vertes, zéro rouge.** Aucune sortie
de porte n'a été filtrée : `make all` écrit dans un fichier et son `rc` est lu
directement, jamais derrière un tube — voir le §11, où l'erreur inverse a été
commise puis corrigée.

**Et la borne de cette table, parce qu'un compte ne peut pas s'inclure
lui-même.** Elle couvre les **trois** commits qui existaient quand elle a été
écrite. Le commit qui porte cette section — le quatrième, qui n'ajoute que ce
fichier — passe la même porte et le même balayage, mais **son résultat ne peut
pas figurer ici** : il serait écrit avant d'être mesuré. Il est rapporté au
pilote dans le message de livraison. Le lot 0b s'est fait prendre exactement
ainsi, en annonçant « dix commits » dans le dixième.

**Une réserve de lecture sur le « 74 formatés ».** `make format-check` porte sur
`src/ tests/` et voit 74 fichiers ; la même commande étendue à `scripts/` en voit
**77**. Les trois fichiers d'écart sont les scripts, que la porte ne contrôle pas
et que le hook `ruff` contrôle. C'est le §4.32.c du registre, et les deux scripts
livrés passent `ruff check` et `ruff format --check` (`mesuré`).

**Hygiène, `mesuré` sur les trois commits.** Auteur et committer :
`florian.horellou@gmail.com` sur les trois, adresse de la liste blanche —
vérifiée sur l'**adresse**, jamais sur le nom. Aucun trailer, aucune signature.
Aucun `--no-verify` : les huit hooks ont tourné et sont passés à chaque commit.
Aucun `skip`, `xfail`, `type: ignore`, `noqa`, aucune règle relâchée, aucun
`except` élargi. `git diff main..HEAD --stat -- src/` et `-- Datas` rendent tous
deux le **vide** : aucune ligne de production touchée, corpus hors du diff. Et le
corpus **sur le disque** est intact à l'octet dans les deux arbres, même
empreinte qu'avant le premier geste.

**TROIS occurrences de « claude » et « ChatGPT » subsistent dans le diff hors du
paragraphe qui les commente, et aucune n'est une attribution.** *(Ce paragraphe
en annonçait **deux** : il avait oublié la troisième, qui vit dans son propre
§10. Le fond tenait, le compte non — c'est la famille de dénombrement du
§4.31.B2, commise dans la ligne qui compte.)* `mesuré` le 3 septembre 2026,
`git diff <base> HEAD | grep '^+' | grep -inE 'claude|chatgpt'` :

1. **`claude/session-c608cd`**, au §8 du registre — un nom de branche créé par
   l'outillage, que le §9 du mandat borne explicitement comme n'attribuant rien ;
2. **`.claude/worktrees/lot-1-observation-b12761`**, au **§10 de ce fichier** —
   le répertoire mort, désigné par le chemin que le harnais lui a donné. Même
   borne, même motif ;
3. **« ChatGPT »**, dans la réponse attendue de `q20` — **cité dans le corpus
   lui-même** : le PDF écrit que les utilisateurs attendent une latence
   « comparable to those of the publicly available ChatGPT ». Recopier fidèlement
   une phrase du corpus n'attribue pas ce dépôt à quiconque.

---

## Annexe — le rappel dense, question par question

`mesuré` le 2 septembre 2026, `scripts/campagne/mesurer-le-rappel-vectoriel.py`
sur les 4 367 chunks. **Lire cette table avec la réserve du §6.4** : c'est un
plancher dense, sans BM25, sans graphe, sans reranker, sans abstention. Les
quatre questions sans réponse n'ont pas de rappel — leur colonne de distance dit
seulement de quoi le système les rapprocherait.

| question | strate | ancrages | r@5 | r@10 | r@20 | distance L2 du 1er voisin |
|---|---|---|---|---|---|---|
| `q01` | multi-passages | 3 | 1/3 | 1/3 | 3/3 | 9.85 |
| `q02` | multi-passages | 3 | 3/3 | 3/3 | 3/3 | 11.42 |
| `q03` | multi-passages | 2 | 2/2 | 2/2 | 2/2 | 9.38 |
| `q04` | multi-passages | 2 | 1/2 | 1/2 | 1/2 | 10.52 |
| `q05` | multi-passages | 3 | 1/3 | 2/3 | 2/3 | 11.23 |
| `q06` | multi-passages | 3 | 2/3 | 3/3 | 3/3 | 8.16 |
| `q07` | multi-passages | 2 | 1/2 | 2/2 | 2/2 | 7.38 |
| `q08` | multi-passages | 3 | 1/3 | 1/3 | 1/3 | 8.99 |
| `q09` | multi-passages | 3 | 0/3 | 0/3 | 1/3 | 8.93 |
| `q10` | multi-passages | 2 | 0/2 | 0/2 | 0/2 | 8.79 |
| `q11` | multi-passages | 3 | 1/3 | 1/3 | 3/3 | 10.09 |
| `q12` | multi-passages | 2 | 2/2 | 2/2 | 2/2 | 12.33 |
| `q13` | simple | 1 | 1/1 | 1/1 | 1/1 | 7.69 |
| `q14` | simple | 1 | 1/1 | 1/1 | 1/1 | 8.80 |
| `q15` | simple | 1 | 1/1 | 1/1 | 1/1 | 6.11 |
| `q16` | simple | 1 | 1/1 | 1/1 | 1/1 | 7.08 |
| `q17` | simple | 1 | 1/1 | 1/1 | 1/1 | 8.06 |
| `q18` | simple | 1 | 1/1 | 1/1 | 1/1 | 7.40 |
| `q19` | simple | 1 | 1/1 | 1/1 | 1/1 | 9.79 |
| `q20` | simple | 1 | 1/1 | 1/1 | 1/1 | 10.18 |
| `q21` | sans-reponse | 0 | — | — | — | 13.11 |
| `q22` | sans-reponse | 0 | — | — | — | 8.73 |
| `q23` | sans-reponse | 0 | — | — | — | 11.44 |
| `q24` | sans-reponse | 0 | — | — | — | 14.86 |
| `q25` | de-suivi | 2 | 0/2 | 0/2 | 0/2 | 14.62 |
| `q26` | de-suivi | 1 | 0/1 | 0/1 | 0/1 | 20.01 |
| `q27` | de-suivi | 1 | 1/1 | 1/1 | 1/1 | 15.68 |
| `q28` | de-suivi | 1 | 0/1 | 0/1 | 0/1 | 15.94 |
| `q29` | reformulee | 1 | 0/1 | 0/1 | 0/1 | 17.34 |
| `q30` | reformulee | 2 | 2/2 | 2/2 | 2/2 | 9.64 |

**Les cinq lignes à zéro, et aucune n'est un défaut de l'index.** `q10` demande
la taille d'un jeu d'évaluation dans deux ouvrages qui l'expriment en mots très
différents ; `q25`, `q26` et `q28` sont des questions **de suivi**, encodées ici
sans leur `chat_history`, donc privées de leur antécédent ; `q29` est
délibérément reformulée jusqu'à ne plus partager de vocabulaire avec son
passage. Ce sont les quatre strates dures faisant leur travail — et le plancher
de contrôle, lui, tient à 8 sur 8.
