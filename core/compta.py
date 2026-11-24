"""
compta.py — Comptabilité en partie double du syndicat des copropriétaires.

Toute copropriété qui dépasse le régime simplifié (plus de 5 lots principaux et un
budget moyen d'au moins 15 000 € sur trois exercices, loi 1965 art. 14-3) tient une
comptabilité d'engagement en partie double, selon le plan comptable du décret
n° 2005-240 et de l'arrêté du 14 mars 2005.

Principe : Mitoyen ne fait rien saisir deux fois. Le journal est RECALCULÉ à partir
de ce qui existe déjà :
  - les appels de fonds validés          -> copropriétaires / provisions ;
  - les ajustements du recouvrement       -> copropriétaires / produits ou avoirs ;
  - les factures saisies                  -> charges / fournisseurs ;
  - chaque ligne du relevé bancaire       -> banque / copropriétaire, fournisseur
                                             ou compte d'attente s'il reste à affecter ;
  - les soldes d'ouverture (à-nouveaux).
Rien ne disparaît : une opération bancaire non expliquée va au compte 471 (attente),
jamais dans un compte d'ajustement. La balance doit donc toujours tomber juste, et
le solde du compte 512 doit égaler celui du relevé.

⚠️ Le plan comptable ci-dessous reprend la nomenclature de l'arrêté du 14 mars 2005.
Avant un usage réel, le comparer au texte en vigueur sur Légifrance, en particulier
les comptes du fonds de travaux (105, 4505), ajoutés après la loi ALUR. Aide à la
gestion, pas un conseil comptable ; l'ADIL du département renseigne gratuitement.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

CENT = Decimal("0.01")
ZERO = Decimal("0")

# --------------------------------------------------------------------------- #
# Plan comptable (extrait utile aux petites copropriétés)
# --------------------------------------------------------------------------- #
PLAN = {
    "102": "Provisions pour travaux décidés",
    "103": "Avances",
    "105": "Fonds de travaux",
    "12": "Solde en attente sur travaux et opérations exceptionnelles",
    "401": "Fournisseurs",
    "408": "Fournisseurs, factures non parvenues",
    "4501": "Copropriétaire, budget prévisionnel",
    "4502": "Copropriétaire, travaux et opérations exceptionnelles",
    "4503": "Copropriétaire, avances",
    "4505": "Copropriétaire, fonds de travaux",
    "459": "Copropriétaires, créances douteuses",
    "471": "Compte d'attente",
    "486": "Charges payées d'avance",
    "487": "Produits encaissés d'avance",
    "512": "Banque, compte séparé du syndicat",
    "601": "Eau",
    "602": "Électricité",
    "603": "Chauffage, énergie et combustibles",
    "604": "Achats de produits d'entretien et petits équipements",
    "606": "Fournitures",
    "611": "Nettoyage des locaux",
    "612": "Locations immobilières",
    "614": "Contrats de maintenance",
    "615": "Entretien et petites réparations",
    "616": "Primes d'assurances",
    "621": "Rémunérations du syndic sur gestion copropriété",
    "623": "Rémunérations de tiers intervenants",
    "624": "Frais du conseil syndical",
    "63": "Impôts, taxes et versements assimilés",
    "64": "Frais de personnel",
    "66": "Charges financières (frais bancaires, agios)",
    "671": "Travaux décidés par l'assemblée générale",
    "672": "Travaux urgents",
    "677": "Pertes sur créances irrécouvrables",
    "678": "Charges exceptionnelles",
    "701": "Provisions sur opérations courantes",
    "702": "Provisions sur travaux et opérations exceptionnelles",
    "703": "Avances",
    "711": "Subventions",
    "713": "Indemnités d'assurances",
    "714": "Produits divers",
    "716": "Produits financiers",
    "718": "Produits exceptionnels",
}
CLASSES = {"1": "Provisions, avances, fonds", "4": "Tiers", "5": "Comptes financiers",
           "6": "Charges", "7": "Produits"}

# Poste du budget -> compte de charge, quand la fiche ne le précise pas
MOTS_CHARGES = [
    (("assurance",), "616"), (("electricite",), "602"), (("eau",), "601"),
    (("chauffage", "gaz", "fioul", "energie"), "603"), (("menage", "nettoyage", "proprete"), "611"),
    (("maintenance", "contrat"), "614"), (("jardin", "entretien", "reparation"), "615"),
    (("banque", "bancaire", "agios"), "66"), (("syndic", "outil", "logiciel"), "621"),
    (("taxe", "impot"), "63"), (("conseil syndical",), "624"), (("honoraire", "expert", "avocat"), "623"),
    (("produit d'entretien", "fourniture"), "604"),
]
# Nature d'un ajustement du recouvrement -> compte de contrepartie (crédit si dû, débit si avoir)
AJUSTEMENTS = {"travaux": ("4502", "702"), "frais_recouvrement": ("4501", "714"),
               "autre": ("4501", "714"), "avoir": ("4501", "701")}


class ComptaInvalide(ValueError):
    pass


def _d(x) -> Decimal:
    return Decimal(str(x)).quantize(CENT)


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()


def libelle_compte(compte: str) -> str:
    racine, _, aux = compte.partition(".")
    for n in range(len(racine), 0, -1):
        if racine[:n] in PLAN:
            return PLAN[racine[:n]] + (f" — {aux}" if aux else "")
    return compte


def compte_charge(poste: dict) -> str:
    """Compte de charge d'un poste du budget : celui de la fiche, sinon deviné du libellé."""
    if poste.get("compte"):
        return str(poste["compte"])
    lib = _norm(poste.get("libelle", ""))
    for mots, compte in MOTS_CHARGES:
        if any(m in lib for m in mots):
            return compte
    return "615"


def tiers(compte: str, cle: str) -> str:
    """Compte auxiliaire : 4501.CP03, 401.ASCENSEURS-EXEMPLE…"""
    cle = re.sub(r"[^A-Z0-9]+", "-", _norm(cle).upper()).strip("-")[:30] or "DIVERS"
    return f"{compte}.{cle}"


# --------------------------------------------------------------------------- #
# Stockage : soldes d'ouverture, factures, affectation des dépenses
# --------------------------------------------------------------------------- #
def dossier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "compta"


def _lire(f: Path, defaut):
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else defaut


def _ecrire(f: Path, contenu) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(contenu, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def charger(racine: Path, copro: str) -> dict:
    d = dossier(racine, copro)
    return {"ouverture": _lire(d / "ouverture.json", None), "factures": _lire(d / "factures.json", []),
            "depenses": _lire(d / "depenses.json", {})}


def definir_ouverture(racine: Path, copro: str, jour: date, banque: str, soldes_coproprietaires: dict,
                      fonds_travaux: str = "0", fournisseurs: dict | None = None) -> dict:
    """Soldes au premier jour de la tenue des comptes dans Mitoyen (repris du dernier
    exercice approuvé ou de l'état transmis par l'ancien syndic). Un solde copropriétaire
    positif = il doit ; négatif = il a payé d'avance."""
    o = {"date": jour.isoformat(), "banque": str(_d(banque)), "fonds_travaux": str(_d(fonds_travaux)),
         "coproprietaires": {k: str(_d(v)) for k, v in soldes_coproprietaires.items() if _d(v) != 0},
         "fournisseurs": {k: str(_d(v)) for k, v in (fournisseurs or {}).items() if _d(v) != 0}}
    _ecrire(dossier(racine, copro) / "ouverture.json", o)
    return o


def ajouter_facture(racine: Path, copro: str, fournisseur: str, jour: date, montant, compte: str,
                    libelle: str, poste: str | None = None) -> dict:
    """Une facture reçue : la charge est constatée à sa date, qu'elle soit payée ou non."""
    if not fournisseur.strip():
        raise ComptaInvalide("Indiquer le fournisseur")
    if not str(compte).startswith("6") or libelle_compte(str(compte)) == str(compte):
        raise ComptaInvalide(f"Compte de charge inconnu : {compte}")
    m = _d(montant)
    if m <= 0:
        raise ComptaInvalide("Le montant d'une facture est positif (un avoir se saisit à part)")
    fac = charger(racine, copro)["factures"]
    f = {"id": f"F{len(fac) + 1:04d}", "fournisseur": fournisseur.strip()[:60], "date": jour.isoformat(),
         "montant": str(m), "compte": str(compte), "libelle": libelle.strip()[:120], "poste": poste}
    _ecrire(dossier(racine, copro) / "factures.json", fac + [f])
    return f


def affecter_depense(racine: Path, copro: str, op_id: str, *, facture: str | None = None,
                     compte: str | None = None, fournisseur: str | None = None, poste: str | None = None) -> dict:
    """Explique un débit du relevé : soit le règlement d'une facture saisie, soit une
    dépense payée directement (frais bancaires, petit achat) avec son compte de charge."""
    dep = charger(racine, copro)["depenses"]
    if facture:
        a = {"facture": facture}
    elif compte:
        if not str(compte).startswith("6"):
            raise ComptaInvalide("Une dépense directe va dans un compte de charge (classe 6)")
        a = {"compte": str(compte), "fournisseur": (fournisseur or "").strip()[:60] or None, "poste": poste}
    else:
        raise ComptaInvalide("Indiquer la facture réglée ou le compte de charge")
    dep[op_id] = a
    _ecrire(dossier(racine, copro) / "depenses.json", dep)
    return a


# --------------------------------------------------------------------------- #
# Journal
# --------------------------------------------------------------------------- #
def _ecriture(jour: str, libelle: str, piece: str, lignes: list[tuple[str, Decimal, Decimal]], source: str) -> dict:
    deb = sum((l[1] for l in lignes), ZERO)
    cred = sum((l[2] for l in lignes), ZERO)
    if deb != cred:
        raise ComptaInvalide(f"Écriture déséquilibrée ({piece}) : {deb} ≠ {cred}")
    return {"date": jour, "libelle": libelle, "piece": piece, "source": source,
            "lignes": [{"compte": c, "debit": d, "credit": k} for c, d, k in lignes if d or k]}


def _rubrique_compte(rubrique: str) -> tuple[str, str]:
    """(compte copropriétaire, compte de contrepartie) pour une rubrique d'appel."""
    if rubrique == "fonds_travaux" or "fonds de travaux" in _norm(rubrique):
        return "4505", "105"
    return "4501", "701"


def journal(fiche: dict, sources: dict) -> list[dict]:
    """sources = {"ouverture", "dues", "ajustements", "operations", "rapprochement",
    "factures", "depenses"} — le journal complet, trié par date."""
    E = []
    o = sources.get("ouverture")
    debut = o["date"] if o else ""       # ce qui précède la reprise est déjà dans les soldes d'ouverture
    if o:
        lignes = [("512", _d(o["banque"]), ZERO) if _d(o["banque"]) >= 0 else ("512", ZERO, -_d(o["banque"]))]
        for cid, s in o["coproprietaires"].items():
            s = _d(s)
            lignes.append((tiers("4501", cid), s, ZERO) if s > 0 else (tiers("4501", cid), ZERO, -s))
        for f, s in o.get("fournisseurs", {}).items():
            lignes.append((tiers("401", f), ZERO, _d(s)))
        lignes.append(("105", ZERO, _d(o["fonds_travaux"])))
        ecart = sum((l[1] - l[2] for l in lignes), ZERO)
        if ecart:            # ce que les soldes repris n'expliquent pas : à justifier, pas à cacher
            lignes.append(("471", ZERO, ecart) if ecart > 0 else ("471", -ecart, ZERO))
        E.append(_ecriture(o["date"], "Soldes d'ouverture", "AN", lignes, "ouverture"))

    for e in sources.get("dues", []):
        if e["type"] != "appel" or e["date"] < debut:
            continue
        lignes = []
        for x in e["detail"]:
            cpt, contre = _rubrique_compte(x["rubrique"])
            lignes += [(tiers(cpt, e["coproprietaire"]), _d(x["montant"]), ZERO), (contre, ZERO, _d(x["montant"]))]
        E.append(_ecriture(e["date"], e["libelle"], e["id"], lignes, "appel"))

    for a in sources.get("ajustements", []):
        m = _d(a["montant"])
        if a["nature"] == "solde_anterieur" or a["date"] < debut:
            continue                          # repris par les soldes d'ouverture
        cpt, contre = AJUSTEMENTS["avoir" if m < 0 else a["nature"]]
        t = tiers(cpt, a["coproprietaire"])
        lignes = [(t, m, ZERO), (contre, ZERO, m)] if m > 0 else [(contre, -m, ZERO), (t, ZERO, -m)]
        E.append(_ecriture(a["date"], a["libelle"], a["id"], lignes, "ajustement"))

    factures = {f["id"]: f for f in sources.get("factures", [])}
    for f in factures.values():
        if f["date"] < debut:
            continue                          # une facture antérieure non payée se reprend en fournisseur
        m = _d(f["montant"])
        E.append(_ecriture(f["date"], f"{f['fournisseur']} — {f['libelle']}", f["id"],
                           [(f["compte"], m, ZERO), (tiers("401", f["fournisseur"]), ZERO, m)], "facture"))

    rap = {r["operation"]: r for r in sources.get("rapprochement", [])}
    dep = sources.get("depenses", {})
    for op in sources.get("operations", []):
        if op["date"] < debut:
            continue
        m = _d(op["montant"])
        r = rap.get(op["id"], {})
        piece = op["id"]
        if r.get("statut") in ("automatique", "confirme") and r.get("parts"):
            lignes = [("512", m, ZERO) if m > 0 else ("512", ZERO, -m)]
            for p in r["parts"]:
                pm, t = _d(p["montant"]), tiers("4501", p["coproprietaire"])
                lignes.append((t, ZERO, pm) if pm > 0 else (t, -pm, ZERO))
            E.append(_ecriture(op["date"], op["libelle"], piece, lignes, "banque"))
            continue
        if m < 0 and op["id"] in dep:
            a = dep[op["id"]]
            if a.get("facture") in factures:
                contre = tiers("401", factures[a["facture"]]["fournisseur"])
            elif a.get("compte"):
                contre = a["compte"]
            else:
                contre = "471"
            E.append(_ecriture(op["date"], op["libelle"], piece, [(contre, -m, ZERO), ("512", ZERO, -m)], "banque"))
            continue
        # non expliquée : compte d'attente, pour que la banque tombe juste
        lignes = [("512", m, ZERO), ("471", ZERO, m)] if m > 0 else [("471", -m, ZERO), ("512", ZERO, -m)]
        E.append(_ecriture(op["date"], op["libelle"], piece, lignes, "attente"))
    return sorted(E, key=lambda e: (e["date"], {"ouverture": 0}.get(e["source"], 1), e["piece"]))


# --------------------------------------------------------------------------- #
# Balance, grand livre, contrôles
# --------------------------------------------------------------------------- #
def balance(E: list[dict], du: str | None = None, au: str | None = None) -> dict[str, dict]:
    b: dict[str, dict] = defaultdict(lambda: {"debit": ZERO, "credit": ZERO})
    for e in E:
        if (du and e["date"] < du) or (au and e["date"] > au):
            continue
        for l in e["lignes"]:
            b[l["compte"]]["debit"] += l["debit"]
            b[l["compte"]]["credit"] += l["credit"]
    return {c: {**v, "solde": v["debit"] - v["credit"], "libelle": libelle_compte(c)} for c, v in sorted(b.items())}


def grand_livre(E: list[dict], compte: str) -> list[dict]:
    """Les mouvements d'un compte (ou de tous ses sous-comptes : '4501' donne 4501.CP01…)."""
    res, solde = [], ZERO
    for e in E:
        for l in e["lignes"]:
            if l["compte"] == compte or l["compte"].startswith(compte + "."):
                solde += l["debit"] - l["credit"]
                res.append({"date": e["date"], "piece": e["piece"], "libelle": e["libelle"], "compte": l["compte"],
                            "debit": l["debit"], "credit": l["credit"], "solde": solde})
    return res


def controles(E: list[dict], operations: list[dict], ouverture: dict | None) -> list[dict]:
    """Ce qui doit être vrai avant d'arrêter les comptes. Chaque écart est montré, jamais compensé."""
    b = balance(E)
    res = []
    td = sum((v["debit"] for v in b.values()), ZERO)
    tc = sum((v["credit"] for v in b.values()), ZERO)
    res.append({"controle": "Total des débits = total des crédits", "ok": td == tc, "detail": f"{td} / {tc}"})
    debut = ouverture["date"] if ouverture else ""
    banque_releve = (_d(ouverture["banque"]) if ouverture else ZERO) + sum(
        (_d(o["montant"]) for o in operations if o["date"] >= debut), ZERO)
    banque_compta = b.get("512", {}).get("solde", ZERO)
    res.append({"controle": "Compte 512 = solde du relevé", "ok": banque_compta == banque_releve,
                "detail": f"{banque_compta} / {banque_releve}"})
    attente = b.get("471", {}).get("solde", ZERO)
    nb = sum(1 for e in E if e["source"] == "attente")
    res.append({"controle": "Compte d'attente soldé", "ok": attente == 0 and nb == 0,
                "detail": f"{nb} opération(s) à affecter, solde {attente}"})
    if ouverture is None:
        res.append({"controle": "Soldes d'ouverture saisis", "ok": False,
                    "detail": "Reprendre la banque, les comptes des copropriétaires et le fonds de travaux"})
    return res


def etat(fiche: dict, racine_appels: Path, racine_data: Path, copro: str, au: date | None = None) -> dict:
    """Vue complète, à partir des données déjà tenues par Mitoyen."""
    import banque as B
    import impayes as I
    st = charger(racine_data, copro)
    ops = B.charger_operations(racine_data, copro)
    dues = I.echeances(racine_appels, racine_data, copro)
    rap = I.rapprocher(fiche, ops, dues, I.charger_affectations(racine_data, copro))
    E = journal(fiche, {"ouverture": st["ouverture"], "dues": dues, "ajustements": I.charger_ajustements(racine_data, copro),
                        "operations": ops, "rapprochement": rap, "factures": st["factures"], "depenses": st["depenses"]})
    jour = (au or date.today()).isoformat()
    E = [e for e in E if e["date"] <= jour]
    return {"au": jour, "journal": E, "balance": balance(E),
            "controles": controles(E, [o for o in ops if o["date"] <= jour], st["ouverture"])}
