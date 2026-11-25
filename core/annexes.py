"""
annexes.py — Les cinq annexes comptables à joindre à la convocation de l'AG qui approuve les comptes.

Modèles fixés par le décret n° 2005-240 et l'arrêté du 14 mars 2005 :
    1. État financier après répartition, à la date de clôture
    2. Compte de gestion général de l'exercice clos et budget prévisionnel
    3. Compte de gestion pour opérations courantes, par clé de répartition
    4. Compte de gestion pour travaux de l'article 14-2 et opérations exceptionnelles
    5. État des travaux et opérations exceptionnelles votés et non encore clôturés

Tout est recalculé depuis le journal (compta.py) : rien n'est saisi deux fois. Les annexes
présentent les comptes « après répartition » : les charges courantes de l'exercice sont
réparties entre les copropriétaires selon leurs tantièmes, et le solde des travaux reste
en attente (compte 12) jusqu'à la clôture de chaque opération.

⚠️ Mise en forme indicative : à comparer avec les modèles de l'arrêté du 14 mars 2005
(Légifrance). Ce n'est pas un conseil comptable ; l'ADIL renseigne gratuitement.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from compta import ZERO, _d, balance, budgets, charger, compte_charge, controles, libelle_compte
from fiche_copro import repartir

AVERTISSEMENT = ("Annexes établies par Mitoyen à partir du journal tenu par le syndic. Mise en forme indicative : "
                 "à comparer avec les modèles de l'arrêté du 14 mars 2005 (Légifrance). Ce n'est pas un conseil "
                 "comptable ; l'ADIL renseigne gratuitement.")

# Lignes de charges courantes de l'annexe 2, dans l'ordre du modèle
LIGNES_CHARGES = [
    ("601", "Eau"), ("602", "Électricité"), ("603", "Chauffage, énergie et combustibles"),
    ("60X", "Autres achats et fournitures"),
    ("611", "Nettoyage des locaux"), ("612", "Locations immobilières et mobilières"),
    ("614", "Contrats de maintenance"), ("615", "Entretien et petites réparations"),
    ("616", "Primes d'assurances"), ("61X", "Autres services extérieurs"),
    ("621", "Rémunération du syndic sur gestion copropriété"), ("622", "Autres honoraires du syndic"),
    ("62X", "Autres honoraires et frais (tiers, conseil syndical)"),
    ("63", "Impôts, taxes et versements assimilés"), ("64", "Frais de personnel"),
    ("66", "Charges financières (frais bancaires, agios)"), ("6X", "Autres charges"),
]
LIGNES_PRODUITS = [
    ("701", "Provisions sur opérations courantes"), ("711", "Subventions"),
    ("713", "Indemnités d'assurances"), ("714", "Produits divers"), ("716", "Produits financiers"),
    ("7X", "Autres produits"),
]
NOTE_N1 = ("Colonne « N-1 » : l'exercice précédent n'est pas tenu dans Mitoyen. "
           "La reprendre des annexes approuvées à la dernière assemblée générale.")


# --------------------------------------------------------------------------- #
# Périodes et classement des comptes
# --------------------------------------------------------------------------- #
def periode(fiche: dict, exercice: int) -> tuple[str, str]:
    """(premier jour, dernier jour) de l'exercice, nommé par l'année de sa clôture."""
    ex = (fiche.get("gouvernance") or {}).get("exercice") or {"debut": "01-01", "fin": "12-31"}
    md, jd = (int(x) for x in ex["debut"].split("-"))
    mf, jf = (int(x) for x in ex["fin"].split("-"))
    fin = date(exercice, mf, jf)
    debut = date(exercice, md, jd) if (md, jd) <= (mf, jf) else date(exercice - 1, md, jd)
    return debut.isoformat(), fin.isoformat()


def _veille(jour: str) -> str:
    return (date.fromisoformat(jour) - timedelta(days=1)).isoformat()


def groupe_charge(compte: str) -> str:
    c3 = compte.split(".")[0][:3]
    if c3 == "613":
        return "612"
    if c3 in {"601", "602", "603", "611", "612", "614", "615", "616", "621", "622"}:
        return c3
    for p in ("60", "61", "62"):
        if c3.startswith(p):
            return p + "X"
    return c3[:2] if c3[:2] in ("63", "64", "66") else "6X"


def groupe_produit(compte: str) -> str:
    c3 = compte.split(".")[0][:3]
    return c3 if c3 in {"701", "711", "713", "714", "716"} else "7X"


def exceptionnelle(ligne: dict) -> bool:
    """Travaux de l'article 14-2 et opérations exceptionnelles : hors budget prévisionnel."""
    c = ligne["compte"]
    return bool(ligne.get("operation")) or c[:2] in ("67", "68") or c[:3] in ("702", "703", "718")


def _cle_defaut(fiche: dict) -> str:
    cles = list(fiche["cles_repartition"])
    return "generales" if "generales" in cles else cles[0]



def _repartir_signe(montant: Decimal, poids: dict) -> dict:
    """repartir() pour un montant éventuellement négatif (un excédent de produits)."""
    if montant >= 0:
        return repartir(montant, poids)
    return {k: -v for k, v in repartir(-montant, poids).items()}


def _parts_proprietaires(fiche: dict, cle: str, montant: Decimal) -> dict[str, Decimal]:
    """Part de chaque copropriétaire, lot par lot puis additionnée (comme sur les avis)."""
    poids = {l["numero"]: l["tantiemes"].get(cle, 0) for l in fiche["lots"] if l["tantiemes"].get(cle, 0) > 0}
    if not poids or not montant:
        return {}
    res: dict[str, Decimal] = defaultdict(Decimal)
    proprio = {l["numero"]: l["proprietaire"] for l in fiche["lots"]}
    for numero, m in _repartir_signe(montant, poids).items():
        res[proprio[numero]] += m
    return dict(res)


def _copro_de(ecriture: dict) -> str | None:
    """Le copropriétaire d'une écriture d'appel ou d'ajustement (un seul compte 450x.CPxx)."""
    cps = {l["compte"].split(".", 1)[1] for l in ecriture["lignes"]
           if l["compte"].startswith("450") and "." in l["compte"]}
    return cps.pop() if len(cps) == 1 else None


# --------------------------------------------------------------------------- #
# Réalisé d'une période
# --------------------------------------------------------------------------- #
def realise(fiche: dict, E: list[dict], du: str, au: str, cle_par_compte: dict[str, str]) -> dict:
    """Charges et produits de la période, classés comme dans les annexes 2, 3 et 4."""
    defaut = _cle_defaut(fiche)
    r = {"charges": defaultdict(Decimal), "produits": defaultdict(Decimal),
         "charges_cle": defaultdict(Decimal), "produits_cle": defaultdict(Decimal),
         "provisions_cle": defaultdict(Decimal), "provisions_copro": defaultdict(Decimal),
         "x_charges": defaultdict(Decimal), "x_produits": defaultdict(Decimal),
         "x_charges_op": defaultdict(Decimal), "x_provisions_op": defaultdict(Decimal),
         "x_produits_op": defaultdict(Decimal)}
    for e in E:
        if not (du <= e["date"] <= au) or e["source"] == "ouverture":
            continue
        cp = None
        for l in e["lignes"]:
            c = l["compte"]
            if c[0] not in "67":
                continue
            net = l["debit"] - l["credit"]
            if exceptionnelle(l):
                op = l.get("operation") or ""
                if c[0] == "6":
                    r["x_charges"][c.split(".")[0]] += net
                    r["x_charges_op"][op] += net
                else:
                    r["x_produits"][c.split(".")[0]] -= net
                    r["x_provisions_op" if c.startswith("702") else "x_produits_op"][op] -= net
                continue
            if c[0] == "6":
                cle = l.get("cle") or cle_par_compte.get(c.split(".")[0]) or defaut
                cle = cle if cle in fiche["cles_repartition"] else defaut
                r["charges"][groupe_charge(c)] += net
                r["charges_cle"][cle] += net
            else:
                g = groupe_produit(c)
                r["produits"][g] -= net
                if g == "701":
                    cle = l.get("cle") if l.get("cle") in fiche["cles_repartition"] else defaut
                    r["provisions_cle"][cle] -= net
                    cp = cp if cp is not None else (_copro_de(e) or "?")
                    r["provisions_copro"][(cp, cle)] -= net
                else:
                    cle = l.get("cle") if l.get("cle") in fiche["cles_repartition"] else defaut
                    r["produits_cle"][cle] -= net
    return r


def _budget_vers(postes: list[dict] | None, fiche: dict) -> dict | None:
    """Un budget voté, ventilé comme le réalisé (par ligne de charges et par clé)."""
    if postes is None:
        return None
    defaut = _cle_defaut(fiche)
    b = {"charges": defaultdict(Decimal), "charges_cle": defaultdict(Decimal), "produits": defaultdict(Decimal),
         "produits_cle": defaultdict(Decimal), "provisions_cle": defaultdict(Decimal)}
    for p in postes:
        m = _d(p["montant"])
        cle = p.get("cle") if p.get("cle") in fiche["cles_repartition"] else defaut
        b["charges"][groupe_charge(compte_charge(p))] += m
        b["charges_cle"][cle] += m
        b["produits"]["701"] += m          # le budget est appelé en provisions, à l'euro près
        b["provisions_cle"][cle] += m
    return b


def _cle_par_compte(postes: list[dict] | None) -> dict[str, str]:
    res = {}
    for p in postes or []:
        res.setdefault(compte_charge(p), p.get("cle"))
    return res


# --------------------------------------------------------------------------- #
# Les cinq annexes (chacune : titre, colonnes, lignes)
# --------------------------------------------------------------------------- #
def _ligne(libelle, valeurs, compte="", type_="ligne"):
    return {"compte": compte, "libelle": libelle, "valeurs": valeurs, "type": type_}


def annexe_2(fiche, cols: list[dict | None], x_cols: list[dict | None], total_n1_approuve=None) -> dict:
    """cols = [N-1 réalisé, N budget, N réalisé, N+1 budget, N+2 budget] (None : non disponible)."""
    lignes = [_ligne("Charges pour opérations courantes", [], type_="titre")]
    for code, lib in LIGNES_CHARGES:
        v = [c["charges"].get(code, ZERO) if c else None for c in cols]
        if any(x for x in v if x):
            lignes.append(_ligne(lib, v, code))
    tot_ch = [sum(c["charges"].values(), ZERO) if c else None for c in cols]
    if total_n1_approuve is not None and tot_ch[0] is None:
        tot_ch[0] = total_n1_approuve
    lignes.append(_ligne("Total des charges courantes", tot_ch, type_="sous_total"))
    lignes.append(_ligne("Produits pour opérations courantes", [], type_="titre"))
    for code, lib in LIGNES_PRODUITS:
        v = [c["produits"].get(code, ZERO) if c else None for c in cols]
        if code == "701" or any(x for x in v if x):
            lignes.append(_ligne(lib, v, code))
    tot_pr = [sum(c["produits"].values(), ZERO) if c else None for c in cols]
    lignes.append(_ligne("Total des produits courants", tot_pr, type_="sous_total"))
    solde = [None if p is None or ch is None or c is None else p - ch
             for p, ch, c in zip(tot_pr, tot_ch, cols)]
    lignes.append(_ligne("Solde (excédent + / insuffisance −) affecté aux copropriétaires", solde, type_="total"))

    lignes.append(_ligne("Travaux de l'article 14-2 et opérations exceptionnelles (hors budget)", [], type_="titre"))
    comptes_x = sorted({k for c in x_cols if c for k in list(c["x_charges"]) + list(c["x_produits"])})
    for k in [k for k in comptes_x if k.startswith("6")] + [k for k in comptes_x if k.startswith("7")]:
        champ = "x_charges" if k.startswith("6") else "x_produits"
        v = [c[champ].get(k, ZERO) if c else None for c in x_cols]
        if any(x for x in v if x):
            lignes.append(_ligne(libelle_compte(k), v, k))
    xch = [sum(c["x_charges"].values(), ZERO) if c else None for c in x_cols]
    xpr = [sum(c["x_produits"].values(), ZERO) if c else None for c in x_cols]
    lignes.append(_ligne("Total des charges de travaux et opérations exceptionnelles", xch, type_="sous_total"))
    lignes.append(_ligne("Total des produits de travaux et opérations exceptionnelles", xpr, type_="sous_total"))
    lignes.append(_ligne("Solde en attente (voir annexes 4 et 5)",
                         [None if a is None else a - b for a, b in zip(xpr, xch)], type_="total"))
    return {"lignes": lignes}


def annexe_3(fiche, cols: list[dict | None]) -> dict:
    lignes = []
    for cle, info in fiche["cles_repartition"].items():
        ch = [c["charges_cle"].get(cle, ZERO) if c else None for c in cols]
        pr = [c["produits_cle"].get(cle, ZERO) if c else None for c in cols]
        if not any(x for x in ch + pr if x):
            continue
        lignes.append(_ligne(info["libelle"], [], type_="titre"))
        lignes.append(_ligne("Charges", ch))
        lignes.append(_ligne("Produits affectés", pr))
        lignes.append(_ligne("Charges nettes", [None if a is None else a - b for a, b in zip(ch, pr)],
                             type_="sous_total"))
    net = [None if c is None else sum(c["charges_cle"].values(), ZERO) - sum(c["produits_cle"].values(), ZERO)
           for c in cols]
    prov = [None if c is None else sum(c["provisions_cle"].values(), ZERO) for c in cols]
    lignes.append(_ligne("Total des charges nettes", net, type_="sous_total"))
    lignes.append(_ligne("Provisions appelées auprès des copropriétaires", prov, "701"))
    lignes.append(_ligne("Solde (excédent + / insuffisance −)",
                         [None if a is None else b - a for a, b in zip(net, prov)], type_="total"))
    return {"lignes": lignes}


def annexe_4(fiche, ops: list[dict], r: dict, du: str, au: str) -> dict:
    cles = fiche["cles_repartition"]
    lignes = []
    vues = [o for o in ops if o["vote_le"] <= au and not (o.get("cloturee_le") and o["cloturee_le"] < du)]
    ids = [o["id"] for o in vues]
    if any(r[k].get("") for k in ("x_charges_op", "x_provisions_op", "x_produits_op")):
        vues.append({"id": "", "libelle": "Non rattaché à une opération votée (à préciser)", "cle": None,
                     "montant_vote": None})
    autres = set(r["x_charges_op"]) | set(r["x_provisions_op"]) | set(r["x_produits_op"])
    for oid in sorted(autres - set(ids) - {""}):
        vues.append({"id": oid, "libelle": f"Opération {oid}", "cle": None, "montant_vote": None})
    tot = [ZERO, ZERO, ZERO, ZERO]
    for o in vues:
        dep = r["x_charges_op"].get(o["id"], ZERO)
        prov = r["x_provisions_op"].get(o["id"], ZERO) + r["x_produits_op"].get(o["id"], ZERO)
        vote = _d(o["montant_vote"]) if o.get("montant_vote") else None
        cle = cles.get(o.get("cle") or "", {}).get("libelle", "")
        lib = o["libelle"] + (f" — {cle.lower()}" if cle else "")
        lignes.append(_ligne(lib, [vote, dep, prov, prov - dep], o["id"]))
        tot = [a + (b or ZERO) for a, b in zip(tot, [vote, dep, prov, prov - dep])]
    lignes.append(_ligne("Total", tot, type_="total"))
    return {"lignes": lignes, "vide": not vues}


def annexe_5(fiche, ops: list[dict], E: list[dict], au: str) -> dict:
    """Cumul depuis le vote (ou la reprise dans Mitoyen) jusqu'à la clôture de l'exercice."""
    paye, realise_, recu = defaultdict(Decimal), defaultdict(Decimal), defaultdict(Decimal)
    for e in E:
        if e["date"] > au:
            continue
        for l in e["lignes"]:
            op = l.get("operation")
            if not op:
                continue
            if l["compte"].startswith("6"):
                realise_[op] += l["debit"] - l["credit"]
                if e["source"] == "banque":
                    paye[op] += l["debit"] - l["credit"]
            elif l["compte"].startswith("401") and e["source"] == "banque":
                paye[op] += l["debit"] - l["credit"]
            elif l["compte"].startswith("7"):
                recu[op] += l["credit"] - l["debit"]
    lignes, tot = [], [ZERO] * 6
    for o in ops:
        if o["vote_le"] > au or (o.get("cloturee_le") and o["cloturee_le"] <= au):
            continue
        a, b, c, d = _d(o["montant_vote"]), paye[o["id"]], realise_[o["id"]], recu[o["id"]]
        f = _d(o.get("a_recevoir") or 0)
        v = [a, b, c, d, d - c, f]
        lignes.append(_ligne(f"{o['libelle']} (voté le {date.fromisoformat(o['vote_le']):%d/%m/%Y})", v, o["id"]))
        tot = [x + y for x, y in zip(tot, v)]
    lignes.append(_ligne("Total", tot, type_="total"))
    return {"lignes": lignes, "vide": len(lignes) == 1, "solde_attente": tot[4]}


def etat_financier(fiche: dict, E: list[dict], au: str, ouverture: dict | None, x_net: Decimal,
                   courant: dict) -> dict:
    """Annexe 1 à une date : soldes du journal, après répartition des charges courantes
    (courant = réalisé depuis la reprise, par clé et par copropriétaire) et avec le solde
    des travaux en attente (x_net = produits − charges exceptionnels cumulés)."""
    b = balance([e for e in E if e["date"] <= au])
    copros: dict[str, Decimal] = defaultdict(Decimal)
    autres_cr, autres_de = defaultdict(Decimal), defaultdict(Decimal)
    s = lambda pref: sum((v["solde"] for c, v in b.items() if c.split(".")[0].startswith(pref)), ZERO)
    for c, v in b.items():
        if c.startswith("450") and "." in c:
            copros[c.split(".", 1)[1]] += v["solde"]
    # Répartition : chaque copropriétaire supporte sa part des charges nettes de chaque clé,
    # et ses provisions appelées viennent en déduction
    for cle in fiche["cles_repartition"]:
        net = courant["charges_cle"].get(cle, ZERO) - courant["produits_cle"].get(cle, ZERO)
        for cp, m in _parts_proprietaires(fiche, cle, net).items():
            copros[cp] += m
    for (cp, _cle), m in courant["provisions_copro"].items():
        copros[cp] -= m
    for c, v in b.items():
        racine = c.split(".")[0]
        if c[0] in "67" or racine.startswith("450") or racine[:2] in ("10", "12", "13", "50", "51", "53"):
            continue
        groupe = {"401": "Fournisseurs", "408": "Fournisseurs"}.get(racine) or (
            "Compte d'attente (à justifier)" if racine.startswith("47") else
            "Comptes de régularisation" if racine.startswith("48") else "Autres créances et dettes")
        if v["solde"] > 0:
            autres_cr[groupe] += v["solde"]
        elif v["solde"] < 0:
            autres_de[groupe] -= v["solde"]
    debiteurs = {cp: m for cp, m in copros.items() if m > 0}
    crediteurs = {cp: -m for cp, m in copros.items() if m < 0}
    tresorerie = {"50": s("50"), "51": s("51"), "53": s("53")}
    fonds = {"102": -s("102"), "103": -s("103"), "105": -s("105"), "131": -s("131"), "12": x_net - s("12")}
    return {"tresorerie": tresorerie, "fonds": fonds, "debiteurs": debiteurs, "crediteurs": crediteurs,
            "autres_creances": dict(autres_cr), "autres_dettes": dict(autres_de),
            "emprunts": -s("16"),
            "actif": sum(tresorerie.values(), ZERO) + sum(debiteurs.values(), ZERO) + sum(autres_cr.values(), ZERO),
            "passif": sum(fonds.values(), ZERO) + sum(crediteurs.values(), ZERO) + sum(autres_de.values(), ZERO)}


def annexe_1(prec: dict | None, cour: dict) -> dict:
    def v(f):
        return [f(prec) if prec else None, f(cour)]
    L = [_ligne("I. Situation financière et trésorerie", [], type_="titre"),
         _ligne("Trésorerie disponible", [], type_="intertitre")]
    for code, lib in (("50", "Fonds placés"), ("51", "Banques (négatif : découvert)"), ("53", "Caisse")):
        vals = v(lambda x: x["tresorerie"][code])
        if code == "51" or any(vals):
            L.append(_ligne(lib, vals, code))
    L.append(_ligne("Total trésorerie", v(lambda x: sum(x["tresorerie"].values(), ZERO)), type_="sous_total"))
    L.append(_ligne("Fonds et provisions", [], type_="intertitre"))
    for code, lib in (("102", "Provisions pour travaux décidés"), ("103", "Avances"), ("105", "Fonds de travaux"),
                      ("131", "Subventions en instance d'affectation"),
                      ("12", "Solde en attente sur travaux et opérations exceptionnelles")):
        vals = v(lambda x: x["fonds"][code])
        if code in ("105", "12") or any(vals):
            L.append(_ligne(lib, vals, code))
    L.append(_ligne("Total fonds et provisions", v(lambda x: sum(x["fonds"].values(), ZERO)), type_="sous_total"))

    L.append(_ligne("II. Créances et dettes, après répartition", [], type_="titre"))
    L.append(_ligne("Créances", [], type_="intertitre"))
    L.append(_ligne("Copropriétaires : sommes exigibles restant à recevoir (liste jointe)",
                    v(lambda x: sum(x["debiteurs"].values(), ZERO)), "45"))
    groupes = sorted({g for x in (prec, cour) if x for g in x["autres_creances"]})
    for g in groupes:
        L.append(_ligne(g, v(lambda x: x["autres_creances"].get(g, ZERO))))
    L.append(_ligne("Total créances", v(lambda x: sum(x["debiteurs"].values(), ZERO)
                                         + sum(x["autres_creances"].values(), ZERO)), type_="sous_total"))
    L.append(_ligne("Dettes", [], type_="intertitre"))
    L.append(_ligne("Copropriétaires : excédents versés (liste jointe)",
                    v(lambda x: sum(x["crediteurs"].values(), ZERO)), "45"))
    groupes = sorted({g for x in (prec, cour) if x for g in x["autres_dettes"]})
    for g in groupes:
        L.append(_ligne(g, v(lambda x: x["autres_dettes"].get(g, ZERO))))
    L.append(_ligne("Total dettes", v(lambda x: sum(x["crediteurs"].values(), ZERO)
                                       + sum(x["autres_dettes"].values(), ZERO)), type_="sous_total"))
    L.append(_ligne("Total général : trésorerie + créances", v(lambda x: x["actif"]), type_="total"))
    L.append(_ligne("Total général : fonds + dettes", v(lambda x: x["passif"]), type_="total"))
    L.append(_ligne("Emprunts : montant restant dû", v(lambda x: x["emprunts"])))
    return {"lignes": L}


# --------------------------------------------------------------------------- #
# Assemblage
# --------------------------------------------------------------------------- #
def annexes(fiche: dict, E: list[dict], st: dict, exercice: int, operations: list[dict],
            tous_budgets: dict[int, list[dict]], aujourd_hui: date | None = None) -> dict:
    """st = compta.charger() ; E = journal complet ; operations = relevé bancaire (contrôles)."""
    N = int(exercice)
    du, au = periode(fiche, N)
    du1, au1 = periode(fiche, N - 1)
    ouv = st.get("ouverture")
    reprise = ouv["date"] if ouv else None
    jour = (aujourd_hui or date.today()).isoformat()
    ops_votees = st.get("operations_votees") or []

    cpc = _cle_par_compte(tous_budgets.get(N))
    r_n = realise(fiche, E, du, au, cpc)
    n1_tenu = bool(reprise) and reprise <= du1
    r_n1 = realise(fiche, E, du1, au1, _cle_par_compte(tous_budgets.get(N - 1))) if n1_tenu else None
    approuve = fiche.get("comptes_approuves") or {}
    total_n1 = (_d(approuve["charges_courantes"]) if not n1_tenu and str(approuve.get("exercice")) == str(N - 1)
                and approuve.get("charges_courantes") is not None else None)
    budget = {k: _budget_vers(tous_budgets.get(k), fiche) for k in (N, N + 1, N + 2)}
    cols = [r_n1, budget[N], r_n, budget[N + 1], budget[N + 2]]

    # État financier : à la clôture de N, et à celle de N-1 si Mitoyen la connaît
    def _etat(fin: str):
        Ef = [e for e in E if e["date"] <= fin]
        courant = realise(fiche, Ef, reprise or "", fin, cpc)
        xr = realise(fiche, Ef, reprise or "", fin, cpc)
        x_net = sum(xr["x_produits"].values(), ZERO) - sum(xr["x_charges"].values(), ZERO)
        return etat_financier(fiche, Ef, fin, ouv, x_net, courant)
    etat_n = _etat(au)
    etat_n1 = _etat(au1) if reprise and reprise <= (date.fromisoformat(au1) + timedelta(days=1)).isoformat() else None
    if etat_n1 is not None and reprise > au1:      # reprise le lendemain de la clôture : les soldes d'ouverture
        Eo = [dict(e, date=au1) for e in E if e["source"] == "ouverture"]
        etat_n1 = etat_financier(fiche, Eo, au1, ouv, ZERO, realise(fiche, [], au1, au1, {}))

    a5 = annexe_5(fiche, ops_votees, E, au)
    copros = {c["id"]: c.get("nom", c["id"]) for c in fiche.get("coproprietaires", [])}

    ctrl = controles([e for e in E if e["date"] <= au], [o for o in operations if o["date"] <= au], ouv)
    ctrl.append({"controle": "Exercice clos", "ok": au < jour,
                 "detail": f"clôture le {date.fromisoformat(au):%d/%m/%Y}"})
    ctrl.append({"controle": "Exercice entièrement tenu dans Mitoyen", "ok": bool(reprise) and reprise <= du,
                 "detail": f"reprise le {date.fromisoformat(reprise):%d/%m/%Y}" if reprise else "pas de soldes d'ouverture"})
    ecart = etat_n["actif"] - etat_n["passif"]
    ctrl.append({"controle": "Annexe 1 : trésorerie + créances = fonds + dettes", "ok": ecart == 0,
                 "detail": f"écart {ecart}"})
    for k in (N, N + 2):
        if budget[k] is None:
            ctrl.append({"controle": f"Budget {k} enregistré", "ok": False,
                         "detail": "à saisir pour remplir les colonnes budget des annexes 2 et 3"})
    x_libres = sum((v for k, v in r_n["x_charges_op"].items() if not k), ZERO)
    if x_libres:
        ctrl.append({"controle": "Dépenses de travaux rattachées à une opération votée", "ok": False,
                     "detail": f"{x_libres} sans opération (annexe 4)"})

    notes = [] if n1_tenu else [NOTE_N1]
    if total_n1 is not None:
        notes.append(f"Total des charges courantes {N - 1} repris des comptes approuvés le "
                     f"{approuve.get('ag_approbation', '…')}.")
    return {
        "exercice": N, "du": du, "au": au, "controles": ctrl, "pret": all(c["ok"] for c in ctrl),
        "notes": notes, "avertissement": AVERTISSEMENT,
        "annexes": [
            {"numero": 1, "titre": f"État financier après répartition au {date.fromisoformat(au):%d/%m/%Y}",
             "colonnes": [f"Exercice {N - 1} approuvé", f"Exercice {N} clos"], **annexe_1(etat_n1, etat_n),
             "listes": {"debiteurs": [(copros.get(k, k), m) for k, m in sorted(etat_n["debiteurs"].items())],
                        "crediteurs": [(copros.get(k, k), m) for k, m in sorted(etat_n["crediteurs"].items())]}},
            {"numero": 2, "titre": f"Compte de gestion général de l'exercice {N} et budget prévisionnel {N + 2}",
             "colonnes": [f"{N - 1} approuvé", f"{N} budget voté", f"{N} réalisé", f"{N + 1} budget voté",
                          f"{N + 2} budget à voter"],
             **annexe_2(fiche, cols, [r_n1, None, r_n, None, None], total_n1)},
            {"numero": 3, "titre": f"Compte de gestion pour opérations courantes de l'exercice {N} et budget {N + 2}",
             "colonnes": [f"{N - 1} approuvé", f"{N} budget voté", f"{N} réalisé", f"{N + 1} budget voté",
                          f"{N + 2} budget à voter"], **annexe_3(fiche, cols)},
            {"numero": 4, "titre": f"Compte de gestion pour travaux de l'article 14-2 et opérations "
                                   f"exceptionnelles de l'exercice {N}",
             "colonnes": ["Dépenses votées", f"{N} dépenses", f"{N} provisions appelées", "Solde"],
             **annexe_4(fiche, ops_votees, r_n, du, au)},
            {"numero": 5, "titre": "Travaux de l'article 14-2 et opérations exceptionnelles votés, non encore clôturés",
             "colonnes": ["A. Votés", "B. Payés", "C. Réalisés", "D. Appels et subventions reçus",
                          "E = D − C. En attente", "F. Subventions et emprunts à recevoir"], **a5},
        ],
    }


def calculer(fiche: dict, racine_appels: Path, racine_data: Path, copro: str, exercice: int,
             aujourd_hui: date | None = None) -> dict:
    """Les annexes à partir des données tenues par Mitoyen (relevé, appels, factures…)."""
    import banque as B
    import compta
    import impayes as I
    st = charger(racine_data, copro)
    ops = B.charger_operations(racine_data, copro)
    dues = I.echeances(racine_appels, racine_data, copro)
    rap = I.rapprocher(fiche, ops, dues, I.charger_affectations(racine_data, copro))
    E = compta.journal(fiche, {"ouverture": st["ouverture"], "dues": dues,
                               "ajustements": I.charger_ajustements(racine_data, copro), "operations": ops,
                               "rapprochement": rap, "factures": st["factures"], "depenses": st["depenses"]})
    return annexes(fiche, E, st, exercice, ops, budgets(fiche, racine_data, copro), aujourd_hui)


# --------------------------------------------------------------------------- #
# PDF (à joindre à la convocation)
# --------------------------------------------------------------------------- #
def montant(m: Decimal | None, pdf: bool = False) -> str:
    """Montant sans le signe € (les tableaux le précisent une fois). pdf=True : espaces et
    signe moins que les polices standard du PDF savent dessiner."""
    if m is None:
        return "—"
    s = f"{m:,.2f}".replace(",", "\u00a0" if pdf else "\u202f").replace(".", ",")
    return s if pdf else s.replace("-", "\u2212")


def generer_pdf(fiche: dict, res: dict, chemin: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import CondPageBreak, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from avis_appel import ENCRE, FILET, FOND, GRIS, S, CanevasNumerote, tampon

    nom = fiche["copropriete"]["nom"]
    N = res["exercice"]
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm, title=f"Annexes comptables – exercice {N}")
    cel = ParagraphStyle("cel", parent=S["txt"], fontSize=8.5, leading=10.5)
    cel_g = ParagraphStyle("cel_g", parent=cel, fontName="Helvetica-Bold")
    tete = ParagraphStyle("tete", parent=cel, fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=GRIS,
                          alignment=2)
    h = [Paragraph(f"Annexes comptables de l'exercice {N}", S["titre"]),
         Paragraph(f"{nom} · du {date.fromisoformat(res['du']):%d/%m/%Y} au {date.fromisoformat(res['au']):%d/%m/%Y}"
                   " · montants en euros", S["sous"]), Spacer(1, 4 * mm),
         Paragraph("Documents à joindre à la convocation de l'assemblée générale appelée à approuver les comptes "
                   "(décret n° 2005-240 et arrêté du 14 mars 2005).", S["petit"]), Spacer(1, 5 * mm)]

    def table(a):
        n = len(a["colonnes"])
        larg_lib = 174 * mm - n * (22 if n > 3 else 28) * mm
        larg = [larg_lib] + [(174 * mm - larg_lib) / n] * n
        rows = [[Paragraph("", tete)] + [Paragraph(c, tete) for c in a["colonnes"]]]
        style = [("LINEBELOW", (0, 0), (-1, 0), 0.8, ENCRE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("FONT", (1, 1), (-1, -1), "Helvetica", 8.5),
                 ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                 ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
        for i, l in enumerate(a["lignes"], start=1):
            t = l["type"]
            lib = (f"{l['compte']} " if l["compte"] and t == "ligne" else "") + l["libelle"]
            if t in ("titre", "intertitre"):
                rows.append([Paragraph(f"<b>{lib}</b>", cel)] + [""] * n)
                style += [("SPAN", (0, i), (-1, i)), ("TOPPADDING", (0, i), (-1, i), 7 if t == "titre" else 4)]
                if t == "titre":
                    style.append(("LINEBELOW", (0, i), (-1, i), 0.5, ENCRE))
                continue
            rows.append([Paragraph(lib, cel_g if t != "ligne" else cel)] + [montant(x, True) for x in l["valeurs"]])
            if t == "ligne":
                style.append(("LINEBELOW", (0, i), (-1, i), 0.3, FILET))
            else:
                style += [("FONT", (1, i), (-1, i), "Helvetica-Bold", 8.5), ("LINEABOVE", (0, i), (-1, i), 0.6, ENCRE)]
                if t == "total":
                    style.append(("BACKGROUND", (0, i), (-1, i), FOND))
        tb = Table(rows, colWidths=larg, repeatRows=1)
        tb.setStyle(TableStyle(style))
        return tb

    for i, a in enumerate(res["annexes"]):
        if i:
            h.append(PageBreak())
        h += [Paragraph(f"Annexe {a['numero']}", S["petit"]),
              Paragraph(a["titre"], ParagraphStyle("t2", parent=S["titre"], fontSize=13.5, leading=17)),
              Spacer(1, 3 * mm)]
        if a.get("vide"):
            h.append(Paragraph("Néant : aucun travaux ni opération exceptionnelle à présenter.", S["txt"]))
        else:
            h.append(table(a))
        if a["numero"] == 1:
            for titre, cle in (("Copropriétaires débiteurs (sommes exigibles restant à recevoir)", "debiteurs"),
                               ("Copropriétaires créditeurs (excédents versés)", "crediteurs")):
                liste = a["listes"][cle]
                h += [CondPageBreak(30 * mm), Spacer(1, 5 * mm), Paragraph(f"<b>Liste jointe — {titre}</b>", cel)]
                if not liste:
                    h.append(Paragraph("Néant.", cel))
                    continue
                rows = [[n_, montant(m, True)] for n_, m in liste] + [["Total", montant(sum((m for _, m in liste), ZERO), True)]]
                tb = Table(rows, colWidths=[134 * mm, 40 * mm])
                tb.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
                                        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8.5),
                                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                                        ("LINEBELOW", (0, 0), (-1, -2), 0.3, FILET),
                                        ("LINEABOVE", (0, -1), (-1, -1), 0.6, ENCRE),
                                        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
                h.append(tb)
        if a["numero"] in (2, 3):
            for n_ in res["notes"]:
                h += [Spacer(1, 3 * mm), Paragraph(n_, S["petit"])]

    h += [Spacer(1, 8 * mm), Paragraph(res["avertissement"], S["petit"])]
    syndic = (fiche.get("gouvernance") or {}).get("syndic") or {}
    nom_syndic = next((c.get("nom") for c in fiche.get("coproprietaires", [])
                       if c["id"] == syndic.get("coproprietaire_id")), None)
    h += [Spacer(1, 3 * mm), Paragraph(f"Établi par le syndic{' : ' + nom_syndic if nom_syndic else ''}, "
                                       f"le ____ / ____ / ________. Signature :", S["txt"])]
    pied = f"{nom} – Annexes comptables {N}"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(not res["pret"], pied),
              onLaterPages=tampon(not res["pret"], pied))
    return chemin
