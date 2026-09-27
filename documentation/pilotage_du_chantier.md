# Piloter le chantier d'audit et de refonte

> **Archive datée, non réécrite.** Journal de pilotage du chantier, tenu jusqu'au 25 septembre 2026. L'état en service est décrit par [`livraison.md`](livraison.md).
>
> **MinIO est retiré depuis le 25 septembre 2026 ; les mentions qui suivent sont
> historiques.** Le stockage d'objets est SeaweedFS, le dépôt ne nomme plus aucun
> serveur — seule `S3_ENDPOINT` le désigne — et le contrat publie `media_url` et
> `object_key`. Ce fichier n'est **pas** réécrit : ce sont des mesures datées, et
> les réécrire les falsifierait. L'état courant est à
> [`etat_des_lieux.md`](etat_des_lieux.md), la procédure de retrait à
> [`campagnes/2026-09-25-retrait-du-stockage-precedent.md`](campagnes/2026-09-25-retrait-du-stockage-precedent.md).

Ce fichier est le **mandat du pilote**. Il est écrit pour être lu par une
conversation qui n'a aucun historique : elle arrive, elle lit ceci, elle sait
où on en est, ce qui a été décidé, pourquoi, et quelle est l'action suivante.

Il est autosuffisant. Rien de ce qui suit ne suppose d'avoir vu une
conversation précédente.

Son compagnon obligatoire est [`axes_amelioration.md`](axes_amelioration.md),
le registre : ce fichier-ci dit **comment on travaille**, le registre dit **ce
qu'il reste à faire**. Les deux se tiennent à jour lot par lot.

> **Dernière mise à jour : 25 septembre 2026, après la BASCULE vers SeaweedFS**
> — le stockage objet du pipeline est **SeaweedFS** depuis ce jour, MinIO est
> conservé debout pour le retour arrière. L'état est au **§5.0 ter** ; le compte
> rendu mesuré est à son site canonique,
> [`documentation/campagnes/2026-09-25-bascule-seaweedfs.md`](campagnes/2026-09-25-bascule-seaweedfs.md),
> et les mesures d'après au **§4.43** du registre.
>
> **Avant elle, le même jour, la DEUXIÈME campagne de référence** — purge,
> réingestion complète **par le capteur**, `DEPLACES 0`. L'état, en trois lignes
> et sans un chiffre recopié, est au **§5.0 bis** ; le compte rendu mesuré est à
> son site canonique,
> [`documentation/campagnes/2026-09-25-deuxieme-campagne-de-reference.md`](campagnes/2026-09-25-deuxieme-campagne-de-reference.md).
>
> **LE PLAN EST ÉPUISÉ**, et il l'est depuis la fusion du lot 6 (`69a6786`, 3
> septembre 2026) : les six lots sont dans `main`, et **les deux campagnes de
> référence sont faites**. Il n'y a plus de lot à distribuer — l'annexe A porte
> la passation, et le §7 dit ce qui monte au plan ensuite. Le lot 11 est dans
> `main` depuis le 25 septembre (§5.0), et la campagne qui l'exerce est faite le
> même jour.
>
> Toute valeur chiffrée ci-dessous porte son étiquette `mesuré`, `calculé` ou
> `supposé`. Une valeur non remesurée ne se recopie pas : on renvoie à son site
> canonique.

---

## 0. Reprendre le chantier en une manipulation

Ce fichier vit sur `main`. Un clone frais le contient : il n'y a **aucune
branche à checkouter** pour reprendre.

Le prompt à coller dans une conversation neuve, tel quel :

> Tu es le pilote d'un chantier d'audit et de refonte sur
> `rag-ingestion-pipeline`. Le dépôt est un clone local de
> `floSa/rag-ingestion-pipeline`, dépôt **personnel**, sur `main`. **Le chemin
> du dépôt et l'URL du distant sont des faits de POSTE : mesure-les.**
> `git rev-parse --show-toplevel` et `git remote -v`. Un poste portait un
> distant SSH `git@github.com-perso:`, un autre le même dépôt en HTTPS
> (`mesuré`, 31 août 2026).
>
> Lis ces deux fichiers EN ENTIER avant de dire quoi que ce soit :
> `documentation/pilotage_du_chantier.md` (ton mandat : ton rôle, l'état du
> chantier, le plan de lots, les conventions, les leçons, et en annexe A le
> prompt prêt à distribuer) et `documentation/axes_amelioration.md` (le
> registre : le contrat avec `rag-agent-chat` en tête, puis les constats
> ouverts et traités).
>
> Ils sont autosuffisants : tu n'as aucun historique de conversation, et tu
> n'en as pas besoin. Vérifie ensuite l'état de tes mains plutôt que de me
> croire — les branches, l'état non versionné du poste (`.env`, stores, pile
> Docker ; le corpus, lui, est versionné depuis le 31 août 2026, §2.2), et
> `make install && make all` sur `main` — puis dis-moi où on en est et quelle
> est la prochaine action. Un prompt à la fois, et **nomme ET numérote**
> chaque conversation destinataire : `Conv' <n> <RÔLE-LOT>`.

Puis ce qui ne voyage pas avec un clone : §2.

---

## 1. Ce que tu es, et ce que tu ne fais pas

Tu es le **pilote**. Tu n'écris pas le code.

Tu écris des **prompts** que l'utilisateur colle dans d'autres conversations,
et il te rapporte leurs sorties. Tu audites, tu décides, tu tranches les
fusions, tu tiens le registre.

Ce que tu fais toi-même, sans le déléguer :

- **lire le code avant d'affirmer ce qu'il fait.** Avec
  `git show <branche>:<fichier>`, pas avec `cat` : sur ce dépôt, un arbre de
  travail a longtemps porté le contenu de juin sur un `HEAD` d'août ;
- **faire tourner la porte qualité de tes mains** avant toute fusion, et lire
  le diff complet ;
- **tenir le registre** : ce qui est corrigé, ce qui reste ouvert, et pourquoi.

Ce que tu ne fais pas :

- écrire ou modifier du code de production ;
- fusionner un lot avant son audit indépendant. Le pilote initial l'a fait une
  fois et l'a reconnu prématuré ; sur les six lots du dépôt jumeau, l'audit
  indépendant a trouvé **chaque fois** quelque chose de matériel que ni le
  développeur ni le pilote n'avaient vu ;
- fusionner un lot qui introduit une régression, même petite.

---

## 2. Reprendre sur un poste de travail neuf

Ce qui **ne voyage pas** avec un `git clone`. Les oublier a déjà coûté un dépôt
entier.

**Le corpus, lui, voyage désormais** — il a été versionné le 31 août 2026, et
le §2.2 dit à quel prix. Restent le garde-fou d'identité (§2.1), le `.env`
(§2.3), et les stores et la pile Docker (§4). **Vérifie chacun sur le poste, ne
lis pas cette liste comme un état.** Un poste a été repris en croyant sur
parole qu'il était le poste d'origine : il n'avait ni `.env`, ni hook installé,
ni conteneur, ni corpus (`mesuré`, 31 août 2026).

### 2.1 Le garde-fou d'identité Git — À FAIRE EN PREMIER

Sept commits sont partis avec une adresse **professionnelle** `@aosis.net` sur
un dépôt **personnel**. Il a fallu réécrire 165 commits **puis détruire et
recréer** le dépôt GitHub : la liste des contributeurs, une fois constituée, ne
se défait pas.

Deux identités portent le même **nom**, « Florian Horellou ». **Ne vérifie
jamais une identité sur le nom, toujours sur l'adresse.**

**Un seul geste, et il vérifie son propre résultat :**

```bash
make install
```

`make install` fait `uv sync`, puis `sh scripts/installer-les-garde-fous.sh`,
qui arme les hooks git **et sort en erreur si le montage n'est pas celui qu'il
annonce**. Il n'y a rien à faire dans un ordre : c'est le script qui tient
l'ordre, et il constate son résultat.

**`uv` est requis, et ce paragraphe a affirmé le contraire.** Il disait « si
`uv` manque sur le poste, le script s'exécute seul ». C'est **faux** : `mesuré`
le 31 août 2026 dans un clone frais,
`env PATH=/usr/bin:/bin sh scripts/installer-les-garde-fous.sh` rend **`rc=1`**,
et il ne pose que les **deux copies du contrôle d'identité** — aucun hook du
framework, aucun `.legacy`. Le script, lui, est honnête : il l'écrit sur sa
sortie d'erreur (« `uv: not found` », puis « le contrôle d'identité est copié et
actif ; les hooks du framework ne le sont pas »). C'était la phrase qui mentait,
pas le code. Un montage à moitié armé est le pire des trois états, parce qu'il
ressemble au bon.

**Et il y a trois choses à se rappeler.** Ce paragraphe disait « rien à se
rappeler » : c'est une phrase d'exhaustivité, et c'est la famille de phrase qui
a caché la régression R1 pendant tout le lot 0b. Les voici — les deux dernières
`mesuré`es, la première étant une consigne de cette section :

1. **`git config user.email`** — deux paragraphes plus bas, dans cette même
   section. Le script n'y touche pas ;
2. **relancer `make install` après toute édition de `ADRESSES_AUTORISEES`** —
   voir « la liste blanche a DEUX sites au runtime » ci-dessous ;
3. **relancer `make install` depuis le clone principal si le `.venv` visé par le
   hook disparaît** — voir « Le hook fige aussi un chemin absolu » ci-dessous.

Cette liste-ci n'est pas fermée non plus. Si tu en trouves une quatrième,
écris-la ici plutôt que de la garder.

**Ce que le script monte, et pourquoi l'ordre compte.** Le contrôle d'identité
vit sous `scripts/git-hooks/pre-commit`, versionné, donc il arrive avec le clone
— mais **inactif tant qu'il n'est pas installé**, git n'exécutant jamais ce qui
arrive avec un dépôt. Le script le copie d'abord dans le répertoire des hooks,
**puis** lance `pre-commit install`, qui déplace cette copie en
`pre-commit.legacy`, continue de l'exécuter **avant** ses propres hooks, et
s'installe par-dessus. Les deux voies exécutent donc les mêmes octets **au
moment de l'installation**.

**Mais la liste blanche a DEUX sites au runtime, et ils peuvent diverger.** Ce
paragraphe affirmait « la liste blanche d'adresses n'a qu'un site » : c'est vrai
du dépôt versionné, **faux du montage armé**. `<type>.legacy` est une **copie
figée à l'installation** ; le hook `repo: local`, lui, relit le script versionné
à chaque commit. `mesuré` le 31 août 2026 dans un clone frais armé par le script
livré, dans les deux sens :

| Édition de `ADRESSES_AUTORISEES`, **commitée** | Effet au commit suivant |
|---|---|
| **ajouter** une adresse | **sans effet** : la couche `repo: local` l'accepte (« Passed »), puis `pre-commit.legacy` refuse, `rc=1`, en affichant l'**ancienne** liste. HEAD ne bouge pas |
| **retirer** une adresse | **appliqué** : la couche `repo: local` refuse, `rc=1`, HEAD ne bouge pas |

C'est donc **fail-closed dans les deux sens** — de la friction, jamais une
exposition — et c'est pour cela que le montage n'est pas changé : la copie figée
**est** la propriété qui rend le contrôle indépendant de l'arbre de travail.
**Le geste :** après toute édition de `ADRESSES_AUTORISEES`, relancer
`make install`, qui réécrit la copie.

Le message de refus est trompeur dans ce cas précis, et il faut le savoir : il
énumère la liste de la copie figée, pas celle du fichier qu'on vient d'éditer.
Si une adresse fraîchement ajoutée est refusée en n'apparaissant pas dans la
liste affichée, c'est ce cas-là, et rien d'autre.

**Le hook fige aussi un chemin absolu, et personne ne le savait.**
`pre-commit install` écrit dans `.git/hooks/<type>` une ligne
`INSTALL_PYTHON=<interpréteur de l'arbre qui a lancé l'installation>`. Un
`make install` lancé depuis un **arbre de travail temporaire** y grave donc le
`.venv` de cet arbre-là — et `.git/hooks` est **partagé par tout le clone**.
`mesuré` le 31 août 2026 : quand ce chemin disparaît et qu'aucun `pre-commit`
n'est au PATH (`which pre-commit` → `rc=1` sur ce poste), **tout commit du dépôt
et de tous ses arbres de travail** est refusé — `rc=1`, HEAD inchangé, sur le
seul message « `` `pre-commit` not found.  Did you forget to activate your
virtualenv? `` », qui ne nomme ni la cause ni `make install`.

C'est **fail-closed**, donc sans danger pour l'historique. Mais le §7 prescrit de
supprimer une branche fusionnée, donc son arbre de travail : **relance
`make install` depuis le clone principal après avoir supprimé un arbre de
travail**, et fais-le de préférence depuis lui dès le départ. Une piste pour ne
plus avoir à s'en souvenir est au registre, non retenue dans ce lot.

**`pre-commit.legacy` n'est pas un doublon : c'est la protection.** Ce point a
coûté au lot 0b sa fusion au premier tour, et il faut le lire en entier. Le hook
généré par le framework ouvre sa configuration en chemin **relatif**
(`--config=.pre-commit-config.yaml`) : un contrôle déclaré dans ce fichier — donc
dans l'**arbre de travail** — ne vaut que pour les arbres dont la configuration
le porte. Sur les 111 commits de `main`, **aucun** ne la porte (`mesuré`,
31 août 2026, `a005172`). Mesuré dans un clone frais monté par
`pre-commit install` seul, arbre sorti à `298c77e` : un commit portant
`@aosis.net` en auteur **et** en committer est **accepté**, `rc=0`. Le hook du
framework tourne, son rapport ne contient aucune ligne d'identité, et le commit
part. `pre-commit.legacy` vit **hors** de l'arbre de travail : c'est la seule
couche qui vaille pour tout commit, toute branche, tout `git bisect`, tout HEAD
détaché.

**Ne passe jamais `-f`.** `pre-commit install` le suggère lui-même dans sa
sortie — « `Use -f to use only pre-commit.` » — et c'est exactement le geste qui
supprime cette couche. Le script ne le passe pas, et sa vérification finale
rougit si la couche a disparu. Un test la garde :
`tests/unit/test_installation_des_garde_fous.py` monte un dépôt jetable dont la
configuration ne déclare **pas** le contrôle d'identité, y exécute le script
livré, et prouve que le refus tient quand même.

**Ce qui est par clone, et ce qui suit la branche.** À distinguer, parce que la
conclusion n'est pas la même pour les deux :

| Objet | Portée | Conséquence |
|---|---|---|
| l'**installation** des hooks | **une fois par clone** — `.git/hooks` est partagé entre le dépôt et tous ses arbres de travail, `core.hooksPath` n'étant pas positionné | rien à refaire par worktree — mais l'installation grave l'interpréteur de l'arbre **d'où on la lance**, donc lance-la depuis le clone principal |
| la **liste blanche** d'adresses | **un site versionné, deux sites armés** : `<type>.legacy` est une copie figée à l'installation | relancer `make install` après toute édition de `ADRESSES_AUTORISEES` |
| l'**identité** `user.email` | **une fois par clone** — `extensions.worktreeConfig` n'est pas activé, donc `git config` écrit dans `.git/config`, partagé (`mesuré`, 31 août 2026 : les quatre arbres de travail lisent le même fichier) | rien à refaire par worktree |
| la **protection d'identité** | **toute branche**, grâce à `pre-commit.legacy` | inconditionnelle, comme avant le lot 0b |
| la **configuration** des hooks du framework | **suit l'arbre de travail** : le hook lit `.pre-commit-config.yaml` en chemin relatif | un arbre sorti à un commit ancien exécute les hooks *de ce commit-là*. Ce n'est pas un défaut, c'est un fait à connaître |

Puis l'identité, une fois :

```bash
git config user.name "floSa" && git config user.email "florian.horellou@gmail.com"
```

Adresses autorisées, et elles seules : `florian.horellou@gmail.com`,
`florian_horellou@laposte.net`. Elles n'ont **qu'un site**,
`ADRESSES_AUTORISEES` dans `scripts/git-hooks/pre-commit`. Le hook ne se
contourne jamais : pas de `--no-verify`.

**Ce que le contrôle couvre, et ce qu'il ne couvre pas.** `mesuré` le 31 août
2026, mouchards posés sur chaque hook de `.git/hooks` :

| Geste | Couvert | Pourquoi |
|---|---|---|
| `git commit` | **oui** | hook `pre-commit` |
| `git commit --amend` | **oui** | hook `pre-commit` |
| `git merge --no-ff` | **oui** | hook `pre-merge-commit`, installé par le script et posé aussi en `pre-merge-commit.legacy` |
| `git revert`, `git cherry-pick` | **non** | git n'y déclenche ni `pre-commit` ni `commit-msg`. Le seul point d'accroche restant, `prepare-commit-msg`, y voit l'identité **locale** et non celle du commit produit (`mesuré`) : un contrôle posé là serait vert sur le défaut |
| `git rebase` | **non** | aucun hook de la famille ; le rebase réécrit le committer |

Les deux dernières lignes sont **ouvertes**, au registre. Elles ne sont pas des
gestes de ce chantier — le mandat interdit le rebase et prescrit `--no-ff` — et
leur fermeture honnête est un hook `pre-push`, qui reste à trancher.

Le distant est **personnel** : `floSa/rag-ingestion-pipeline`.

### 2.2 Le corpus — versionné depuis le 31 août 2026

**`Datas/htms/` et `Datas/pdfs/` sont VERSIONNÉS.** Le commit `a005172` les a
sortis du `.gitignore` : 25 fichiers, **57 381 999 octets** (`mesuré`,
31 août 2026, `git ls-files -z -- Datas | xargs -0 stat -c '%s %n'`). Un clone
frais les porte. **Il n'y a plus rien à transporter à la main.**

Restent ignorés `Datas/database/` (volumes écrits par Docker), `Datas/.cleaned/`
(sortie du nettoyage, régénérée) et `Datas/mds/`.

**Pourquoi c'est la bonne décision, et ce qu'elle a coûté.** Le corpus non
versionné imposait un transport manuel, et `source_path` entre dans le calcul
d'`element_id` (contrat, exigence 2) : deux postes dont les noms de fichiers
diffèrent d'un caractère produisent des identifiants différents, donc des
mesures que rien ne permet de comparer, **sans qu'aucune erreur ne le signale**.
Versionner supprime ce chemin de divergence — les deux côtés lisent les mêmes
octets sous les mêmes noms. Le prix : 55 Mo dans l'historique de chaque clone,
et deux effets qu'il faut connaître, tous deux mesurés et traités par le lot 0b
(registre, constat **C**) — les hooks du framework `pre-commit` **réécrivaient**
le corpus, et `check-added-large-files` en **interdisait l'extension**. Le
corpus est désormais soustrait à tous les hooks par un `exclude: '^Datas/'`
racine, et le geste pour l'étendre est écrit au `README.md`.

**Le procédé, en revanche, n'était pas bon, et c'est consigné.** `a005172` a été
poussé droit dans `main` par une conversation sans mandat, pendant qu'un lot
travaillait, sans audit — la règle centrale du chantier. Le fond se défend, le
procédé non. Les deux sont vrais et ne s'annulent pas.

**Ce que le corpus contient** (`mesuré`, 31 août 2026) :

```
Datas/htms/MLOps with Databricks/                              12 fichiers
Datas/htms/Practical MLflow for Generative AI on Databricks/   12 fichiers
Datas/pdfs/Hands-On_RAG_for_Production_ER_-_Ofer_Mendelevitch.pdf   71 pages
                     25 fichiers, 57 381 999 octets ; le plus gros 6 362 475,
                     le plus petit 671 707 — 19 des 25 dépassent 1 Mo
```

*(Historique, conservé parce qu'il explique les noms de fichiers.)* Deux sources
ont existé et **n'étaient pas interchangeables** :

```
Datas/htms/MLOps with Databricks/                              12 fichiers
Datas/htms/Practical MLflow for Generative AI on Databricks/   12 fichiers
Datas/pdfs/Hands-On_RAG_for_Production_ER_-_Ofer_Mendelevitch.pdf   71 pages
                                            25 fichiers, environ 56 Mo au total
```

**La sauvegarde** `corpus-rag-sauvegarde` (27 fichiers, 64 Mo, locale au poste
initial ; **absente des postes vérifiés depuis**) divergeait de l'arbre de
travail sur deux points, tous deux nuisibles :

- elle porte **13** fichiers pour `MLOps with Databricks` contre 12 : c'est le
  chapitre capturé deux fois, dont le doublon a été retiré. Elle contient aussi
  un `docling_paper.pdf` qui n'appartient pas au corpus ;
- elle porte **les noms d'origine, horodatages de capture compris**. Ceux du
  dépôt en ont été débarrassés **avant toute ingestion, délibérément**.

C'est le second point qui compte. `source_path` entre dans le calcul de
`element_id` (contrat, exigence 2) : deux machines dont les noms de fichiers
diffèrent d'un caractère produisent des identifiants différents, donc des
mesures que rien ne permet de comparer, **sans qu'aucune erreur ne le
signale**. Les noms doivent être identiques au caractère près des deux côtés.

C'est ce second point qui a rendu le versionnement nécessaire. **Et ne renomme
rien** : un renommage après ingestion tue le jeu de questions de l'agent.

### 2.3 Le `.env`

`.env` est dans le `.gitignore`. Le recréer depuis `.env.example`, et vérifier
en priorité `EMBEDDING_MODEL_NAME` — c'est le chemin par lequel la panne la
plus coûteuse du système est déjà arrivée une fois (contrat, exigence 1).

### 2.4 La mesure de contrôle

```bash
make install && make all
```

**La présence de `make` est un fait de POSTE : mesure-la, ne la lis pas ici.**
`command -v make`. Sur un poste elle a manqué, sans droits pour l'y mettre
(`mesuré`, 31 août 2026) ; sur un autre, `make` était bien là — GNU Make 4.4.1,
`/usr/bin/make` (`mesuré`, 31 août 2026, même jour). Ce paragraphe a longtemps
affirmé l'absence comme un fait du chantier : c'était une mesure de poste
présentée comme universelle, et chaque conversation la reprenait sans la
vérifier. Le corpus, le `.env` et les stores relèvent de la même famille (§2.2,
§2.3, §4).

Si `make` manque, exécute les recettes du `Makefile` **versionné**, lues depuis
le fichier, dans l'ordre et avec arrêt au premier échec — et note **deux**
changements : `install` arme désormais les garde-fous, et `format-check` vient en
dernier.

```bash
uv sync && sh scripts/installer-les-garde-fous.sh \
  && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest tests/ \
  && uv run ruff format --check src/ tests/
```

**Les DEUX cibles `ruff` portent `src/ tests/`, et la seconde ne le portait pas.**
Le commit qui pretendait aligner les portees n'en a corrige que la moitie :
`ruff check` est passe a `src/ tests/`, `ruff format --check` est reste a `src/`.
`mesure` le 1er septembre 2026 sur la pointe du lot 4 : `--check src/` voit **36**
fichiers, `--check src/ tests/` en voit **73**. Le repli etait donc aveugle aux
fichiers de `tests/`, et les deux verdicts ne coincidaient que par chance.

Mesure du desaccord, de mes mains, sur un arbre ou une seule ligne d'un fichier de
`tests/` est pliee a la main :

| Sequence | arbre propre | une ligne pliee dans `tests/` |
|---|---|---|
| `make all` | `rc=0` | **`rc=2`** |
| le repli tel qu'il etait ecrit | `rc=0` | **`rc=0`** — aveugle |
| le repli corrige ci-dessus | `rc=0` | **`rc=1`** — il voit |

**Lis la colonne comme un VERDICT et non comme un code.** `make` traduit tout
echec de recette en **2** ; `ruff format --check` sort lui-meme en **1**. Les deux
sequences rendent donc le meme verdict — vert sur l'arbre propre, rouge sur
l'arbre sale — et jamais le meme entier. Un controle ecrit `rc = 2` sur le repli
serait vert sur le defaut, exactement comme le `rc=123` d'`xargs` du registre F3.

C'est le trou que ce §2.4 decrit lui-meme pour l'installeur — la premiere ligne
d'une cible recopiee, la seconde oubliee — refait un cran plus loin, dans le
commit qui pretendait aligner les portees.

**La preuve est une mesure et non un test**, et il faut le dire : F7 reste ouvert,
aucun test de ce depot ne lit le `Makefile` ni ce fichier. Un repli qui derive de
la cible qu'il remplace ne rougira nulle part.

**Le `sh scripts/installer-les-garde-fous.sh` de la deuxième position n'était pas
là, et son absence était le trou.** Ce repli prétend remplacer
`make install && make all` ; il ne portait que `uv sync`, c'est-à-dire la
**première** ligne de la cible `install` — celle qui installe les dépendances —
et pas la **seconde**, celle qui arme les hooks. Un poste sans `make` suivant
cette recette n'avait donc **aucun garde-fou** : ni contrôle d'identité, ni
`detect-secrets`, exactement l'état que ce lot ferme. `mesuré` le 31 août 2026,
clone frais : après le repli tel qu'il était écrit, `.git/hooks` ne porte **aucun**
hook ; après celui-ci, les quatre attendus, et la suite rend `lint=0`,
`typecheck=0`, `test=0`, `format-check=1` — le rouge d'alors. Ce rouge-la est
**fermé** : les quatre fichiers ont été reformatés par la réparation du lot 3, et
la même suite rend désormais `format-check=0`. Le repli est conservé tel quel ;
seul son verdict attendu a changé.

La différence avec `make` est nulle pour ce `Makefile` — pas de variable, pas de
motif, pas de parallélisme — mais elle existe : dis-le dans ton rapport plutôt
que de laisser croire que `make` a tourné.

Attendu sur `main` : `ruff` propre, `mypy --strict` sans erreur, et la suite
verte. **Le nombre de fichiers que `mypy` annonce a été retiré de cette case**,
comme le SHA de `main` l'avait été du §5.1 et pour la même raison : il valait 36
le 31 août 2026, il vaut **35** depuis que le lot 5 a retiré `blocks.py`
(`mesuré`, 2 septembre 2026, `uv run mypy src/`), et une case qui donne un
chiffre invite à lire le chiffre plutôt qu'à le remesurer. Le compte canonique
de tests vit dans `README.md`, section Tests — n'en recopie pas la valeur ici.

**`make all` ne mute plus l'arbre : il le constate, et il rend 0.**
Le lot 0b a séparé `format` — qui écrit, geste volontaire — de `format-check` —
qui constate, et qui est la dernière étape de `make all`. Il n'y a donc plus
rien à révoquer avant un commit, et c'est le point : le garde-fou ne repose plus
sur la mémoire du développeur.

**L'exception « rc=2 est le rouge attendu » est FERMÉE, et c'est un changement de
sens.** Elle a vécu du lot 0b à la réparation du lot 3 : quatre fichiers pliés à
la main faisaient sortir la porte en 2, chaque prompt du chantier devait porter
l'exception, chaque conversation la redécouvrait, et **elle a déjà masqué un vrai
rouge une fois**. Les quatre — `extraction.py` et `matter.py` par le lot 3,
`language.py` et `tests/unit/test_wipe_stores.py` par sa réparation — sont
désormais format-propres.

`mesuré` sur la pointe de la réparation du lot 3 :
`uv run ruff format --check src/ tests/` → « 66 files already formatted »,
`rc=0`, et `make all` → `rc=0`.

**Ce que cela change pour toi : un `rc` non nul de `make all` est un défaut, sans
exception à connaître.** N'écris plus « rc=2 attendu » dans un prompt.

Le coût total du reformatage est **mesuré** et il est petit : **20 lignes** de
diff sur les trois commits de style — 9 pour `extraction.py`, 4 pour `matter.py`,
7 pour les deux derniers (`git show --numstat --format= <commit>`). Le récit d'un
« reformatage massif » était surdimensionné de bout en bout. Le détail vit au
registre §5.4.

`format-check` passe **en dernier**, donc `lint`, `typecheck` et `test` rendent
leur verdict avant lui. Pour lire ces trois seuls : `make lint typecheck test`.

Si le compte diffère, ne suppose rien : c'est le dépôt qui a bougé, et il faut
comprendre pourquoi avant de continuer.

**Et lis ce nombre avec sa réserve.** C'est le compte des tests qui passent, pas
le compte des tests qui prouvent quelque chose. Le fichier
`tests/unit/test_hierarchie_bout_en_bout.py` **fabrique l'arbre imbriqué qu'il
prétend vérifier** et reste vert des deux côtés de son défaut (registre §3.3) —
même si l'audit indépendant a montré qu'il apporte tout de même une couverture
réelle, 3 mutations sur 7 n'étant vues que par lui. Un compte de tests est une
mesure de volume, jamais une mesure de garantie.

---

## 3. Le contrat avec `rag-agent-chat`

Il est écrit en tête du registre, [`axes_amelioration.md` §0](axes_amelioration.md).
**Va le lire là-bas** : c'est son site canonique, et il ne doit pas exister en
deux versions qui peuvent diverger.

En une phrase, pour savoir de quoi on parle : cinq exigences dures — modèle
d'embedding identique des deux côtés, `element_id` déterministe en 10
hexadécimaux, `source_path` comme identité, `sequence` monotone sur `PARENT_OF`,
`POST /reindex` en fin de pipeline — et deux contraintes d'ordre — ne pas
mesurer l'ablation du graphe avant d'avoir constaté sa profondeur réelle, et
savoir qu'une hiérarchie réelle coûte de la fenêtre de contexte.

La conception du jeu d'évaluation, et pourquoi elle n'est pas négociable, est
au [§1 du registre](axes_amelioration.md).

---

## 4. Faits établis — ne les redérive pas

- **Les stores sont vides et prêts — SUR LE POSTE DE RÉFÉRENCE SEULEMENT.**
  Bind mounts sous `Datas/database/`, pas de volumes nommés. **Ce fait ne
  voyage pas.** Sur le poste `/home/florian/mes_projets/`, ChromaDB porte la
  collection `rag_documents` avec 137 854 vecteurs et MinIO un bucket
  `documents` non vide (`mesuré`, 29 août 2026), et le corpus présent n'est pas
  celui du §2.2. **Avant tout lot qui ingère, mesure le poste au lieu de lire
  cette ligne** — registre §2.
- **Le réseau `rag_network` est créé par ce dépôt.** `rag-agent-chat` s'y
  raccroche en `external: true` et ne démarre pas sans lui.
- **Aucun GPU n'est requis.** L'ingestion tourne sur processeur. La réservation
  `nvidia` écrite en dur rendait le service **incréable** sans runtime nvidia ;
  elle vit désormais dans un `docker-compose.gpu.yml` superposable.
- **L'image Docling est à reconstruire — toujours vrai au 31 août 2026**, et la
  panne est identifiée précisément (`mesuré`) : `GET /health` rend **503** avec
  `graph_ready: true`, `objects_ready: true`, **`models_ready: false`**, et le
  journal donne la cause en clair —
  `PermissionError: [Errno 13] Permission denied: '/tmp/.cache/huggingface'`,
  levée par `_warm_up` au chargement de l'embedder. Le conteneur tourne en
  **Python 3.10.17** alors que `Dockerfile.docling` déclare `python:3.12-slim` :
  l'image précède donc le fichier. Or ce `Dockerfile` **corrige déjà** la panne
  (`mkdir -p /tmp/.cache && chown -R docling:docling /tmp/.cache`). Un
  `docker compose up -d --build docling-service` doit suffire — c'est la
  première manipulation du lot 1.
- *(Constat d'origine, conservé.)* Le conteneur tournait en Python 3.10
  alors que `Dockerfile.docling` déclare `python:3.12-slim` : l'image a plus de
  six semaines. Elle échouait sur `PermissionError: /tmp/.cache/huggingface`,
  que le `Dockerfile` actuel corrige déjà.
- **Le corpus est difficile par construction.** Les deux ouvrages traitent de
  sujets voisins : un passage sur le « model serving » a des sosies plausibles
  dans les deux. C'est voulu.
- **`Index.html` est écarté par le capteur** (`matter.py:40`), **`Preface.html`
  ne l'est pas** — « preface » n'est pas dans `FRONT_BACK_MATTER_TITLES`. Il
  sera donc ingéré depuis les deux ouvrages : c'est le cas d'école de
  l'exigence 3, et c'est bien qu'il y soit.
- **L'image Docling peut ne pas EXISTER, et pas seulement être périmée**
  (`mesuré`, 31 août 2026). Sur un poste, `docker images | grep -i docling`
  rendait le vide : la panne décrite ci-dessus n'a donc pas pu être observée, et
  un `docker compose up -d --build docling-service` a suffi à obtenir
  `models_ready: true`, Python 3.12.14, zéro `PermissionError`. **Ne présente
  pas ces symptômes comme un état courant : mesure d'abord.** L'image pèse
  **10,4 Go** (registre §6.12).
- **Une pile montée depuis un ARBRE DE TRAVAIL est invisible depuis le clone
  principal, et son arbre ne peut plus être supprimé** (`mesuré`, registre
  §4.26). `docker compose ps` depuis le dépôt principal rend 20 avertissements
  de variables vides et **aucune ligne de service**, alors que six conteneurs
  tournent. Et tous les stores sont des bind mounts de cet arbre : le supprimer
  détruirait graphe, vecteurs, objets et Postgres, sans qu'aucun garde-fou git
  ne s'y oppose — `Datas/database/` est ignoré. **Monte la pile depuis le clone
  principal**, ou sache ce que tu ancres.
- **Un chapitre était capturé deux fois**, texte identique au caractère près :
  le doublon a été retiré avant le chantier.
- **SUR UN POSTGRES DAGSTER VIERGE, `docker compose up -d` DÉCLENCHE L'INGESTION
  COMPLÈTE DU CORPUS, EN SILENCE, 15 s APRÈS LE DÉMARRAGE** (`mesuré`, 31 août
  2026). Ce n'est **pas** un défaut : c'est `default_status=RUNNING` sur les
  sensors d'ingestion (§4.18, fermé par le lot 0b) plus des curseurs vides. C'est
  le comportement voulu. **Mais ce n'était écrit nulle part**, et il n'y a aucun
  avertissement au démarrage.

  Corollaire, et c'est lui qu'il faut retenir : **la copie de
  `Datas/database/postgres` est le maillon qui l'empêche**, et c'est précisément
  celui qui a échoué au lot 3 — le répertoire appartient à `root` dans le
  conteneur, `Permission denied`.

  **Le geste, avant le premier `up` sur un poste dont tu veux garder les
  mesures** : soit copier le Postgres en `sudo`, soit
  `docker compose up -d && docker compose stop dagster-daemon` — ou mieux,
  arrêter le daemon **avant** que les sensors n'aient un tick. Sinon les stores
  sont réécrits par une ingestion que personne n'a demandée, et l'antécédent de
  toute mesure en cours est perdu.
- **Le service Docling monte `/app/src` depuis le CLONE PRINCIPAL, pas depuis ton
  arbre de travail.** Donc `docker compose exec docling-service python -m
  src.<module>` exécute le code de `main`, quelle que soit la branche que tu as
  sortie. `mesuré` : la même commande rend `rc=0` « Contrat respecté » avec le
  code de `main` et `rc=1` avec deux anomalies avec celui de la réparation du
  lot 3. Et un `rc=1` peut venir d'un `ImportError` plutôt que d'un garde. **Le
  pilote s'y est fait prendre.** Le geste — monter son propre `src` — est au
  registre §4.27. **Depuis la fusion du lot 3 (`4e28594`), `main` PORTE le code
  réparé** : le conteneur et `main` disent la même chose, et la divergence
  reviendra à la première branche en vol. Ne lis pas cette ligne comme un état,
  mesure-la.
- **`verify_data` et `verify_contract` ne tournent PAS côté hôte.** `chromadb`
  n'est pas dans le `.venv` du clone — il appartient aux dépendances du service
  Docling, pas à celles du dépôt. `mesuré` le 1er septembre 2026 :
  `uv run python -m src.verify_data` rend `rc=1` sur un
  `ModuleNotFoundError: No module named 'chromadb'`, **et ce rc=1 ressemble à un
  garde qui a parlé**. Le geste :
  `docker exec rag_assistant-docling-service-1 python -m src.verify_data`.
- **Les stores survivent au redémarrage de l'instance.** `mesuré` le
  1er septembre 2026, après une coupure et un redémarrage complet de la machine :
  la pile se relève seule, et l'index est intact à l'octet — 4 365 chunks,
  15 196 sommets, 15 374 arêtes, 23 documents, 13 objets MinIO, exactement les
  chiffres d'avant la coupure. Les bind mounts sous `Datas/database/` sont la
  raison. **Ce qui ne survit pas est le contenu des conversations, pas l'index.**

---

## 5. Où on en est

### 5.0 Le lot 11 est fusionné — 25 septembre 2026

`main` = **`2918ccc`** (fusion `--no-ff` de `claude/reingestion-empty-elements-e8882f`,
sommet `4398784`, 20 commits, arbre `1ff7d1e`). Porte qualité rejouée **sur le
commit de fusion lui-même**, dans un arbre de travail détaché : `make all`,
rc=**0**, **1 084 tests passés**, **35 mutations rejouées, toutes rouges**.

Ce que le lot met dans `main` : le harnais d'équivalence des `element_id`
(`src/equivalence_des_identifiants.py`, **qu'aucun module de production
n'importe** — c'est le pilote qui le lance), les scripts `scripts/campagne/*.py`
et `scripts/rejouer-les-mutations.py` avec leurs tests, la table des mutations,
l'instantané versionné
`documentation/campagnes/2026-09-24-instantane-des-identifiants/`
(empreinte `e945893b1021e2f1aa3809434a889443ed9fb85e2a7e290cd329f077687f0f6d`),
le registre §4.36 à §4.41, et un `Makefile` dont `lint`, `typecheck`, `format`
et `format-check` voient désormais `scripts/`, et dont `all` appelle `mutations`.

**La décision du 24 septembre 2026, prise par le pilote : option (a).** On ne
touche pas aux puces vides. La réparation **sort du plan** : le motif et les six
options chiffrées sont au registre (§4.37). Ce qui est livré n'est donc pas une
réparation, c'est l'**instrument** qui permettra de constater que la réingestion
ne déplace rien.

**La fusion est un déploiement, et il a été observé.** Les conteneurs montent
`./src` depuis ce clone et le démon tourne avec ses quatre capteurs armés :
quatre minutes de surveillance après la fusion, **quatre recyclages du serveur
de code**, **zéro erreur de chargement**, les quatre capteurs évalués et tous
`skipped`, **zéro run créé** (958 avant, 958 après), `docling-service` toujours
`healthy`, et les **huit comptes des stores identiques** au relevé d'avant.

**Prochaine étape : la campagne.** Purge, puis réingestion **sans aucun
changement du code d'extraction**, puis `comparer` contre l'instantané figé.
**Zéro `element_id` déplacé est le résultat attendu** — et c'est la seule
manière de le savoir, puisque la décision (a) laisse l'extraction en l'état.


### 5.0 bis La DEUXIÈME campagne de référence est FAITE — 25 septembre 2026

**Elle est faite, et son résultat est celui qu'on attendait : `DEPLACES 0`.**
Le compte rendu mesuré, chiffre par chiffre avec sa commande et son heure, vit
à son site canonique
[`documentation/campagnes/2026-09-25-deuxieme-campagne-de-reference.md`](campagnes/2026-09-25-deuxieme-campagne-de-reference.md).
**Aucun chiffre n'est recopié ici** : le §0 de ce mandat interdit de dupliquer
une valeur mesurée, et les trois lignes ci-dessous sont un état, pas une table.

**Ce que la campagne a fait**, sur la branche `claude/campagne-2-purge-reingestion-08b58a`,
partie de `d22a153` : purge des trois stores **et** du HTML nettoyé par
`python -m src.wipe_stores` (`rc=0`, quatre volets), l'unique redémarrage de
`docling-service` que la purge prescrit elle-même, puis la réingestion par le
**geste du lot 8** — le marqueur `reingerer:2026-09-25-campagne-2` posé sur les
curseurs des deux capteurs dont la source porte des fichiers.

**Trois résultats, et ce sont des états :**

1. **la réingestion est complète et elle est passée par le CAPTEUR** — 23
   partitions demandées, **23 runs créés**, **23 `SUCCESS`**, zéro échec, zéro
   reprise. Le silence du §4.32.a **ne s'est pas produit** ;
2. **`comparer` contre l'instantané versionné rend `rc=0`, `23 / 23`,
   `DEPLACES 0`**, aucun déplacement déclaré. Les huit comptes, l'empreinte des
   clés MinIO, `verify_contract` et `index_report` **ligne pour ligne**, le texte
   des 44 ancrages et les quatre valeurs de rappel sont identiques avant et
   après. La décision (a) est confirmée par la mesure ;
3. **l'exigence 5 du contrat est ÉPROUVÉE pour la première fois** — le service de
   l'agent tourne désormais sur ce poste, `agent_reindex_sensor` est parti seul en
   fin d'ingestion, et son run a réussi.

**Deux constats du registre se ferment par elle** — §4.32.a, dont le lot 8
disait que « le premier geste de réingestion reste à faire sous les yeux de
quelqu'un », et §4.28.c sur l'exigence 5. **Deux constats neufs s'ouvrent** :
§4.42.a, la CLI Dagster pose un curseur et ne sait pas le lire ; §4.42.b,
l'empreinte des clés MinIO circule sans sa recette.

**Ce que la branche porte**, et rien d'autre : le compte rendu, le registre
§4.42, ce paragraphe, et **un** commit de code — `9f21b38`, qui ajoute `k = 50`
aux valeurs de rappel mesurées par défaut, dans `scripts/campagne/`.
`git diff main..HEAD --stat -- src/` et `-- Datas` rendent tous deux le **vide**.

**La branche a depuis été vérifiée, corrigée et FUSIONNÉE** (`--no-ff`, 25
septembre 2026). La vérification a mesuré **deux phrases fausses** dans le
compte rendu — les 44 ancrages ne sont pas tous `label=text` (36 `text`, 8
`list_item`), et les 13 ticks bloqués ne citent pas tous `pdfs_job` (12 sur 13,
le premier cite `livres_html_job`) — corrigées **dans la branche avant la
fusion**, chacune à son site, avec la mesure qui les tranche.

**La pile est laissée debout, démon compris.** C'est la différence avec la
première campagne, qui avait dû arrêter le démon pour cesser de produire un run
rouge toutes les trente secondes : l'agent tournant, la réindexation réussit et
le capteur saute proprement. Le §7 du compte rendu dit l'état exact.

**La branche n'est pas supprimée** : elle est sortie dans l'arbre de travail
`.claude/worktrees/reingestion-empty-elements-e8882f`.


### 5.0 ter SeaweedFS est EN SERVICE — 25 septembre 2026

**La bascule du stockage objet est faite.** SeaweedFS est la solution **retenue
par le propriétaire du chantier en début de semaine du 21 septembre 2026** ;
elle est **en service depuis le 25**. Le choix ne se rouvre pas : il se
consigne. Les deux sites canoniques sont
[`documentation/campagnes/2026-09-25-bascule-seaweedfs.md`](campagnes/2026-09-25-bascule-seaweedfs.md)
— les huit critères, la procédure et le retour arrière — et le **§4.43** du
registre, qui porte les mesures d'après. **Aucun chiffre n'est recopié ici.**

**Ce qui a changé, en trois lignes :**

1. **le pipeline écrit et lit sur `seaweedfs:8333`**, et les trois conteneurs
   qui parlent au store — `dagster-daemon`, `dagster-webserver`,
   `docling-service` — ont été **recréés** pour relire le `.env`, jamais
   redémarrés : un `restart` ne relit pas le `.env` ;
2. **le corpus a été réingéré en entier derrière la nouvelle passerelle**, par
   le geste du lot 8 et sous l'étiquette `reingerer:2026-09-25-bascule-seaweedfs`.
   Elle était **obligatoire** : les `minio_url` du graphe et des copies
   nettoyées portent l'endpoint, donc changer l'endpoint change toutes les
   adresses stockées. Les **clés**, elles, ne changent pas ;
3. **les huit comptes, l'empreinte des clés et `comparer` rendent exactement ce
   qu'ils rendaient sur MinIO.** La bascule est donc **transparente pour
   l'index**, et c'est mesuré, pas supposé.

**MinIO est CONSERVÉ, debout, avec ses 212 objets, et c'est le retour arrière.**
Il n'a été ni arrêté, ni recréé, ni purgé, et rien n'y a été écrit — les dates de
modification de ses 212 objets sont celles d'avant la bascule. **On ne le retire
pas sans une décision du pilote**, et tant qu'il est là, le retour arrière coûte
une purge et une réingestion, procédure écrite au §4.8 du compte rendu de la
bascule.

**Le piège qui commande toute la procédure, et qu'il faut connaître avant de
toucher à la pile** : `MINIO_ROOT_USER` et `MINIO_ROOT_PASSWORD` portent
désormais le jeu **SeaweedFS**, et ce sont **aussi** les variables dont le
service `minio` se configure lui-même. **Recréer `minio` changerait ses
identifiants et détruirait le retour arrière.** Donc : on **nomme** les services
qu'on recrée, et un `docker compose up -d` **nu** est interdit sur cette pile.
Le défaut est consigné au **§4.43.c**, avec la forme de son remède.

**L'autre dépôt reste à basculer.** `rag-agent-chat` a son propre `.env` : il
doit recevoir `MINIO_ENDPOINT=seaweedfs:8333` et le jeu **lecture seule**. Un
témoin l'attend dans SeaweedFS — bucket `temoin-bascule`, objet
`bascule-2026-09-25.txt` — lu par appel direct avec ce jeu-là. **Cette bascule
appartient au pilote de l'agent**, et elle se coordonne avec lui.

**Un état persistant à ne pas oublier** : les quatre capteurs ont été **arrêtés
puis relancés** autour de la recréation du démon (le geste prudent du §4.3 du
compte rendu). Ils sont donc passés de `DECLARED_IN_CODE` à `RUNNING`, et cet
état-là **vit dans le Postgres de Dagster**, pas dans le code. Il est armé et
correct ; il n'est simplement plus celui que le code déclare.

### 5.1 Les branches — il n'y en a plus qu'une

| Réf | Pointe | Rôle |
|---|---|---|
| `main` | *mesure-la* : `git rev-parse --short main` | **tout ce qui est fusionné, y compris ce mandat, le registre et le corpus.** Le lot 0 y est depuis le 29 août 2026 (fusion `b59bf38`), le lot 0b depuis le 31 (fusion `e998e7d`). Un clone frais suffit : il n'y a rien à checkouter. **Le SHA a été retiré de cette case, à dessein** : il a périmé quatre fois en trois jours, dont une fois dans l'heure qui a suivi le commit qui le corrigeait. Une case qui dit « remesure » et donne quand même un chiffre invite à lire le chiffre |
| tag `reference/lot-0-avant-reparation` | `832c566` | la version du lot 0 avant sa **première** réparation. Base de comparaison, pas une ligne de travail — d'où un tag et non une branche |

**Aucun lot n'est en vol.** `lot-0` a été fusionnée (`--no-ff`, `b59bf38`) puis
supprimée, en local **et côté distant**. Le lot 0b l'a été le 31 août 2026
(`--no-ff`, `e998e7d`), branche supprimée des deux côtés dans le même geste. **Le
lot 3 l'a été le 1er septembre 2026** (`--no-ff`, `4e28594`), et avec lui **cinq**
branches et leurs arbres de travail — les deux du lot 3 et les trois des lots 1 et
3 qui ne portaient plus rien hors `main`. Un clone frais ne voit qu'une seule
branche et un tag (`mesuré`, 1er septembre 2026).

**Le lot 6 a été fusionné le 3 septembre 2026** (`--no-ff`, `69a6786`) : 4
commits de campagne, 15 de réparation, `499ecb2` intact comme ancêtre. **C'est le
dernier lot du plan.** Ses quatre arbres de travail et ses trois branches ont été
supprimés, la branche du lot des deux côtés, et `make install` relancé depuis le
clone principal **après** la suppression.

**Le lot 5 a été fusionné le 2 septembre 2026** (`--no-ff`, `d8c67c5`) : 12
commits de livraison, 18 de réparation, `e5103cf` intact comme ancêtre. Ses trois
arbres de travail et ses trois branches ont été supprimés, la branche du lot des
deux côtés, et `make install` relancé depuis le clone principal **après** la
suppression. **Aucun lot n'est en vol, et il n'en reste qu'un au plan.**

**Le lot 4 a été fusionné le 2 septembre 2026** (`--no-ff`, `79cd2bc`) : 14
commits de livraison, 11 de réparation, `e9ebe43` intact comme ancêtre — zéro
réécriture. Ses trois arbres de travail et ses deux branches ont été supprimés,
la branche du lot des deux côtés. **Aucun lot n'est en vol.**

**Un répertoire d'arbre de travail a résisté, et il faut le savoir.**
`.claude/worktrees/lot-1-observation-b12761` — 484 Mo — porte un
`Datas/database/` écrit par Docker en `root` : `git worktree remove` rend
« Permission denied ». La **branche** est supprimée et `git worktree prune` a
retiré l'enregistrement, donc git n'en sait plus rien et rien ne l'ancre
(`mesuré` : aucun conteneur n'y monte quoi que ce soit). Il ne reste qu'un
répertoire mort, à retirer en `sudo` quand l'occasion se présente.

**Cinq branches vides ont été supprimées avec elle**, toutes à 0 commit hors
`main` (`mesuré`) : le harnais crée un arbre de travail et une branche pour
chaque conversation, y compris celles qui n'écrivent rien — un auditeur, un
pilote. **Ce n'est pas une infraction à la règle « une branche par lot en
vol »**, mais ça la rend illisible : à la fin d'un lot, compte les branches qui
portent des commits, pas les branches.

**Règle, pour ne pas refaire le désordre : une branche par lot en vol, jamais
plus.** Le chantier a compté jusqu'à cinq branches parce qu'une conversation
qui répondait à une question créait sa branche. Un lot qui n'est pas en vol
n'est pas une branche : soit il est fusionné dans `main`, soit il devient un
tag s'il faut pouvoir y revenir.

**Ce qui a été supprimé, et pourquoi c'était sans risque :**

- `claude/audit-refonte-rag-pipeline-fd8418` — portait ce mandat, le registre
  et le hook versionné, **aucun code**. Fusionnée dans `main` en avance rapide.
  Elle n'avait plus de raison d'être, et tant qu'elle existait il fallait
  savoir la checkouter pour lire ce fichier ;
- `claude/rag-ingestion-pipeline-restore-5e9fa1` — remplacée par le tag
  `reference/lot-0-avant-reparation`, qui pointe **exactement le même commit**.
  Rien n'est perdu : la comparaison qui a servi d'angle A à l'audit reste
  possible depuis le tag, `lot-0` étant désormais dans `main` — l'audit a
  conclu que rien n'avait été perdu au replantage (registre §8) ;
- `claude/rag-ingestion-restore-9e5aa5` — 0 commit au-dessus de `main`, jamais
  poussée (`mesuré`). Vide.

**La règle a tenu jusqu'au bout :** `lot-0` n'a été fusionnée qu'après son
audit indépendant **et** la réparation que cet audit a rendue nécessaire.

**L'écart au mandat du lot 0, tranché.** Le lot 0 avait été livré sur une
branche neuve plutôt qu'en réparant celle du mandat, et proposait soit de
force-pousser l'historique réparé sur l'originale, soit de livrer droit dans
`main`. Les deux ont été refusées : la première aurait détruit la base de
comparaison au moment où l'audit en a besoin, la seconde aurait fusionné sans
audit. Le choix du développeur — livrer ailleurs et garder l'originale — était
le bon ; c'est de ne pas l'avoir posé comme un écart au moment de le faire qui
était le défaut.

### 5.1 bis Le lot 0b : livré, audité, réparé, réaudité, réparé, fusionné

Cinq conversations, dix commits, deux tours d'audit indépendant. Le détail vit
au **registre §8** — les constats **R1**, **D1**, **C**, les neuf affirmations
fausses et les neuf points de la seconde réparation. C'est son site canonique.

Ce que le pilote a vérifié **de ses mains**, sur le contenu final et sur le
résultat de la fusion (`mesuré`, 31 août 2026) :

- **la porte sur le commit de fusion** : `ruff` propre, `mypy` « no issues found
  in 36 source files », **552 tests verts**, `make all` en **2** — le rouge
  d'alors, `format-check` sur les quatre fichiers pliés à la main — et l'arbre
  **non sali**. *(Mesure du 31 août 2026, conservée telle quelle : elle décrit le
  commit de fusion du lot 0b. Ces quatre fichiers ont été reformatés depuis, et
  `make all` rend 0 — §2.4.)* ;
- **le contrôle d'identité, depuis un clone frais, après `make install` seul,
  dans un arbre sorti à un commit dont la configuration ne porte pas le hook** :
  auteur interdit → refusé ; committer interdit → refusé ; auteur seul interdit
  → refusé ; liste blanche → accepté. Puis la même chose sur un **vrai**
  `git merge --no-ff` : refusé, `HEAD` inchangé ;
- **le corpus intouché** : `pre-commit run --all-files` laisse `Datas/` à
  **0 fichier modifié**, `detect-secrets` passe sur tout l'arbre, une édition
  de 26 octets entre à +26 octets, et un chapitre neuf de 4 Mo est accepté ;
- **le geste canonique de scan du `README`** rend `rc=0` et **0 octet** sur le
  résultat de la fusion — il rendait `rc=123` avant la seconde réparation ;
- **les mutations rejouées** : `default_status` retiré → deux tests rouges et la
  suite privée de la classe neuve **verte**, ce qui EST le constat §4.18 ;
  `TYPES=""` dans l'installeur → il sortait en **0** en annonçant un montage
  qu'il n'avait pas fait ; `files: '^Datas/'` ajouté à la racine → sept hooks
  « no files to check », un fichier sale commité en `rc=0`, **550 tests verts** ;
- **`make install` relancé depuis le clone principal** après la fusion :
  `INSTALL_PYTHON` pointe désormais le `.venv` du dépôt et non celui d'un arbre
  de travail temporaire. Sans ce geste, supprimer la branche fusionnée aurait
  rendu **tout commit impossible** dans le dépôt et tous ses arbres — échec
  fermé, donc sans danger, mais bloquant. **C'est désormais l'étape 5 bis du
  §7.**

**La leçon de pilotage du lot 0b, et elle est chère.** La première livraison a
**fermé une porte et en a entrouvert une autre sans l'écrire** : en déménageant
le contrôle d'identité de `.git/hooks` vers `.pre-commit-config.yaml`, elle l'a
rendu **conditionnel à l'arbre de travail** — et aucun des 111 commits de `main`
ne portait le hook. Trois arbres sur quatre acceptaient l'adresse
professionnelle, et le pilote l'a mesuré en créant le commit. Ni le développeur
ni le pilote ne l'avaient vu ; l'audit indépendant l'a trouvé. **Une règle
survit à son motif : quand du code change de place, rouvre les propriétés dont
le seul motif était l'ancienne place.**

### 5.1 ter Le lot 1 : mesuré, audité, zéro commit — et un lot supprimé du plan

Deux conversations, **aucun commit**, aucun diff, corpus intact à l'octet. Le
détail vit au registre §3.2, §3.3, §3.4, §3.5 et §4.21 à §4.27.

Ce que le pilote a vérifié **de ses mains**, sur la pile laissée debout
(`mesuré`, 31 août 2026) :

- **le chiffre qui décide** : **159** arêtes `SectionHeader → SectionHeader`
  contre **29** `Document → SectionHeader`. Un graphe plat rendrait 0 et 188 ;
- les profondeurs des trois documents au chiffre près, et des fils d'Ariane
  réels à trois niveaux ;
- **la cause du chapitre plat, recomptée sur le corpus versionné** : le nombre de
  titres de rang 0 égale le nombre de balises `<h1>` dans **22 chapitres sur
  22**. *(Le pilote avait ajouté ici que `Practical/…/10. Unifying GenAI Systems
  with MLflow.html` était « le seul chapitre retenu sans aucun `<h2>` ». **C'est
  faux : ils sont trois**, et le tableau des balises était sous ses yeux. Les deux
  `Preface.html` n'ont aucun `<h2>` non plus et **s'imbriquent quand même** —
  `{0: 9, 1: 4}` et `{0: 8, 1: 4}` sur le graphe vivant. « Sans aucun `<h2>` »
  n'est donc pas la propriété discriminante ; la vraie est au registre §3.2, et
  elle est désormais assertée par `test_non_platitude.py` à pleine portée.)* ;
- **le no-op**, dans le code : `elements.py:272` fait
  `place(element_id, heading_rank or 0)` et `docling_level_rank` rend `None`
  quand `level` est absent. La correction §3.2 ne pouvait rien changer ;
- **la troncature** : 8 (1,0 %) sur le texte stocké contre **16 (2,1 %)** sur le
  texte encodé, maximum 140 contre **149**, et les 8 déjà tronqués sont **tous**
  `label=table`. `index_report` annonce bien 8 et 1,0 %, **pas 0 %** ;
- **26 images HTML sur 26 sans `minio_url`**, PDF 10/10 ;
- `sequence` sur **2 285 arêtes sur 2 285**, de 0 à 1 269, aucune absente ;
- le schéma `SectionHeader` : `label`, `page_no`, `text`, `minio_url` — **pas de
  `depth`** (§4.11) ;
- **§4.26** : les cinq stores sont des bind mounts de l'arbre de travail du lot,
  et le seul `.env` du poste y vit aussi.

**Le pilote s'est trompé une fois, et l'audit l'a corrigé** : il avait écrit que
le hook figé sur le `.venv` d'un arbre temporaire était « bloquant ». Il ne
l'était pas — le `.venv` existait, son `python` étant un lien vers
l'interpréteur partagé d'`uv`. Le piège était **armé, pas déclenché**. Mesure
l'état, ne déduis pas la conséquence.

### 5.1 quater Le lot 3 : livré, audité, réparé, fusionné

Onze commits de livraison, puis six de réparation, fusionnés le 1er septembre 2026
(`--no-ff`, `4e28594`). Le détail vit au registre.

**Ce que le pilote a remesuré de ses mains avant de trancher, et rien n'a été pris
sur parole** (`mesuré` le 1er septembre 2026) :

| Ce qui décidait | Mesure du pilote |
|---|---|
| le juge de la réparation — la mutation « groupes anonymes comptés comme des titres », `ranking.py:68` → `if True` | `test_non_platitude.py` **ROUGE**, `rc=1`, 2 tests. C'est la bascule : la même mutation le laissait vert avant la réparation |
| `make all` sur le **résultat de la fusion d'essai**, pas sur la branche | `rc=0`, 708 tests, « 67 files already formatted » |
| `make install && make all` sur `main` après fusion | `rc=0` tous les deux |
| le balayage de graines sur `main` fusionné — graine 0 plus 25 aléatoires | **26/26 vertes**, 0 rouge |
| M15 (la levée contre le mélange de deux modèles), M12 (la remontée de racine), M20 (le code de sortie de `verify_data`) | rougissent : 4, 7 et 5 tests |
| les deux mutations que le rapport déclare **survivantes** | survivantes, confirmé : suite entière `rc=0` sous chacune |
| les 11 SHA du lot 3 sous la réparation | intacts — `22c782e` est ancêtre de `7eb0922`, zéro réécriture |
| l'index vivant, dans le conteneur | 4 365 chunks, 15 196 sommets, 23 documents, 13 objets MinIO, `verify_contract` `rc=1` sur ses deux anomalies |
| les mentions interdites, fichiers **et** messages de commit | aucune |

**Et le pilote a trouvé deux affirmations fausses que ni le lot ni son audit
n'avaient vues**, toutes deux nées dans le commit de style `9d2e341` :
`README.md` annonçait « 66 files already formatted » là où la mesure rend **67**,
et sa table des cibles décrivait encore `ruff format src/` alors que le même
commit venait d'étendre les deux cibles à `src/ tests/`. **Le commit qui fermait
un angle mort a créé un mensonge de documentation dans le même geste** — c'est-à-dire
exactement le défaut que le lot 5 doit chasser. Corrigé par le pilote après fusion,
pas renvoyé en troisième tour : la porte était verte et le juge était passé.

*(Le rapport de réparation annonçait « un total de 20 lignes de diff réparties sur
trois commits de style ». Remesuré : 9 + 4 + 7 = **20**. Exact.)*

**Ce que l'audit a établi, et qui est à son crédit** : aucune régression, les six
points du mandat livrés plus §4.5 et §4.14, et **tous ses chiffres reproduits** —
sur le graphe comme sur ChromaDB — par l'audit et par le pilote. Le lot était bon.

**Les cinq bloquants, et le premier est le plus instructif :**

1. **la fixture assertait ce que la production ne produit pas.**
   `document.iterate_items()` ne rend jamais les nœuds de groupe, la capture en
   omettait 262, et deux titres perdaient leur rang **en silence** dans le filtre
   des `None`. Le test assertait 39 titres là où le graphe en porte **41**. Et le
   coût dépassait deux titres : **le test bâti sur du réel était aveugle au
   mécanisme même qu'il existe pour éprouver sur du réel** — la mutation
   « conteneurs anonymes comptés comme des titres » le laissait vert, et seul
   l'arbre fabriqué à la main la voyait. Registre §3.6 bis ;
2. **« le seul chapitre sans `<h2>` »** : ils sont **trois**, et deux s'imbriquent.
   Le faux est né au lot 1, le pilote l'a recopié deux fois en ayant le tableau des
   balises sous les yeux, et le lot 3 l'a recopié de lui, jusque dans le nom d'un
   test. Registre §3.2 ;
3. **trois gardes neufs que rien ne gardait** — M15 (la levée contre le mélange de
   deux modèles d'embedding), M12 (le seul contrôle d'ordre du contrat), M20 (le
   code de sortie de `verify_data`). Registre §4.4 et §4.5 ;
4. **`verify_contract` avait cinq trous**, dont `rc=0` sur un index vide — et tous
   ses contrôles vivent derrière ce garde. Registre §4.4 ;
5. **`index_report` comptait les documents par `filename`** et rendait 22 pour 23,
   les deux `Preface.html` se confondant. Le cas d'école que l'exigence 3 cite
   comme sa preuve, dans un fichier que le lot venait de réécrire.

**La leçon de pilotage, et elle est nouvelle.** Le lot 3 a fait exactement ce
qu'on lui demandait — bâtir le test sur des captures réelles plutôt que sur un
arbre fabriqué — et **c'est cette bonne décision qui a produit le défaut** : une
capture est une donnée, et une donnée peut être incomplète sans que rien ne le
dise. Le test rejouait un algorithme de **remontée** sur une fixture qui ne
portait que les nœuds de contenu. **Quand un test rejoue un parcours, sa fixture
doit porter le graphe complet, pas seulement les nœuds qui l'intéressent** — et
la seule façon de le savoir est de compter ce qu'on jette.

### 5.1 quinquies Le lot 4 : livré, audité, réparé, fusionné

Quatorze commits de livraison, onze de réparation, fusionnés le 2 septembre 2026
(`--no-ff`, `79cd2bc`). Le détail vit au registre ; §4.29 porte ce qu'il laisse.

**Ce que le pilote a remesuré de ses mains avant de trancher** (`mesuré` le
2 septembre 2026) :

| Ce qui décidait | Mesure du pilote |
|---|---|
| `e9ebe43` sous la réparation | ancêtre de `a845736`, 11 commits, **zéro réécriture**, 0 fusion dans la plage |
| l'arbre de la fusion d'essai | **identique** à celui de la pointe, 0 conflit — la branche était descendante linéaire |
| `make all` sur le résultat de la fusion d'essai | **rc=0**, 857 tests, 74 fichiers formatés |
| balayage de graines sur ce résultat — graine 0 plus 25 aléatoires | **26/26 vertes** |
| les sept juges de B1 et B2.a à B2.d | **tous rouges** : 9, 1, 2, 2, 3, 1, 1 |
| le juge de B6 — un septième module rendu inimportable | **rouge** |
| B3 — le repli du §2.4 contre le `Makefile` | aligné, **cible par cible** |
| B4 — le compte des `pragma` porteurs | **11** (7 en Python, 4 dans la capture YAML), exact |
| le reste de B1 — `CLEANED_SUBDIR=htms` sur un faux corpus | **corpus détruit** ; `=database` détruit les stores |
| corpus | 25 fichiers, 57 381 999 octets, **non touché par le diff** |

**Le renversement de plan, et il est double.** Le lot a mesuré que ses
`element_id` ne bougent pas ; l'audit l'a reproduit indépendamment — 15 173 des
deux côtés, différence symétrique nulle, et les 3 750 identifiants de l'index
vivant sont un sous-ensemble strict des deux ; le pilote l'a confirmé
**statiquement** : `main` faisait `prov[0].page_no`, le lot fait `pages[0]`, la
même valeur par construction. **§4.22 ne tue donc plus le jeu de questions du lot
6** — ce que le §6 et le registre §4.28.e affirmaient. Mais **l'ordre tient quand
même**, pour deux raisons neuves : le jeu de *chunks* change (4 365 → 4 367) et
`page_no_end` demande une réingestion pour exister. La conclusion survit à
l'effondrement de son motif, et c'est la seule raison pour laquelle elle n'a pas
coûté un lot.

**La leçon de ce lot, et elle est nouvelle.** Le lot a trouvé et fermé **cinq de
ses propres gardes creux** en rejouant ses mutations, l'a déclaré, et son audit en
a trouvé **quatre autres**. Personne n'a menti, aucun chiffre n'était faux — et
neuf gardes décoratifs ont quand même failli être livrés. **Un garde ne se juge
jamais à sa lecture, seulement à la mutation qui doit le faire rougir**, et le
motif commun des neuf est unique : *le test observe ce qu'il a lui-même fourni, ou
observe une absence.*

### 5.1 sexies Le lot 5 : livré, audité, réparé, fusionné — et il n'était pas cosmétique

Douze commits de livraison, dix-huit de réparation, fusionnés le 2 septembre 2026
(`--no-ff`, `d8c67c5`). Le détail vit au registre.

**Le mandat l'annonçait « ingrat, qui ne corrige presque aucun comportement ». Le
mandat avait tort, et c'est le vrai retour du lot** : trois de ses constats
étaient des défauts de comportement, et le premier **rompait le contrat**.

| Ce qu'on croyait cosmétique | Ce que c'était |
|---|---|
| `CLEANED_SUBDIR`, un réglage de trop | **deux sites décidaient du nom du sous-répertoire nettoyé** — celui selon lequel le nettoyage écrit, celui selon lequel `document_identity` retire le segment — et rien ne gardait leur accord. L'`element_id` d'un chapitre changeait : **exigences 2 et 3 rompues, sans aucune erreur**. Reproduit par l'audit sur l'index vivant |
| `chunk_ids`, du code mort à retirer | **contourné, pas mort** : `vectors.py` réinlinait la même forme, seule version exécutée, et **gardée par rien**. L'amputer aurait supprimé les seuls tests d'une clause du contrat |
| la fenêtre du modèle, un chiffre de documentation | **gardée par rien** : la fixer à 256 laissait la suite verte, donc l'instrument pouvait rapporter une fenêtre fabriquée et son taux de troncature avec elle |

**Et ses quatre bloquants étaient, quatre fois, la famille qu'il existe pour
fermer — commise par lui.** Un renvoi `mesuré` rendu faux par le commit *suivant*
et recopié à cinq sites ; un dénombrement qui **niait le déverrouillage sur lequel
reposent ses propres tests** ; une conséquence devenue fausse au lot 4, recopiée à
neuf passages ; et un invariant énoncé dans un docstring sans écrire le garde —
le treizième garde creux du chantier.

**Ce n'est pas une charge contre le lot : c'est la mesure de la difficulté du
travail, et c'est la leçon de ce lot.** Écrire une documentation vraie est plus
dur que d'écrire du code juste, parce qu'une phrase ne rougit pas. Le lot s'est
fait prendre deux fois de son propre aveu, l'audit deux fois de plus, la
réparation trois fois encore — et le pilote une fois, deux jours plus tôt. **Le
seul remède qui ait tenu est celui que le lot a nommé : désigner un SYMBOLE et non
une ligne, et convertir toute phrase d'exhaustivité en garde qui rougit.**

**Ce que le pilote a remesuré de ses mains** (`mesuré` le 2 septembre 2026) : le
juge de B4 — un `DESCRIBE` en échec relu comme « colonne présente » — rend `rc=1`
et 3 rouges là où il laissait la suite **entièrement verte** ; `sed -n '230p'` ne
porte plus le renvoi et les cinq sites nomment le symbole ; le balayage AST rend
**14** modules sans dépendance et **4** porteurs, indépendamment ; `delete_document`
supprime par `source_path` et **jamais par id**, donc la duplication annoncée était
impossible ; `make all` rend **0** sur le résultat de la fusion d'essai, **865
tests**, balayage de graines **26/26 vertes**, corpus intact à l'octet.

### 5.1 septies Le lot 6 : la campagne — et le seul lot dont la trouvaille n'est pas dans son diff

Quatre commits de campagne, quinze de réparation, fusionnés le 3 septembre 2026
(`--no-ff`, `69a6786`). **Zéro ligne de `src/`** : ce lot mesure, il ne corrige
pas. Son compte rendu vit à son site canonique,
`documentation/campagnes/2026-09-02-premiere-campagne-de-reference.md`.

**Ce que la campagne a fermé par la mesure**, sur un index réingéré par le code de
`main` : la chaîne d'images HTML passe de **0 sur 199** à **199 sur 199** et le
bucket de 13 à **212** objets ; les jeux de chunks troués de **2 à 0** et les
chunks de 4 365 à **4 367**, exactement la prédiction du §4.28.a ; `page_no_end`
est peuplé — **0 sommet sur 15 173** à `NULL` contre 15 173 avant ; et le garde du
§4.15 est **observé en vol pour la première fois**, 12 ticks `SKIPPED` consécutifs
nommant chacun le run qui bloque.

**Sa trouvaille matérielle n'est pas dans son diff, et c'est le fait le plus
important de ce mandat aujourd'hui.** Réingérer par le chemin nominal **ne marche
pas, en silence** : le capteur demande 23 runs, Dagster en crée **zéro**,
`skip_reason` vaut `None`. La clé de run dérive du `mtime`, donc elle est consommée
pour toujours — le défaut exact que la réparation du lot 0 avait fermé dans
`reindex_job.py` et laissé intact dans `factory.py`. Registre **§4.32.a**.

**Et il porte une ironie qu'il faut connaître avant de le corriger** : *c'est ce
défaut qui protège l'index en ce moment même.* Le daemon a démarré **trois fois**
sans qu'aucune conversation du chantier le décide, et rien n'a été réingéré
par-dessus la campagne — uniquement parce que la clé était déjà consommée. **Le
jour où on répare §4.32.a, il faut avoir tranché si les capteurs restent armés.**

**La leçon de ce lot, et elle est neuve.** On lui demandait « un récit et non du
code », et son audit a montré que **le récit se vérifie comme du code** : chaque
chiffre remesuré s'est reproduit exactement, mais quatre affirmations ont été
prises en défaut — une phrase qui prêtait au garde un périmètre qu'il n'avait pas,
des agrégats donnés `mesuré` sous une commande qui ne les produit pas, un compte de
constats faux d'une unité, et un « pas éprouvable » qui n'était qu'un choix de
périmètre. **Un rapport de mesure n'est pas plus fiable qu'un test : il faut un
juge pour chacune de ses phrases.**

### 5.2 Le lot 0 : livré, audité, réparé, fusionné

Le détail complet — les six points de réparation, la conception retenue pour
la reprise de réindexation, les alternatives écartées — vit au **registre §8**.
C'est son site canonique ; ne le recopie pas ici.

Ce que le pilote a vérifié **de ses mains**, sans reprendre un chiffre
(`mesuré`, 29 août 2026) :

- les 8 commits d'origine **intacts** : `390ce8a` est resté ancêtre, rien n'a
  été réécrit ni rebasé ;
- `make all` sur le **résultat de la fusion** — c'est le point où deux branches
  vertes peuvent donner un arbre rouge, et personne ne l'avait mesuré :
  **535 tests verts**, `ruff` propre, `mypy` sans erreur ;
- **8 des 9 mutations annoncées, rejouées et rouges** : le `default_status` du
  sensor, l'asset qui lève, le `run_key` à tentative, le filtre `SUCCESS`, la
  garde « déjà en vol », le `max()` multi-sources, le code de sortie de
  `wipe_stores` et le décompte de l'échec MinIO ;
- aucun test perdu : deux noms disparus, **tous deux renommés**. Le test
  `test_un_echec_ne_rougit_pas_le_run_mais_le_crie` *devait* disparaître — il
  assertait le défaut ;
- le compte du README juste **dans chaque commit qui le change** ;
- hygiène : aucune mention d'IA, auteur en liste blanche, aucun `skip`,
  `xfail`, `type: ignore` ni `noqa` ajouté.

### 5.3 Ce que le lot 0 a fait apparaître, et qui reste ouvert

Le lot lui-même avait fait naître §5.4, §5.5 et §5.6 au registre. Son audit et
sa réparation en ont ajouté sept : **§4.15** (famine sur un run bloqué, et le
*run monitoring* absent de `dagster.yaml` qui les fermerait toutes d'un geste),
**§4.16** (réindexations concurrentes, cas étroit résiduel), **§4.17**
(classification des statuts terminaux non gardée), **§4.18** (les sensors
d'ingestion de `factory.py:335` livrés armés sans garde — tout le pipeline est
livrable à l'arrêt), **§4.19** (le refus de démarrer hors contrat non prouvé),
**§4.20** (`make audit` rouge et aveugle au groupe `dev`), **§5.7** et **§5.8**.

**Aucun n'est entré dans le diff.** Périmètre strict : ce qui est trouvé et non
traité va au registre.

**Trois d'entre eux sont désormais fermés par le lot 0b** — §4.18, §5.4
(première moitié : la porte constate au lieu d'écrire) et §5.5. Le titre de
cette section reste au passé : elle dit ce que le lot 0 a fait APPARAÎTRE, pas
ce qui reste ouvert aujourd'hui. **L'état ouvert/fermé a un seul site canonique,
le registre §3 à §7 contre son §8.** Ne le déduis pas d'ici.

### 5.4 Les deux désaccords tranchés

**Le développeur du lot 0 sur « une fois par rafale ».** Il a livré une
réindexation par rafale là où le contrat dit « une fois l'ingestion terminée »,
et il l'a dit lui-même. Il avait raison : « fin d'ingestion » n'existe pas comme
événement dans cette architecture. **C'est un écart assumé, écrit comme tel** —
`README.md`, `documentation/orchestration.md` et le docstring de
`reindex_job.py`. Le levier si l'agent supporte mal des réindexations
rapprochées est `minimum_interval_seconds` (30 s). Un réglage, pas une refonte.

**Le développeur de la réparation sur `make all`, et le pilote s'est rangé.**
Le registre rangeait §5.4 dans le lot de la hiérarchie au motif qu'il touche
`extraction.py`. C'était confondre deux choses : *reformater* peut attendre,
mais *une porte qualité qui écrit dans le dépôt qu'elle contrôle* ne le peut
pas. Il a dû révoquer trois fichiers avant chacun de ses six commits, parce
qu'il le savait ; le suivant ne le saura pas. **Versé au lot 0b.**

**Et le développeur du lot 3 sur les quatre fichiers, deux fois de suite.** Il a
reformaté `extraction.py` et `matter.py` en écarts déclarés, parce que le hook
`ruff-format --check` refuse tout commit qui les touche et que ses gardes y
vivent. **Le pilote s'est rangé, puis il est allé plus loin** : le report des deux
derniers au lot 5 supposait que personne n'y toucherait, alors que le lot 4 vise
`extraction.py` quatre fois. Sa réparation a donc reformaté `language.py` et
`tests/unit/test_wipe_stores.py`, et **`make all` rend 0** — l'exception « rc=2
est le rouge attendu », qui traînait dans chaque prompt depuis le lot 0b et avait
déjà masqué un vrai rouge, disparaît avec eux. Le §5.4 du registre est fermé.

**Et l'auditeur sur `test_hierarchie_bout_en_bout.py`.** Le registre §3.3
laissait entendre que le fichier ne prouve rien. L'auditeur a mesuré sa
couverture marginale : **3 mutations sur 7 que lui seul voit**. Le registre a
été nuancé.

---

## 6. Le plan de lots

L'ordre se décide au **coût de l'attente**, pas à la sévérité. Un défaut grave
mais inerte attend ; un défaut mineur qui bloque une mesure passe devant.

| Lot | Contenu | Débloque | État |
|---|---|---|---|
| **0** | Porte qualité reproductible, `mypy`, `/reindex` déplacé **et sa reprise réparée** | démarrage de la stack, exigences **1** et **5** | ✅ **fusionné le 29 août 2026** (`b59bf38`) |
| **0b** | **Les gardes qu'on croit avoir.** §5.5 : les hooks du framework `pre-commit` ne sont installés nulle part — `detect-secrets` n'a **jamais** tourné en garde-fou. *(La justification d'origine ajoutait « sur un dépôt dont le `.env` porte les mots de passe MinIO et Postgres ». C'était une survente : un hook `pre-commit` ne voit que les fichiers **indexés**, et `.env` est ignoré par git, donc jamais indexé — l'installer ne le fera jamais scanner. Le gain réel est prospectif, et il est réel : empêcher qu'un secret parte un jour dans un fichier **versionné**. Registre §5.5.)* Plus §5.4 : `make all` cesse d'écrire dans le dépôt qu'il contrôle (`ruff format --check` dans la cible `all`). Plus §4.18, une ligne : les sensors d'ingestion sont livrables à l'arrêt sans qu'un test bronche | un garde-fou de secrets qui existe vraiment, un `make all` qui contrôle au lieu de muter, et un pipeline qui ne se déploie pas éteint | ✅ **fusionné le 31 août 2026** (`e998e7d`) — et ce ne fut pas court : cinq conversations, dix commits, **deux** tours d'audit indépendant. Il a livré en plus un contrôle d'identité **inconditionnel**, les commits de **fusion** couverts, le corpus versionné **soustrait aux hooks**, et une installation en **un geste** — `make install` — qui vérifie son propre résultat |
| **1** | **Observer sans corriger.** Monter la pile, reconstruire l'image Docling, ingérer 1 chapitre par ouvrage + le PDF. Trois questions : profondeur réelle du graphe (§3.2), `minio_url` sur les images HTML (§3.5), troncature réelle à l'embedding (§3.4) | contrainte **6** | ✅ **mesuré le 31 août 2026**, sans aucun commit — et son audit indépendant a élargi la mesure de 2 chapitres à **22**. Résultats au registre §3.2, §3.4, §3.5 et §4.21 à §4.27 |
| **2** | ~~La hiérarchie des titres~~ | — | ❌ **SUPPRIMÉ le 31 août 2026.** Pas parce que le graphe est imbriqué — il l'est à 21/22 — mais parce que **la correction qu'il portait est un no-op** : `level` est absent sur les titres concernés et `elements.py:272` fait `heading_rank or 0`, donc le rang reste 0 (registre §3.2). §3.3 est **retourné** : les deux tests qu'il fallait « amender ensemble » assertent le comportement juste. §4.11 en sort vivant et monte au lot 3 ; §4.12 reste consigné inerte avec sa vraie condition d'activation — l'entrée d'un Markdown au corpus |
| **3** | ✅ **FUSIONNÉ le 1er septembre 2026** (`--no-ff`, `4e28594`). **Instruments et gardes.** §3.4 (l'instrument sous-comptait la troncature **de moitié**), §4.4 (dont le garde de `sequence`, §6.16), §4.14, §4.5, §4.11 — le niveau du titre dans le graphe — §4.21, §4.23, §4.24, et le test de non-platitude que l'audit du lot 1 réclamait | la confiance dans tout chiffre produit après l'ingestion, **et** un agent capable de lire la hiérarchie qui existe | ✅ **livré le 31 août 2026** — **onze** commits, **les six points du mandat**, plus §4.5 et §4.14. Il a fermé §3.4, §4.4, §4.5, §4.11, §4.14, §4.21, §4.23, §4.24 et §5.3. **Audité, puis RÉPARÉ, puis fusionné** : l'audit n'a trouvé aucune régression et a reproduit tous ses chiffres, mais cinq bloquants — dont la fixture du test de non-platitude, qui assertait 39 titres là où la production en produit 41. Les cinq sont fermés, le juge de la réparation est passé sous la main du pilote, et `make all` rend **0** sur `main`. Voir §5.1 quater. Il laisse **deux mutations survivantes** consignées et non fermées (§4.12, §4.28.d) et **cinq constats** au lot 4 (§4.28). *(Cette case portait « dix commits » : un compte ne peut pas s'inclure lui-même, et le lot 0b s'était fait prendre pareil. Elle portait aussi « il a fermé §6.16 » : le registre le garde **ouvert**, et le registre a raison — la moitié « écrire au contrat côté agent » n'est pas faite. Le compte de tests a été retiré : son site canonique est `README.md`, section Tests.)*
| **4** | ✅ **FUSIONNÉ le 2 septembre 2026** (`--no-ff`, `79cd2bc`) — 16 constats fermés, 857 tests, neuf constats versés au §4.29. La perte silencieuse : §4.1, §4.2, §4.6, §4.7, §4.3, §4.10, §5.6, plus §4.15 à §4.17 et §4.19 — la famille « un run bloqué gèle tout », qui se ferme d'un geste par le *run monitoring* absent de `dagster.yaml`. **Plus §4.22** (six pages du PDF sans aucun élément, leur texte attribué à la page précédente) et **§4.25** (les URL du graphe rendent 403 en GET anonyme). **Plus les cinq constats que la réparation du lot 3 lui a versés, §4.28** : `chunk_count` mensonger (a), les 199 images HTML absentes du bucket **et** `Datas/.cleaned/` que `wipe_stores` ne purge pas — à lire **avant** d'attaquer §3.5 (b), le daemon arrêté et l'exigence 5 inéprouvable (c), et le déverrouillage de `nebula.py` pour que `document_vid` soit enfin gardé (d) | la certitude que le corpus ingéré est le corpus complet | **à faire — c'est l'action suivante, §7** |
| **5** | ✅ **FUSIONNÉ le 2 septembre 2026** (`--no-ff`, `d8c67c5`) — et il n'était pas cosmétique : voir §5.1 sexies. Code mort et documentation contre code : §5.1, §5.2, §5.7, §5.8, tout le §6 — **dont §6.16 (les trois réserves de `sequence` à écrire au contrat) et §6.17 (chiffres et renvois faux)**, et les deux docstrings de `vectors.py` qui promettent « plus de troncature » alors que 8 chunks sortent de la fenêtre. **Plus, en PREMIER point et tranché par le pilote le 2 septembre 2026 : `CLEANED_SUBDIR` cesse d'être un réglage** (§4.29.a). Personne ne configure où l'étape de nettoyage écrit — c'est un détail d'implémentation — et c'est le seul chemin par lequel un outil de purge peut viser le corpus versionné ou les bind mounts des stores. `mesuré` sur un faux corpus : `CLEANED_SUBDIR=htms` passe le containment livré par le lot 4 et détruit 24 des 25 fichiers ; `=database` détruit les stores. **Un réglage annoncé à l'opérateur dont trois valeurs sur quatre détruisent le corpus coûte plus qu'il ne rend, et une configuration que rien ne configure est de la configuration morte** — c'est le périmètre de ce lot au mot près. **Plus les huit autres constats du §4.29** que le lot 4 a versés | la lisibilité, et l'arrêt des faux réglages | **à faire — c'est l'action suivante, §7** |
| **6** | ✅ **FUSIONNÉ le 3 septembre 2026** (`--no-ff`, `69a6786`) — voir §5.1 septies. Ingestion complète → `verify_contract` → `index_report` → **puis** les 30 questions | la première campagne de référence | **à faire — et ses trois premières étapes sont déjà faites par accident** (§4.28.e). **Tranché le 1er septembre 2026 : les 30 questions attendent le lot 4. La conclusion tient toujours, mais SON MOTIF EST TOMBÉ — et c'est instructif.** Le motif était : `compute_id` dérive de `(identity.key, page_no, position_in_page, text[:50])`, donc §4.22, §4.6 et §4.7 déplaceraient les `element_id`. **Mesuré trois fois — par le lot 4, reproduit par son audit, confirmé statiquement par le pilote — c'est FAUX** : les ensembles d'`element_id` sont rigoureusement égaux de part et d'autre du lot 4, 15 173 des deux côtés, différence symétrique nulle, parce que `page_no_end` est **additif** et que `pages[0]` vaut exactement ce que valait `prov[0].page_no`.

L'ordre tient quand même, pour deux raisons neuves et mesurées : le jeu de **chunks** change (4 365 → 4 367, §4.28.a) et **`page_no_end` n'est peuplé sur aucun sommet** — la colonne **existe** depuis le redémarrage de `docling-service` du 2 septembre 2026, et les 7 251 `Paragraph` sont à `NULL` (`mesuré` ; registre §4.29.e). Une réingestion reste donc requise. *La ligne précédente disait « la colonne n'existe pas encore » : c'était vrai le 1er septembre et faux le 2. **Un état de poste n'est vrai qu'à une date** — remesure-le, ne le lis pas ici.* Un jeu de questions écrit avant est un jeu à refaire, et l'écrire *quand même* pour « avancer » est le piège : il paraîtrait bon jusqu'à la réingestion.

**Ce que le chantier doit retenir de cet épisode** : une conclusion juste peut reposer sur un raisonnement faux, et alors elle ne survit que par chance. Le motif ici était un raisonnement sur le code — plausible, jamais mesuré — et il a fallu trois mesures indépendantes pour le renverser. **Étiquette `supposé` tout ce qui n'a pas été mesuré, même quand ta conclusion te paraît sûre** : c'est cette étiquette qui a déjà économisé un lot entier au §6, et son absence ici a failli en coûter un. Ce qui est acquis en revanche l'est vraiment : le corpus complet est indexé et les deux instruments ont rendu leur verdict dessus, ce qui donne au lot 4 son antécédent mesuré |

**Après le lot 6, un item et un seul est déjà au plan : la bascule à clé
provisoire** (registre §4.29.i, tranché le 2 septembre 2026). Le comportement
retenu est celui que le lot 4 a livré — *entre un index qui sert un document
périmé et un index qui n'en sert aucun, le second* — parce qu'une perte
silencieuse coûte plus qu'une panne bruyante. Écrire sous une clé provisoire puis
basculer serait **strictement meilleur** : absence de perte silencieuse **et**
continuité de service. Ce n'est pas fait avant, faute d'antécédent : personne ne
sait à quelle fréquence une conversion échoue durablement sur ce corpus, et
**c'est la première campagne qui le dira**. Décider avant serait décider sur un
`supposé`.

**Le lot 1 a payé son pari, et pas comme prévu.** Il n'a rien corrigé, il n'a
produit aucun commit, il a coûté quelques minutes d'ingestion — et il a
**supprimé un lot entier du plan** tout en faisant naître sept constats
(§4.21 à §4.27). Le pari « observer avant de corriger » est le meilleur retour
du chantier à ce jour.

**Et il a montré où était le vrai risque : la représentativité.** Le lot 1
avait mesuré 2 chapitres sur 22, et concluait juste. Son audit a mesuré les
**22** et a trouvé le chapitre plat, les 46 % de rangs PDF issus d'un repli, et
le fait que la correction était un no-op — trois choses qu'aucun rapport en
prose ne pouvait porter. **Quand une mesure décide du plan, mesure tout le
corpus, ou dis le périmètre exact où ta conclusion vaut.**

**La réserve du pilote a payé, et elle est conservée telle quelle parce qu'elle
dit comment on l'a gagnée.** Elle disait : « le constat §3.2 est un raisonnement
sur le comportement du backend HTML de Docling, **pas une observation** ; il est
étiqueté `supposé` ; si Docling imbrique bien, le constat tombe et le lot 2
disparaît ». Le lot 1 a mesuré, son audit a élargi la mesure aux 22 chapitres, et
**le lot 2 a disparu** — pour une raison encore plus forte que celle prévue : la
correction était un no-op. Un constat étiqueté `supposé` et traité comme tel a
économisé un lot entier.

---

## 7. L'action suivante — le plan est épuisé, et voici ce qui monte

**Les six lots sont dans `main`. La première campagne de référence est faite.
Il n'y a plus de lot à distribuer.**

L'action suivante n'est donc pas un lot : c'est **une décision de plan**, et le
pilote l'a prise le 3 septembre 2026. Elle est écrite ici pour que personne ne la
reprenne à zéro.

### 7.0 La décision : on s'arrête au bord de ce dépôt

Deux des six points qui restent vivent dans **l'autre dépôt**, `rag-agent-chat`.
Trois options ont été posées : étendre le mandat là-bas, s'arrêter au bord en
écrivant une passation, ou ne rien décider. **Retenu : s'arrêter au bord.**

Le motif, en deux phrases. L'exigence 5 n'est pas éprouvable d'ici sans démarrer
un service qu'on n'a pas audité, et étendre le mandat maintenant **doublerait le
périmètre juste après avoir épuisé le premier**. Une passation coûte une heure et
ne referme aucune porte.

**Son livrable est [`etat_des_lieux.md`](etat_des_lieux.md)** — l'état des lieux,
écrit pour être lu **sans lancer le projet**, par une personne comme par une
conversation neuve. Il porte ce que le pipeline garantit, ce qu'il ne garantit
pas, comment lire le graphe, et ce qui reste à faire de chaque côté. **C'est le
point d'entrée de quiconque part travailler sur `rag-agent-chat`**, et l'annexe A
ci-dessous porte le prompt qui l'y envoie.

### 7.0 bis Ce qui monte au plan, par ordre

| | Ce que c'est | Qui | Pourquoi ce rang |
|---|---|---|---|
| **1** | **§4.32.a** — réingérer par le chemin nominal ne marche pas, en silence | ici | c'est un **chemin de récupération cassé vers lequel un message d'erreur pointe** : `verify_contract` dit « réingérez », le `README` dit « redémarrez puis réingérez », et le capteur perd ses 23 runs sans une ligne au journal. **Et lis l'ironie du §5.1 septies avant d'y toucher** : ce défaut protège l'index en ce moment même |
| **2** | l'**exigence 5** — prévenir l'agent en fin de chaîne | **`rag-agent-chat`** | seule exigence du contrat non prouvée. Le dépôt de l'agent est sur le poste, service `agent-api` sur `rag_network`, **sans `.env`** : il ne tourne pas. Ce n'est pas un lot d'ici |
| **3** | les **trois réserves de `sequence`** (§6.16) | **`rag-agent-chat`** | le garde existe ici, l'explication manque là-bas. Petit, et ça débloque l'agent |
| **4** | **§4.29.i** — écrire sous une clé provisoire puis basculer | ici | amélioration franche, mais c'est un chantier. La campagne dira si la panne est fréquente : décider avant serait décider sur un `supposé` |
| **5** | le **second tour de questions** — les pièges | **humain** | c'est la strate où l'on écrit le plus facilement un faux piège. Elle demande une relecture humaine, pas une conversation |
| **6** | **F7** — faire lire le `Makefile` et les documents par un test | ici | **le dernier angle mort de la méthode** : la documentation peut encore dériver sans que rien ne rougisse, et c'est le seul endroit où le chantier ne s'applique pas à lui-même |

### 7.0 quater Ce que la bascule vers SeaweedFS met devant — 25 septembre 2026

**Le rang 1 de la table ci-dessus est FERMÉ** : §4.32.a l'a été par le lot 8, et
le geste de réingestion a été exercé **deux fois sous les yeux de quelqu'un** le
25 septembre (§4.42, §4.43). Le rang 2, l'**exigence 5**, est **éprouvé** des
deux côtés le même jour. Ce qui monte à leur place, par ordre :

| | Ce que c'est | Qui | Pourquoi ce rang |
|---|---|---|---|
| **1** | **basculer `rag-agent-chat` sur SeaweedFS** — son `.env` reçoit `MINIO_ENDPOINT=seaweedfs:8333` et le jeu **lecture seule** | **`rag-agent-chat`** | le pipeline écrit déjà là-bas. Tant que l'agent vise `minio:9000`, il sert des images d'un store **figé**, et son écran dira « image absente » **sans erreur** — un 403 remonte en 404 silencieux. Le témoin `temoin-bascule/bascule-2026-09-25.txt` l'attend, lisible par appel direct avec ce jeu |
| **2** | **§4.43.c** — découpler `MINIO_*` : une variable configure le serveur MinIO **et** authentifie auprès de SeaweedFS | ici **et** là-bas | tant qu'il tient, recréer `minio` détruit le retour arrière, et un `docker compose up -d` nu suffit à le faire. C'est le contrat avec l'agent : le renommage se coordonne, il ne se décrète pas |
| **3** | **décider du sort de MinIO** — le garder, ou le retirer | **humain** | il est le retour arrière. Le retirer libère 29 Mo et un conteneur, et ferme la porte. Ce n'est pas une décision de conversation |
| **4** | **§4.15** — un service d'agent absent fait échouer la réindexation toutes les 30 s, sans délai de garde ni alerte | ici | les **886 `FAILURE`** de l'historique sont exactement cela, caractérisés au §4.43.a. Le défaut est inerte tant que l'agent tourne, et il repart le jour où il tombe |
| **5** | **§4.29.i**, le **second tour de questions**, **F7** | *inchangés* | voir la table du §7.0 bis, leurs motifs n'ont pas bougé |

**Ce que la bascule N'A PAS établi**, et qui ne doit pas se lire comme fait :
aucune mesure de performance, de tenue en charge ni de durabilité de SeaweedFS ;
aucune requête posée à l'agent contre le nouveau store. Le §5 du compte rendu de
la bascule les nomme un par un.

**Le rang 1 a été relevé d'un cran par l'audit du lot 6, et le pilote l'a suivi**
— il passe **devant §4.29.i**, qui était en tête. Le motif : §4.29.i est une
amélioration, §4.32.a est une panne qu'un message d'erreur du système invite à
déclencher.

### 7.0 ter Si un lot est distribué malgré tout, l'ordre invariable ne change pas

1. lire le rapport ;
2. **faire auditer par une conversation qui n'en a écrit aucune ligne.** Sur ce
   chantier : **quinze passages, quinze trouvailles matérielles** ;
3. lire le diff soi-même et faire tourner `make all` de ses mains, **y compris sur
   le résultat de la fusion** — et **résoudre soi-même tout conflit** : sur le lot
   6, la résolution naïve réintroduisait une date fausse que le lot venait de
   trouver ;
4. **alors seulement**, trancher la fusion ;
5. si fusion : `--no-ff`, jamais `--ff-only`, jamais de rebase. Puis **relancer
   `make install` depuis le clone principal**, vérifier qu'aucun projet Compose ni
   bind mount n'ancre l'arbre, supprimer la branche local **et** distant, retirer
   l'arbre — et **relancer `make install` une fois de plus après ce retrait** ;
6. mettre le registre **et** `etat_des_lieux.md` à jour ;
7. **n'annonce jamais le résultat attendu d'une mesure que tu commandes.** Le
   pilote l'a fait deux fois et s'est trompé une fois : voir §11.

### 7.1 L'état de la pile — §4.26 est TRAITÉ

**La pile ne vit plus dans un arbre de travail.** Le lot 3 l'a remontée depuis le
clone principal, et il a **déménagé les données du lot 1** plutôt que de
réingérer : `docker compose down` depuis l'arbre du lot 1, copie de `.env` et de
`Datas/database/` vers `/home/ubuntu/RAG/rag-ingestion-pipeline`, puis
`docker compose up -d`. Le graphe a survécu à l'octet — 2 288 sommets avant,
2 288 après (`mesuré`).

**État au 1er septembre 2026 (`mesuré`), après une coupure et un redémarrage
complet de l'instance** : projet compose **`rag-ingestion-pipeline`**, neuf
services debout, `.env` et bind mounts dans le clone principal, aucun montage vers
un arbre de travail. **L'index est intact à l'octet** — 4 365 chunks, 15 196
sommets, 15 374 arêtes, 23 documents, 13 objets MinIO, exactement les chiffres
d'avant la coupure. La pile se relève seule ; c'est un fait acquis, pas une chance.

État au 31 août 2026 (`mesuré`) : projet compose **`rag-ingestion-pipeline`**,
bind mounts sous le clone principal, `.env` dans le clone principal.
**L'arbre `lot-1-observation-b12761` n'ancre plus rien et peut être supprimé** —
ses données y restent en copie, filet volontaire.

**Ce qui n'a PAS été déménagé** : le `Datas/database/postgres` du lot 1,
inaccessible en lecture (`root`, `Permission denied`). Le Postgres de Dagster est
donc reparti **vierge**, et il faut savoir ce que cela a fait : les curseurs des
sensors sont repartis de zéro, et **les sensors étant livrés armés** (§4.18,
fermé par le lot 0b), le simple `docker compose up -d` a déclenché
**l'ingestion complète du corpus**. Ce n'est pas un défaut — c'est le
comportement voulu — mais c'est un effet à connaître avant de remonter la pile.

Il en est sorti un bénéfice : le lot 3 a mesuré ses antécédents sur le **corpus
complet** ingéré par le code de `main`, et non sur les 3 documents du lot 1.

### 7.2 L'état du poste après la campagne — mesuré le 3 septembre 2026

**Tout ce qui suit est un ÉTAT DE POSTE : il périme, et il a déjà périmé trois
fois pendant ce chantier. Mesure-le, ne le lis pas.**

| | `mesuré` le 3 septembre 2026 |
|---|---|
| pile Docker | 9 services debout, projet `rag-ingestion-pipeline`, montés depuis le clone principal, aucun bind mount vers un arbre de travail |
| `dagster-daemon` | **arrêté** — et « arrêté » n'est PAS une propriété stable : il a démarré **trois fois** sans qu'aucune conversation le décide, cause jamais cherchée |
| l'index | 4 367 chunks, 15 196 sommets, 15 173 `PARENT_OF`, 23 documents, 212 objets MinIO — **produit par le code de `main`**, c'est l'antécédent de tout ce qui suivra |
| `verify_contract` | `rc=1`, **une seule anomalie** : 52 sommets visuels sur 264 sans URL, et ce sont **52 tables HTML sur 55** — une table HTML est du Markdown, il n'y a rien à téléverser. **`rc=0` est inatteignable sur ce corpus**, et le pilote s'est trompé en l'attendant (§11) |
| le schéma du graphe | à jour : les 11 tags d'élément portent leurs 6 colonnes, `page_no_end` comprise, et **0 sommet sur 15 173** est à `NULL` |
| corpus | 25 fichiers, 57 381 999 octets, empreinte inchangée depuis le versionnement |

**Les gestes à connaître, dans l'ordre, si une réingestion redevient nécessaire :**

1. **redémarrer `docling-service`** — c'est `init_schema()`, joué **au démarrage**
   du service, qui met le schéma du graphe à jour. Sans lui on écrit contre un
   schéma incomplet ;
2. **purger avec `wipe_stores`, qui purge QUATRE choses** — les trois stores **et**
   `Datas/.cleaned/`. Cette quatrième est celle qui compte : sans elle, la
   réingestion repart du HTML nettoyé **périmé** et pointe des objets absents ;
3. **faire exécuter l'asset `cleaned_html`** — **réextraire ne suffit pas**
   (§4.28.b). C'est le seul chemin qui re-téléverse les images des captures HTML ;
4. **et sache que le chemin nominal est mort** : démarrer le daemon ne déclenche
   rien, parce que la clé de run est déjà consommée (§4.32.a). Le lot 6 a lancé les
   23 partitions par `dagster job launch`, après avoir vidé les curseurs.

**Deux faits d'outillage qui ne se devinent pas :**

- **`verify_data` et `verify_contract` ne tournent pas côté hôte** : `chromadb`
  appartient aux dépendances du service Docling, pas à celles du dépôt. Le geste
  est `docker exec rag_assistant-docling-service-1 python -m src.<module>` — et ce
  conteneur monte `/app/src` depuis le **clone principal**, donc il exécute le code
  de `main` quelle que soit la branche sortie. Monter son propre `src` est au
  registre §4.27 ;
- **un répertoire mort subsiste** : `.claude/worktrees/lot-1-observation-b12761`,
  484 Mo, écrit par Docker en `root`. Git n'en sait plus rien, rien ne l'ancre, il
  se retire en `sudo` à l'occasion.

## 8. Comment on pilote

Conventions apprises à leurs dépens sur le dépôt jumeau.

- **Un seul prompt à la fois, séquentiel.** Ne distribue jamais un prompt dont
  l'entrée dépend d'un rapport que tu n'as pas encore reçu.
- **Nomme ET NUMÉROTE la conversation destinataire en tête de ton message**,
  sous la forme `Conv' <n> <RÔLE-LOT>` — par exemple `Conv' 1 LOT-0B`,
  `Conv' 2 AUDIT-0B`. Le numéro est obligatoire et ne se réutilise **jamais**,
  même pour le même lot : le lot 0b a consommé cinq conversations, dont deux
  audits et deux réparations, et un nom seul les aurait confondues. Le routage a
  déraillé plusieurs fois ; des prompts sont arrivés au mauvais endroit. Sois
  brutalement explicite : « ceci va à X, rien d'autre à envoyer ».
- **Chaque prompt se termine par l'obligation d'écrire `TÂCHE TERMINÉE` en
  dernière ligne**, ou `TÂCHE BLOQUÉE — <raison>`. Sans ça, l'utilisateur ne
  sait pas si le message lui est destiné ou t'est destiné.
- **Un développeur écrit, teste et livre ; un auditeur indépendant vérifie.**
  Un auditeur ne doit **jamais** avoir écrit une ligne de ce qu'il audite —
  c'est ce qui le rend éligible, et il faut le lui dire dans son mandat.
- **Audite avant de fusionner.** Toujours.
- **Une branche par lot en vol, jamais plus.** Une conversation qui répond à
  une question ne crée pas de branche. Un lot fusionné disparaît de la liste ;
  un commit auquel il faut pouvoir revenir devient un **tag**, pas une branche.
  Le chantier a compté cinq branches avant qu'on ne pose la règle.
- **Quand une conversation grossit, demande-lui un `/compact`** avant de lui
  envoyer la suite, avec des instructions sur ce qu'elle doit **garder** — sa
  méthode et sa connaissance du dépôt — et ce qu'elle doit **jeter** : ses
  rapports, les diffs, les sorties de commandes. Les preuves sont dans le
  dépôt.
- **Encourage le désaccord argumenté dans chaque prompt**, noir sur blanc. Le
  pilote a été renversé plusieurs fois par des audits, par des développeurs et
  par l'utilisateur, chaque fois à raison.
- **Comités réguliers avec l'utilisateur.** On vérifie à chaque fois. On pousse
  à la fin des tâches.

---

## 9. Les règles imposées à chaque conversation

À reproduire **dans chaque prompt**, sans les résumer.

**L'identité Git, en premier** — §2.1 de ce fichier, mot pour mot. C'est la
règle dont l'oubli a coûté un dépôt.

**Aucune ATTRIBUTION du travail à un assistant de génération de code.** Aucun
assistant ne doit apparaître comme **auteur ou contributeur** : ni dans un
message de commit, ni dans un trailer — **aucun `Co-Authored-By`** — ni dans une
signature, ni dans un en-tête de fichier, ni dans une ligne de documentation qui
dirait qui a écrit quoi. C'est une règle de **paternité**, et son motif est celui
du §2.1 : la liste des contributeurs d'un dépôt GitHub, une fois constituée, ne
se défait pas.

**Cette règle s'écrivait « aucune mention de Claude, Claude Code, Anthropic,
Copilot ou ChatGPT nulle part — code, documentation, messages de commit ». Prise
au mot, elle est FAUSSE, et c'est une phrase d'exhaustivité de plus.** `mesuré`
le 2 septembre 2026 sur `main` à `27a6304`, fichiers versionnés hors `Datas/`,
`git grep -nIiE 'claude|anthropic|copilot|chatgpt'` : **13 occurrences** sur
12 lignes, **hors la ligne de la règle elle-même** — qui en porte cinq de plus,
et qu'aucune formulation ne peut éviter.

| Famille | Occurrences | Où |
|---|---|---|
| **noms de branche et d'arbre de travail** — `claude/<lot>-<sha>`, `.claude/worktrees/…` | **7** | les **deux documents de gouvernance**, écrits par le pilote lui-même : `axes_amelioration.md` (3) et ce fichier (4) |
| **choix de fournisseur de modèle**, mentions **produit** | **6** | `llm_integration_plan.md` : le tableau des composants, un arbre de fichiers, `ANTHROPIC_API_KEY`, `LLM_MODEL=…`, et la ligne « intégration … via SDK » |

**Aucune des treize ne viole la règle, et voici pourquoi.** Un **nom de branche
créé par l'outillage** n'attribue rien : il nomme un fil de travail, il est
imposé par le harnais qui crée l'arbre, et le refuser demanderait de renommer
chaque branche du chantier — donc de mentir sur ce que `git branch` montre. Un
**choix de fournisseur de modèle dans un document de conception** n'attribue rien
non plus : il dit quel modèle le système *appellera*, exactement comme
`EMBEDDING_MODEL_NAME` dit quel modèle d'embedding il charge. Ni l'un ni l'autre
ne dit qui a **écrit** une ligne de ce dépôt.

**Le geste est donc : borner, ne rien nettoyer.** Retirer ces treize mentions
appauvrirait le dépôt — un plan d'intégration qui tait le modèle qu'il prescrit
ne prescrit plus rien — sans rien fermer, la règle ne visant pas cela. Ce qui
reste interdit est inchangé et n'a jamais été enfreint : **aucun commit de ce
chantier ne porte un assistant en auteur, en committer, en trailer ou en
signature** (`mesuré` à chaque fusion).

**Commits atomiques en français**, dans le style du dépôt (`git log`). Une même
affirmation fausse vivant dans le **code** et dans un **document** se corrige
dans **un seul** commit — sans quoi il existe un commit où le document
contredit son code. Documentation dans le même commit que le code. Compte de
tests à jour. Push régulier.

**Chaque commit vert INDIVIDUELLEMENT**, ce qui inclut l'absence de rouge
aléatoire. Balayage des graines `PYTHONHASHSEED` : au moins 25 graines
aléatoires **plus la graine 0**, qui désactive la randomisation et est donc un
cas distinct. Un lot du dépôt jumeau s'est fait prendre à 2 graines sur 400.

**Aucun test désactivé**, aucun `skip`, `xfail`, `type: ignore`, aucune règle
`ruff` ou `mypy` relâchée, aucun `except` élargi sans justification écrite **au
site**.

**Aucun chiffre inventé** : étiquetage `mesuré` / `calculé` / `supposé`. Une
valeur reprise sans remesure s'écrit avec sa réserve, **une fois**, au site
canonique ; les autres mentions y renvoient.

**Périmètre strict** : ce qui est trouvé et non traité va au **rapport** et au
**registre**, jamais au diff.

**Test rouge d'abord.** Et chaque garde prouvé par **mutation du code livré** :
on casse la ligne, le test devient rouge, on remet, il redevient vert. Creux
avant, rouge après, tests nommés dans le rapport.

---

## 10. Les leçons qui ont trouvé les défauts

Elles ont produit tous les résultats du dépôt jumeau — une régression HTTP 500,
un instrument de mesure qui jetait son dénominateur, un `set` qui décidait
quelle source payait la fenêtre de contexte, un modèle d'embedding anglais armé
dans un `.env`. Aucun de ces défauts n'était visible sans cette discipline.
**Mets-les dans tes prompts, pas seulement dans ta tête.**

- Un test « ça marche » est vert **des deux côtés** du défaut. Il faut un test
  qui fait **régresser** ce qu'on prétend garder. Un test « ça tient » est vert
  des deux côtés d'un défaut de dimensionnement ; seul un test de **serrage**
  le voit.
- **Asserte depuis le côté qui PRODUIT le comportement**, pas depuis celui qui
  le consomme. Un code de sortie documenté et justifié n'était asserté nulle
  part : le remplacer par 0 laissait 390 tests verts.
- Une **phrase d'exhaustivité** dans un document ou un docstring est un défaut
  en attente : elle clôt une énumération que personne ne rouvre. « Les deux
  seules façons dont l'appel échoue » a autorisé une régression réelle.
- **Un test qui choisit lui-même son cas doit prouver qu'il l'a atteint.** Un
  test croyait vérifier `httpx.InvalidURL` avec une URL sans schéma, qui lève
  `UnsupportedProtocol` — laquelle hérite de `HTTPError`.
- **Vérifie tes bornes de balayage** : un lot balayait 1 250 cas en commençant
  juste au-dessus de la bande où le défaut vivait.
- Une généralisation tirée d'**une** branche d'une fonction qui en a plusieurs
  est fausse jusqu'à preuve du contraire.
- **Un montage de test qui bouchonne trop haut rend intestable ce qu'il
  prétend vérifier. Mute le producteur, pas le consommateur.**
- **Deux erreurs qui se compensent se cachent mutuellement.**
- Tester le point d'entrée d'un script demande un **sous-processus**, pas un
  import.
- Quand un développeur te donne une table de couverture, **n'audite pas sa
  liste** : construis la tienne depuis la documentation et les docstrings, puis
  diffe. Ce que ta liste contient et la sienne pas est le résultat qui compte.
- **La question la plus productive des deux dépôts : qu'est-ce que la
  documentation affirme que le code ne fait pas ?**

Celles que le lot 1 a ajoutées :

- **Un raisonnement juste sur un antécédent faux produit une conclusion fausse,
  et il se relit comme une preuve.** Le constat §3.2 était logiquement
  impeccable : *si* Docling n'imbrique pas, *alors* le graphe est plat. Personne
  n'avait mesuré le *si* — pendant des semaines, et le plan portait un lot entier
  dessus. **Cherche l'antécédent avant d'auditer le raisonnement.**
- **Une conclusion tirée d'un échantillon doit porter son périmètre, ou elle sera
  lue comme universelle.** Le lot 1 mesurait 2 chapitres sur 22 et écrivait « le
  constat tombe ». Son audit a mesuré les 22 : 21 imbriquent, **1 est plat**. La
  conclusion ne tombait pas, elle se **bornait** — et le chapitre plat serait
  devenu un défaut découvert au lot 6, sur le corpus complet.
- **N'annonce jamais le résultat attendu d'une mesure que tu commandes.** Le
  prompt du lot 1 donnait « 0 % de troncature » ; la réponse était 1,0 %, et un
  développeur qui confirme aurait vu un bruit d'arrondi au lieu du défaut.
- **Une correction peut être un no-op, et son avertissement coûter deux tests
  justes.** Avant de planifier une correction, mesure ce qu'elle change.
- **Une mesure qui décide du plan doit laisser un artefact rejouable.** Les
  scripts du lot 1 étaient jetables — donc sa preuve vivait dans un rapport, et
  la conversation suivante ne pouvait que *recroire* ou *tout refaire*.

Celles que le lot 0 a ajoutées, et elles ont chacune trouvé quelque chose :

- **Un curseur qui avance à l'ÉMISSION d'une demande, et non à son succès,
  transforme une panne passagère en perte définitive.** C'était le défaut au
  cœur du lot 0.
- **Une clé d'idempotence déterministe interdit la reprise.** Un `run_key`
  consommé l'est pour toujours ; Dagster le cherche dans tout l'historique,
  sans borne de temps. Le geste de récupération naturel — remettre le curseur à
  zéro — ne rattrapait rien.
- **Toute reprise BORNÉE réintroduit la perte qu'elle prétend corriger.** Une
  `RetryPolicy` à trois tentatives ne fait que déplacer l'échec définitif plus
  tard.
- **Ne rien écrire est plus robuste que bien écrire.** Si l'historique porte
  déjà l'information, ne tiens pas d'état : un état que rien ne réconcilie avec
  la réalité est une seconde source de vérité, donc une source de divergence.
- **Une règle survit à son motif.** « Ne jamais lever » venait d'un endroit où
  une reprise coûtait des heures de reconversion ; le code a déménagé, la
  reprise est devenue un appel HTTP, et la règle est restée. Quand du code
  change de place, rouvre les règles dont le seul motif était l'ancienne place.
- **Un défaut peut être une ligne qui manque au TEST, pas au code.** La ligne
  `default_status=RUNNING` était juste et rien ne la gardait : la retirer
  laissait 508 tests verts et rendait tout le lot inerte au déploiement.
- **Ce qu'un test n'importe pas, il ne teste pas.** `test_wipe_stores.py`
  importait trois fonctions d'aide et jamais `main()` — où vivaient les deux
  moitiés du titre du commit. Lis la ligne d'`import` avant de croire une
  couverture.
- **Un harnais de test peut effacer ce qu'il doit observer.** Le harnais du
  sensor reconstruisait un contexte neuf à chaque tick, effaçant le curseur que
  le sensor venait de poser : le test de reprise aurait été vert des deux côtés
  du défaut. Vérifie ton harnais avant de croire ton rouge-d'abord.

---

## 11. Les erreurs de pilotage à ne pas refaire

Motif unique : **affirmer un comportement de code depuis sa mémoire au lieu de
relire.**

- Écrire qu'une fonction lit SQLite alors qu'elle ne fait aucune
  entrée-sortie ; le vrai coupable était ailleurs.
- Reprendre « sous-représenté de 9 points » d'un audit sans recalculer : c'est
  10,6 ou 3,1 selon la lecture, jamais 9.
- Présenter un budget comme une constante alors qu'il vaut
  `constante − len(question)`.
- **Vérifier une identité d'auteur sur le nom et non sur l'adresse** —
  l'erreur qui a coûté un dépôt entier.
- Lire `settings.py` dans un arbre de travail périmé et croire que le code
  avait dérivé.
- Renommer des fichiers en masse sans vérifier les collisions.
- Proposer d'échantillonner **l'ingestion** pour construire le jeu de
  questions. L'utilisateur a corrigé, et il avait raison : on échantillonne les
  questions, jamais le corpus.
- **Fusionner un lot avant son audit indépendant.**
- **Renvoyer à un fichier qu'on n'a pas écrit.** Le pilote a annoncé un prompt
  « prêt, dans tel fichier » sans l'avoir produit. Un artefact qu'on cite doit
  exister avant qu'on le cite.
- **Distribuer un prompt sans le relire contre l'état réel du dépôt.**
  L'annexe A portait « `main` = 77d4f5b, avance rapide possible » — vrai le jour
  où elle a été écrite, faux dès que `main` a bougé. Un prompt prêt à
  distribuer périme : relis-le contre `git`, pas contre ta mémoire.
- **Corriger une erreur sur la forme qu'on a cherchée, et la laisser vivre sous
  une autre.** Le pilote a corrigé ses neuf dates fausses en remplaçant la chaîne
  `3 septembre 2026`. **Deux occurrences de « 3 septembre » sans l'année ont
  survécu**, et elles étaient fausses elles aussi — trouvées en relisant le mandat
  au lot suivant. *Une correction bornée au motif qu'on a tapé n'est pas une
  correction : c'est un échantillon.* Le geste juste est de mesurer le reste après
  avoir corrigé — `grep '3 septembre'`, pas `grep '3 septembre 2026'`.
- **Écrire une date sans la mesurer.** Le pilote a daté tout le lot 5 du
  « 3 septembre 2026 » — **neuf mentions** dans le mandat et le registre. La date
  était le **2** : aucun commit du dépôt ne porte le 3, et `date -u` le dit en un
  mot. Trouvé par le lot 6, qui a comparé les dates écrites aux dates des commits.
  **Une date est une mesure comme une autre** — `date -u` ou `git log --date=short`
  — et le chantier étiquette `mesuré` tout le reste. Corrigé aux neuf sites.
- **Annoncer dans un prompt le résultat attendu d'une mesure, et se tromper.** Le
  prompt du lot 6 écrivait « les quatre anomalies doivent se fermer ». Trois se
  sont fermées ; la quatrième **était inatteignable**, et le lot l'a mesuré :
  les sommets visuels sans URL sont **52 tables HTML sur 55**, et une table HTML
  est du Markdown — il n'y a rien à téléverser. `verify_contract` ne peut donc pas
  rendre 0 sur ce corpus. Le mandat interdit d'annoncer le résultat attendu d'une
  mesure qu'on commande (§7) : **le pilote l'a fait, et son attente était fausse.**
  Un développeur moins rigoureux aurait cherché à la satisfaire.
- **Affirmer dans un prompt un état de poste qu'on n'a pas mesuré.** Le pilote a
  écrit au réparateur du lot 5 « son arbre de travail a été retiré : la branche est
  libre ». **C'était faux** : il avait retiré celui du lot 4, pas celui du lot 5, et
  n'a pas vérifié. Le réparateur l'a mesuré avant d'écrire une ligne — `git worktree
  list` — et a travaillé dans l'arbre existant en le déclarant. Aucun dégât, et
  c'est le seul mérite de l'affaire. **Le mandat prescrit vingt fois « mesure l'état
  du poste au lieu de le lire » : cette règle vaut aussi pour la main qui l'écrit**,
  et un prompt est le dernier endroit où placer une affirmation non mesurée, parce
  qu'il est lu par quelqu'un qui n'a pas de raison d'en douter.
- **Supprimer un arbre de travail sans relancer `make install` depuis le clone
  principal.** Le §2.1 le prescrit noir sur blanc — le hook `pre-commit` fige un
  chemin absolu vers le `.venv` de l'arbre **d'où l'installation a été lancée**, et
  `.git/hooks` est partagé par tout le clone. Le pilote a retiré l'arbre du lot 4
  pour libérer sa branche, sans relancer : **le premier commit du réparateur a été
  refusé**, sur le message « `pre-commit` not found » qui ne nomme ni la cause ni
  le remède. C'est fail-closed, donc sans dégât — et c'est le piège F6, que le
  pilote avait lu, cité dans son propre prompt, et n'a pas appliqué. **Une règle
  qu'on écrit pour les autres vaut pour soi.**
- **Accepter le verdict d'un auditeur sur sa sévérité.** L'audit du lot 0
  qualifiait la perte de réindexation de « troc net-positif à consigner ».
  C'était une régression. Un rapport excellent peut sous-appeler sa propre
  trouvaille : lis ses faits, refais son raisonnement, et cote toi-même.
- **Livrer autre chose que la forme demandée.** L'utilisateur a demandé un
  `/compact` — des instructions de compaction — et le pilote a produit un prompt
  pour une conversation neuve. Un demi-million de tokens de contexte, une
  consigne d'une ligne, et la mauvaise forme. **Quand l'utilisateur nomme la forme
  du livrable, produis cette forme** ; l'utilité de ce qu'on livre à la place ne
  rachète rien.
- **Croire qu'un commit qui ferme un angle mort ne peut pas en ouvrir un.** Le
  commit `9d2e341` a étendu `format` et `format-check` à `tests/` — le bon geste,
  qui fermait l'angle mort D7 — et a laissé la table du `README.md` décrire
  `ruff format src/`, plus un « 66 files » là où la mesure rend 67. Le lot 5
  s'appelle « la documentation contre le code » : **son gibier naît dans les
  commits qui font bien leur travail**, parce que c'est là que personne ne
  relit la phrase qui décrivait l'ancien état. Trouvé par le pilote après la
  fusion, ni par le lot ni par son audit.

Traite tes propres affirmations comme des hypothèses. Vérifie avant d'écrire un
chiffre. Relis le code avant d'affirmer ce qu'il fait.

---

# Annexe A — Prompt de passation vers `rag-agent-chat`

> **Le plan de ce dépôt est épuisé. Il n'y a plus de lot à distribuer.**
>
> Les prompts des lots 0, 0b, 1, 3, 4, 5 et 6 sont consommés. Ce qu'ils ont
> produit vit au registre §8 et aux §5.1 bis à 5.1 septies ci-dessus. **Le lot 2 a
> été supprimé du plan** : voir §6.
>
> Cette annexe porte désormais **la passation**, décidée au §7.0 : deux des six
> points qui restent vivent dans l'autre dépôt, et on s'arrête au bord de
> celui-ci. **Routage : conversation NEUVE, à nommer `Conv' <n> AGENT-1`.**
>
> **Relis-la contre `git` avant de la coller.** La pointe de `main` et l'état du
> poste sont des faits qui périment.

---

Tu reprends **`rag-agent-chat`**, l'agent conversationnel qui interroge le
pipeline d'ingestion `rag-ingestion-pipeline`.

## Avant d'écrire une ligne

Lis **en entier** `documentation/etat_des_lieux.md` du dépôt
`rag-ingestion-pipeline`. Il est écrit pour être lu **sans lancer le projet** et
il est autosuffisant : ce que le pipeline garantit, ce qu'il ne garantit pas,
comment lire le graphe, et ce qui reste à faire de chaque côté.

Puis, et seulement si tu as besoin du détail : le **§0 du registre**
(`documentation/axes_amelioration.md`) porte le contrat mot pour mot, et
`documentation/CHANGEMENTS.md` raconte ce qui a changé et pourquoi.

**Ne lis pas `pilotage_du_chantier.md` en entier** — c'est le mandat du pilote de
l'autre dépôt, et il ne te concerne que par son §7.0.

Puis **mesure l'état du poste au lieu de le lire.** Cette consigne a attrapé, sur
l'autre dépôt : un poste qu'on croyait être le poste d'origine, une colonne
apparue dans le graphe pendant qu'un lot travaillait, un démon rallumé trois fois
tout seul, un arbre de travail que le pilote croyait avoir supprimé, et neuf dates
écrites sans regarder l'horloge.

## Tes deux points, et ils sont dans cet ordre

**1 — Prouver l'exigence 5 du contrat : `POST /reindex` en fin de pipeline.**

C'est la **seule des cinq exigences qui ne soit pas prouvée**. Le pipeline émet
bien l'appel — c'est mesuré de son côté — mais l'agent ne tourne pas sur ce poste,
donc l'aller-retour n'a jamais été observé.

Ce qui est mesuré et t'évite de le redécouvrir : `/home/ubuntu/RAG/rag-agent-chat`
existe, son `docker-compose.yml` déclare un service **`agent-api`** sur le réseau
`rag_network` — l'hôte même qu'`AGENT_SERVICE_URL` attend — et **il n'a pas de
`.env`**. C'est ce qui manque pour le démarrer.

Pourquoi cette exigence compte : l'agent tient un index lexical **en mémoire**.
Sans cet appel, un document ingéré après son démarrage est **invisible en
recherche lexicale**. Et son filet interne compare un compte de collection au
nombre de chunks indexés : il est donc **aveugle à une réingestion qui retire
autant de chunks qu'elle en ajoute** — exactement le cas de ce corpus.

**Avant de démarrer quoi que ce soit, lis le §9 de l'état des lieux.** Deux
gestes du pipeline peuvent détruire l'antécédent de mesure, et l'un d'eux est de
démarrer un démon.

**2 — Écrire les trois réserves de lecture de `sequence` dans la documentation de
l'agent.**

Elles sont au §5.3 de l'état des lieux, mesurées et chiffrées. Le garde existe
côté pipeline — `sequence` est complète et monotone, 0 arête sans valeur sur
15 173, 0 inversion — mais **rien ne dit à l'agent comment la lire**, et deux des
trois réserves interdisent des implémentations qu'on écrirait naturellement.

La troisième est la plus coûteuse : **le plus grand écart entre deux enfants d'un
même parent vaut 994.** Un agent qui implémente « la fenêtre d'éléments » comme
« les enfants de P dont `sequence ∈ [s−k, s+k]` » rendra **silencieusement moins**
d'éléments que demandé.

C'est le seul point du contrat qui reste ouvert, et **il ne peut être fermé que de
ton côté** : le registre le porte au §6.16 depuis le lot 3.

## Ce que tu ne fais pas

- **tu ne modifies pas `rag-ingestion-pipeline`.** Si tu trouves un défaut chez
  lui, écris-le et rends-le : son registre est le site canonique, et son pilote
  tranche ;
- **tu ne renommes aucun fichier du corpus.** Le chemin entre dans le calcul des
  identifiants : un renommage après ingestion **tue le jeu de 30 questions** qui
  vient d'être écrit ;
- **tu ne changes pas le modèle d'embedding d'un seul côté.** Un désaccord est la
  panne la plus coûteuse du système et elle est **parfaitement silencieuse** : les
  deux modèles candidats rendent 384 dimensions, donc rien ne bronche et la
  recherche rend des passages plausibles et faux. C'est le **nom** qui discrimine,
  jamais la dimension ;
- **tu ne réingères pas**, et tu ne démarres pas le démon d'orchestration du
  pipeline. L'index actuel est l'antécédent de la campagne de référence.

## Ce dont tu disposes, et qui n'existait pas avant

Un **jeu de 30 questions** écrit après l'ingestion, désignant **44 identifiants
réels**, avec ses cinq strates et son plancher de rappel mesuré — 55,3 % à k=5,
61,7 % à k=10, 72,3 % à k=20 en recherche vectorielle seule. Il vit à
`documentation/campagnes/2026-09-02-jeu-de-questions.yaml`.

**Lis sa réserve avant de t'en servir pour arbitrer quoi que ce soit** : trente
questions prouvent que la chaîne fonctionne et montrent un défaut grossier. Elles
**ne suffisent pas à arbitrer un réglage** — un écart de deux points est du bruit.
Et deux bornes sont mesurées : la strate « de suivi » rend 20 % parce que la
question est encodée **sans son historique** (60 % avec), et le corpus est
**entièrement anglais**, donc l'axe « question anglaise → document français » a
disparu.

## La méthode, si tu veux reprendre celle qui a marché

Six lots ont été audités sur l'autre dépôt, chacun par une conversation qui n'en
avait écrit aucune ligne. **Quinze passages, quinze trouvailles matérielles** — y
compris sur un lot qui n'avait produit aucun commit, et sur un lot dont tous les
chiffres étaient justes. Deux règles ont produit presque tout :

1. **un garde ne se juge jamais à sa lecture, seulement à la mutation qui doit le
   faire rougir.** On casse volontairement le code livré ; si le test reste vert,
   le garde est décoratif. **Treize gardes décoratifs** ont été trouvés ainsi,
   dont trois par le lot qui venait de les écrire ;
2. **une phrase ne rougit pas.** Une documentation fausse survit indéfiniment,
   contrairement à un bug. D'où : chaque chiffre porte sa commande et sa date, et
   toute phrase du genre « le seul », « aucun », « les trois » est soit bornée,
   soit gardée par un test.

Le §10 du mandat de l'autre dépôt porte les leçons complètes, et son §11 les
erreurs de pilotage à ne pas refaire. **Elles valent la lecture même en dehors de
ce chantier.**
