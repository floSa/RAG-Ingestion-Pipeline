# Configuration requise

Ce qu'il faut pour faire tourner la pile de `docker-compose.yml` (dix services)
et ingérer le corpus. Le minimum est ce qui passe à la mesure, plus une marge
écrite dans la dernière colonne.

| Ressource | Minimum | Recommandé | Ce que couvre le chiffre |
|---|---|---|---|
| processeur | 2 vCPU x86-64 | 4 vCPU | La conversion des 23 documents passe sur 1 vCPU, mais 3,2 fois plus lentement que sur 2 ; le second vCPU couvre aussi les neuf autres services, qui tournent pendant l'ingestion (environ 0,3 vCPU au repos, capteurs toutes les 30 s), et l'encodage des vecteurs, absent de la mesure. De 2 à 4 vCPU, le temps de conversion est divisé par deux. |
| mémoire | 12 Gio | 16 Gio | `docling-service` monte à 6,5 Gio en ingestion continue (modèles d'extraction et d'encodage chargés), les neuf autres services occupent 1,5 Gio : 8 Gio en tout. La marge d'environ 50 % couvre le système et les runs Dagster. Le recommandé laisse `docling-service` atteindre sa limite de 10 Gio (`docker-compose.yml`) sans priver les autres. |
| GPU | non requis | non requis | L'extraction et l'encodage tournent sur processeur : `docling-service` n'a aucune réservation de périphérique. |
| VRAM | aucune | aucune | Sans objet sans GPU. |
| disque | 30 Go libres | 50 Go libres | Images Docker (15 Go, dont 10,4 Go pour `docling-service`), cache des modèles (0,7 Go), stores et corpus (0,7 Go) : 16 Go. La marge couvre la construction des images par `docker compose up --build`, la réécriture des stores par une réingestion et la croissance du corpus. |
| système et logiciels | Linux x86-64, Docker Engine avec Docker Compose v2 | versions éprouvées : Docker Engine 29.5, Docker Compose 5.1 | Les images sont `linux/amd64`. Python 3.12 et [`uv`](https://docs.astral.sh/uv/) ne servent qu'à la porte qualité (`make all`), pas à l'exploitation. |
| réseau | ports hôte 3002 et 7001 libres ; accès Internet au premier démarrage | idem | `3002` : interface Dagster ; `7001` : Nebula Studio. Les autres services ne se joignent que par le réseau Docker `rag_network`. Le premier démarrage télécharge les images, les dépendances Python et les modèles (Docling, embeddings) ; ensuite, les modèles restent dans le volume `docling_models`. |

## Avec un GPU

Un GPU NVIDIA accélérerait l'extraction Docling et l'encodage : l'image embarque
PyTorch compilé pour CUDA 12.1. Il faut un pilote NVIDIA compatible CUDA 12.1,
le NVIDIA Container Toolkit, et superposer `docker-compose.gpu.yml`
([`services/docling.md`](services/docling.md)). Ce mode n'est pas mesuré : ni
gain, ni VRAM nécessaire ne sont établis.

## D'où viennent ces chiffres

- Processeur et mémoire de la conversion : conversion complète des 23 documents
  par le chemin de production, dans un conteneur bridé (`--cpus`, `--memory`),
  sans écriture dans aucun store (harnais `comparer`,
  [`livraison.md` §4.3](livraison.md#43-comparer-contre-linstantané)).
- Mémoire de `docling-service` en ingestion continue :
  [`guide_du_depot.md`](guide_du_depot.md) (« Débit et ressources »).
- Consommation au repos des autres services et tailles sur disque :
  `docker stats --no-stream`, `du -sh`, `docker images`.

Les relevés bruts sont archivés dans
[`campagnes/2026-09-27-configuration-minimale.md`](campagnes/2026-09-27-configuration-minimale.md).
