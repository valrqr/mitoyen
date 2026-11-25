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


def test_vendeur_endette_dette_ancienne_isolee(tmp_path):
    E, st, bud = _journal(tmp_path, travaux=True)
    ed = ED.etat_date(FICHE, E, st, bud, [9], date(2027, 2, 15))
    p1 = dict(ed["partie_1"])
    assert p1["Charges impayées des exercices antérieurs"] == D("120")        # repris à l'ouverture
    assert p1["Provisions exigibles du budget prévisionnel, exercice en cours"] == D("280")
    assert p1["Provisions exigibles hors budget (travaux, opérations exceptionnelles)"] == D("450")
    assert ed["total_1"] == D("850") and not ed["libre"]
    # Les trois appels de l'année encore à venir incombent à l'acquéreur, et la part des travaux restant à appeler
    assert {a["date"] for a in ed["appels_a_echoir"]} == {"2027-04-01", "2027-07-01", "2027-10-01"}
    assert ed["travaux_a_appeler"][0]["reste"] == D("9550")


def test_trop_verse_apure_les_autres_comptes(tmp_path):
    E, st, bud = _journal(tmp_path)
    ed = ED.etat_date(FICHE, E, st, bud, [1], date(2027, 2, 15))     # 20 € payés sur le budget, dus au fonds
    assert ed["total_1"] == 0 and ed["total_2"] == 0 and ed["libre"]
    ed = ED.etat_date(FICHE, E, st, bud, [2, 21], date(2027, 2, 15))  # avance de 50 € reprise à l'ouverture
    assert ed["libre"] and ed["total_2"] == D("50")


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
