# Politique de sécurité

## Gestion des secrets

- Tous les secrets sont dans `.env`, ignoré par git (`.gitignore`), ainsi que
  `.env.dev`, `.env.prod`, `.env.test` et `.env.local`.
- `.env.example` documente les clés attendues sans valeur sensible, et la façon
  de générer chacune : `openssl rand -base64 24` pour
  `DAGSTER_POSTGRES_PASSWORD` ; `openssl rand -hex 16` (clé d'accès) et
  `openssl rand -base64 32 | tr -d '/+='` (clé secrète) pour les jeux
  `SEAWEEDFS_*`. La table complète des variables est au
  [§2.2 de livraison.md](livraison.md#22-le-env--toutes-les-variables).
- `docker-compose.yml` charge le `.env` entier (`env_file: .env`) dans
  `seaweedfs`, `postgres-dagster`, `dagster-webserver`, `dagster-daemon` et
  `docling-service` : chacun de ces conteneurs voit tous les secrets du fichier
  dans son environnement.
- `detect-secrets` tourne en hook `pre-commit` (`.pre-commit-config.yaml`). Il
  est installé, avec les autres hooks du dépôt, par `make install`, qui lance
  `scripts/installer-les-garde-fous.sh`.
- **Ce hook ne protège pas le `.env`** : un hook `pre-commit` ne voit que les
  fichiers **indexés**, et `.env`, ignoré par git, n'est jamais indexé. Il
  empêche qu'un secret parte dans un fichier **versionné**. Détail dans
  [guide_du_depot.md](guide_du_depot.md), section « Ce que `detect-secrets`
  protège, et ce qu'il ne protège pas ».
- Le corpus (`Datas/`) est exclu de tous les hooks (`exclude: '^Datas/'` à la
  racine de `.pre-commit-config.yaml`) : un secret déposé sous `Datas/` ne
  serait pas détecté.
- Un faux positif se déclare **à l'endroit concerné**, avec sa justification,
  par un commentaire `# pragma: allowlist secret` sur la ligne qui porte la
  valeur. Il n'y a pas de fichier `.secrets.baseline` (registre §5.5).

## Stockage objet : deux jeux d'identifiants

La passerelle S3 déclare deux identités (`SEAWEEDFS_RW_*` et `SEAWEEDFS_RO_*`,
dans `.env`) :

- le jeu **RW** (actions `Admin`, `Read`, `Write`, `List`, `Tagging` ; `Admin`
  est ce que `make_bucket` exige) sert au pipeline : `docling-service`, qui
  téléverse les crops PDF et les images Markdown et que `wipe_stores` emploie
  pour purger, et `dagster-webserver` / `dagster-daemon`, qui téléversent les
  images des HTML (`src/pipeline/media.py`). `docker-compose.yml` en dérive
  `S3_ACCESS_KEY` et `S3_SECRET_KEY` pour ces trois services ;
- le jeu **RO** (actions `Read` et `List` seulement) sert à `rag-agent-chat`.

Le fichier d'identités du serveur (`/run/seaweedfs/s3.json`) est écrit au
démarrage dans un tmpfs du conteneur (mode `0700`, `umask 077`), à partir de ces
variables : aucune clé n'est écrite dans le dépôt ni passée en argument de
commande. Un refus de droits se présente au client comme un 403, que l'agent
rend en 404 silencieux : ces droits se contrôlent par appel direct
(`scripts/campagne/essayer-la-passerelle-s3.py`,
[livraison.md §4.4](livraison.md#44-la-passerelle-s3-et-ses-huit-critères)).
Détail : [services/stockage_objet.md](services/stockage_objet.md).

Le bucket n'est pas public : un `GET` anonyme sur une adresse `media_url` rend
403, y compris depuis le réseau Docker. L'agent lit les objets avec son jeu RO
et les re-sert ; il ne transmet jamais l'adresse à un navigateur.

## Audit des dépendances

```bash
make audit
```

La cible lance `uv run pip-audit -r requirements.txt -r src/docling_service/requirements.txt`
(`pip-audit` est épinglé dans `pyproject.toml`). Les versions sont épinglées avec
`==` dans les deux fichiers. Mettre à jour régulièrement et ré-auditer.

## Isolation réseau

- Les services internes (ChromaDB, SeaweedFS, NebulaGraph, PostgreSQL,
  `docling-service`) ne publient aucun port sur l'hôte : ils sont joignables
  sur le seul réseau `rag_network` (`expose:` ou rien, jamais `ports:`).
- Seuls `dagster-webserver` (port hôte 3002, vers 3000 dans le conteneur) et
  `nebula-studio` (7001) sont publiés, sur toutes les interfaces de l'hôte.
  L'interface Dagster n'a pas d'authentification : quiconque joint le port 3002
  peut lancer et annuler des runs.
- ChromaDB n'a pas d'authentification sur cette pile, et `graphd` ne reçoit pas
  `--enable_authorize` : le couple `NEBULA_USER` / `NEBULA_PASSWORD` n'y est
  pas un contrôle d'accès. La protection de ces deux stores est l'isolation
  réseau.
- Pour joindre un service interne en débogage, passer par un conteneur du
  réseau (`docker compose exec …`), ou ajouter un `docker-compose.override.yml`
  local, non versionné, qui publie le port voulu.

## Conteneurs

- Images de base sur un tag fixe (`python:3.12-slim`, sans digest) ; les
  images tierces sont elles aussi sur un tag de version (`chromadb/chroma:0.6.3`,
  `vesoft/nebula-*:v3.6.0`, `chrislusf/seaweedfs:3.80`, `postgres:15-alpine`…).
- Utilisateur non-root dans les deux Dockerfiles du dépôt (`USER dagster` dans
  `Dockerfile.dagster`, `USER docling` dans `Dockerfile.docling`).
- `--no-install-recommends` à l'installation des paquets système, pour réduire
  la surface d'attaque.

## Rotation des secrets

1. Générer les nouvelles valeurs avec les commandes de `.env.example`.
2. **`DAGSTER_POSTGRES_PASSWORD` d'abord dans la base.** L'image Postgres ne lit
   `POSTGRES_PASSWORD` qu'à l'initialisation d'un répertoire de données vide ;
   celui-ci persiste dans `Datas/database/postgres`. Changer seulement le
   `.env` laisserait Dagster présenter un mot de passe que la base refuse. Il
   faut d'abord `ALTER USER` dans `postgres-dagster`, puis mettre le `.env` à
   jour.
3. Mettre à jour `.env`.
4. Recréer les conteneurs, car `restart` ne relit pas le `.env` :
   `docker compose up -d --force-recreate` (ou `docker compose down` puis
   `docker compose up -d`, sans `-v`). SeaweedFS réécrit son fichier
   d'identités à ce démarrage.
5. Si le jeu `SEAWEEDFS_RO_*` a changé, reporter les nouvelles valeurs dans la
   configuration de `rag-agent-chat`.

## Couche LLM / agent

La couche agent vit dans le projet `rag-agent-chat` ; ce dépôt n'appelle aucun
LLM. Mesures à y prévoir :

- **Presidio** ou **NeMo Guardrails** pour la détection et l'anonymisation de
  PII dans les prompts et les réponses ;
- **limitation de débit** sur les endpoints exposés ;
- **journal d'audit** des requêtes LLM (prompts, tokens, latence) ;
- aucune clé API LLM en dur : passer par des réglages pydantic.
