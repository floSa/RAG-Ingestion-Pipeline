# Bascule de MinIO vers SeaweedFS — 25 septembre 2026

> **Archive datée, non réécrite.** Compte rendu de la préparation de la bascule, 25 septembre 2026 ; la bascule a été exécutée le même jour. L'état en service est décrit par [`livraison.md`](../livraison.md).

Ce fichier est le **compte rendu mesuré** de la préparation de la bascule du
stockage objet du pipeline, de **MinIO** vers **SeaweedFS**. SeaweedFS est la
solution **retenue** par le propriétaire du chantier : ce document ne compare
rien, il **prouve** que la passerelle S3 de SeaweedFS satisfait les huit
critères co-écrits avec le pilote de `rag-agent-chat`, et il écrit la procédure
de bascule et de retour arrière.

**La bascule n'a PAS été exécutée.** MinIO tourne, porte ses **212** objets, et
n'a été ni arrêté, ni modifié, ni purgé. Aucun store du pipeline n'a été écrit.
Le démon Dagster n'a pas été touché. Ce qui a été fait tient en un service
ajouté à côté, un script d'essai, et une répétition générale en lecture seule
du côté de MinIO.

Toute valeur porte son étiquette `mesuré`, `calculé` ou `NON VÉRIFIÉ`, et la
commande qui la rend. Les heures sont UTC, le 25 septembre 2026.

**Le poste** : branche `claude/bascule-seaweedfs-46`, partie de `main` =
`d22a153`, dans un worktree séparé. La pile `rag-ingestion-pipeline` du clone
principal tourne avec ses dix services.

---

## 0. Le verdict, en trois lignes

- **Les huit critères passent.** Les sept premiers par le script versionné
  `scripts/campagne/essayer-la-passerelle-s3.py`, `rc=0`, **7/7** — dont le
  critère 1, éliminatoire. Le huitième par la répétition générale :
  l'empreinte des clés côté SeaweedFS est **`c91f5be6…0994`**, celle du mandat.
- **La branche** est `claude/bascule-seaweedfs-46`, un seul service ajouté à
  `docker-compose.yml`, un script, un `.env.example` documenté, **aucun secret
  commité**.
- **Prêt à basculer** du point de vue de la passerelle. Ce qui reste à faire
  est la bascule elle-même (§4), qui n'a pas été exercée : la réingestion
  complète derrière le nouvel endpoint est **NON VÉRIFIÉE** (§5).

---

## 1. Ce qui a été ajouté

| Objet | Où | Ce que c'est |
|---|---|---|
| service `seaweedfs` | `docker-compose.yml` | la passerelle S3, **à côté** de `minio`, sur `rag_network` |
| variables `SEAWEEDFS_*` | `.env.example` | quatre noms, **sans valeur**, documentés |
| `essayer-la-passerelle-s3.py` | `scripts/campagne/` | le juge des critères 1 à 7 |
| ce fichier | `documentation/campagnes/` | le compte rendu |

`git diff --stat main` (`mesuré`) : **4 fichiers**, aucun fichier de `src/`
touché, aucun autre service de `docker-compose.yml` modifié.

### 1.1 Le service, et les trois décisions qu'il porte

```yaml
  seaweedfs:
    image: chrislusf/seaweedfs:3.80
```

**Version épinglée, pas `latest`.** `mesuré`, le condensat de l'image tirée :
`sha256:1055999e08eed1789b0ae45d235126e4495e23d3fb9d6396293fd42539b1ae6a`.
(`minio:latest`, lui, reste tel quel : on ne touche pas à MinIO aujourd'hui.)

**Commande** : `weed server -dir=/data -ip=seaweedfs -filer -s3 -s3.port=8333
-s3.config=/run/seaweedfs/s3.json -master.volumeSizeLimitMB=1024 -volume.max=0`.
Un seul processus porte master, volume, filer et passerelle S3 — c'est la forme
mono-nœud, celle qui correspond au poste.

**Volume à lui** : `./Datas/database/seaweedfs:/data`, à côté de
`./Datas/database/minio`, comme les quatre autres stores. `Datas/database/` est
ignoré par git. `mesuré` après la répétition générale : **29 Mo**.

**Aucun secret dans le dépôt, et c'est la décision qui a coûté le plus de
réflexion.** SeaweedFS n'a pas de console propriétaire : ses identités se
déclarent dans un **fichier** (`-s3.config`), donc un fichier qui porte des
clés. Trois voies s'offraient, et deux ont été écartées :

| Voie | Écartée / retenue | Motif |
|---|---|---|
| fichier `s3.json` versionné | **écartée** | des clés dans le dépôt, `detect-secrets` rouge, et un secret qui survit à sa rotation |
| fichier monté depuis hors du dépôt | écartée | un fichier de plus à transporter d'un poste à l'autre, hors de toute source de vérité |
| **fichier rendu au démarrage dans un `tmpfs`** | **retenue** | les clés viennent des quatre variables du `.env` non versionné ; rien n'est monté, rien n'est écrit sur disque |

Le rendu passe par un **heredoc** dans l'entrypoint, et non par des arguments :
une clé passée en argument se lit dans `docker inspect` et dans la table des
processus. `mesuré` : le fichier existe dans le conteneur en
`-rw------- root root 526`, dans un `tmpfs` monté `mode=0700`.

**Deux jeux d'identifiants aux droits distincts** — ce que la pile n'avait pas,
MinIO n'y servant qu'un seul jeu racine partagé par le pipeline et par l'agent :

| Identité | Actions SeaweedFS | Pour qui |
|---|---|---|
| `pipeline` | `Admin`, `Read`, `Write`, `List`, `Tagging` | `docling-service`, `wipe_stores` |
| `agent` | `Read`, `List` | `rag-agent-chat` |

`Admin` est dans le jeu écriture parce que **`make_bucket` l'exige** : c'est une
mesure, pas une supposition (critère 5, §2.5). Les noms de variables du contrat
avec l'agent — `MINIO_ENDPOINT`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`,
`MINIO_BUCKET` — **ne changent pas** : les renommer est un lot à part.

### 1.2 La sonde de santé, et le piège qu'elle a révélé

La première écriture de la sonde était `wget http://localhost:8333/`, et le
conteneur est resté **`unhealthy`** sur un service parfaitement sain. Deux
défauts, tous deux mesurés :

1. **`localhost` est refusé.** `-ip=seaweedfs` fait écouter le serveur sur
   cette adresse-là et sur elle seule. `mesuré`, depuis le conteneur :
   `http://localhost:8333/…` rend « connection refused » sur les quatre ports,
   `http://seaweedfs:8333/…` répond.
2. **La racine S3 rend un 403.** `mesuré` : `http://seaweedfs:8333/` rend
   **`HTTP/1.1 403 Forbidden`** sans identifiants — ce qui est le bon
   comportement, et ce qui rendrait la sonde éternellement rouge.
   `http://seaweedfs:8333/healthz` rend **`HTTP/1.1 200 OK`**, et c'est lui qui
   est utilisé.

`mesuré` après correction : `Up 25 seconds (healthy)`.

### 1.3 Le lancement — un seul service, et rien d'autre n'a bougé

La commande **exacte**, jouée depuis le worktree :

```bash
docker compose -p bascule-seaweedfs up -d seaweedfs
```

Trois choses la rendent sûre, et elles étaient le piège annoncé :

- **le service est nommé.** `docker compose up -d` sans nom recrée tout ce qui a
  changé, donc tous les services que `docker-compose.yml` déclare ;
- **le projet est nommé** (`-p bascule-seaweedfs`), donc distinct du projet
  `rag-ingestion-pipeline` du clone principal : Compose ne peut pas atteindre
  ses conteneurs ;
- le réseau `rag_network` porte un **nom stable** et existe déjà : Compose le
  réutilise. Il en avertit (« a network with name rag_network exists but was not
  created for project »), et c'est exactement l'effet recherché.

**Les heures de démarrage, avant et après** (`mesuré`,
`docker inspect -f '{{.Name}} {{.State.StartedAt}}'` sur tous les conteneurs de
la machine, 26 conteneurs) : `diff` entre les deux relevés rend **la seule ligne
du conteneur ajouté**. Les trois conteneurs qui comptent le plus :

| Conteneur | `StartedAt` | `RestartCount` |
|---|---|---|
| `rag-ingestion-pipeline-minio-1` | `2026-09-24T11:23:09.972057699Z` | **0** |
| `rag-ingestion-pipeline-dagster-daemon-1` | `2026-09-24T11:23:10.331748227Z` | **0** |
| `rag_assistant-docling-service-1` | `2026-09-25T03:42:24.243206813Z` | **0** |

Ces trois valeurs sont **identiques avant et après**, et celle de
`docling-service` est celle de la deuxième campagne de référence, à 03:42 —
c'est-à-dire que rien de ce chantier-ci ne l'a touchée.

---

## 2. Les critères 1 à 7, un par un

Le juge est `scripts/campagne/essayer-la-passerelle-s3.py`. Il utilise
**`minio-py` 7.2.20**, la même bibliothèque et la même version que
`src/docling_service/images.py` et que l'agent : un essai mené avec `boto3`
validerait un dialecte que personne n'émet en production.

Il tourne **dans un conteneur sur `rag_network`**, parce que `seaweedfs:8333` et
`minio:9000` ne se résolvent nulle part ailleurs — c'est aussi la position d'où
le pipeline parle :

```bash
docker run --rm --network rag_network \
  -e ESSAI_S3_ENDPOINT=seaweedfs:8333 -e ESSAI_S3_BUCKET="$MINIO_BUCKET" \
  -e ESSAI_S3_RW_ACCESS_KEY=… -e ESSAI_S3_RW_SECRET_KEY=… \
  -e ESSAI_S3_RO_ACCESS_KEY=… -e ESSAI_S3_RO_SECRET_KEY=… \
  -v "$PWD":/w -v "$SCRATCH":/scratch -w /w python:3.12-slim \
  sh -c "pip install -q minio==7.2.20; \
         python scripts/campagne/essayer-la-passerelle-s3.py --cles /scratch/cles-minio.txt"
```

**Les identifiants passent par l'environnement, jamais par la ligne de
commande** : un secret passé en argument se lit dans la table des processus.

`mesuré` : **`rc=0`, 7/7 critères passés**, et le `rc` est celui du
**processus**, relevé hors de tout tube.

### 2.1 Critère 1 — `GetBucketLocation` servi. ÉLIMINATOIRE

`minio-py` émet un `GetBucketLocation` **avant tout échange** sur un bucket
qu'il ne connaît pas encore (`Minio._get_region`, api.py:498), et il le fait des
deux côtés. Le script vide le cache de régions (`_region_map`) avant chaque
appel, sans quoi le second critère qui la demande ne quitterait plus le
processus, et **ne fixe aucune région au constructeur** : la fixer
court-circuiterait l'appel, l'essai passerait sur une passerelle qui ne le sert
pas, et la production casserait.

| Jeu | Région rendue |
|---|---|
| écriture | **`us-east-1`** |
| lecture seule | **`us-east-1`** |

**Le critère éliminatoire est rempli.** L'essai continue.

### 2.2 Critère 2 — deux jeux aux droits distincts, sans console propriétaire

`mesuré` : les deux clés d'accès diffèrent, et les deux jeux sont **acceptés**
— `list_buckets` rend **1 bucket** pour chacun. Ils sont déclarés par le fichier
d'identités du §1.1, donc **sans aucune console** : SeaweedFS n'en a pas, et
c'est ici un avantage, la déclaration étant un fichier versionnable dans sa
forme et secret dans ses valeurs.

### 2.3 Critère 3 — le jeu lecture seule lit

`mesuré`, quatre appels directs avec le jeu lecture seule :

| Appel | Résultat |
|---|---|
| `GetBucketLocation` | `us-east-1` |
| `ListBucket` (`list_objects`) | **1** objet sous `essai/` |
| `GetObject` | **6 octets**, identiques à l'écrit |
| `StatObject` | taille **6** |

### 2.4 Critère 4 — adresses path-style

Le script **espionne l'URL réellement émise** en enveloppant
`client._http.urlopen` le temps d'un `stat_object`, puis il la découpe. Ce n'est
pas une lecture de la configuration : c'est ce qui est parti sur le fil.

```
URL émise : http://seaweedfs:8333/documents/essai/critere-3-temoin.bin
```

L'hôte est **`seaweedfs:8333`**, donc le bucket n'est **pas** passé dans le nom
de domaine, et le chemin est **`/documents/essai/critere-3-temoin.bin`**, soit
`scheme://host:port/<bucket>/<objet>`. Le critère est rempli.

### 2.5 Critère 5 — les cinq écritures, et leur refus en lecture seule

`mesuré`, avec le **jeu écriture** :

| Opération | Résultat |
|---|---|
| `bucket_exists` | **vrai** |
| `make_bucket` | `documents-essai-make-bucket` **créé** (puis retiré) |
| `put_object` | **9 octets** écrits |
| `list_objects` | **2** objets rendus, dont celui qu'on vient d'écrire |
| `remove_object` | **fait** |

`mesuré`, les mêmes opérations destructrices avec le **jeu lecture seule** :

| Opération | Verdict |
|---|---|
| `make_bucket` | **refusé — HTTP 403 / `AccessDenied`** |
| `put_object` | **refusé — HTTP 403 / `AccessDenied`** |
| `remove_object` | **refusé — HTTP 403 / `AccessDenied`** |

**`bucket_exists` et `list_objects` restent PERMIS en lecture seule, et c'est
voulu** : ce sont les lectures du critère 3, et les refuser casserait l'agent.
Le critère 5 demande que les cinq opérations soient refusées au jeu lecture
seule ; les deux qui sont des lectures sont **exigées par le critère 3**. Les
deux critères se contredisent sur ces deux appels, et la contradiction est
tranchée en faveur du critère 3, qui décrit ce dont l'agent a besoin pour
fonctionner. C'est un **écart au mandat, assumé et nommé**, et non un oubli.

### 2.6 Critère 6 — l'alphabet des clés, à l'aller-retour

**222 clés** écrites, listées et `stat`ées, **toutes rendues octet pour
octet** : les **212 clés réelles** du corpus, tirées du bucket MinIO de
production en lecture seule, plus **10 clés d'épreuve** qui portent ce que
l'alphabet `[\w\-./]` ne couvre pas.

Les dix clés d'épreuve, écrites dans le script et non tirées au hasard :
chemins imbriqués, majuscules, points multiples, tirets et tirets bas, **espace
nu**, **deux-points pleine chasse `：` (U+FF1A)**, accents `éèêàçüñ`, chiffres,
et une clé de 124 caractères.

**Un fait mesuré, et il corrige le mandat** : les 212 clés actuelles du corpus
sont **purement ASCII**, et leur alphabet complet est exactement
`[A-Za-z0-9/_.-]` (`mesuré`, ensemble des caractères distincts des 212 clés :
aucun caractère non-ASCII, aucun espace). Ni espace ni deux-points pleine chasse
n'y survivent.

Le deux-points pleine chasse vit bien dans le **corpus** — la partition
`MLOps with Databricks/4. Model Serving：Architectures and Implementation` le
porte — mais **il n'arrive pas jusqu'aux clés d'objet**. `sanitize_key`
(`images.py:132`) remplace par `_` tout ce qui n'est pas `[A-Za-z0-9/_.-]`, si
bien que la clé écrite est
`images/html/htms/MLOps_with_Databricks/4_Model_Serving_Architectures_and_Implementation/img_0000.png`
(`mesuré`, clé réelle du bucket).

Les caractères difficiles sont donc éprouvés par les **clés d'épreuve**, qui
sont là précisément parce que le corpus ne les fournit plus — et elles vont
au-delà de ce que le pipeline écrit aujourd'hui, ce qui est le bon sens de
l'épreuve : elles couvrent ce qu'un `sanitize_key` assoupli laisserait passer
demain.

Le script détecte, et nomme, le défaut qu'une passerelle pourrait avoir ici :
si une clé ne revient pas, il cherche une **forme normalisée NFC** parmi les
clés rendues et le dit. Une passerelle qui normalise rend une clé différente de
celle qu'elle a reçue, et le graphe pointe alors dans le vide **sans qu'aucune
erreur ne le signale**. SeaweedFS ne normalise pas.

### 2.7 Critère 7 — les droits par appel direct, jamais par l'affichage

C'est le critère de **méthode**, et le script l'incarne de bout en bout : aucun
état n'est lu sur une console, chaque droit est établi par l'appel lui-même, et
le code HTTP est imprimé tel quel.

`mesuré` : un `put_object` avec le jeu lecture seule rend
**`HTTP 403 / AccessDenied`**. Le script **refuse explicitement un refus qui ne
serait pas un 403**, et il écrit pourquoi : un 403 remonte chez
`rag-agent-chat` en **404 silencieux** — l'image demandée « n'existe pas », dit
l'écran, et le corpus a simplement l'air incomplet. Un droit mal posé ne se voit
pas à l'usage ; il se voit ici.

### 2.8 Le contrôle négatif — l'essai sait échouer

Un essai qui ne sait pas échouer ne prouve rien. La **même commande**, avec un
jeu d'identifiants **faux** :

```
PREPARATION IMPOSSIBLE : S3Error: … code: InvalidAccessKeyId,
message: The access key ID you provided does not exist in our records.

VERDICT : ROUGE (le bucket d'essai n'a pas pu etre cree)
rc=1
```

`mesuré` : **`rc=1`**, du processus. Le script sort en 1 dès qu'un seul critère
échoue, et il **s'arrête sans jouer les suivants** si le critère 1, éliminatoire,
est rouge.

---

## 3. La répétition générale, et le critère 8

**Sans toucher au vrai pipeline, et sans jamais écrire du côté de MinIO.** Le
sens de la copie n'est pas réversible : une erreur d'aiguillage ici écraserait
le store de production. Le script de copie ne construit du côté MinIO que des
appels de **lecture** (`list_objects`, `get_object`), et ne l'écrit ni ne l'efface
jamais.

`mesuré` :

```
MinIO : 212 cles a copier
copie : 212 objets, 29 385 971 octets
SeaweedFS : 212 cles distinctes
empreinte SeaweedFS : c91f5be6e24fbcba5f4a744119bf8da65fed44b7ecac79cce0ae1b027ed0b994
comparaison octet pour octet : 212 objets compares, 0 differents, 0 illisibles
rc=0
```

### 3.1 Le critère 8

| | |
|---|---|
| empreinte attendue (mandat) | `c91f5be6e24fbcba5f4a744119bf8da65fed44b7ecac79cce0ae1b027ed0b994` |
| empreinte **mesurée côté SeaweedFS** | **la même** |
| empreinte mesurée côté MinIO, le même jour | **la même** |

**La recette, écrite à côté de l'empreinte**, comme le mandat le demande :

> Les clés d'objet **distinctes** (`set`), triées par `sorted()` de Python,
> jointes par `"\n"`, **avec un `"\n"` final**, encodées en **UTF-8**,
> condensées en **SHA-256**, rendues en hexadécimal minuscule.

En trois lignes :

```python
cles = sorted({o.object_name for o in client.list_objects(bucket, recursive=True)})
empreinte = hashlib.sha256(("\n".join(cles) + "\n").encode("utf-8")).hexdigest()
```

C'est mot pour mot la recette de l'agent, et elle rend la même valeur des deux
côtés. **Les clés ne changent pas à la bascule** — seul l'endpoint change — donc
cette égalité était attendue ; elle est **constatée** plutôt que supposée, et
elle établit surtout que SeaweedFS **rend les clés telles qu'il les a reçues**.

### 3.2 La comparaison octet pour octet

**Tous les 212 objets**, pas un échantillon : 29 Mo au total, la comparaison
prend quelques secondes, et un échantillon aurait demandé de justifier son
tirage. Chaque objet est relu des deux côtés et les deux SHA-256 sont comparés.
`mesuré` : **0 différent, 0 illisible**.

### 3.3 Ce que la recréation du conteneur a prouvé en passant

La sonde de santé du §1.2 a dû être corrigée, donc le conteneur `seaweedfs` a
été **recréé** après la première répétition générale. Les 212 objets étaient
toujours là, et la seconde répétition a rendu les **mêmes** chiffres. Le volume
tient, et c'est un fait qu'on n'avait pas prévu de mesurer.

### 3.4 MinIO, après tout cela

`mesuré`, immédiatement après la répétition générale, par la même sonde qu'au
départ :

| | |
|---|---|
| objets dans le bucket `documents` | **212** |
| clés distinctes | **212** |
| empreinte | **`c91f5be6…0994`** — inchangée |
| `StartedAt` du conteneur | **inchangé** |
| `RestartCount` | **0** |

**MinIO n'a été ni arrêté, ni modifié, ni purgé, et rien n'y a été écrit.**

---

## 4. La procédure de bascule, et le retour arrière

**Elle n'a pas été exécutée.** Elle est écrite pour la fusion, et chaque étape
porte le motif qui la rend nécessaire.

### 4.0 Avant de commencer — les conditions d'arrêt

1. `main` porte cette branche fusionnée, et le clone principal est dessus.
2. Le service `seaweedfs` du `docker-compose.yml` fusionné est celui-ci.
3. Les huit comptes et l'empreinte sont relevés **avant**, par les sondes de la
   deuxième campagne de référence : sans l'état d'avant, l'après ne se compare
   à rien.
4. Aucun run Dagster en cours.
5. **MinIO est debout avec ses 212 objets** — c'est le retour arrière, et il
   doit exister avant qu'on parte.

### 4.1 Le `.env` du clone principal

Quatre lignes ajoutées, une ligne changée, deux lignes remplacées :

```diff
+ SEAWEEDFS_RW_ACCESS_KEY=…      # openssl rand -hex 16
+ SEAWEEDFS_RW_SECRET_KEY=…      # openssl rand -base64 32 | tr -d '/+='
+ SEAWEEDFS_RO_ACCESS_KEY=…
+ SEAWEEDFS_RO_SECRET_KEY=…

- MINIO_ENDPOINT=minio:9000
+ MINIO_ENDPOINT=seaweedfs:8333
- MINIO_ROOT_USER=…             # l'ancien jeu MinIO
- MINIO_ROOT_PASSWORD=…
+ MINIO_ROOT_USER=${SEAWEEDFS_RW_ACCESS_KEY}        # valeur recopiée, pas l'expansion
+ MINIO_ROOT_PASSWORD=${SEAWEEDFS_RW_SECRET_KEY}
```

`MINIO_BUCKET` **ne change pas** : `documents`.

**Trois pièges à cet endroit précis.**

1. `MINIO_ROOT_USER` et `MINIO_ROOT_PASSWORD` sont **aussi** ce que le service
   `minio` lit pour se configurer lui-même. Leur donner le jeu SeaweedFS
   changerait les identifiants du MinIO **au prochain démarrage de son
   conteneur**, et le retour arrière deviendrait impossible. **On ne recrée donc
   pas `minio`** (§4.2), et l'ancien jeu est conservé hors ligne, par écrit,
   pour le retour arrière.
2. Ce couplage est le **défaut de conception** que la bascule met en lumière :
   une variable qui sert à la fois à configurer un serveur et à s'authentifier
   auprès d'un autre. Le découpler est le lot de renommage, déjà prévu, qui
   n'est pas celui d'aujourd'hui.
3. `docker compose` **n'expanse pas** `${…}` à l'intérieur d'un `.env` de façon
   fiable selon les versions : on recopie les **valeurs**, on n'écrit pas
   l'expansion.

Côté `rag-agent-chat`, son propre `.env` reçoit `MINIO_ENDPOINT=seaweedfs:8333`
et le jeu **lecture seule**. C'est un dépôt distinct, et sa bascule est à
coordonner avec son pilote.

### 4.2 Les services à recréer, et l'ordre

```bash
cd /home/ubuntu/RAG/rag-ingestion-pipeline

# 1. SeaweedFS d'abord : la cible doit être debout avant que quoi que ce soit
#    la vise.
docker compose up -d seaweedfs
docker compose ps seaweedfs          # attendre « healthy »

# 2. Le démon Dagster, puis le webserver. NOMMER LES SERVICES.
docker compose up -d --force-recreate dagster-daemon dagster-webserver

# 3. docling-service en dernier : il crée le bucket au démarrage, et il doit
#    le créer sur la NOUVELLE passerelle.
docker compose up -d --force-recreate docling-service
docker compose ps docling-service    # attendre « healthy » (start_period 600 s)
```

**`--force-recreate` et non `restart`.** Un `restart` **ne relit pas le
`.env`** : le conteneur repartirait avec l'ancien endpoint, et rien ne le
dirait. C'est la même phrase que `.env.example` écrit déjà pour
`EMBEDDING_MODEL_NAME`.

**Les services nommés, jamais `docker compose up -d` nu**, qui recréerait tout
ce qui a changé — c'est-à-dire, après cette fusion, tous les services qui lisent
le `.env` modifié, **`minio` compris**, ce que le §4.1 interdit.

**`minio` n'est PAS recréé**, et c'est le retour arrière qui l'exige.

### 4.3 Le démon Dagster — le recréer sans qu'une ingestion parte

Le démon **doit** être recréé : il porte les capteurs, et les runs qu'il crée
héritent de son environnement. Mais il porte quatre capteurs armés, évalués
toutes les 30 s.

**Ce qui déclenche un run, lu dans le code** (`src/pipeline/factory.py`) : un
`mtime` de fichier du corpus plus récent que le curseur, **ou** un curseur qui
commence par `reingerer:`. Rien d'autre.

**Ce qu'une recréation du démon change** : rien de tout cela. Les **curseurs
vivent dans le Postgres de Dagster**, pas dans le conteneur ; ils survivent. Les
`mtime` du corpus ne sont pas touchés. Le fait le plus proche qu'on ait
`mesuré` : la purge de la deuxième campagne de référence, qui a retiré
`Datas/.cleaned/`, a créé **0 run** — 958 avant, 958 après.

**La conclusion est donc : recréer le démon ne part pas.** Elle est `calculé`,
pas `mesuré` sur une recréation réelle. Pour qui veut la ceinture **et** les
bretelles, le geste prudent, à jouer **avant** l'étape 2 du §4.2 :

```bash
docker compose exec -T -w /opt/dagster/app -e PYTHONPATH=/opt/dagster/app \
  dagster-webserver dagster sensor stop livres_html_sensor -w src/workspace.yaml
# idem pdfs_sensor, markdown_sensor, agent_reindex_sensor
```

et le `dagster sensor start` correspondant **après** que `docling-service` est
`healthy`. Ce geste a son propre coût : un capteur arrêté puis relancé repart de
son curseur, donc rien n'est perdu, mais l'état « arrêté » est persistant et
**s'oublie**. Quoi qu'on choisisse, on le note.

### 4.4 La purge — elle visera SeaweedFS, et c'est vérifié dans le code

`src/wipe_stores.py:350` appelle `purge_bucket(images.get_client(),
settings.minio_bucket)`. `images.get_client()` (`images.py:34`) construit un
`Minio(settings.minio_endpoint, …)`, et `settings` est le `DoclingSettings` de
`src/docling_service/settings.py:18`, dont `minio_endpoint` est peuplé par la
variable d'environnement **`MINIO_ENDPOINT`**.

**Donc : `wipe_stores` vise ce que `MINIO_ENDPOINT` désigne, et rien d'autre.**
Une fois la bascule faite, il purge **SeaweedFS**, et il ne touche plus MinIO —
ce qui est exactement ce que le retour arrière demande. Il n'y a **aucun**
endpoint écrit en dur dans ce chemin. C'est `mesuré` par lecture du code, et
non supposé.

La purge, inchangée, **après** que `docling-service` est `healthy` :

```bash
docker run --rm --network rag_network \
  -v "$PWD/src":/app/src:ro \
  -v "$PWD/Datas":/opt/dagster/app/Datas \
  --env-file "$PWD/.env" -e HOME=/tmp -e PYTHONPATH=/app -w /app \
  rag-ingestion-pipeline-docling-service python -m src.wipe_stores
```

**Attendu : `0 objets supprimes du bucket documents`** si SeaweedFS est neuf —
et **non** 212. Un « 212 objets supprimés » ici voudrait dire que l'endpoint
n'a pas changé, c'est-à-dire **que MinIO vient d'être purgé**. C'est le signal
d'arrêt le plus important de toute la procédure : si ce chiffre n'est pas 0, on
s'arrête et on constate avant tout autre geste.

*(La répétition générale a laissé 212 objets dans le SeaweedFS d'essai, sur le
projet Compose `bascule-seaweedfs` et son volume à lui. Le SeaweedFS de la pile
principale sera neuf. Si le même volume devait être réutilisé, le chiffre
attendu serait 212, et il faudrait le dire avant.)*

### 4.5 Le redémarrage de `docling-service`, et pourquoi il est déjà fait

La purge joue `DROP SPACE`, et `init_schema()` ne tourne **qu'au démarrage** du
service. Il faut donc le redémarrer **après** la purge :

```bash
docker compose restart docling-service
```

Ici, `restart` **suffit** — le `.env` a déjà été relu à l'étape 3 du §4.2. Le
journal doit porter les deux lignes que la deuxième campagne a relevées :

```
INFO [src.docling_service.images] Bucket MinIO 'documents' pret.
INFO [src.docling_service.nebula] Schema semantique NebulaGraph pret.
```

La première ligne dit « MinIO » et parlera de SeaweedFS : le message porte le
nom de la bibliothèque, pas celui du serveur. C'est cosmétique, et c'est le lot
de renommage.

### 4.6 La réingestion, par le marqueur

Deux capteurs, ceux dont la source porte des fichiers :

```bash
docker compose exec -T -w /opt/dagster/app -e PYTHONPATH=/opt/dagster/app \
  dagster-webserver dagster sensor cursor livres_html_sensor \
    --set 'reingerer:2026-09-25-bascule-seaweedfs' -w src/workspace.yaml

docker compose exec -T -w /opt/dagster/app -e PYTHONPATH=/opt/dagster/app \
  dagster-webserver dagster sensor cursor pdfs_sensor \
    --set 'reingerer:2026-09-25-bascule-seaweedfs' -w src/workspace.yaml
```

Pas de marqueur sur `markdown_sensor` (source vide) ni sur
`agent_reindex_sensor` (ce n'est pas un capteur de fichiers). Attendu :
**22 + 1 = 23 runs** créés par les capteurs, aucun à la main.

**La réingestion est ici obligatoire, et non facultative.** `images.py:118`
stocke l'adresse `http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{clé}` **dans le
graphe** (`minio_url`) et dans les copies HTML nettoyées. Changer l'endpoint
change donc toutes les adresses stockées. **Les clés, elles, ne changent pas** —
c'est ce que le critère 8 établit.

### 4.7 Les mesures d'après

| Mesure | Attendu |
|---|---|
| sommets, tous tags, `Document` compris | **15 196** |
| sommets `Document` | **23** |
| sommets `Paragraph` | **7 251** |
| sommets `ListItem` | **1 748** |
| sommets `Code` | **4 963** |
| arêtes `PARENT_OF` | **15 173** |
| chunks ChromaDB | **4 367** |
| objets dans le bucket | **212** |
| **empreinte des clés (critère 8)** | **`c91f5be6…0994`** |
| `comparer` contre l'instantané | **23 / 23**, **`DEPLACES 0`**, `rc=0` |

Le compte de sommets se fait par `MATCH … RETURN count(n)`, tag par tag, et
**jamais** par `SHOW STATS`, qui rend 0 sur un space peuplé.

Et un neuvième témoin, propre à cette bascule : **les `minio_url` du graphe
portent le nouvel endpoint**. `MATCH (n) WHERE n.minio_url != "" RETURN
n.minio_url LIMIT 1` doit commencer par `http://seaweedfs:8333/documents/`. Si
elles portent encore `minio:9000`, la réingestion a tourné derrière l'ancien
environnement, et c'est le démon qui n'a pas été recréé.

### 4.8 Le retour arrière

**MinIO est resté debout avec ses 212 objets pendant toute la bascule.** C'est
ce qui rend le retour arrière possible, et c'est pourquoi `minio` n'est jamais
recréé ni purgé.

1. Remettre l'**ancien `.env`** — d'où la nécessité de l'avoir conservé :
   `MINIO_ENDPOINT=minio:9000`, l'ancien `MINIO_ROOT_USER` et l'ancien
   `MINIO_ROOT_PASSWORD`. Les quatre `SEAWEEDFS_*` peuvent rester : elles ne
   servent plus qu'au service `seaweedfs`, qu'on laisse tourner à vide.
2. Recréer **les mêmes services, dans le même ordre**, `minio` toujours exclu :
   `docker compose up -d --force-recreate dagster-daemon dagster-webserver`
   puis `docker compose up -d --force-recreate docling-service`.
3. **Purger** — elle visera de nouveau MinIO, par le même chemin qu'au §4.4, et
   elle doit annoncer **212 objets supprimés**.
4. **Réingérer** par le marqueur du §4.6, avec une autre étiquette
   (`reingerer:2026-09-25-retour-arriere`).
5. Reprendre les mesures du §4.7. Les huit comptes et l'empreinte doivent
   revenir aux mêmes valeurs — ce sont les mêmes que ceux d'aujourd'hui.

**Ce que le retour arrière coûte : une purge et une réingestion complète**, soit
l'ordre de grandeur mesuré par la deuxième campagne de référence. Ce n'est pas
un basculement instantané, et il ne peut pas l'être : les `minio_url` du graphe
portent l'endpoint.

**Le point de non-retour** est le §4.4, la purge. Avant elle, il suffit de
remettre le `.env` et de recréer les trois services. Après elle, les stores sont
vides et la réingestion est obligatoire dans un sens comme dans l'autre.

---

## 5. NON VÉRIFIÉ

Ce que ce chantier **n'a pas** établi, nommé pour que personne ne le croie fait.

1. **La bascule elle-même n'a pas été exécutée.** Aucune étape du §4 n'a été
   jouée. Le `.env` du clone principal est intact, aucun service de la pile n'a
   été recréé, aucune purge n'a tourné.
2. **La réingestion derrière SeaweedFS est NON VÉRIFIÉE.** Les huit comptes du
   §4.7 sont ceux de la deuxième campagne de référence, recopiés du mandat :
   ce sont des **attendus**, pas des mesures de cette bascule. Que
   `docling-service` écrive correctement ses crops sur SeaweedFS **en
   conditions réelles** — et non par un script de copie — reste à voir.
3. **La recréation du démon Dagster sans départ d'ingestion est `calculé`, pas
   `mesuré`.** Le raisonnement du §4.3 s'appuie sur le code et sur une mesure
   voisine (la purge qui n'a créé aucun run), pas sur une recréation réelle.
4. **L'agent n'a pas été essayé contre SeaweedFS.** Le critère 3 établit que le
   jeu lecture seule peut faire les quatre appels dont l'agent a besoin, avec la
   même bibliothèque et la même version. Que `rag-agent-chat` **lui-même**
   serve une image depuis SeaweedFS n'a pas été vu, et cela appartient à son
   pilote.
5. **Aucune mesure de performance.** Ni débit, ni latence, ni tenue en charge,
   ni comportement à volume croissant. La répétition générale a copié 29 Mo en
   quelques secondes ; ce chiffre ne dit rien d'une exploitation.
6. **La durabilité n'a pas été éprouvée.** Le volume a survécu à **une**
   recréation de conteneur (§3.3). Rien n'a été mesuré sur un redémarrage de la
   machine, une coupure en cours d'écriture, ou un disque plein.
   `-master.volumeSizeLimitMB=1024` et `-volume.max=0` sont des réglages de
   confort mono-nœud, choisis et **non éprouvés**.
7. **Le bucket d'essai `documents` du SeaweedFS de test contient les 212 objets
   copiés.** Il vit dans le projet Compose `bascule-seaweedfs` et dans son
   volume à lui (`Datas/database/seaweedfs` du worktree), et il ne doit pas
   être confondu avec celui de la pile principale, qui n'existe pas encore.
8. **Le renommage `MINIO_*` → un nom neutre n'est pas fait**, délibérément :
   c'est le contrat avec l'agent, et un lot à part. Le couplage relevé au §4.1
   — une même variable configure MinIO **et** authentifie auprès de SeaweedFS —
   est un défaut réel que ce lot-là devra fermer.
