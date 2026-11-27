"""Le plan de relève du syndic."""
import copy
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))
import releve  # noqa: E402

JOUR = date(2027, 3, 1)


@pytest.fixture
def fiche():
    f = yaml.safe_load((RACINE / "config" / "mimosas.yaml").read_text(encoding="utf-8"))
    return copy.deepcopy(f)


def test_enregistrer_controles(tmp_path, fiche):
    syndic = fiche["gouvernance"]["syndic"]["coproprietaire_id"]
    cs = [c for c in fiche["gouvernance"]["conseil_syndical"] if c != syndic]
    hors_cs = next(c["id"] for c in fiche["coproprietaires"] if c["id"] not in fiche["gouvernance"]["conseil_syndical"])
    with pytest.raises(releve.ReleveInvalide, match="au moins un"):
        releve.enregistrer(tmp_path, "c", fiche, {}, JOUR)
    with pytest.raises(releve.ReleveInvalide, match="propre suppléant"):
        releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": syndic, "role1": "membre_cs", "accord1": "2027-02-01"}, JOUR)
    with pytest.raises(releve.ReleveInvalide, match="accord"):
        releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": cs[0], "role1": "vice_president"}, JOUR)
    with pytest.raises(releve.ReleveInvalide, match="pas au conseil syndical"):
        releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": hors_cs, "role1": "president_cs", "accord1": "2027-02-01"}, JOUR)
    with pytest.raises(releve.ReleveInvalide, match="deux fois"):
        releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": cs[0], "role1": "vice_president", "accord1": "2027-02-01",
                                                  "suppleant2": cs[0], "role2": "membre_cs", "accord2": "2027-02-01"}, JOUR)
    r = releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": cs[0], "role1": "vice_president", "accord1": "2027-02-01",
                                                  "suppleant2": hors_cs, "role2": "autre", "accord2": "2027-02-10"}, JOUR)
    assert [s["role"] for s in r["suppleants"]] == ["vice_president", "autre"]
    assert releve.acces_dossier(fiche, r)
    # Un suppléant hors conseil syndical seul n'a pas accès au dossier complet
    r2 = releve.enregistrer(tmp_path, "d", fiche, {"suppleant1": hors_cs, "role1": "autre", "accord1": "2027-02-10"}, JOUR)
    assert not releve.acces_dossier(fiche, r2)


def test_lien_et_journal(tmp_path, fiche):
    with pytest.raises(releve.ReleveInvalide, match="suppléant"):
        releve.partager(tmp_path, "c", True)
    cs = [c for c in fiche["gouvernance"]["conseil_syndical"] if c != fiche["gouvernance"]["syndic"]["coproprietaire_id"]]
    releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": cs[0], "role1": "vice_president", "accord1": "2027-02-01"}, JOUR)
    j = releve.partager(tmp_path, "c", True)["jeton"]
    assert releve.jeton_valide(tmp_path, "c", j) and not releve.jeton_valide(tmp_path, "c", "x" * 22)
    j2 = releve.partager(tmp_path, "c", True, renouveler=True)["jeton"]
    assert j2 != j and not releve.jeton_valide(tmp_path, "c", j)
    releve.partager(tmp_path, "c", False)
    assert not releve.jeton_valide(tmp_path, "c", j2)
    for i in range(25):
        releve.noter_telechargement(tmp_path, "c", "dossier", "suppleant")
    assert len(releve.charger(tmp_path, "c")["telechargements"]) == 20


def test_etat(tmp_path, fiche):
    r = releve.charger(tmp_path, "c")
    e = releve.etat(fiche, r, JOUR)
    assert not e[0]["ok"] and sum(x["ok"] for x in e) <= 3
    cs = [c for c in fiche["gouvernance"]["conseil_syndical"] if c != fiche["gouvernance"]["syndic"]["coproprietaire_id"]]
    releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": cs[0], "role1": "vice_president", "accord1": "2027-02-01"}, JOUR)
    releve.partager(tmp_path, "c", True)
    releve.noter_telechargement(tmp_path, "c", "dossier", "syndic")
    e = {x["titre"]: x for x in releve.etat(fiche, releve.charger(tmp_path, "c"), date.today())}
    assert e["Un vice-président peut suppléer le syndic"]["ok"] and e["Le suppléant a son lien"]["ok"]
    assert e["Le dossier de passation a été vérifié"]["ok"]
    # Mandat qui s'achève bientôt ; syndic bénévole classique sans conseil syndical
    f = copy.deepcopy(fiche)
    f["gouvernance"].update(mode_gestion="benevole", conseil_syndical=[])
    f["gouvernance"]["syndic"]["fin_mandat"] = "2027-04-15"
    e = {x["titre"]: x for x in releve.etat(f, releve.charger(tmp_path, "c"), JOUR)}
    assert not e["Le président du conseil syndical est suppléant"]["ok"]
    assert "tribunal" in e["La copropriété a un conseil syndical"]["detail"]
    assert "renouvellement" in e["Le mandat du syndic court encore"]["detail"]


def test_convocation(tmp_path, fiche):
    from pypdf import PdfReader
    cs = [c for c in fiche["gouvernance"]["conseil_syndical"] if c != fiche["gouvernance"]["syndic"]["coproprietaire_id"]]
    r = releve.enregistrer(tmp_path, "c", fiche, {"suppleant1": cs[0], "role1": "vice_president", "accord1": "2027-02-01"}, JOUR)
    t = "".join(p.extract_text() for p in PdfReader(releve.generer_convocation(fiche, r, JOUR, tmp_path / "a.pdf")).pages)
    assert "Convocation du conseil syndical" in t and "17-1" in t
    f = copy.deepcopy(fiche)
    f["gouvernance"]["mode_gestion"] = "benevole"
    r["suppleants"][0]["role"] = "president_cs"
    t = "".join(p.extract_text() for p in PdfReader(releve.generer_convocation(f, r, JOUR, tmp_path / "b.pdf")).pages)
    assert "assemblée générale" in t and "Désignation d'un nouveau syndic" in t and "21 jours" in t
    assert "président du conseil syndical" in t
