"""Comptabilité en partie double : python -m pytest tests/test_compta.py"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))

import compta  # noqa: E402
import fiche_copro  # noqa: E402

FICHE = fiche_copro.charger_fiche(RACINE / "config" / "mimosas.yaml")
D = Decimal


def _sources(tmp_path):
    compta.definir_ouverture(tmp_path, "m", date(2027, 1, 1), banque="8200", fonds_travaux="6800",
                             soldes_coproprietaires={"CP08": "120", "CP02": "-50"}, fournisseurs={"Propreté Exemple": "500"})
    f = compta.ajouter_facture(tmp_path, "m", "Ascenseurs Exemple", date(2027, 1, 10), "600", "614", "Maintenance T1")
    compta.affecter_depense(tmp_path, "m", "OP3", facture=f["id"])
    compta.affecter_depense(tmp_path, "m", "OP4", compte="66", fournisseur="Banque")
    st = compta.charger(tmp_path, "m")
    dues = [{"id": "2027-T1-CP01", "coproprietaire": "CP01", "type": "appel", "libelle": "Appel T1", "date": "2027-01-01",
             "detail": [{"rubrique": "budget:generales", "montant": D("300")}, {"rubrique": "fonds_travaux", "montant": D("20")}]},
            {"id": "2027-T1-CP08", "coproprietaire": "CP08", "type": "appel", "libelle": "Appel T1", "date": "2027-01-01",
             "detail": [{"rubrique": "budget:generales", "montant": D("280")}]}]
    ops = [{"id": "OP1", "date": "2027-01-05", "libelle": "VIR MIMOSAS-2027-T1-CP01", "montant": "320.00"},
           {"id": "OP2", "date": "2027-01-06", "libelle": "VIR INCONNU", "montant": "75.00"},
           {"id": "OP3", "date": "2027-01-20", "libelle": "PRLV ASCENSEURS", "montant": "-600.00"},
           {"id": "OP4", "date": "2027-01-31", "libelle": "FRAIS TENUE COMPTE", "montant": "-12.00"},
           {"id": "OP5", "date": "2027-02-02", "libelle": "VIR PROPRETE", "montant": "-500.00"}]
    rap = [{"operation": "OP1", "statut": "automatique", "parts": [{"coproprietaire": "CP01", "montant": D("320")}]},
           {"operation": "OP2", "statut": "non_rapproche", "parts": []}]
    return {"ouverture": st["ouverture"], "dues": dues, "ajustements": [], "operations": ops,
            "rapprochement": rap, "factures": st["factures"], "depenses": st["depenses"]}, ops, st


def test_journal_equilibre_et_banque_juste(tmp_path):
    src, ops, st = _sources(tmp_path)
    E = compta.journal(FICHE, src)
    b = compta.balance(E)
    assert sum(v["debit"] for v in b.values()) == sum(v["credit"] for v in b.values())
    assert b["512"]["solde"] == D("8200") + D("320") + D("75") - D("600") - D("12") - D("500")
    assert b["701"]["solde"] == D("-580") and b["105"]["solde"] == D("-6820")
    assert b["4501.CP01"]["solde"] == D("-20") and b["4505.CP01"]["solde"] == D("20")   # payé sur un seul compte
    assert b["4501.CP08"]["solde"] == D("400")              # 120 repris + 280 appelés
    assert b["614"]["solde"] == D("600") and b["401.ASCENSEURS-EXEMPLE"]["solde"] == 0
    assert b["66"]["solde"] == D("12")


def test_rien_ne_disparait_dans_un_ajustement(tmp_path):
    src, ops, st = _sources(tmp_path)
    E = compta.journal(FICHE, src)
    c = {x["controle"]: x for x in compta.controles(E, ops, st["ouverture"])}
    assert c["Total des débits = total des crédits"]["ok"]
    assert c["Compte 512 = solde du relevé"]["ok"]
    att = c["Compte d'attente soldé"]
    assert not att["ok"] and "2 opération(s)" in att["detail"]     # le virement inconnu et le paiement non affecté
    # l'écart d'ouverture (8200 + 120 - 50 - 500 - 6800 = 970) est rendu visible en 471
    ouv = next(e for e in E if e["piece"] == "AN")
    assert {"compte": "471", "debit": D("0"), "credit": D("970")} in ouv["lignes"]


def test_grand_livre_et_comptes(tmp_path):
    src, _, _ = _sources(tmp_path)
    E = compta.journal(FICHE, src)
    gl = compta.grand_livre(E, "4501")
    assert {l["compte"] for l in gl} >= {"4501.CP01", "4501.CP08", "4501.CP02"}
    assert compta.compte_charge({"libelle": "Électricité parties communes"}) == "602"
    assert compta.compte_charge({"libelle": "Ménage parties communes"}) == "611"
    assert compta.compte_charge({"libelle": "Truc", "compte": "678"}) == "678"
    assert compta.libelle_compte("4501.CP03").startswith("Copropriétaire, budget")


def test_garde_fous(tmp_path):
    import pytest
    with pytest.raises(compta.ComptaInvalide):
        compta.ajouter_facture(tmp_path, "m", "X", date(2027, 1, 1), "10", "512", "pas une charge")
    with pytest.raises(compta.ComptaInvalide):
        compta.ajouter_facture(tmp_path, "m", "X", date(2027, 1, 1), "-10", "615", "négatif")
    with pytest.raises(compta.ComptaInvalide):
        compta._ecriture("2027-01-01", "x", "P", [("512", D("1"), D("0"))], "t")


def test_etat_sur_donnees_vides(tmp_path):
    e = compta.etat(FICHE, tmp_path / "out", tmp_path / "data", "mimosas", date(2027, 3, 1))
    assert e["journal"] == [] and e["balance"] == {}
    assert any(c["controle"] == "Soldes d'ouverture saisis" and not c["ok"] for c in e["controles"])
