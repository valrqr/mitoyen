"""Le mode « Je pars en vacances »."""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import absence  # noqa: E402

JOUR = date(2027, 3, 1)


def test_enregistrer_et_controles(tmp_path):
    base = {"du": "2027-03-10", "au": "2027-03-24"}
    with pytest.raises(absence.AbsenceInvalide, match="précède"):
        absence.enregistrer(tmp_path, "c", {"du": "2027-03-10", "au": "2027-03-01"}, JOUR)
    with pytest.raises(absence.AbsenceInvalide, match="trois mois"):
        absence.enregistrer(tmp_path, "c", {"du": "2027-03-10", "au": "2027-07-01"}, JOUR)
    with pytest.raises(absence.AbsenceInvalide, match="nom du relais"):
        absence.enregistrer(tmp_path, "c", {**base, "relais_telephone": "06 00 00 00 00"}, JOUR)
    with pytest.raises(absence.AbsenceInvalide, match="numéro du relais"):
        absence.enregistrer(tmp_path, "c", {**base, "relais_nom": "Inès", "telephone_public": "1"}, JOUR)
    with pytest.raises(absence.AbsenceInvalide, match="illisible"):
        absence.enregistrer(tmp_path, "c", {**base, "relais_nom": "Inès", "relais_telephone": "appelez-moi"}, JOUR)
    a = absence.enregistrer(tmp_path, "c", {**base, "relais_nom": " Inès   Laurent ", "relais_telephone": "01 99 00 00 01",
                                            "telephone_public": "1", "message": "Badges remis au retour."}, JOUR)
    assert a["relais"]["nom"] == "Inès Laurent" and a["telephone_public"] and len(a["jeton_relais"]) >= 20
    # Une modification garde le lien du relais
    b = absence.enregistrer(tmp_path, "c", {**base, "au": "2027-03-20", "relais_nom": "Inès Laurent"}, JOUR)
    assert b["jeton_relais"] == a["jeton_relais"] and not b["telephone_public"]
    absence.annuler(tmp_path, "c")
    assert absence.charger(tmp_path, "c") is None


def test_avis_et_lien_du_relais(tmp_path):
    a = absence.enregistrer(tmp_path, "c", {"du": "2027-03-10", "au": "2027-03-24", "relais_nom": "Inès Laurent",
                                            "relais_telephone": "01 99 00 00 01", "telephone_public": "1"}, JOUR)
    assert absence.avis_voisins(a, date(2027, 3, 9)) is None
    v = absence.avis_voisins(a, date(2027, 3, 12))
    assert "jusqu'au 24 mars inclus" in v["texte"] and v["contact"]["telephone"] == "01 99 00 00 01"
    assert absence.avis_voisins(a, date(2027, 3, 25)) is None
    j = a["jeton_relais"]
    assert not absence.jeton_relais_valide(a, j, date(2027, 3, 8))
    assert absence.jeton_relais_valide(a, j, date(2027, 3, 9))          # la veille, pour découvrir la page
    assert absence.jeton_relais_valide(a, j, date(2027, 3, 24))
    assert not absence.jeton_relais_valide(a, j, date(2027, 3, 25))
    assert not absence.jeton_relais_valide(a, "x" * 22, date(2027, 3, 12))
    # Numéro non autorisé : les voisins sont prévenus, sans numéro
    a = absence.enregistrer(tmp_path, "c", {"du": "2027-03-10", "au": "2027-03-24", "relais_nom": "Inès Laurent",
                                            "relais_telephone": "01 99 00 00 01"}, JOUR)
    assert absence.avis_voisins(a, date(2027, 3, 12))["contact"] is None


def test_a_preparer():
    a = {"du": "2027-03-10", "au": "2027-03-24"}
    appels = [{"trimestre": 1, "date": date(2027, 1, 1), "statut": "valide"},
              {"trimestre": 2, "date": date(2027, 4, 1), "statut": None},     # avis à envoyer le 11/03 : pendant
              {"trimestre": 3, "date": date(2027, 7, 1), "statut": None}]     # trop loin
    ag = {"id": "AG1", "date": "2027-04-20", "limite_notification": "2027-03-29"}
    alertes = [{"type": "contrat", "titre": "Entretien du jardin", "message": "Échéance", "date": "2027-03-31"},
               {"type": "diagnostic", "titre": "DTG", "message": "…", "date": "2027-06-01"},
               {"type": "impayes", "titre": "Relances", "message": "…", "date": "2027-03-01"}]
    t = absence.a_preparer(a, JOUR, appels, 21, ag, alertes)
    assert [x["titre"] for x in t] == ["Appel de fonds du 2e trimestre", "Convocations de l'AG", "Entretien du jardin"]
    assert t[0]["quand"] == date(2027, 3, 11) and t[1]["lien_type"] == "ag"
    # L'AG elle-même pendant l'absence
    t = absence.a_preparer(a, JOUR, [], 21, {"id": "AG1", "date": "2027-03-15", "limite_notification": "2027-02-20"}, [])
    assert t[0]["titre"].startswith("L'assemblée générale a lieu pendant")


def test_resolution():
    r = absence.resolution_delegation("Inès Laurent", 1500)
    assert "Inès Laurent" in r and "1 500 € TTC" in r and "article 25" in r and "fin avec le mandat" in r
    assert "[montant] €" in absence.resolution_delegation("", 0)
