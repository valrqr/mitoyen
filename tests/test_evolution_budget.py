"""Évolution du budget d'un exercice à l'autre. python -m pytest tests/test_evolution_budget.py"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))

import bulletin  # noqa: E402
import evolution_budget as EV  # noqa: E402
import fiche_copro  # noqa: E402

MIMOSAS = fiche_copro.charger_fiche(RACINE / "config" / "mimosas.yaml")


def _b(**postes):
    return [{"libelle": k.replace("_", " "), "cle": "generales", "montant": str(v)} for k, v in postes.items()]


BUDGETS = {
    2025: _b(Ménage=4000, Assurance=3000, Électricité=1000, Ascenseur=2000),
    2026: _b(Ménage=4600, Assurance=3100, Électricité=1050, Ascenseur=2000),
    2027: _b(Ménage=5290, Assurance=3200, Électricité=1100, Jardin=600),
}


def test_cle_poste():
    assert EV.cle_poste("Ménage des parties communes.") == EV.cle_poste("menage des parties  communes")


def test_un_seul_budget():
    ev = EV.evolution(MIMOSAS, {2027: BUDGETS[2027]})
    assert not ev["disponible"] and "deux budgets" in ev["message"]
    assert EV.indicateur(MIMOSAS, {2027: BUDGETS[2027]})["etat"] == bulletin.INCONNU


def test_evolution_et_postes():
    ev = EV.evolution(MIMOSAS, BUDGETS)
    assert ev["exercices"] == [2025, 2026, 2027] and ev["annees"] == 2
    assert ev["totaux"][0]["total"] == Decimal("10000") and ev["totaux"][-1]["total"] == Decimal("10190")
    assert ev["variation"] == Decimal("1.9")
    menage = next(l for l in ev["postes"] if l["libelle"] == "Ménage")
    assert menage["variation"] == Decimal("32.3") and menage["taux_annuel"] == Decimal("15.0")
    assert [l["libelle"] for l in ev["a_regarder"]] == ["Ménage"]               # assurance +3 %/an : non
    assert [l["libelle"] for l in ev["nouveaux"]] == ["Jardin"]
    assert [l["libelle"] for l in ev["disparus"]] == ["Ascenseur"]
    assert ev["plus_forte_hausse"]["libelle"] == "Ménage"
    lots = EV.lots_principaux(MIMOSAS)
    assert ev["totaux"][0]["par_lot"] == (Decimal("10000") / lots).quantize(Decimal("0.01"))


def test_indicateur_du_bulletin():
    i = EV.indicateur(MIMOSAS, BUDGETS)
    assert i["theme"] == "Évolution du budget" and i["valeur"] == "+2 % en 2 ans"
    assert "ménage (+32 %)" in i["detail"] and i["etat"] == bulletin.ATTENTION       # un poste à regarder
    calme = {2025: _b(Ménage=4000), 2026: _b(Ménage=4080)}
    assert EV.indicateur(MIMOSAS, calme)["etat"] == bulletin.OK


def test_ligne_dans_le_bulletin():
    b = bulletin.bulletin(MIMOSAS, date(2027, 6, 1), budgets=BUDGETS)
    assert any(i["theme"] == "Évolution du budget" for i in b["indicateurs"])
    seul = bulletin.bulletin(MIMOSAS, date(2027, 6, 1))                            # fiche seule : un budget
    assert next(i for i in seul["indicateurs"] if i["theme"] == "Évolution du budget")["etat"] == bulletin.INCONNU
