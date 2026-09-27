# Orchestrateur ETL (Dagster)

## Présentation du service
Dagster orchestre l'ingestion : il détecte les documents ajoutés ou modifiés dans `Datas/` et soumet chacun au service d'extraction, sans intervention manuelle.

Il se compose de trois services :
- **postgres-dagster** : base PostgreSQL des métadonnées de l'orchestrateur (historique des runs, événements, états et curseurs des capteurs).
- **dagster-webserver** : interface pour gérer et visualiser les pipelines (jobs, assets, capteurs).
- **dagster-daemon** : composant de fond qui évalue les capteurs, dépile la file des runs, les exécute dans son propre conteneur (`DefaultRunLauncher`) et surveille les runs orphelins.

## Accès au service
- **Interface web** : [http://localhost:3002](http://localhost:3002)
- **Base de données interne** : `postgres-dagster:5432` (variables : [livraison.md §2.2](livraison.md#22-le-env--toutes-les-variables))

Fiches d'exploitation : [`services/dagster.md`](services/dagster.md), [`services/postgres.md`](services/postgres.md).

## Structure et définition des données
- **La déclaration des sources (`sources.yaml` et `sources.py`)** : chaque source de documents (un dossier de PDF, une capture de site en HTML, un dossier de notes Markdown) est un bloc YAML : nom, motif glob relatif à `/opt/dagster/app/Datas`, type (`pdf`, `html` ou `md`), options de nettoyage (HTML seulement) et filtre des pages liminaires. Ajouter une source ne demande aucun code Python ([`guide_du_depot.md`](guide_du_depot.md#ajouter-une-nouvelle-source)).
- **La fabrique (`factory.py`)** : pour chaque source déclarée, elle génère les partitions dynamiques (`{name}_files`, une par fichier), les assets, le job (`{name}_job`) et le capteur (`{name}_sensor`). Les trois types suivent le même mécanisme ; les sources HTML ont un asset de nettoyage (`cleaned_html`) en amont de l'extraction, dont PDF et Markdown n'ont pas besoin.
- **Le nettoyage HTML (`cleaning.py`)** : pré-passe déterministe (scripts, styles, navigation, images `data:` SingleFile), puis, par ordre de priorité : un profil dédié au site s'il détecte la page ; un conteneur sémantique (`<article>`, `<main>`) qui passe les seuils ; sinon trafilatura et readability-lxml comparés, le candidat qui garde le plus de texte l'emportant. Si aucun ne passe les seuils, le HTML pré-nettoyé est conservé.
- **Le curseur** : pour qu'un livre ne soit pas réingéré à chaque redémarrage, chaque capteur garde dans son curseur, stocké en PostgreSQL, le `mtime` de chaque fichier traité (un objet JSON, clé de partition vers `mtime`). Un fichier dont le `mtime` n'a pas bougé est ignoré. La clé de run vaut `{source}_{partition}_{mtime}` ; une réingestion se demande en posant le marqueur `reingerer:<étiquette>` à la place du curseur (`PREFIXE_REINGESTION`, procédure : [livraison.md §3.2](livraison.md#32-réingérer--le-marqueur-sur-le-curseur)).
- **Les partitions** : chaque fichier est une partition dynamique (clé = chemin relatif à `Datas/`), ce qui permet de relancer un échec sur un livre précis sans rejouer tout le pipeline.
- **L'extraction** : l'asset `extracted_document` soumet le document au service Docling (`POST /extract`, avec `filepath` et `source_path`), qui rend un identifiant de job, puis suit son avancement (`GET /jobs/{id}`) jusqu'à la fin. Le service écrit lui-même dans NebulaGraph, ChromaDB et le stockage d'objets ; seules les images des captures HTML y sont téléversées en amont, par `cleaned_html` (`src/pipeline/media.py`). Le bilan (`elements`, `chunks`, `pages`, `elapsed_seconds`, `pages_skipped`, `ocr`, `language`, `failed_batches`, et `duplicate_of` pour un doublon écarté) est publié dans les métadonnées de l'asset.
- **Les reprises** : un échec transitoire (service redémarré, coupure réseau) est repris deux fois, après 120 s puis avec un délai exponentiel (`EXTRACTION_RETRY_POLICY`). Un échec propre au document (`status: failed`) n'est pas repris.

## Cadencer le débit

Un corpus de plusieurs dizaines de livres crée autant de partitions et de runs. Deux limites empilées évitent de saturer la machine :

1. **La file Dagster** : `QueuedRunCoordinator` avec `max_concurrent_runs: 2` dans `dagster.yaml`. Sans limite explicite, le coordinateur en lance jusqu'à dix, soit autant de processus dans le conteneur daemon.
2. **Le worker du service d'extraction** : un seul document converti à la fois, la conversion saturant déjà la machine.

Une fois l'ingestion retombée, `POST /reindex` part sur `rag-agent-chat` (`AGENT_SERVICE_URL`) pour que son index lexical BM25, tenu en mémoire, voie les documents qui viennent d'être écrits. L'appel n'est pas dans l'asset d'extraction : il a son job, `agent_reindex_job`, et son capteur, `agent_reindex_sensor`.

Le capteur définit « fin d'ingestion » comme un **état** et non comme un événement, faute de point de fin dans cette architecture : un job par source, un run par fichier, des partitions créées au fil de l'eau. Il arme le job quand aucun run d'ingestion n'est en vol (les statuts non terminaux, `QUEUED` compris : les runs d'une rafale attendent dans la file) et qu'au moins un a réussi depuis la dernière réindexation. Le nombre d'appels ne suit donc pas le nombre de documents.

Le capteur **ne tient aucun curseur**. Il compare deux faits qu'il lit dans l'historique des runs : le repère de la dernière ingestion réussie, et celui de la dernière **réindexation réussie**. Un repère est un `storage_id`, entier croissant attribué à la création d'un run. Conséquence : tant qu'aucune réindexation n'a réussi depuis la dernière ingestion réussie, il en reste une à faire, et le capteur réarme au tick suivant. Une réindexation lancée à la main depuis l'interface compte elle aussi, si elle réussit.

L'appel ne peut pas faire échouer une ingestion : il vit dans son propre run. Ce run-là, en revanche, **échoue** quand l'appel n'aboutit pas : l'échec est visible dans l'interface, et c'est ce que le capteur relit pour décider de retenter. Une URL vide ne fait rien échouer : l'appel n'est pas tenté, c'est un choix de configuration. En cas de succès, le résultat est publié dans les métadonnées de l'asset `agent/lexical_index`, sous la clé `reindex`.

Les runs en attente sont visibles dans **Runs > Queued**. Relever `max_concurrent_runs` n'accélère rien tant que le service reste mono-worker : c'est un levier à ne toucher que si l'extraction est parallélisée.

### Un run bloqué ne gèle pas la réindexation

Le capteur de réindexation saute tant qu'un run d'ingestion est non terminal. Un
run qui ne revient jamais (worker tué, daemon interrompu) bloquerait donc la
réindexation indéfiniment. Le *run monitoring* de Dagster, activé dans
`dagster.yaml`, fait échouer ces runs orphelins. La règle vit à ce seul endroit
et vaut pour toutes les sources : aucun capteur ne décide lui-même qu'un run est
mort.

| Réglage | Valeur | Ce qu'il borne |
|---|---|---|
| `enabled` | `true` | active la surveillance |
| `poll_interval_seconds` | 60 | intervalle de contrôle du daemon |
| `start_timeout_seconds` | 900 | un run que le launcher n'arrive jamais à démarrer |
| `max_runtime_seconds` | 90 000 (**25 h**) | un run qui ne finit jamais |
| `max_resume_run_attempts` | 0 | `DefaultRunLauncher` ne sait pas reprendre un run ; un run mort est marqué en échec |

**Pourquoi 90 000 et non une valeur serrée.** `EXTRACTION_TIMEOUT_SECONDS` vaut
86 400 s (24 h) : c'est le plafond que le pipeline s'accorde lui-même *par
document*. **Les deux nombres ne sont pas le même plafond** : 90 000 s = 25 h,
86 400 s = 24 h, l'écart délibéré est d'**une heure**. C'est donc **25 h** qu'un
opérateur attend au pire devant un run gelé, et non 24. L'arithmétique est aussi
écrite dans `dagster.yaml`, au-dessus du réglage.

Un `max_runtime_seconds` plus court tuerait des runs que le pipeline considère
encore légitimes. Ce délai est la **dernière ligne** : il ne se déclenche que
si le plafond du pipeline a lui-même échoué, donc quand le run est réellement
gelé et non lent. Pour mémoire, le run le plus long mesuré sur ce corpus vaut
**111 s** (mesuré le 1er septembre 2026, 23 runs réussis) : la marge est de 810×.

`tests/unit/test_dagster_yaml.py` vérifie ces valeurs par trois tests :

- la borne ne descend pas sous le plafond du pipeline ;
- l'écart au-dessus de ce plafond ne dépasse pas un dixième de celui-ci, faute
  de quoi la borne deviendrait un second plafond indépendant ;
- `dagster.yaml` et ce fichier annoncent, en heures, la valeur effective de
  `max_runtime_seconds` (registre §4.35.a).

**Limite** : un run `QUEUED` pendant que le daemon est **arrêté** reste en file,
puisque c'est le daemon qui dépile. Il repart au
`docker compose start dagster-daemon`.

La raison de saut du capteur **nomme le run qui bloque et son âge** : elle
distingue un run qui travaille d'un run gelé.

Avant de soumettre, l'asset attend que le service se déclare prêt (`GET /health`) : au démarrage de la stack, le chargement des modèles et l'initialisation du schéma NebulaGraph prennent plusieurs minutes, et le premier run échouerait pour une raison sans rapport avec le document.

## Combien de temps prend une ingestion

Chiffres mesurés au plus tard le 2 août 2026 (commit `c3df938`) sur 439 runs enregistrés dans la base Dagster, machine WSL2, extraction mono-worker, deux runs Dagster en parallèle, sur un corpus antérieur de 43 documents qui n'est plus celui en service (état en service : [livraison.md §4](livraison.md#4-vérifier)). Ils servent à dimensionner une campagne, pas à qualifier le matériel : sur une autre machine, seuls les ordres de grandeur tiennent.

| Unité ingérée | Le plus rapide | Habituel (médiane) | Le plus lent |
|---|---|---|---|
| Une note Markdown | 2,5 s | **2,6 s** | 35 s |
| Un chapitre HTML (≈ 40 000 caractères) | 4,5 s | **6 s** | 68 s |
| Un PDF de 280 pages | 62 s | **1 min 50** | 4 min 11 |

Mesures de bout en bout sur des ensembles complets :

| Ensemble | Volume | Temps constaté |
|---|---|---|
| Practical MLOps | 22 chapitres HTML | 1 min 54 |
| The Statistics and Calculus with Python Workshop | 14 chapitres HTML | 1 min 08 |
| Notes Obsidian | 6 fichiers Markdown | 19 s |
| **Corpus complet** | **43 documents** | **4 min 32** |

Ramené à l'unité, pour estimer une campagne :

| Coût unitaire | Valeur |
|---|---|
| Un chapitre HTML | ≈ 6 s |
| Un livre en chapitres HTML | ≈ 5 s × nombre de chapitres |
| 100 pages de PDF | ≈ 22 s au mieux, **40 s** en régime courant |
| Un livre PDF de 300 pages | **1 à 2 min** |
| 50 livres de 300 pages | **1 h 30 à 2 h** |

Les écarts entre le meilleur et le pire temps ne viennent pas des documents mais de la concurrence : un chapitre HTML monte à 68 s lorsqu'un PDF de 280 pages occupe le worker au même moment. Le débit global reste stable, c'est la latence individuelle qui varie.

## Commandes utiles
- Dans l'interface web (`http://localhost:3002`), l'onglet **Overview > Sensors** active ou désactive l'ingestion automatique. L'état enregistré en base prime alors sur le `default_status` du code ([livraison.md §6.1](livraison.md#6-à-savoir-avant-de-toucher)).
- **Vérifier l'état de l'orchestrateur** (en cas d'échec d'un job) :
  ```bash
  docker compose logs dagster-daemon --tail 50
  docker compose logs dagster-webserver --tail 50
  ```

## Problèmes rencontrés et solutions
- **Réingestion complète après un redémarrage de la machine** :
  - *Problème* : sans politique de redémarrage, les conteneurs ne repartaient pas après un arrêt de la machine (par exemple une fermeture de WSL), et les capteurs relançaient le traitement de tous les livres.
  - *Solution* : `restart: unless-stopped` sur les conteneurs de `docker-compose.yml` (`restart: always` pour `docling-service`). La base PostgreSQL de Dagster, persistée dans `Datas/database/postgres/`, conserve les curseurs des capteurs : un fichier déjà traité n'est pas réingéré.
