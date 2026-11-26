"""
evolution_budget.py — Le budget de la copropriété comparé à lui-même, d'un exercice à l'autre.

Les données publiques du registre des copropriétés ne contiennent aucun montant : on ne peut
pas comparer une copropriété à ses voisines sans leurs propres chiffres. Mais on peut toujours
la comparer à elle-même. Ce module répond à trois questions, à partir des budgets prévisionnels
enregistrés (et de celui de la fiche) :

    - de combien le budget a-t-il évolué, au total et par lot principal ?
    - quels postes augmentent le plus vite ?
    - quels postes sont apparus ou ont disparu ?

Un poste « à regarder » augmente de plus de 5 % par an en moyenne et pèse au moins 3 % du
budget : assez pour compter, assez vite pour mériter une question (renégocier, remettre en
concurrence, comprendre). Ce n'est jamais un jugement : un poste peut augmenter pour une
bonne raison (nouveau contrat, travaux d'entretien).

Les postes sont rapprochés par leur libellé (sans accents, ni casse, ni ponctuation).
"""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
SEUIL_HAUSSE_ANNUELLE = Decimal("5")   # % par an, en moyenne
PART_MINIMALE = Decimal("3")           # % du dernier budget
REPERE = ("au-delà de 5 % de hausse par an en moyenne, les postes qui augmentent le plus "
          "méritent une question : renégocier, remettre en concurrence ou comprendre")


def _d(x) -> Decimal:
    return Decimal(str(x or 0))


def cle_poste(libelle: str) -> str:
    """« Ménage des parties communes » et « menage des parties communes. » sont le même poste."""
    t = unicodedata.normalize("NFKD", str(libelle)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def lots_principaux(fiche: dict) -> int:
    return sum(1 for l in fiche["lots"] if l.get("type") not in ("cave", "parking"))


def taux_annuel(debut: Decimal, fin: Decimal, annees: int) -> Decimal | None:
    """Hausse annuelle moyenne, en % (taux composé). None si le calcul n'a pas de sens."""
    if debut <= 0 or fin <= 0 or annees <= 0:
        return None
    return ((Decimal(float(fin / debut) ** (1 / annees)) - 1) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)


def variation(debut: Decimal, fin: Decimal) -> Decimal | None:
    if debut <= 0:
        return None
    return ((fin - debut) / debut * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)


def evolution(fiche: dict, budgets: dict) -> dict:
    """budgets : {exercice: [{libelle, cle, montant}]}, comme compta.budgets()."""
    exercices = sorted(int(n) for n, p in budgets.items() if sum((_d(x["montant"]) for x in p), ZERO) > 0)
    nb = lots_principaux(fiche) or 1
    totaux = {n: sum((_d(x["montant"]) for x in budgets[n]), ZERO) for n in exercices}
    res = {"exercices": exercices, "lots_principaux": nb,
           "totaux": [{"exercice": n, "total": totaux[n], "par_lot": (totaux[n] / nb).quantize(Decimal("0.01"))}
                      for n in exercices],
           "disponible": len(exercices) >= 2, "repere": REPERE}
    if not res["disponible"]:
        res["message"] = ("Il faut au moins deux budgets pour voir l'évolution : enregistrez le budget "
                          "de l'exercice suivant, ou celui d'un exercice passé.")
        return res

    premier, dernier = exercices[0], exercices[-1]
    annees = dernier - premier
    res.update({"premier": premier, "dernier": dernier, "annees": annees,
                "variation": variation(totaux[premier], totaux[dernier]),
                "taux_annuel": taux_annuel(totaux[premier], totaux[dernier], annees)})

    # Postes, rapprochés par libellé
    postes: dict[str, dict] = {}
    for n in exercices:
        for x in budgets[n]:
            k = cle_poste(x["libelle"])
            p = postes.setdefault(k, {"libelle": x["libelle"], "montants": {}})
            p["montants"][n] = p["montants"].get(n, ZERO) + _d(x["montant"])
            p["libelle"] = x["libelle"]                      # le libellé le plus récent
    lignes = []
    for p in postes.values():
        m = p["montants"]
        debut, fin = m.get(premier, ZERO), m.get(dernier, ZERO)
        part = (fin / totaux[dernier] * 100).quantize(Decimal("0.1")) if totaux[dernier] else ZERO
        l = {"libelle": p["libelle"], "montants": [m.get(n) for n in exercices], "part": part,
             "variation": variation(debut, fin), "taux_annuel": taux_annuel(debut, fin, annees),
             "ecart": fin - debut,
             "statut": "nouveau" if not debut and fin else "disparu" if debut and not fin else "suivi"}
        l["a_regarder"] = bool(l["statut"] == "suivi" and l["taux_annuel"] is not None
                               and l["taux_annuel"] > SEUIL_HAUSSE_ANNUELLE and part >= PART_MINIMALE)
        lignes.append(l)
    lignes.sort(key=lambda l: (-l["ecart"], l["libelle"]))
    res["postes"] = lignes
    res["a_regarder"] = [l for l in lignes if l["a_regarder"]]
    res["nouveaux"] = [l for l in lignes if l["statut"] == "nouveau"]
    res["disparus"] = [l for l in lignes if l["statut"] == "disparu"]
    suivis = [l for l in lignes if l["statut"] == "suivi" and l["variation"] is not None]
    res["plus_forte_hausse"] = max(suivis, key=lambda l: l["ecart"]) if suivis and max(
        l["ecart"] for l in suivis) > 0 else None
    return res


def indicateur(fiche: dict, budgets: dict | None) -> dict:
    """La ligne du bulletin de santé."""
    from bulletin import ATTENTION, INCONNU, OK, _eur
    theme = "Évolution du budget"
    if not budgets:
        return {"theme": theme, "valeur": "non renseigné", "detail": "", "repere": REPERE, "etat": INCONNU}
    ev = evolution(fiche, budgets)
    if not ev["disponible"]:
        seul = ev["totaux"][0] if ev["totaux"] else None
        return {"theme": theme, "valeur": "un seul budget connu",
                "detail": f"{_eur(seul['par_lot'])} par lot principal en {seul['exercice']}" if seul else "",
                "repere": REPERE, "etat": INCONNU}
    dernier = ev["totaux"][-1]
    an = "an" if ev["annees"] == 1 else "ans"
    detail = f"{_eur(dernier['par_lot'])} par lot principal en {dernier['exercice']}"
    if ev["plus_forte_hausse"]:
        h = ev["plus_forte_hausse"]
        detail += f" ; plus forte hausse : {h['libelle'].lower()} ({h['variation']:+.0f} %)"
    if ev["nouveaux"]:
        detail += f" ; {len(ev['nouveaux'])} poste(s) nouveau(x)"
    trop = ev["taux_annuel"] is not None and ev["taux_annuel"] > SEUIL_HAUSSE_ANNUELLE
    return {"theme": theme, "valeur": f"{ev['variation']:+.0f} % en {ev['annees']} {an}",
            "detail": detail, "repere": REPERE, "etat": ATTENTION if trop or ev["a_regarder"] else OK}
