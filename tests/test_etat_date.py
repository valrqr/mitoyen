"""État daté, certificat de l'article 20, suivi de la vente : python -m pytest tests/test_etat_date.py"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import compta  # noqa: E402
import etat_date as ED  # noqa: E402
from test_compta import FICHE, _sources  # noqa: E402

D = Decimal


def _journal(tmp_path, travaux=False):
    src, ops, st = _sources(tmp_path)
    if travaux:
        o = compta.voter_operation(tmp_path, "m", "Toiture", "generales", "10000", date(2026, 5, 20))
        src["ajustements"] = [{"id": "AJ1", "coproprietaire": "CP08", "date": "2027-02-01", "libelle": "Appel toiture",
                               "montant": "450", "nature": "travaux", "operation": o["id"]}]
    E = compta.journal(FICHE, src)
    return E, compta.charger(tmp_path, "m"), compta.budgets(FICHE, tmp_path, "m")


def _l(partie, ref, debut=""):
    return next(l for l in partie if l["ref"] == ref and l["libelle"].startswith(debut))


def test_vendeur_endette_rubriques_de_l_article_5(tmp_path):
    E, st, bud = _journal(tmp_path, travaux=True)
    ed = ED.etat_date(FICHE, E, st, bud, [9], date(2027, 2, 15))
    p1 = ed["partie_1"]
    assert _l(p1, "c")["total"] == D("120")          # repris à l'ouverture : exercice antérieur
    assert _l(p1, "a")["total"] == D("280")
    assert _l(p1, "b")["total"] == D("450")
    assert [l["ref"] for l in p1][:7] == list("abcdefg") and not _l(p1, "d")["suivi"]
    assert ed["total_1"] == ed["du_compte"] == D("850") and not ed["libre"]
    # Les trois appels de l'année à venir incombent à l'acquéreur, comme sa part des travaux restant à appeler
    assert ed["appels_a_echoir"] == ["2027-04-01", "2027-07-01", "2027-10-01"]
    assert _l(ed["partie_3"], "c")["par_lot"][9] == D("429.75")      # 9 550 € × 450 / 10 000
    assert _l(ed["partie_3"], "b")["total"] > 0
    # Le décompte classe les créances comme l'exige une opposition (art. 5-1)
    dec = ED.decompte_opposition(FICHE, ed)
    assert [g["ref"] for g in dec] == ["1°", "2°", "3°", "4°"] and dec[0]["total"] == D("850")


def test_cedant_qui_garde_un_lot_dette_ventilee(tmp_path):
    E, st, bud = _journal(tmp_path)
    ed = ED.etat_date(FICHE, E, st, bud, [9], date(2027, 2, 15))
    assert ed["autres_lots_du_vendeur"] == []
    # CP14 possède 4 lots : la vente de deux d'entre eux ne porte que leur part
    ed = ED.etat_date(FICHE, E, st, bud, [15, 24], date(2027, 2, 15))
    assert ed["autres_lots_du_vendeur"] == [16, 20] and ed["libre"]


def test_trop_verse_apure_les_autres_comptes(tmp_path):
    E, st, bud = _journal(tmp_path)
    ed = ED.etat_date(FICHE, E, st, bud, [1], date(2027, 2, 15))     # 20 € payés sur le budget, dus au fonds
    assert ed["total_1"] == 0 and ed["libre"]
    ed = ED.etat_date(FICHE, E, st, bud, [2, 21], date(2027, 2, 15))  # avance de 50 € reprise à l'ouverture
    assert ed["libre"] and ed["solde_crediteur"] == D("50")


def test_sans_comptes_pas_d_etat_date(tmp_path):
    E, st, bud = _journal(tmp_path)
    with pytest.raises(ED.EtatDateInvalide, match="soldes d'ouverture"):
        ED.etat_date(FICHE, E, st, bud, [1], date(2026, 6, 1))
    with pytest.raises(ED.EtatDateInvalide):
        ED.etat_date(FICHE, E, st, bud, [1, 9], date(2027, 2, 15))           # deux vendeurs


def test_pdf_certificat_ou_decompte(tmp_path):
    E, st, bud = _journal(tmp_path)
    import pypdf
    for lots, attendu in (([1], "libre de toute obligation"), ([9], "15 jours")):
        ed = ED.etat_date(FICHE, E, st, bud, lots, date(2027, 2, 15))
        ED.generer_etat_date(FICHE, ed, tmp_path / "ed.pdf")
        c = ED.generer_certificat(FICHE, ed, tmp_path / "c.pdf")
        texte = " ".join(p.extract_text() for p in pypdf.PdfReader(c).pages).replace("\n", " ")
        assert attendu in texte


def test_comptes_vendeur_pour_le_pre_etat_date(tmp_path):
    E, st, bud = _journal(tmp_path)
    cv = ED.comptes_vendeur(FICHE, E, st, bud, [9], date(2028, 3, 1))
    assert [c["exercice"] for c in cv["charges_payees"]] == [2027]          # 2026 n'est pas tenu dans Mitoyen
    assert cv["impayes_vendeur"] == "400.00" and cv["etat_global"]["exercice"] == 2027


def test_suivi_delai_opposition(tmp_path):
    m = ED.enregistrer_vente(tmp_path, "m", FICHE, [9], date(2027, 3, 1), "M. Exemple")
    s = ED.suivi(m, date(2027, 3, 5))
    assert s["limite_opposition"] is None and not s["etapes"][0]["fait"]
    m = ED.avis_de_mutation(tmp_path, "m", m["id"], date(2027, 3, 10))
    s = ED.suivi(m, date(2027, 3, 20))
    assert s["limite_opposition"] == "2027-03-25" and s["jours_restants"] == 5
    assert "pour 400,00" in ED.suivi(m, date(2027, 3, 20), Decimal("400"))["etapes"][1]["texte"]
    assert ED.suivi(m, date(2027, 3, 20), Decimal("0"))["etapes"][1]["fait"]
    m = ED.marquer_fiche_a_jour(tmp_path, "m", m["id"])
    assert ED.suivi(m, date(2027, 4, 1))["etapes"][2]["fait"]
