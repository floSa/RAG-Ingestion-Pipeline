# Stockage objet (passerelle S3)

## Rôle

Stockage S3 des médias extraits des documents : SeaweedFS, par sa passerelle S3.
Fonctionnement (client, clés d'objet, `media_url` et `object_key`, choix) :
[`stockage_objets.md`](../stockage_objets.md).

## Conteneur

- Service `seaweedfs`, image `chrislusf/seaweedfs:3.80`, `hostname: seaweedfs`.
  Aucun `container_name` : nom attribué par Compose.
- Port interne 8333 (passerelle S3, `expose`). Ni port publié, ni console : le
  service n'est joignable que depuis `rag_network`.
- Commande : `weed server -dir=/data -ip=seaweedfs -master.volumeSizeLimitMB=1024 -volume.max=0 -filer -s3 -s3.port=8333 -s3.config=/run/seaweedfs/s3.json`.
- Politique de redémarrage : `unless-stopped`.

## Volumes

- `./Datas/database/seaweedfs` monté sur `/data`
- tmpfs `/run/seaweedfs` (mode `0700`) : reçoit le fichier d'identités

Le fichier d'identités (`-s3.config`) est écrit au démarrage dans ce tmpfs, par
un heredoc de l'`entrypoint`, à partir des variables du `.env`. Rien n'est monté
depuis le dépôt, aucune clé n'y est écrite, et aucune ne passe en argument de
commande.

## Variables consommées

Rôle et génération : [livraison.md §2.2](../livraison.md#22-le-env--toutes-les-variables).

Côté serveur (`seaweedfs`), les identités :

| Variables | Identité | Actions |
|---|---|---|
| `SEAWEEDFS_RW_ACCESS_KEY`, `SEAWEEDFS_RW_SECRET_KEY` | `pipeline` | `Admin`, `Read`, `Write`, `List`, `Tagging` |
| `SEAWEEDFS_RO_ACCESS_KEY`, `SEAWEEDFS_RO_SECRET_KEY` | `agent` | `Read`, `List` |

Côté clients (`docling-service`, `dagster-webserver`, `dagster-daemon`) :
`S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`. Les deux dernières
ne sont pas dans le `.env` : `docker-compose.yml` les dérive du jeu RW
([livraison.md §6.2](../livraison.md#62-ladresse-du-stockage-na-aucune-valeur-par-défaut)).
Le jeu RO est celui de `rag-agent-chat`, hors de cette pile.

## Bucket

`documents`, créé au démarrage de `docling-service` s'il n'existe pas. Forme des
clés : [`stockage_objets.md`](../stockage_objets.md#qui-écrit-quoi).

## Dépendances

Aucune. Aucun service ne le déclare en `depends_on` : `docling-service` attend
le stockage au démarrage (`images.ensure_bucket`, 15 tentatives à 5 s).

## Sonde de santé

`wget -q -O /dev/null http://seaweedfs:8333/healthz`, toutes les 15 s (délai
10 s, 10 essais, `start_period` 60 s). `docker compose ps` doit afficher
`healthy`. Pourquoi `seaweedfs` et non `localhost`, `/healthz` et non `/` :
[livraison.md §2.4](../livraison.md#24-la-santé-des-services).

## Diagnostic

```bash
docker compose logs seaweedfs --tail 50
docker compose run --rm --no-deps -T -e PYTHONPATH=/app -w /app \
  docling-service python -m src.verify_data
```

`verify_data` affiche l'adresse qu'il interroge (`S3_ENDPOINT`) à côté du compte
d'objets du bucket. Comptes attendus :
[livraison.md §4.2](../livraison.md#42-les-huit-comptes-et-lempreinte-des-clés).

Un refus S3 (403) arrive chez l'agent en 404 silencieux : les droits des deux
jeux ne se contrôlent pas à l'écran, mais par appel direct avec
`scripts/campagne/essayer-la-passerelle-s3.py`
([livraison.md §4.4](../livraison.md#44-la-passerelle-s3-et-ses-huit-critères)).
