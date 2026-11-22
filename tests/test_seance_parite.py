"""L'outil du président de séance (seance/regles.js) applique les mêmes règles que le moteur Python."""

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from core import vote

RACINE = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


def _cas(n: int = 400) -> list[dict]:
    hasard = random.Random(1965)
    cas = []
    for _ in range(n):
        nb = hasard.randint(2, 12)
        tantiemes = [hasard.randint(1, 300) for _ in range(nb)]
        if hasard.random() < 0.1:                 # un copropriétaire majoritaire (art. 22)
            tantiemes[0] = sum(tantiemes) * 2
        copros = [{"id": f"c{i}", "nom": f"C{i}", "tantiemes": t} for i, t in enumerate(tantiemes)]
        bulletins = {c["id"]: hasard.choice(["pour", "pour", "contre", "abstention"])
                     for c in copros if hasard.random() < 0.75}
        cas.append({"coproprietaires": copros, "bulletins": bulletins,
                    "majorite": hasard.choice(["24", "25", "26"])})
    return cas


@pytest.mark.skipif(NODE is None, reason="node absent")
def test_memes_resultats_que_le_moteur_python():
    cas = _cas()
    res = subprocess.run([NODE, str(RACINE / "tests/seance/parite.mjs")], input=json.dumps(cas),
                         capture_output=True, text=True, check=True, cwd=RACINE)
    js = json.loads(res.stdout)
    for c, r in zip(cas, js["sortie"]):
        fiche = {"lots": [{"proprietaire": x["id"], "tantiemes": {"generales": x["tantiemes"]}}
                          for x in c["coproprietaires"]]}
        voix = vote.electorat(fiche, "generales")
        py = vote.decompter(c["bulletins"], voix, c["majorite"])
        passerelle = "25-1" if py["passerelle_25_1"] else "26-1" if py["passerelle_26_1"] else None
        assert r["voix"] == voix
        assert (r["adoptee"], r["passerelle"]) == (py["adoptee"], passerelle), c
        assert (r["pour"], r["contre"], r["abstention"]) == (py["pour"], py["contre"], py["abstention"])

    liste = js["liste"]
    assert liste["lignes"] == [
        {"nom": "Mme Dupont", "tantiemes": 125, "lots": 1},
        {"nom": "M. Martin", "tantiemes": 80, "lots": 1},
        {"nom": "SCI Les Pins", "tantiemes": 45, "lots": 1},
        {"nom": "GARNIER Paul", "tantiemes": 170, "lots": 2},      # deux lots regroupés
        {"nom": "M. ROUQUIER", "tantiemes": 50, "lots": 1},        # numéro de compte retiré
    ]
    assert liste["ignorees"] == ["Nom Tantièmes", "Total 470", "M. Zéro ; 0"]
    assert liste["base"] == 1000
