"""Annexes comptables : python -m pytest tests/test_annexes.py"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import annexes  # noqa: E402
import compta  # noqa: E402
from test_compta import FICHE, _sources  # noqa: E402

D = Decimal


def _calcul(tmp_path, avec_travaux=True):
    src, ops, st = _sources(tmp_path)
    if avec_travaux:
        o = compta.voter_operation(tmp_path, "m", "Réfection toiture", "generales", "10000", date(2026, 5, 20))
        compta.ajouter_facture(tmp_path, "m", "Couvreur Exemple", date(2027, 3, 1), "4000", "671", "Acompte",
                               operation=o["id"])
        src["factures"] = compta.charger(tmp_path, "m")["factures"]
        src["ajustements"] = [{"id": "AJ1", "coproprietaire": "CP01", "date": "2027-02-01", "libelle": "Appel toiture",
                               "montant": "450", "nature": "travaux", "operation": o["id"]}]
    compta.enregistrer_budget(tmp_path, "m", 2029, FICHE["budget_previsionnel"]["postes"])
    E = compta.journal(FICHE, src)
    st = compta.charger(tmp_path, "m")
    return annexes.annexes(FICHE, E, st, 2027, ops, compta.budgets(FICHE, tmp_path, "m"), date(2028, 3, 1))


def _ligne(a, libelle):
    return next(l for l in a["lignes"] if l["libelle"].startswith(libelle))


def test_annexe_1_equilibree_apres_repartition(tmp_path):
    r = _calcul(tmp_path)
    a1 = r["annexes"][0]
    c = {x["controle"]: x for x in r["controles"]}
    assert c["Annexe 1 : trésorerie + créances = fonds + dettes"]["ok"]
    assert _ligne(a1, "Total général : trésorerie")["valeurs"] == _ligne(a1, "Total général : fonds")["valeurs"]
    assert _ligne(a1, "Banques")["valeurs"] == [D("8200"), D("7483")]
    # le solde des travaux reste en attente (compte 12) : 450 appelés − 4 000 réalisés
    assert _ligne(a1, "Solde en attente")["valeurs"][1] == D("-3550")
    # répartition : chacun supporte sa part des 612 € de charges, les provisions viennent en déduction
    deb = dict(a1["listes"]["debiteurs"])
    cred = dict(a1["listes"]["crediteurs"])
    total = sum(deb.values(), D(0)) - sum(cred.values(), D(0))
    assert total == _ligne(a1, "Copropriétaires : sommes")["valeurs"][1] - _ligne(a1, "Copropriétaires : excédents")["valeurs"][1]


def test_annexes_2_3_budgets_et_realise(tmp_path):
    r = _calcul(tmp_path)
    a2, a3 = r["annexes"][1], r["annexes"][2]
    tot = _ligne(a2, "Total des charges courantes")["valeurs"]
    assert tot[0] is None and tot[1] == D("19800") and tot[2] == D("612") and tot[3] is None and tot[4] == D("19800")
    assert _ligne(a2, "Solde (excédent")["valeurs"][2] == D("580") - D("612")
    assert _ligne(a3, "Total des charges nettes")["valeurs"][2] == D("612")
    assert annexes.NOTE_N1 in r["notes"]          # N-1 non tenu dans Mitoyen : dit, pas inventé


def test_annexes_4_5_travaux(tmp_path):
    r = _calcul(tmp_path)
    a4, a5 = r["annexes"][3], r["annexes"][4]
    assert _ligne(a4, "Réfection toiture")["valeurs"] == [D("10000"), D("4000"), D("450"), D("-3550")]
    a, b, c, d, e, f = _ligne(a5, "Réfection toiture")["valeurs"]
    assert (a, b, c, d, e) == (D("10000"), D("0"), D("4000"), D("450"), D("-3550"))


def test_sans_travaux_neant_et_pdf(tmp_path):
    r = _calcul(tmp_path, avec_travaux=False)
    assert r["annexes"][3]["vide"] and r["annexes"][4]["vide"]
    assert not r["pret"]                          # compte d'attente non soldé : le PDF porte « PROJET »
    p = annexes.generer_pdf(FICHE, r, tmp_path / "annexes.pdf")
    assert p.stat().st_size > 3000


def test_periode_decalee():
    fiche = {"gouvernance": {"exercice": {"debut": "07-01", "fin": "06-30"}}}
    assert annexes.periode(fiche, 2027) == ("2026-07-01", "2027-06-30")
