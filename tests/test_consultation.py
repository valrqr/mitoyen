"""Petites copropriétés : consultation écrite à l'unanimité. python -m pytest tests/test_consultation.py"""
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))

import consultation as C  # noqa: E402
import fiche_copro  # noqa: E402

TILLEULS = fiche_copro.charger_fiche(RACINE / "config" / "tilleuls.yaml")
MIMOSAS = fiche_copro.charger_fiche(RACINE / "config" / "mimosas.yaml")
T0 = datetime(2027, 3, 1, 10, 0)


def _ouvrir(tmp_path, **kw):
    return C.ouvrir(tmp_path, "t", TILLEULS, "Remplacement de la boîte aux lettres collective",
                    "Les copropriétaires décident de remplacer la boîte aux lettres collective, pour 450 € TTC.",
                    date(2027, 3, 15), maintenant=T0, **kw)


def test_regime_petites_coproprietes():
    r = C.regime(TILLEULS)
    assert r["applicable"] and r["lots_principaux"] == 4                     # les caves ne comptent pas
    m = C.regime(MIMOSAS)
    assert not m["applicable"] and "ne s'applique pas" in m["detail"]
    # Critère du budget : moyenne de trois exercices consécutifs sous 15 000 €
    petits = {2025: [{"montant": 12000}], 2026: [{"montant": 13000}], 2027: [{"montant": 14000}]}
    r = C.regime(MIMOSAS, petits)
    assert r["applicable"] and r["budget_moyen"] == Decimal("13000.00") and r["exercices"] == [2025, 2026, 2027]


def test_grande_copro_refusee(tmp_path):
    with pytest.raises(C.ConsultationInvalide, match="assemblée générale"):
        C.ouvrir(tmp_path, "m", MIMOSAS, "Q", "Texte", date(2027, 3, 15), maintenant=T0)


def test_budget_et_comptes_exclus(tmp_path):
    with pytest.raises(C.ConsultationInvalide, match="budget prévisionnel"):
        C.ouvrir(tmp_path, "t", TILLEULS, "Vote du budget prévisionnel 2028", "…", date(2027, 3, 15), maintenant=T0)


def test_unanimite_et_tous_doivent_repondre(tmp_path):
    c, jetons = _ouvrir(tmp_path)
    assert set(c["electeurs"]) == {"TL01", "TL02", "TL03"} and "jeton" not in str(jetons.values())
    assert all(len(v["jeton"]) == 64 for v in c["electeurs"].values())        # empreinte, jamais le jeton
    assert C.trouver(c, jetons["TL02"]) == "TL02" and C.trouver(c, "faux") is None
    C.voter(c, "TL01", "pour", "lien", maintenant=T0)
    C.voter(c, "TL02", "pour", "lien", maintenant=T0)
    r = C.resultat(c, T0)
    assert r["statut"] == "en_cours" and r["attente"] == ["TL03"]
    with pytest.raises(C.ConsultationInvalide, match="déjà voté"):
        C.voter(c, "TL01", "contre", "lien", maintenant=T0)
    C.voter(c, "TL03", "pour", "courrier", piece="bulletin signé reçu le 05/03", maintenant=T0)
    # Consultation écrite : la décision n'est formalisée qu'au terme du délai (loi, art. 41-12)
    r = C.resultat(c, T0)
    assert r["statut"] == "unanimite_acquise" and "15/03/2027" in r["texte"]
    assert C.resultat(c, datetime(2027, 3, 16))["statut"] == "adoptee"


def test_reunion_sans_ecrit_formalisee_tout_de_suite(tmp_path):
    c, _ = _ouvrir(tmp_path)
    for e in ("TL01", "TL02", "TL03"):
        C.voter(c, e, "pour", "presence", maintenant=T0)
    assert C.resultat(c, T0)["statut"] == "adoptee"


def test_cloture_avant_terme_refusee_si_unanimite_ecrite(tmp_path):
    c, _ = _ouvrir(tmp_path)
    for e in ("TL01", "TL02", "TL03"):
        C.voter(c, e, "pour", "lien", maintenant=T0)
    C.sauver(tmp_path, "t", c)
    with pytest.raises(C.ConsultationInvalide, match="terme du délai"):
        C.clore(tmp_path, "t", c["id"], T0)
    assert C.clore(tmp_path, "t", c["id"], datetime(2027, 3, 16))["resultat"] == "adoptee"


def test_une_abstention_suffit_a_empecher(tmp_path):
    c, _ = _ouvrir(tmp_path)
    C.voter(c, "TL01", "pour", "lien", maintenant=T0)
    C.voter(c, "TL02", "abstention", "lien", maintenant=T0)
    r = C.resultat(c, T0)
    assert r["statut"] == "rejetee" and "assemblée générale" in r["suite"]


def test_sans_reponse_au_terme_caduque(tmp_path):
    c, _ = _ouvrir(tmp_path)
    C.voter(c, "TL01", "pour", "lien", maintenant=T0)
    assert C.resultat(c, datetime(2027, 3, 16))["statut"] == "caduque"
    with pytest.raises(C.ConsultationInvalide, match="close"):
        C.voter(c, "TL02", "pour", "lien", maintenant=datetime(2027, 3, 16))


def test_demande_d_un_coproprietaire_21_jours(tmp_path):
    c, _ = _ouvrir(tmp_path, demandee_par="TL02", demandee_le=date(2027, 2, 20))
    assert C.a_organiser(c) == "2027-03-13"


def test_documents(tmp_path):
    c, _ = _ouvrir(tmp_path)
    C.voter(c, "TL01", "pour", "presence", maintenant=T0)
    assert C.bulletin_pdf(TILLEULS, c, "TL03", tmp_path / "b.pdf").stat().st_size > 2000
    import pypdf
    p = C.proces_verbal_pdf(TILLEULS, c, tmp_path / "pv.pdf", T0)
    texte = " ".join(x.extract_text() for x in pypdf.PdfReader(p).pages)
    assert "Lambert Sophie" in texte and "42-5" in texte
