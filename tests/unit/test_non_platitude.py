"""Le graphe est-il plat ? La reponse depend du chapitre, pas de Docling.

Ce fichier distingue « Docling imbrique les titres » de « ce chapitre-la
imbrique ses titres » (registre, constat 3.2). Il couvre deux cas reels :

- un chapitre imbrique rend une distribution de rangs non degeneree ;
- le chapitre `Practical MLflow .../10. Unifying GenAI Systems with MLflow.html`
  rend 8 titres, tous de rang 0 : son graphe est reellement plat. Un test qui ne
  couvrirait que le premier cas lirait cette platitude comme un defaut.

La cause de cette platitude n'est pas l'absence de <h2> : sept des 57 chapitres
retenus n'en ont aucun (mesure du 27 septembre 2026), et les deux
`Preface.html` s'imbriquent quand meme (`{0: 9, 1: 4}` et `{0: 8, 1: 4}` sur le
graphe vivant). La propriete qui discrimine est qu'aucun titre n'est rendu sous
le niveau de tete (titres rendus = <h1>). Sur ce chapitre, la seule balise de
titre sous <h1> est la legende de sa figure, que Docling classe `caption` et non
titre.

Portee. Les tests rejouent le code de rang sur des arbres Docling captures
depuis les captures HTML reelles et versionnees, et non sur un arbre fabrique a
la main (ce que fait ``test_hierarchie_bout_en_bout.py``, qui pose lui-meme les
parents qu'il verifie). Un changement de comportement de Docling n'est pas vu
ici : c'est le role de ``scripts/capturer-larbre-docling.py --verifier``, et
docling est epingle a 2.117.0.

La conversion Docling ne peut pas entrer dans ``make test`` : mesure du 31 aout
2026, ``uv pip install docling==2.117.0`` ajoute 85 paquets (dont torch et
quinze paquets NVIDIA CUDA) et retrograde ``websockets``, alors que le pipeline
tourne sur processeur et que les dependances lourdes vivent dans l'image.

Le nettoyage, lui, est reellement execute : il ne demande que trafilatura et
readability, presents dans l'environnement. C'est ce qui relie la capture au
corpus versionne : si le HTML ou le nettoyage change, les empreintes divergent
et le test echoue en demandant une nouvelle capture.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml
from bs4 import BeautifulSoup

from src.docling_service import ranking
from src.docling_service.matter import is_front_back_matter
from src.pipeline.cleaning import clean_html
from src.pipeline.sources import CleaningOptions

RACINE = Path(__file__).resolve().parents[2]
FIXTURE = RACINE / "tests" / "fixtures" / "arbres_docling.yaml"

# Les deux cas attendus. Le test echoue si la capture ne contient pas
# exactement ces deux-la : une fixture amputee donnerait une boucle vide, qui
# passerait sans rien prouver. Les noms de fichiers du corpus contiennent des
# espaces et de la ponctuation, d'ou la comparaison exacte.
CAS_ATTENDUS = frozenset({"imbrique", "plat"})


class _Ref:
    """Reference Docling : porte un ``cref`` et sait le resoudre."""

    def __init__(self, cref: str, items: dict[str, Any]) -> None:
        self.cref = cref
        self._items = items

    def resolve(self, _document: Any) -> Any:
        return self._items.get(self.cref)


class _Item:
    """Item Docling reduit a ce que le code de rang lit : label et parent."""

    def __init__(self, label: str, parent_cref: str, items: dict[str, Any]) -> None:
        self.label = label
        self.parent = _Ref(parent_cref, items) if parent_cref else None


@pytest.fixture(scope="module")
def capture() -> dict[str, Any]:
    """L'arbre capture par ``scripts/capturer-larbre-docling.py``."""
    assert FIXTURE.is_file(), f"{FIXTURE} absent : rejouer le script de capture."
    contenu: dict[str, Any] = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    assert set(contenu) == CAS_ATTENDUS, (
        f"la capture porte {sorted(contenu)} au lieu de {sorted(CAS_ATTENDUS)} : "
        "un cas manquant rendrait ce fichier vert sans rien verifier"
    )
    return contenu


def _titres(cas: dict[str, Any]) -> list[str]:
    """References des items que Docling a etiquetes comme des titres."""
    return [r for r in cas["ordre"] if cas["items"][r]["label"] in ranking.HEADING_LABELS]


def _rangs(cas: dict[str, Any]) -> list[int]:
    """Rejoue le code de rang de production sur l'arbre capture.

    ``flat_rank`` rend ``None`` pour deux raisons tres differentes :

    - l'item n'est pas un titre : cas nominal, des milliers d'items ;
    - l'item est un titre et aucun signal n'a repondu : c'est un defaut.

    Filtrer les ``None`` sans les compter confondrait les deux. Par exemple, une
    capture sans noeuds de groupe coupe la chaine de parents de deux titres du
    chapitre imbrique, qui disparaitraient ici (39 titres au lieu de 41).
    L'assertion ci-dessous exige donc autant de rangs que de titres, pour tous
    les appelants.

    Args:
        cas: Un des deux cas de la capture.

    Returns:
        Le rang de chaque titre, dans l'ordre de la capture.
    """
    items: dict[str, Any] = {}
    for reference, info in cas["items"].items():
        items[reference] = _Item(info["label"], info["parent"], items)
    rangs = [ranking.flat_rank(items[reference], None) for reference in cas["ordre"]]
    classes = [rang for rang in rangs if rang is not None]
    titres = _titres(cas)
    assert len(classes) == len(titres), (
        f"{len(titres) - len(classes)} titre(s) sur {len(titres)} n'ont recu AUCUN "
        f"rang et seraient jetes en silence. Les references concernees : "
        f"{[r for r in titres if ranking.flat_rank(items[r], None) is None]}. "
        "Cause la plus probable : la capture ne porte pas les noeuds de groupe "
        "qui sont sur leur chaine de parents — rejouer "
        "scripts/capturer-larbre-docling.py, qui passe with_groups=True."
    )
    return classes


def _fichier(cas: dict[str, Any]) -> Path:
    return RACINE / cas["source"]


class TestLaCaptureDecritBienCeChapitreLa:
    """Un test qui choisit son cas doit prouver qu'il l'a atteint."""

    def test_the_captured_file_exists_under_its_exact_name(self, capture):
        for nom in CAS_ATTENDUS:
            chemin = _fichier(capture[nom])
            assert chemin.is_file(), f"{nom} : {chemin} introuvable"

    def test_the_raw_html_still_hashes_to_what_was_captured(self, capture):
        """Lien avec le corpus versionne : si le HTML change, la capture est perimee."""
        for nom in CAS_ATTENDUS:
            cas = capture[nom]
            brut = _fichier(cas).read_bytes()
            assert hashlib.sha256(brut).hexdigest() == cas["sha256_brut"], (
                f"{nom} : le HTML source a change depuis la capture"
            )

    def test_the_real_cleaning_still_produces_what_was_captured(self, capture):
        """Le nettoyage reel produit encore le HTML capture (empreinte comparee).

        C'est ce qui garantit que la capture decrit ce que le pipeline convertit
        reellement.
        """
        for nom in CAS_ATTENDUS:
            cas = capture[nom]
            brut = _fichier(cas).read_text(encoding="utf-8", errors="ignore")
            nettoye, _ = clean_html(brut, CleaningOptions())
            assert hashlib.sha256(nettoye.encode()).hexdigest() == cas["sha256_nettoye"], (
                f"{nom} : le nettoyage ne rend plus ce qui a ete converti ; "
                "rejouer scripts/capturer-larbre-docling.py"
            )

    def test_the_two_cases_are_different_chapters(self, capture):
        sources = {capture[nom]["source"] for nom in CAS_ATTENDUS}
        assert len(sources) == 2

    def test_no_parent_reference_points_outside_the_capture(self, capture):
        """La capture est un arbre complet : toute reference de parent y est resolue.

        ``ranking.docling_parent_rank`` remonte la chaine des parents. Une
        reference vers un noeud absent de la capture casse la remontee : la
        resolution rend ``None``, la boucle s'arrete, et le titre perd son rang.

        ``document.iterate_items()`` ne rend pas les noeuds de groupe : une
        capture faite ainsi en omet 262 (257 sur le chapitre imbrique, 5 sur le
        plat) et laisse 1 175 references de parent sans cible, dont celles de
        deux titres.

        L'assertion vaut pour toute famille de noeud oubliee, pas seulement les
        groupes, ce qui la rend utile a chaque montee de version de Docling.
        """
        for nom in sorted(CAS_ATTENDUS):
            items = capture[nom]["items"]
            perdues = {
                reference: info["parent"]
                for reference, info in items.items()
                if info["parent"] and info["parent"] != "#/body" and info["parent"] not in items
            }
            assert not perdues, (
                f"{nom} : {len(perdues)} reference(s) de parent pointent un noeud "
                f"absent de la capture (ex. {sorted(perdues.items())[:3]}). "
                "Rejouer scripts/capturer-larbre-docling.py."
            )

    def test_the_capture_carries_the_anonymous_containers(self, capture):
        """Les groupes sont dans la capture, et ils portent bien un label non-titre.

        Deux proprietes distinctes :

        - les noeuds de groupe sont presents. Sans eux, une erreur qui
          compterait les conteneurs anonymes comme des titres ne serait pas
          detectee par ces tests ;
        - aucun ne porte un label de titre. Si Docling etiquetait un groupe
          ``section_header``, la remontee le compterait, et tous les rangs sous
          ce groupe augmenteraient d'un.

        Mesure : 257 groupes sur le chapitre imbrique, 5 sur le plat, de labels
        ``inline``, ``list``, ``section`` et ``unspecified``.
        """
        for nom, attendus in (("imbrique", 257), ("plat", 5)):
            items = capture[nom]["items"]
            groupes = {r: i["label"] for r, i in items.items() if r.startswith("#/groups/")}
            assert len(groupes) == attendus, (
                f"{nom} : {len(groupes)} noeuds de groupe au lieu de {attendus}. "
                "La capture doit passer with_groups=True."
            )
            titres_deguises = {r: l for r, l in groupes.items() if l in ranking.HEADING_LABELS}
            assert not titres_deguises, (
                f"{nom} : des conteneurs anonymes portent un label de titre "
                f"({titres_deguises}) : la remontee les compterait comme des niveaux"
            )


class TestUnChapitreImbriqueNEstPasPlat:
    def test_the_rank_distribution_is_not_degenerate(self, capture):
        """Un graphe plat rendrait un seul rang. Celui-ci en rend quatre."""
        distribution = Counter(_rangs(capture["imbrique"]))
        assert len(distribution) > 1, f"distribution degeneree : {dict(distribution)}"
        assert dict(sorted(distribution.items())) == {0: 5, 1: 10, 2: 21, 3: 5}

    def test_most_headings_are_nested_under_another_heading(self, capture):
        rangs = _rangs(capture["imbrique"])
        imbriques = sum(1 for rang in rangs if rang > 0)
        assert imbriques == 36
        assert imbriques > len(rangs) - imbriques

    def test_the_root_headings_match_the_h1_tags_of_the_source(self, capture):
        """Invariant verifie sur les 22 chapitres retenus du corpus d'avant le 26 septembre 2026.

        Il relie la sortie du code de rang a une propriete du HTML d'entree que
        personne ne calcule : le nombre de titres de rang 0 egale le nombre de
        balises <h1>. Aucun des deux cotes ne peut deriver sans l'autre.
        """
        cas = capture["imbrique"]
        brut = _fichier(cas).read_text(encoding="utf-8", errors="ignore")
        h1 = len(BeautifulSoup(brut, "lxml").find_all("h1"))
        assert Counter(_rangs(cas))[0] == h1 == 5


class TestLeChapitrePlatEstReellementPlat:
    """Ce n'est pas un defaut : c'est ce que la capture contient."""

    def test_every_heading_sits_at_rank_zero(self, capture):
        rangs = _rangs(capture["plat"])
        assert len(rangs) == 8
        assert set(rangs) == {0}

    def test_nothing_survives_below_the_top_level(self, capture):
        """La propriete qui discrimine : aucun titre rendu sous le niveau de tete.

        Sans cette assertion, `test_every_heading_sits_at_rank_zero` se lirait
        comme la preuve que le code echoue a imbriquer ; en realite, il n'y a
        rien a imbriquer.

        L'absence de <h2> ne discrimine pas : sept des 57 chapitres retenus
        n'en ont aucun, et deux s'imbriquent (voir le test suivant). Ce qui
        discrimine : le nombre de titres rendus egale le nombre de <h1>. Le
        chapitre imbrique, lui, rend 41 titres pour 5 <h1>.
        """
        brut = _fichier(capture["plat"]).read_text(encoding="utf-8", errors="ignore")
        h1 = len(BeautifulSoup(brut, "lxml").find_all("h1"))
        assert len(_rangs(capture["plat"])) == h1 == 8
        # Le contraste avec le chapitre imbrique montre que « titres == h1 » est
        # une propriete du chapitre, et non de Docling.
        assert len(_rangs(capture["imbrique"])) == 41
        assert Counter(_rangs(capture["imbrique"]))[0] == 5

    def test_the_absence_of_h2_is_shared_by_seven_chapters_so_it_explains_nothing(self, capture):
        """Sept chapitres retenus n'ont aucun <h2> : ce critere n'explique rien.

        Mesure sur les 57 chapitres que le capteur retient reellement, et non
        sur une liste ecrite a la main. Le corpus ajoute le 26 septembre 2026
        (4ed61af) a fait passer ces comptes de 22 et 3 a 57 et 7.

        Le test ne verifie pas que les deux Prefaces s'imbriquent : il faudrait
        la conversion Docling, exclue de `make test` (voir la docstring du
        module). Cette mesure figure au registre §3.2, avec sa commande. Il
        suffit ici d'etablir que l'absence de <h2> est partagee.

        Cout mesure le 31 aout 2026 : +0,86 s pour lire les balises des
        22 chapitres d'alors.
        """
        racine = RACINE / "Datas" / "htms"
        retenus = [f for f in sorted(racine.rglob("*.html")) if not is_front_back_matter(f.stem)]
        assert len(retenus) == 57, (
            f"{len(retenus)} chapitres retenus au lieu de 57 : le corpus ou le "
            "capteur a change, et la mesure ci-dessous ne porte plus"
        )
        sans_h2 = [
            f
            for f in retenus
            if not BeautifulSoup(f.read_text(encoding="utf-8", errors="ignore"), "lxml").find_all(
                "h2"
            )
        ]
        assert len(sans_h2) == 7, (
            f"{len(sans_h2)} chapitres retenus sans <h2> au lieu de 7 : {[f.name for f in sans_h2]}"
        )
        plat = _fichier(capture["plat"])
        assert plat in sans_h2, (
            "le chapitre plat doit faire partie des sept : c'est ce qui rend le "
            "contre-exemple pertinent"
        )
        # Les six autres ne sont pas le chapitre plat : c'est tout l'argument.
        assert len([f for f in sans_h2 if f != plat]) == 6

    def test_the_only_heading_tag_below_h1_is_a_figure_caption(self, capture):
        """Cause mesuree de la platitude, sur ce chapitre seulement.

        Le chapitre porte une seule balise de titre sous <h1>, un <h6>, et c'est
        la legende de sa figure. Docling la classe `caption` et la rattache a
        l'image : elle ne devient donc jamais un titre. Les deux Prefaces, elles,
        portent quatre <h6> qui sont des libelles d'admonition — Tip, Note,
        Warning, Note — que Docling rend comme des titres.

        Ce test verifie ce qui est mesure dans la capture : 1 picture,
        1 caption, 8 items a label de titre pour 8 <h1>. Il n'en deduit pas que
        toute legende de figure en <h6> devient un `caption`.
        """
        items = capture["plat"]["items"]
        labels = Counter(info["label"] for info in items.values())
        assert labels["caption"] == 1
        assert labels["picture"] == 1
        assert len(_titres(capture["plat"])) == 8

        brut = _fichier(capture["plat"]).read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(brut, "lxml")
        # Une seule balise de titre sous <h1>, et c'est la legende de la figure.
        sous_h1 = [t for n in range(2, 7) for t in soup.find_all(f"h{n}")]
        assert len(sous_h1) == 1
        assert sous_h1[0].get_text(strip=True).startswith("Figure 10-1.")

    def test_the_two_chapters_do_not_behave_the_same(self, capture):
        """La comparaison est le resultat : « Docling imbrique » serait faux ici,
        « Docling n'imbrique pas » serait faux la-bas."""
        assert len(set(_rangs(capture["imbrique"]))) == 4
        assert len(set(_rangs(capture["plat"]))) == 1
