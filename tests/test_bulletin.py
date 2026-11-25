"""Bulletin de santé de la copropriété : python -m pytest tests/test_bulletin.py"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bulletin as BU  # noqa: E402
import compta  # noqa: E402
from test_compta import FICHE, _sources  # noqa: E402


def _ind(b, theme):
    return next(i for i in b["indicateurs"] if i["theme"] == theme)


def test_faits_et_reperes(tmp_path):
    src, ops, st = _sources(tmp_path)
    E = compta.journal(FICHE, src)
    b = BU.bulletin(FICHE, date(2027, 3, 1), E=E, st=compta.charger(tmp_path, "m"),
                    budgets=compta.budgets(FICHE, tmp_path, "m"), ags=[], signalements=[])
    assert _ind(b, "Fonds de travaux")["etat"] == "ok" and "6 %" in _ind(b, "Fonds de travaux")["detail"]
    assert _ind(b, "Charges impayées")["valeur"] == "moins de 5 % du budget"
    assert _ind(b, "Plan pluriannuel de travaux")["etat"] == "attention"        # élaboré, pas encore adopté
    assert _ind(b, "Budget tenu")["etat"] == "inconnu"                         # rien d'inventé
    assert _ind(b, "Assemblée générale")["valeur"] == "dernière le 20/05/2026"
    assert "note" not in b and all(i["etat"] in ("ok", "attention", "inconnu") for i in b["indicateurs"])


def test_impayes_en_tranches_jamais_en_montant():
    assert BU.tranche_impayes(Decimal("400"), Decimal("19800"))[0] == "moins de 5 % du budget"
    assert BU.tranche_impayes(Decimal("1500"), Decimal("10000"))[0] == "entre 10 et 25 % du budget"
    assert BU.tranche_impayes(Decimal("3000"), Decimal("10000"))[0] == "25 % du budget ou plus"


def test_lien_desactive_par_defaut(tmp_path):
    assert not BU.jeton_valide(tmp_path, "m", "")
    r = BU.partager(tmp_path, "m", True)
    assert BU.jeton_valide(tmp_path, "m", r["jeton"])
    BU.partager(tmp_path, "m", False)
    assert not BU.jeton_valide(tmp_path, "m", r["jeton"])
    r2 = BU.partager(tmp_path, "m", True, renouveler=True)
    assert r2["jeton"] != r["jeton"] and not BU.jeton_valide(tmp_path, "m", r["jeton"])


def test_pdf(tmp_path):
    b = BU.bulletin(FICHE, date(2027, 3, 1))
    assert BU.generer_pdf(b, tmp_path / "b.pdf").stat().st_size > 2000
