"""Modifier la fiche depuis l'interface. python -m pytest tests/test_fiche_edition.py"""
import sys
from datetime import date
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))

import fiche_copro  # noqa: E402
import fiche_edition as FE  # noqa: E402
import rappel_ag  # noqa: E402

BASE = fiche_copro.charger_fiche(RACINE / "config" / "mimosas.yaml")
LE = date(2027, 3, 12)


def test_modifier_coordonnees_et_journal(tmp_path):
    f = FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP01", {"email": "Alice.Nouvelle@Exemple.fr",
                                                                 "telephone": "06 00 00 00 00"}, LE, "nouvelle adresse")
    c = next(x for x in f["coproprietaires"] if x["id"] == "CP01")
    assert c["email"] == "alice.nouvelle@exemple.fr" and c["telephone"] == "06 00 00 00 00"
    assert FE.fiche_a_jour(BASE, tmp_path, "m") == f                     # rejoué à la lecture
    j = FE.journal(tmp_path, "m")
    assert len(j) == 1 and j[0]["motif"] == "nouvelle adresse" and set(j[0]["champs"]) == {"email", "telephone"}
    assert BASE["coproprietaires"][0]["email"] == "alice.martin@exemple.fr"   # la base n'est pas touchée
    with pytest.raises(FE.FicheInvalide, match="Aucune modification"):
        FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP01", {"telephone": "06 00 00 00 00"}, LE)


def test_controles(tmp_path):
    with pytest.raises(FE.FicheInvalide, match="invalide"):
        FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP01", {"email": "pas-une-adresse"}, LE)
    with pytest.raises(FE.FicheInvalide, match="accord écrit"):
        FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP01", {"aidant_nom": "Martin Paul"}, LE)
    with pytest.raises(FE.FicheInvalide, match="incohérente"):          # mail demandé sans adresse
        FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP01", {"email": ""}, LE)
    assert FE.journal(tmp_path, "m") == []                                # rien d'enregistré


def test_aidant_et_courrier(tmp_path):
    f = FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP02", {
        "envoi": "courrier", "demande_papier_le": "2027-03-01", "demande_papier_moyen": "main_propre",
        "grands_caracteres": True, "aidant_nom": "Bernard Zoé", "aidant_email": "zoe@exemple.fr",
        "aidant_consentement_le": "2027-03-01"}, LE)
    c = next(x for x in f["coproprietaires"] if x["id"] == "CP02")
    assert c["envoi"] == "courrier" and c["grands_caracteres"] is True
    assert c["demande_papier"] == {"recue_le": date(2027, 3, 1), "moyen": "main_propre"}
    assert c["aidant"]["consentement_le"] == date(2027, 3, 1)
    assert fiche_copro.valider(f).ok
    f = FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP02", {"aidant_nom": ""}, LE)   # retrait de l'aidant
    assert "aidant" not in next(x for x in f["coproprietaires"] if x["id"] == "CP02")


def test_vente_a_une_nouvelle_personne(tmp_path):
    lots_cp01 = [l["numero"] for l in BASE["lots"] if l["proprietaire"] == "CP01"]
    cid, f = FE.changer_proprietaire(tmp_path, "m", BASE, lots_cp01, LE,
                                     nouveau_saisie={"nom": "Nouveau Jean", "email": "jean@exemple.fr"})
    assert cid == "CP15"
    assert all(l["proprietaire"] == "CP15" for l in f["lots"] if l["numero"] in lots_cp01)
    vendeur = next(x for x in f["coproprietaires"] if x["id"] == "CP01")
    assert vendeur["ancien"] is True and vendeur["ancien_depuis"] == LE         # gardé pour ses comptes
    assert fiche_copro.valider(f).ok
    assert "CP01" not in {c["id"] for c in fiche_copro.actuels(f)}
    assert [m["action"] for m in FE.journal(tmp_path, "m")] == ["coproprietaire_ajout", "lots_proprietaire"]


def test_vente_a_un_copropriétaire_existant_et_rachat(tmp_path):
    lots_cp02 = [l["numero"] for l in BASE["lots"] if l["proprietaire"] == "CP02"]
    _, f = FE.changer_proprietaire(tmp_path, "m", BASE, lots_cp02, LE, nouveau="CP03")
    assert next(x for x in f["coproprietaires"] if x["id"] == "CP02")["ancien"]
    _, f = FE.changer_proprietaire(tmp_path, "m", BASE, lots_cp02[:1], date(2028, 1, 5), nouveau="CP02")
    assert "ancien" not in next(x for x in f["coproprietaires"] if x["id"] == "CP02")   # il revient
    assert fiche_copro.valider(f).ok


def test_vente_refusee(tmp_path):
    l1 = next(l["numero"] for l in BASE["lots"] if l["proprietaire"] == "CP01")
    l2 = next(l["numero"] for l in BASE["lots"] if l["proprietaire"] == "CP02")
    with pytest.raises(FE.FicheInvalide, match="différents"):
        FE.changer_proprietaire(tmp_path, "m", BASE, [l1, l2], LE, nouveau="CP03")
    with pytest.raises(FE.FicheInvalide, match="déjà"):
        FE.changer_proprietaire(tmp_path, "m", BASE, [l1], LE, nouveau="CP01")
    with pytest.raises(FE.FicheInvalide, match="obligatoire"):
        FE.changer_proprietaire(tmp_path, "m", BASE, [l1], LE, nouveau_saisie={"nom": ""})
    with pytest.raises(FE.FicheInvalide, match="lot"):
        FE.changer_proprietaire(tmp_path, "m", BASE, [999], LE, nouveau="CP03")
    assert FE.journal(tmp_path, "m") == []


def test_l_ancien_ne_recoit_plus_les_rappels(tmp_path):
    lots_cp01 = [l["numero"] for l in BASE["lots"] if l["proprietaire"] == "CP01"]
    _, f = FE.changer_proprietaire(tmp_path, "m", BASE, lots_cp01, LE, nouveau="CP03")
    ag = {"id": "x", "titre": "Assemblée générale ordinaire", "date": "2027-06-12", "heure": "18h30",
          "lieu": "Salle", "resolutions": [], "correspondance": {}}
    r = rappel_ag.rappels(f, ag, "m", date(2027, 6, 5))                       # J-7
    destinataires = {e["coproprietaire"] for e in r["envois"]} | {x["coproprietaire"] for x in r["courrier"]}
    assert "CP03" in destinataires and "CP01" not in destinataires


def test_historique_lisible(tmp_path):
    FE.modifier_coproprietaire(tmp_path, "m", BASE, "CP01", {"telephone": "0600"}, LE)
    lots_cp02 = [l["numero"] for l in BASE["lots"] if l["proprietaire"] == "CP02"]
    _, f = FE.changer_proprietaire(tmp_path, "m", BASE, lots_cp02, LE, nouveau="CP03")
    h = FE.historique(f, FE.journal(tmp_path, "m"))
    assert h[0]["quoi"].endswith("Bernard Louis → Durand Camille") and "téléphone" in h[1]["quoi"]
