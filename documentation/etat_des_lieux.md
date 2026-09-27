# État des lieux — ce que le pipeline garantit à l'agent

> Ce document se lit **sans lancer le projet**, y compris depuis
> [`rag-agent-chat`](https://github.com/floSa/rag-agent-chat). Il dit ce que le
> pipeline garantit à l'agent, comment lire le graphe, et ce qui n'est pas
> garanti. Les procédures et toutes les mesures datées sont dans
> [`livraison.md`](livraison.md) ; le contrat champ par champ est au §4 de
> [`llm_integration_plan.md`](llm_integration_plan.md).
> [`axes_amelioration.md`](axes_amelioration.md) (le registre),
> [`pilotage_du_chantier.md`](pilotage_du_chantier.md) et
> [`campagnes/`](campagnes/) sont des archives datées, non tenues à jour.

---

## 1. Ce que fait ce projet

Le pipeline lit des livres techniques et en produit trois stores : un **graphe**
NebulaGraph (la structure), un **index vectoriel** ChromaDB (la recherche par le
sens) et un **stockage d'objets** SeaweedFS (les images). Il ne répond à aucune
question : c'est le rôle de `rag-agent-chat`, un autre dépôt qui lit ces trois
stores.

`docling-service` est le seul service à écrire dans le graphe et dans l'index
vectoriel. Le stockage d'objets reçoit deux flux : les découpes d'images des PDF et les
images des Markdown, par `docling-service` (`src/docling_service/images.py`), et
les images inline
des captures HTML, téléversées par l'étape de nettoyage de Dagster
(`src/pipeline/media.py`).

Services, chemin d'un document et schéma : [`architecture.md`](architecture.md)
et le §1.1 de [`livraison.md`](livraison.md#11-les-services-et-le-chemin-dun-document).

## 2. L'état mesuré

Les comptes en service (documents, chunks, sommets, arêtes, objets, empreinte
des clés) sont au
[§4.2 de `livraison.md`](livraison.md#42-les-huit-comptes-et-lempreinte-des-clés),
mesurés le 25 septembre 2026 sur le corpus d'alors. Les résultats de la porte
qualité (tests, `mypy`, mutations) sont au
[§4.1](livraison.md#41-la-porte-qualité).

Le corpus versionné a changé le 26 septembre 2026 (commit `4ed61af`) et n'est
pas encore ingéré : les comptes du 25 septembre décrivent le corpus précédent,
et aucun chiffre n'est établi pour le nouveau.

## 3. Les images : ce que l'agent reçoit

Le contrat avec l'agent, côté images, tient en quatre points. Le détail est au
[§1.2 de `livraison.md`](livraison.md#12-le-contrat-avec-rag-agent-chat) et
dans [`stockage_objets.md`](stockage_objets.md).

1. **Le graphe publie deux propriétés** sur les sommets `Picture` et `Table` :
   `media_url`, l'adresse `http://<S3_ENDPOINT>/<bucket>/<clé>`, et
   `object_key`, la clé nue passée à `put_object`. L'adresse contient l'hôte et
   change si le serveur change ; la clé ne change pas. L'agent n'a pas à défaire
   l'adresse pour retrouver la clé.
2. **L'adresse est interne et authentifiée** : un `GET` anonyme rend 403.
   L'agent sert de proxy ; l'adresse ne va jamais à un navigateur.
3. **L'agent reçoit le jeu d'identifiants lecture seule**, `SEAWEEDFS_RO_*`,
   dont les actions sont `Read` et `List` (`docker-compose.yml`, fichier
   `-s3.config` écrit au démarrage de `seaweedfs`). Le jeu `SEAWEEDFS_RW_*` est
   celui du pipeline.
4. **Un refus de droit ne fait pas de bruit** : un 403 `AccessDenied` remonte
   chez l'agent en 404, et l'écran dit « image absente ». Un jeu d'identifiants
   mal posé se voit par appel direct, avec
   `scripts/campagne/essayer-la-passerelle-s3.py`
   ([§4.4 de `livraison.md`](livraison.md#44-la-passerelle-s3-et-ses-huit-critères)).

Le code ne nomme aucun serveur : le client S3 est construit à un seul site
(`src/docling_service/images.py`, `build_client`, bibliothèque `minio`), et
seule `S3_ENDPOINT` désigne le serveur. Cette variable n'a aucune valeur par
défaut ([§6.2 de `livraison.md`](livraison.md#62-ladresse-du-stockage-na-aucune-valeur-par-défaut)).

## 4. Les cinq exigences de l'agent

Ce sont les conditions sans lesquelles `rag-agent-chat` ne peut pas travailler.
Leur texte d'origine est le §0 du [registre](axes_amelioration.md).

| | L'exigence | Ce qui la tient |
|---|---|---|
| **1** | le modèle d'embedding est `paraphrase-multilingual-MiniLM-L12-v2`, identique des deux côtés | le service refuse de démarrer sur un autre modèle (`EmbeddingContractError`, `src/docling_service/embedding.py`) et refuse d'écrire dans une collection inscrite au nom d'un autre (`_inscrire_le_modele`, `src/docling_service/vectors.py`) |
| **2** | `element_id` déterministe, dérivé du contenu, 10 caractères hexadécimaux | contrôlé par `verify_contract` : format, et accord entre l'index et le graphe ([§4.5 de `livraison.md`](livraison.md#45-verify_contract--le-contrat-avec-lagent)) ; stable d'une ingestion à l'autre, vérifié par `comparer` contre l'instantané ([§4.3](livraison.md#43-comparer-contre-linstantané)) |
| **3** | `source_path` est l'identité d'un document, jamais `filename` seul | `document_identity` (`src/docling_service/elements.py`) ; `Index.html` et `Preface.html` existent dans plusieurs ouvrages et restent des documents distincts |
| **4** | `sequence` porte l'ordre de lecture, et il est monotone | contrôlé par `verify_contract` : arêtes sans `sequence`, inversions de page ([§4.5](livraison.md#45-verify_contract--le-contrat-avec-lagent)). Trois réserves de lecture au §5.3 |
| **5** | `POST /reindex` sur l'agent en fin de chaîne | `agent_reindex_sensor` (`src/pipeline/reindex_job.py`), une fois par rafale d'ingestion ([§1.2 de `livraison.md`](livraison.md#12-le-contrat-avec-rag-agent-chat)) |

**L'exigence 1 est la panne la plus coûteuse, et elle est silencieuse.** Les
deux modèles candidats rendent des vecteurs de 384 dimensions : ChromaDB les
accepte, aucune sonde ne réagit, et la recherche rend des passages plausibles et
faux. Vérifier la dimension ne protège de rien ; c'est le **nom** du modèle qui
discrimine (registre §6.14).

## 5. Ce que l'agent doit savoir pour lire le graphe

Trois choses, qui ne se déduisent pas du schéma.

### 5.1 `depth` mélange deux échelles, et `label` dit laquelle

Chaque élément porte `depth` : le nombre de liens qui le séparent de la racine de
son document. Il ne compte pas la même chose selon l'élément :

| L'élément | Ce que `depth` compte |
|---|---|
| un **titre** | les titres au-dessus de lui |
| **tout autre** élément | celui de son titre, **plus 1** |

Un paragraphe sous un titre de premier niveau vaut donc `1`, comme un sous-titre.
**La valeur seule est ambiguë : il faut lire `label` avec elle.** La profondeur
n'est pas plafonnée. La règle et la distribution de référence sont écrites à un
seul endroit : `ChunkMetadata.depth`, dans `src/pipeline/schemas.py`.

### 5.2 `depth` d'un titre n'est lisible que dans le graphe

Aucun titre n'est un chunk. La métadonnée `depth` existe dans l'index vectoriel,
mais elle ne décrit jamais un titre. Le niveau d'un titre se lit sur son sommet
du graphe, ou se compte sur la chaîne `PARENT_OF`.

### 5.3 `sequence` a trois pièges, à documenter côté agent

`sequence`, portée par les arêtes `PARENT_OF`, donne l'ordre de lecture. Elle est
monotone et complète. Mais :

1. **elle repart à 0 dans chaque document** : tout « avant / après » doit être
   borné au document (`test_sequence_restarts_at_zero_in_each_document`,
   `tests/unit/test_verify_contract.py`) ;
2. **elle n'est pas contiguë sous un parent**, par construction : l'écart entre
   deux frères vaut la taille du sous-arbre du frère précédent. Mesuré le
   2 septembre 2026 : 167 parents sur 763 ont des valeurs non contiguës, et
   l'écart s'explique entièrement ainsi. Ce n'est pas une perte ;
3. **l'écart entre deux enfants d'un même parent peut être grand** : 994 au plus
   à la même date, soit 993 valeurs intercalaires. Une « fenêtre d'éléments »
   implémentée comme « les enfants de P dont `sequence ∈ [s−k, s+k]` » rend
   silencieusement moins d'éléments que demandé.

Ces trois réserves décrivent comment l'agent lit : leur documentation relève de
`rag-agent-chat` (registre §6.16), et elle n'y est pas encore écrite
([§10 de `livraison.md`](livraison.md#10-non-vérifié)).

## 6. Ce que le pipeline ne garantit pas

| Ce que c'est | Détail | Gravité |
|---|---|---|
| 52 tables HTML comptées comme des visuels sans adresse | une table HTML est du texte, il n'y a rien à téléverser. `verify_contract` rend donc `rc=1` et ne peut pas rendre 0 sur ce corpus (registre §4.32.b) | cosmétique |
| une conversion qui échoue durablement retire un document sain de l'index | choix assumé : une absence est visible, un document périmé ne l'est pas. Écrire sous une clé provisoire puis basculer est inscrit au registre (§4.29.i) | assumé |
| l'émiettement des éléments HTML | Docling découpe certains `<li>` ou paragraphes mis en forme en plusieurs éléments, parfois d'un seul caractère ou vides ; chacun occupe une place de la fenêtre de l'agent. Compté, non corrigé ([§7 de `livraison.md`](livraison.md#7-défauts-connus)) | connu |
| « réextraire » ne restaure pas les images HTML | seule une exécution de l'étape de nettoyage (`src/pipeline/media.py`) re-téléverse les images inline d'une capture HTML | à savoir |
| le rappel mesuré est celui de la recherche dense seule | BM25, reconstruction par le graphe, reranker et abstention vivent dans l'agent. Trente questions ne suffisent pas à arbitrer un réglage ([§4.7 de `livraison.md`](livraison.md#47-le-jeu-de-questions-et-le-rappel-vectoriel)) | borne de mesure |
| la mesure translinguistique est coupée en deux | le corpus est entièrement anglais : « question française vers document anglais » se mesure, l'inverse non | borne de mesure |
| la qualité des réponses de l'agent | non mesurée ([§10 de `livraison.md`](livraison.md#10-non-vérifié)) | non établi |
| la documentation n'est presque pas tenue par des tests | trois tests lisent la documentation, le `Makefile` n'est lu par aucun ([§10 de `livraison.md`](livraison.md#10-non-vérifié), point 8) | angle mort, borné |

**Une réingestion non voulue n'a que deux déclencheurs** : le `mtime` d'un
fichier du corpus, ou un marqueur `reingerer:<étiquette>` posé à la main sur le
curseur d'un capteur. D'où la règle de ne jamais `toucher` le corpus
([§6.5 de `livraison.md`](livraison.md#65-ne-jamais-toucher-le-corpus)). Les
pièges d'exploitation sont au
[§6](livraison.md#6-à-savoir-avant-de-toucher) ; les défauts connus au
[§7](livraison.md#7-défauts-connus).

## 7. Ce qui reste à faire

Les prochaines étapes de ce dépôt sont au
[§8 de `livraison.md`](livraison.md#8-prochaines-étapes-dans-lordre). Deux
points relèvent de la frontière entre les dépôts :

- documenter côté agent les trois réserves de `sequence` (§5.3) ;
- écrire un second tour de questions, les questions pièges, par relecture
  humaine : c'est la strate où un faux piège s'écrit le plus facilement.

Le jeu de questions actuel est
[`campagnes/2026-09-02-jeu-de-questions.yaml`](campagnes/2026-09-02-jeu-de-questions.yaml) ;
ses 44 ancrages désignent des `element_id` réels, et toute nouvelle source le
rend obsolète ([§8.4 de `livraison.md`](livraison.md#84-les-sources-enfichables)).
