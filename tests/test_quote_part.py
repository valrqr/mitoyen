"""« Combien ça me coûte ? » : la part de chaque copropriétaire. python -m pytest tests/test_quote_part.py"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))

import ag  # noqa: E402
import fiche_copro  # noqa: E402
import quote_part as Q  # noqa: E402
from avis_appel import euros  # noqa: E402

MIMOSAS = fiche_copro.charger_fiche(RACINE / "config" / "mimosas.yaml")
TILLEULS = fiche_copro.charger_fiche(RACINE / "config" / "tilleuls.yaml")


def _ag(tmp_path, fiche=MIMOSAS, autres=()):
    odj = ag.ordre_du_jour_type(fiche) + list(autres)
    return ag.creer_ag(tmp_path, "c", fiche, date(2027, 5, 20), "18h30", "Salle", odj, aujourd_hui=date(2027, 3, 1))


def test_lire_montant():
    assert Q.lire_montant("4 800 €") == Decimal("4800.00")
    assert Q.lire_montant("4800,5") == Decimal("4800.50")
    assert Q.lire_montant("") is None
    for faux in ("abc", "-5", "0"):
        with pytest.raises(Q.MontantInvalide):
            Q.lire_montant(faux)


def test_parts_somme_juste_et_non_concernes():
    p = Q.parts(MIMOSAS, Decimal("1200.00"), "ascenseur")
    assert sum(p.values()) == Decimal("1200.00")
    concernes = {l["proprietaire"] for l in MIMOSAS["lots"] if l["tantiemes"].get("ascenseur", 0) > 0}
    assert set(p) == concernes
    g = Q.parts(MIMOSAS, Decimal("4800.00"), "generales")
    assert sum(g.values()) == Decimal("4800.00")


def test_resolutions_chiffrees(tmp_path):
    a = _ag(tmp_path, autres=[{"titre": "Remplacement de la porte du hall", "montant": "4 800 €", "echeances": 2}])
    r = {x["num"]: x for x in a["resolutions"]}
    assert r[2]["cout"] == "budget" and r[3]["cout"] == "fonds_travaux"
    porte = a["resolutions"][-1]
    assert porte["montant"] == "4800.00" and porte["echeances"] == 2
    assert Q.cout(MIMOSAS, r[1]) is None and Q.cout(MIMOSAS, r[4]) is None      # comptes, syndic : pas de montant
    # La somme des parts de tous les copropriétaires retombe sur le total
    for res in a["resolutions"]:
        lignes = [Q.resolution(MIMOSAS, a, res, c["id"]) for c in MIMOSAS["coproprietaires"]]
        if lignes[0] is None:
            continue
        assert sum(x["part"] for x in lignes) == lignes[0]["total"]
        for x in lignes:                                                       # échéances = part
            assert sum(m for _, m in x["echeances"]) == x["part"]


def test_echeances_et_textes(tmp_path):
    a = _ag(tmp_path, autres=[{"titre": "Porte", "montant": "4800", "echeances": 2}])
    porte = Q.resolution(MIMOSAS, a, a["resolutions"][-1], "CP01")
    assert [d for d, _ in porte["echeances"]] == [date(2027, 7, 1), date(2027, 10, 1)]   # après l'AG du 20/05
    chiffre, suite = Q.resume(porte, euros)
    assert chiffre == euros(porte["part"]) and suite.startswith("en 2 appels de")
    budget = Q.resolution(MIMOSAS, a, a["resolutions"][1], "CP01")
    exercice = MIMOSAS["budget_previsionnel"]["exercice"]
    assert budget["echeances"][0][0] == date(exercice + 1, 1, 1)                 # budget de l'exercice suivant
    assert "par an" in Q.resume(budget, euros)[1] and f"exercice {exercice}" in Q.resume(budget, euros)[1]


def test_non_concerne_et_total(tmp_path):
    import copy
    fiche = copy.deepcopy(MIMOSAS)                      # un rez-de-chaussée hors charges d'ascenseur
    lot = fiche["lots"][0]
    lot["tantiemes"]["ascenseur"] = 0
    exclu = lot["proprietaire"]
    fiche["lots"] = [l for l in fiche["lots"] if l["proprietaire"] != exclu or l is lot]
    a = _ag(tmp_path, fiche, autres=[{"titre": "Contrat ascenseur", "montant": "1200", "cle": "ascenseur"},
                                     {"titre": "Porte", "montant": "4800"}])
    x = Q.resolution(fiche, a, a["resolutions"][-2], exclu)
    assert not x["concerne"] and x["echeances"] == [] and Q.resume(x, euros)[0] == ""
    vp = Q.votre_part(fiche, a, exclu)
    assert vp["total_travaux"] == Q.resolution(fiche, a, a["resolutions"][-1], exclu)["part"] > 0


def test_devis_concurrents_compte_le_plus_cher():
    a = {"date": "2027-05-20", "resolutions": [
        {"num": 1, "titre": "Toiture : devis A", "majorite": "24", "cle": "generales", "dossier": "d1",
         "devis": "A", "montant": "10000.00", "echeances": 1},
        {"num": 2, "titre": "Toiture : devis B", "majorite": "24", "cle": "generales", "dossier": "d1",
         "devis": "B", "montant": "12000.00", "echeances": 1}]}
    vp = Q.votre_part(MIMOSAS, a, "CP01")
    assert vp["total_travaux"] == max(x["part"] for x in vp["lignes"])


def test_montant_invalide_refuse(tmp_path):
    with pytest.raises(ag.AGInvalide, match="montant"):
        _ag(tmp_path, autres=[{"titre": "Porte", "montant": "beaucoup"}])
    with pytest.raises(ag.AGInvalide, match="échéances"):
        _ag(tmp_path, autres=[{"titre": "Porte", "montant": "100", "echeances": 30}])


def test_pdfs(tmp_path):
    a = _ag(tmp_path, TILLEULS, autres=[{"titre": "Ravalement de la façade", "montant": "18000", "echeances": 4}])
    for c in TILLEULS["coproprietaires"]:
        f = ag.generer_formulaire(TILLEULS, a, c["id"], tmp_path / f"f_{c['id']}.pdf")
        q = Q.generer_pdf(TILLEULS, a, c["id"], tmp_path / f"q_{c['id']}.pdf")
        assert f.stat().st_size > 1000 and q.stat().st_size > 1000
    from pypdf import PdfReader
    texte = PdfReader(str(tmp_path / "q_TL01.pdf")).pages[0].extract_text()
    assert "Ce que chaque résolution vous coûterait" in texte and "Ravalement" in texte
    assert "Votre part" in PdfReader(str(tmp_path / "f_TL01.pdf")).pages[0].extract_text()


# --------------------------------------------------------------------------- #
# Après le vote : agenda des échéances et « L'AG en bref »
# --------------------------------------------------------------------------- #
def _votee(tmp_path):
    a = _ag(tmp_path, autres=[{"titre": "Ravalement de la façade", "montant": "48000", "echeances": 4},
                              {"titre": "Remplacement de la porte du hall", "montant": "4800"}])
    tous = [c["id"] for c in MIMOSAS["coproprietaires"]]
    a["presences"] = {c: {"mode": "present"} for c in tous}
    porte = a["resolutions"][-1]["num"]
    return a, ag.depouiller(MIMOSAS, a, {porte: {"contre": tous}})        # la porte est rejetée


def test_adoptees_et_ics(tmp_path):
    a, dep = _votee(tmp_path)
    ad = Q.adoptees(MIMOSAS, a, dep, "CP01")
    assert [x["titre"] for x in ad] == ["Ravalement de la façade"]           # ni la porte rejetée, ni le budget
    ics = Q.generer_ics(MIMOSAS, a, dep, "CP01", "mimosas")
    assert ics.count("BEGIN:VEVENT") == 4 and "TRIGGER:-P7D" in ics and "DTSTART;VALUE=DATE:20270701" in ics
    assert all(len(l.encode()) <= 75 for l in ics.split("\r\n"))             # RFC 5545


def test_ag_en_bref(tmp_path):
    import ag_bref
    a, dep = _votee(tmp_path)
    avant = ag_bref.contenu(MIMOSAS, a, "CP01")
    assert avant["moment"] == "avant" and avant["limite_correspondance"] == date(2027, 5, 16)
    apres = ag_bref.contenu(MIMOSAS, a, "CP01", dep)
    assert apres["rejetees"] == 1 and apres["a_payer"] == Q.adoptees(MIMOSAS, a, dep, "CP01")[0]["part"]
    assert apres["prochain_appel"][0] == date(2027, 7, 1)
    porte = next(p for p in apres["points"] if p["titre"].startswith("Remplacement"))
    assert porte["issue"] == "rejetée" and "part" not in porte
    for moment in (None, dep):
        f = ag_bref.generer_pdf(MIMOSAS, a, "CP01", tmp_path / "b.pdf", moment)
        assert f.stat().st_size > 1000
    from pypdf import PdfReader
    assert "Ce qu'a décidé" in PdfReader(str(tmp_path / "b.pdf")).pages[0].extract_text()


def test_mail_de_resultats_le_lendemain(tmp_path):
    import rappel_ag
    a, _ = _votee(tmp_path)
    tous = [c["id"] for c in MIMOSAS["coproprietaires"]]
    a["depouillement"] = {"votes": {a["resolutions"][-1]["num"]: {"contre": tous}}, "amendees": [],
                          "le": "2027-05-20"}
    assert rappel_ag.resultats(MIMOSAS, a, "mimosas", date(2027, 5, 20)) is None        # pas le jour même
    assert rappel_ag.resultats(MIMOSAS, a, "mimosas", date(2027, 5, 22)) is None
    r = rappel_ag.resultats(MIMOSAS, a, "mimosas", date(2027, 5, 21))
    assert r["rappel"] == "résultats" and r["envois"]
    e = next(x for x in r["envois"] if not x.get("aidant"))
    assert "Ravalement de la façade" in e["texte"] and "Rejeté :" in e["texte"] and "deux mois" in e["texte"]
    assert e["fichier_pdf"].endswith(f"/en-bref/{e['coproprietaire']}")
    assert e["fichier_ics"].endswith(f"/echeances/{e['coproprietaire']}.ics")         # il a une part à payer
    # Les copropriétaires au courrier : le syndic reçoit leur liste
    au_courrier = {c["id"] for c in MIMOSAS["coproprietaires"] if c.get("envoi") == "courrier" or not c.get("email")}
    assert au_courrier <= {x["coproprietaire"] for x in r["courrier"]}
    # Sans dépense adoptée pour lui, pas de fichier d'agenda
    a["depouillement"]["votes"] = {x["num"]: {"contre": tous} for x in a["resolutions"] if x["majorite"] != "info"}
    r = rappel_ag.resultats(MIMOSAS, a, "mimosas", date(2027, 5, 21))
    assert all(x["fichier_ics"] == "" for x in r["envois"]) and "Rien n'a été adopté." in r["envois"][0]["texte"]
