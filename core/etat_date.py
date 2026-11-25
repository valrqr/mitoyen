"""
etat_date.py — La vente d'un lot, côté syndic : état daté, certificat de l'article 20, suivi de la mutation.

    1. COMPTES DU VENDEUR pour le pré-état daté (art. L. 721-2 du CCH) : charges des deux
       derniers exercices, sommes dues, état global des impayés et des dettes fournisseurs.
       Calculés depuis le journal (compta.py) : plus de rubrique « à compléter » quand
       l'exercice est tenu dans Mitoyen.
    2. ÉTAT DATÉ (décret n° 67-223 du 17 mars 1967, art. 5), à la date de la vente :
         1re partie — sommes dues par le vendeur au syndicat
         2e partie  — sommes dues par le syndicat au vendeur
         3e partie  — sommes qui incomberont à l'acquéreur
         annexe     — quote-part des lots dans les budgets des deux derniers exercices,
                      procédures en cours
    3. CERTIFICAT DE L'ARTICLE 20 (loi du 10 juillet 1965) quand le vendeur ne doit rien ;
       sinon, le DÉCOMPTE des créances liquides et exigibles qui servira, le cas échéant,
       à l'opposition (15 jours après réception de l'avis de mutation, par commissaire de justice).
    4. SUIVI : la vente enregistrée, la date de l'avis de mutation, le délai d'opposition.

Un syndic bénévole n'étant pas rémunéré, Mitoyen ne facture rien pour ces documents.

⚠️ Aide à la préparation, à comparer avec les textes sur Légifrance. Le notaire vérifie le
dossier ; ce n'est pas un conseil juridique. L'ADIL renseigne gratuitement.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from compta import ZERO, _d, balance, charger as charger_compta
from fiche_copro import appel_par_lot, repartir

AVERTISSEMENT = ("Document préparé avec Mitoyen à partir des comptes tenus par le syndic. Contenu établi d'après "
                 "l'article 5 du décret du 17 mars 1967 : à comparer avec le texte sur Légifrance. Le notaire "
                 "vérifie le dossier ; ce n'est pas un conseil juridique. L'ADIL renseigne gratuitement.")
DELAI_OPPOSITION = 15          # jours à compter de la réception de l'avis de mutation (loi 1965, art. 20)


class EtatDateInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Outils
# --------------------------------------------------------------------------- #
def lots_du_vendeur(fiche: dict, numeros: list[int]) -> tuple[str, list[dict]]:
    from vente import VenteInvalide, lots_vendus
    try:
        return lots_vendus(fiche, numeros)
    except VenteInvalide as e:
        raise EtatDateInvalide(str(e)) from e


def part_lots(fiche: dict, nums: set[int], montant: Decimal, cle: str) -> Decimal:
    """Part exacte de ces lots dans un montant réparti lot par lot (comme sur les avis)."""
    poids = {l["numero"]: l["tantiemes"].get(cle, 0) for l in fiche["lots"] if l["tantiemes"].get(cle, 0) > 0}
    if not poids or not montant:
        return ZERO
    signe = 1 if montant > 0 else -1
    return signe * sum((m for n, m in repartir(abs(montant), poids).items() if n in nums), ZERO)


def exercice_de(fiche: dict, jour: date) -> int:
    """L'exercice (nommé par l'année de sa clôture) qui contient ce jour."""
    import annexes
    for n in (jour.year, jour.year + 1):
        du, au = annexes.periode(fiche, n)
        if du <= jour.isoformat() <= au:
            return n
    return jour.year


def _fr(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


# --------------------------------------------------------------------------- #
# 1. Comptes du vendeur (pré-état daté)
# --------------------------------------------------------------------------- #
def charges_exercice(fiche: dict, E: list[dict], ouverture: dict | None, nums: set[int], exercice: int,
                     budgets: dict, operations_votees: list[dict]) -> dict | None:
    """Quote-part réelle des lots dans les charges d'un exercice clos (après répartition) ;
    None si l'exercice n'est pas entièrement tenu dans Mitoyen."""
    import annexes
    du, au = annexes.periode(fiche, exercice)
    if not ouverture or ouverture["date"] > du:
        return None
    r = annexes.realise(fiche, E, du, au, annexes._cle_par_compte(budgets.get(exercice)))
    budget = sum((part_lots(fiche, nums, r["charges_cle"].get(k, ZERO) - r["produits_cle"].get(k, ZERO), k)
                  for k in fiche["cles_repartition"]), ZERO)
    cle_op = {o["id"]: o["cle"] for o in operations_votees}
    defaut = annexes._cle_defaut(fiche)
    hors = sum((part_lots(fiche, nums, m, cle_op.get(op) or defaut) for op, m in r["x_charges_op"].items()), ZERO)
    return {"exercice": exercice, "budget": budget, "hors_budget": hors}


def creances_vendeur(fiche: dict, E: list[dict], cid: str, jour: date) -> dict:
    """Ce que le copropriétaire doit encore, mouvement par mouvement. Ses paiements apurent
    d'abord les dettes les plus anciennes, tous comptes confondus (c'est une même personne).
    Renvoie les sommes restant dues, chacune avec sa nature et son exercice d'origine, et ce
    qu'il a versé au-delà (solde créditeur)."""
    j = jour.isoformat()
    debits, credits = [], ZERO
    for e in sorted((e for e in E if e["date"] <= j), key=lambda e: (e["source"] != "ouverture", e["date"])):
        for l in e["lignes"]:
            racine, _, aux = l["compte"].partition(".")
            if aux != cid or not racine.startswith("450"):
                continue
            if l["debit"]:
                # un solde repris à l'ouverture date d'avant la reprise
                jour_origine = date.fromisoformat(e["date"]) - timedelta(days=1 if e["source"] == "ouverture" else 0)
                debits.append({"date": e["date"], "racine": racine, "montant": l["debit"], "piece": e["piece"],
                               "libelle": e["libelle"], "exercice": exercice_de(fiche, jour_origine)})
            credits += l["credit"]
    for d in debits:
        pris = min(d["montant"], credits)
        credits -= pris
        d["reste"] = d["montant"] - pris
    return {"dues": [d for d in debits if d["reste"] > 0], "credit": credits}

def comptes_vendeur(fiche: dict, E: list[dict], st: dict, budgets: dict, numeros: list[int],
                    jour: date) -> dict:
    """Ce que le pré-état daté demandait « à compléter », tiré du journal quand c'est possible."""
    import annexes
    cid, lots = lots_du_vendeur(fiche, numeros)
    nums = {l["numero"] for l in lots}
    N = exercice_de(fiche, jour)
    ouv = st.get("ouverture")
    charges = [c for c in (charges_exercice(fiche, E, ouv, nums, n, budgets, st.get("operations_votees") or [])
                           for n in (N - 2, N - 1)) if c]
    res: dict = {"charges_payees": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in c.items()}
                                    for c in charges]}
    if ouv and ouv["date"] <= jour.isoformat():
        cr = creances_vendeur(fiche, E, cid, jour)
        res["impayes_vendeur"] = str(sum((d["reste"] for d in cr["dues"]), ZERO))
    # État global au dernier exercice clos tenu dans Mitoyen
    du1, au1 = annexes.periode(fiche, N - 1)
    if ouv and ouv["date"] <= (date.fromisoformat(au1) + timedelta(days=1)).isoformat():
        b = balance([e for e in E if e["date"] <= au1])
        par_copro = defaultdict(Decimal)
        for c, v in b.items():
            if c.startswith("450") and "." in c:
                par_copro[c.split(".", 1)[1]] += v["solde"]
        res["etat_global"] = {
            "exercice": N - 1, "au": au1,
            "impayes": str(sum((m for m in par_copro.values() if m > 0), ZERO)),
            "dettes_fournisseurs": str(-sum((v["solde"] for c, v in b.items()
                                             if c.split(".")[0] in ("401", "408") and v["solde"] < 0), ZERO)),
            "source": "comptabilité tenue dans Mitoyen (soldes à la clôture, avant répartition)"}
    return res


# --------------------------------------------------------------------------- #
# 2. État daté
# --------------------------------------------------------------------------- #
def _poids_lots(fiche: dict, cid: str) -> dict[int, int]:
    """Poids de chaque lot du vendeur : sa part de l'appel de fonds (en centimes). Sert à
    ventiler par lot ce que doit le copropriétaire, « d'une manière même approximative »."""
    par_lot = appel_par_lot(fiche)
    poids = {l["numero"]: 0 for l in fiche["lots"] if l["proprietaire"] == cid}
    for (_rid, n), m in par_lot.items():
        if n in poids:
            poids[n] += int(m * 100)
    if not any(poids.values()):
        poids = {n: 1 for n in poids}
    return poids


def _ventiler(montant: Decimal, poids: dict[int, int]) -> dict[int, Decimal]:
    if not montant:
        return {n: ZERO for n in poids}
    return {n: m for n, m in repartir(montant, {k: v for k, v in poids.items() if v}).items()} | \
        {n: ZERO for n, v in poids.items() if not v}


def _appels_a_echoir(fiche: dict, budgets: dict, nums: set[int], jour: date) -> dict:
    """Provisions de l'exercice en cours pas encore exigibles, par lot : elles incomberont à
    l'acquéreur, copropriétaire à leur date d'exigibilité (décret 1967, art. 6-2)."""
    import annexes
    N = exercice_de(fiche, jour)
    adf = fiche["appels_de_fonds"]
    nb = len(adf["dates_exigibilite"])
    budget, fonds = defaultdict(Decimal), defaultdict(Decimal)     # par appel, par lot
    if fiche["budget_previsionnel"].get("exercice") == N:
        for (rid, n), m in appel_par_lot(fiche).items():
            if n in nums:
                (fonds if rid == "fonds_travaux" else budget)[n] += m
        source = "budget voté"
    elif budgets.get(N):
        par_cle = defaultdict(Decimal)
        for p in budgets[N]:
            par_cle[p["cle"]] += _d(p["montant"])
        for n in nums:
            budget[n] = sum((part_lots(fiche, {n}, m, k) for k, m in par_cle.items()), ZERO) / nb
            ft = fiche["fonds_travaux"]
            fonds[n] = part_lots(fiche, {n}, _d(ft["cotisation_annuelle"]), ft["cle"]) / nb
        source = f"budget {N} enregistré"
    else:
        return {"dates": [], "budget": {}, "fonds": {}, "source": None}
    du = annexes.periode(fiche, N)[0]
    annee = int(du[:4])
    dates = []
    for mmjj in adf["dates_exigibilite"]:
        d = date(annee if f"{annee}-{mmjj}" >= du else annee + 1, *(int(x) for x in mmjj.split("-")))
        if d > jour:
            dates.append(d.isoformat())
    k = len(dates)
    q = Decimal("0.01")
    return {"dates": dates, "source": source,
            "budget": {n: (budget[n] * k).quantize(q) for n in nums},
            "fonds": {n: (fonds[n] * k).quantize(q) for n in nums}}


def _travaux_a_appeler(fiche: dict, E: list[dict], operations: list[dict], nums: set[int], jour: str) -> list[dict]:
    """Travaux votés pas encore entièrement appelés : estimation de la part de chaque lot."""
    appele = defaultdict(Decimal)
    for e in E:
        if e["date"] > jour:
            continue
        for l in e["lignes"]:
            if l.get("operation") and l["compte"].startswith("702"):
                appele[l["operation"]] += l["credit"] - l["debit"]
    res = []
    for o in operations:
        if o["vote_le"] > jour or o.get("cloturee_le"):
            continue
        reste = _d(o["montant_vote"]) - appele[o["id"]]
        if reste > 0:
            res.append({"libelle": o["libelle"], "vote_le": o["vote_le"], "reste": reste,
                        "par_lot": {n: part_lots(fiche, {n}, reste, o["cle"]) for n in nums}})
    return res


def _ligne(ref: str, libelle: str, valeurs: dict | None, nums: list[int], suivi: bool = True) -> dict:
    """Une rubrique de l'état daté, lot par lot. suivi=False : non tenue par Mitoyen (affichée « — »)."""
    v = {n: (valeurs or {}).get(n, ZERO) for n in nums} if suivi else {n: None for n in nums}
    return {"ref": ref, "libelle": libelle, "par_lot": v, "suivi": suivi,
            "total": sum((x for x in v.values() if x is not None), ZERO) if suivi else None}


def etat_date(fiche: dict, E: list[dict], st: dict, budgets: dict, numeros: list[int], jour: date,
              procedures: str = "", acquereur: str = "") -> dict:
    """État daté selon l'article 5 du décret du 17 mars 1967, rubrique par rubrique et lot par lot."""
    cid, lots = lots_du_vendeur(fiche, numeros)
    nums = sorted(l["numero"] for l in lots)
    ouv = st.get("ouverture")
    if not ouv or ouv["date"] > jour.isoformat():
        raise EtatDateInvalide("Les comptes ne sont pas tenus dans Mitoyen à cette date : saisir d'abord les "
                               "soldes d'ouverture (Comptabilité)")
    vendeur = next(c for c in fiche["coproprietaires"] if c["id"] == cid)
    N = exercice_de(fiche, jour)
    poids = _poids_lots(fiche, cid)
    autres_lots = sorted(n for n in poids if n not in nums)

    # 1re partie : ce que doit le vendeur, par nature, ventilé entre tous ses lots
    cr = creances_vendeur(fiche, E, cid, jour)
    nature = defaultdict(Decimal)
    for d in cr["dues"]:
        if d["racine"] == "4505":
            nature["fonds"] += d["reste"]
        elif d["racine"] == "4503":
            nature["avances"] += d["reste"]
        elif d["exercice"] < N:
            nature["anterieur"] += d["reste"]
        else:
            nature["hors_budget" if d["racine"] == "4502" else "budget"] += d["reste"]
    v = {k: _ventiler(m, poids) for k, m in nature.items()}
    p1 = [_ligne("a", "Provisions exigibles du budget prévisionnel", v.get("budget"), nums),
          _ligne("b", "Provisions exigibles des dépenses non comprises dans le budget prévisionnel",
                 v.get("hors_budget"), nums),
          _ligne("c", "Charges impayées sur les exercices antérieurs", v.get("anterieur"), nums),
          _ligne("d", "Sommes mentionnées à l'article 33 de la loi du 10 juillet 1965", None, nums, False),
          _ligne("e", "Avances exigibles", v.get("avances"), nums),
          _ligne("f", "Montant restant dû au titre de l'emprunt collectif (art. 26-4 de la loi)", None, nums, False),
          _ligne("g", "Montant versé par l'établissement de cautionnement (art. 26-7 et 26-12 de la loi)",
                 None, nums, False),
          _ligne("", "Cotisations exigibles au fonds de travaux (art. 14-2-1 de la loi)", v.get("fonds"), nums)]
    du_compte = sum(nature.values(), ZERO)          # tout le compte du vendeur, y compris ses autres lots

    # 2e partie : ce que le syndicat pourrait devoir au vendeur
    import annexes
    b = balance([e for e in E if e["date"] <= jour.isoformat()])
    avances_syndicat = -sum((x["solde"] for c, x in b.items() if c.split(".")[0] == "103"), ZERO)
    defaut = annexes._cle_defaut(fiche)
    avances = {n: part_lots(fiche, {n}, avances_syndicat, defaut) for n in nums} if avances_syndicat > 0 else {}
    p2 = [_ligne("a", "Avances mentionnées à l'article 45-1 du décret", avances, nums),
          _ligne("b", "Provisions des périodes postérieures rendues exigibles par la déchéance du terme "
                      "(art. 19-2 de la loi)", None, nums, False)]

    # 3e partie : ce qui incombera à l'acquéreur
    ech = _appels_a_echoir(fiche, budgets, set(nums), jour)
    travaux = _travaux_a_appeler(fiche, E, st.get("operations_votees") or [], set(nums), jour.isoformat())
    hors = {n: sum((t["par_lot"][n] for t in travaux), ZERO) for n in nums}
    p3 = [_ligne("a", "Reconstitution des avances mentionnées à l'article 45-1 du décret", avances, nums),
          _ligne("b", "Provisions non encore exigibles du budget prévisionnel", ech["budget"], nums),
          _ligne("c", "Provisions non encore exigibles des dépenses non comprises dans le budget prévisionnel "
                      "(travaux votés restant à appeler, estimation)", hors, nums),
          _ligne("", "Cotisations non encore exigibles au fonds de travaux", ech["fonds"], nums)]

    # Annexe : quote-part des lots dans le budget et dans le total des dépenses hors budget, N-2 et N-1
    annexe = []
    cle_op = {o["id"]: o["cle"] for o in st.get("operations_votees") or []}
    for n_ex in (N - 2, N - 1):
        postes = budgets.get(n_ex)
        budget_lots = None
        if postes:
            par_cle = defaultdict(Decimal)
            for p in postes:
                par_cle[p["cle"]] += _d(p["montant"])
            budget_lots = {n: sum((part_lots(fiche, {n}, m, k) for k, m in par_cle.items()), ZERO) for n in nums}
        du_, au_ = annexes.periode(fiche, n_ex)
        hors_lots = None
        if ouv["date"] <= du_:
            r = annexes.realise(fiche, E, du_, au_, {})
            hors_lots = {n: sum((part_lots(fiche, {n}, m, cle_op.get(op) or defaut)
                                 for op, m in r["x_charges_op"].items()), ZERO) for n in nums}
        annexe.append({"exercice": n_ex, "budget": budget_lots, "hors_budget": hors_lots})

    def total(p):
        return sum((l["total"] for l in p if l["total"] is not None), ZERO)
    return {
        "etabli_le": jour.isoformat(), "exercice": N,
        "vendeur": {"id": cid, "nom": vendeur["nom"]}, "acquereur": acquereur.strip()[:120],
        "lots": [{"numero": l["numero"], "type": l["type"], "desc": l.get("desc", "")} for l in lots],
        "autres_lots_du_vendeur": autres_lots,
        "partie_1": p1, "total_1": total(p1), "du_compte": du_compte, "creances": cr["dues"],
        "solde_crediteur": cr["credit"],
        "partie_2": p2, "total_2": total(p2),
        "partie_3": p3, "total_3": total(p3), "appels_a_echoir": ech["dates"], "travaux_a_appeler": travaux,
        "annexe": annexe, "procedures": procedures.strip()[:2000] or "Aucune procédure en cours connue du syndic.",
        "libre": du_compte == 0, "avertissement": AVERTISSEMENT,
    }


def decompte_opposition(fiche: dict, ed: dict) -> list[dict]:
    """Les créances du syndicat classées comme l'exige une opposition (décret 1967, art. 5-1) :
    année courante et deux dernières années échues, puis les deux années antérieures, puis le reste."""
    N = ed["exercice"]
    groupes = [("1°", "Année courante et deux dernières années échues", lambda x: x >= N - 2),
               ("2°", "Deux années antérieures aux deux dernières années échues", lambda x: N - 4 <= x < N - 2),
               ("3°", "Créances garanties par une hypothèque légale, non comprises ci-dessus", lambda x: False),
               ("4°", "Autres créances", lambda x: x < N - 4)]
    noms = {"4501": "provisions du budget", "4502": "travaux et opérations exceptionnelles",
            "4503": "avances", "4505": "fonds de travaux"}
    res = []
    for ref, lib, test in groupes:
        lignes = [{"cause": f"{d['libelle']} — {noms.get(d['racine'], d['racine'])}", "exercice": d["exercice"],
                   "date": d["date"], "montant": d["reste"]} for d in ed["creances"] if test(d["exercice"])]
        res.append({"ref": ref, "libelle": lib, "lignes": lignes, "total": sum((x["montant"] for x in lignes), ZERO),
                    "suivi": ref != "3°"})
    return res

# --------------------------------------------------------------------------- #
# 3 et 4. Suivi de la vente
# --------------------------------------------------------------------------- #
def _fichier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "compta" / "mutations.json"


def charger_mutations(racine: Path, copro: str) -> list[dict]:
    f = _fichier(racine, copro)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []


def _sauver(racine: Path, copro: str, liste: list[dict]) -> None:
    f = _fichier(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(liste, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def enregistrer_vente(racine: Path, copro: str, fiche: dict, numeros: list[int], date_acte: date,
                      acquereur: str = "", notaire: str = "") -> dict:
    cid, lots = lots_du_vendeur(fiche, numeros)
    liste = charger_mutations(racine, copro)
    m = {"id": f"M{len(liste) + 1:03d}", "lots": sorted(l["numero"] for l in lots), "vendeur": cid,
         "acquereur": acquereur.strip()[:120], "notaire": notaire.strip()[:120],
         "date_acte": date_acte.isoformat(), "avis_recu_le": None, "fiche_mise_a_jour": False}
    _sauver(racine, copro, liste + [m])
    return m


def avis_de_mutation(racine: Path, copro: str, mid: str, recu_le: date) -> dict:
    liste = charger_mutations(racine, copro)
    for m in liste:
        if m["id"] == mid:
            m["avis_recu_le"] = recu_le.isoformat()
            _sauver(racine, copro, liste)
            return m
    raise EtatDateInvalide(f"Vente inconnue : {mid}")


def marquer_fiche_a_jour(racine: Path, copro: str, mid: str) -> dict:
    liste = charger_mutations(racine, copro)
    for m in liste:
        if m["id"] == mid:
            m["fiche_mise_a_jour"] = True
            _sauver(racine, copro, liste)
            return m
    raise EtatDateInvalide(f"Vente inconnue : {mid}")


def suivi(m: dict, jour: date, du_vendeur: Decimal | None = None) -> dict:
    """Ce qu'il reste à faire après la vente, avec le délai d'opposition. du_vendeur : ce que le
    vendeur devait à la date de l'acte (None si inconnu)."""
    limite = (date.fromisoformat(m["avis_recu_le"]) + timedelta(days=DELAI_OPPOSITION)).isoformat() \
        if m.get("avis_recu_le") else None
    etapes = [
        {"texte": "Avis de mutation reçu du notaire", "fait": bool(m.get("avis_recu_le")),
         "detail": f"reçu le {_fr(m['avis_recu_le'])}" if m.get("avis_recu_le") else
         "si le vendeur n'a pas présenté le certificat de l'article 20, le notaire l'envoie en recommandé"},
        {"texte": "Opposition au versement du prix : inutile, le vendeur ne devait rien à la date de l'acte",
         "fait": True, "detail": "aucune démarche"} if du_vendeur == 0 else
        {"texte": "Opposition au versement du prix" + (f" pour {_m(du_vendeur)}" if du_vendeur else
                                                       ", si le vendeur doit encore des sommes"),
         "fait": bool(limite and limite < jour.isoformat()),
         "detail": (f"au plus tard le {_fr(limite)}, par acte d'un commissaire de justice, avec le décompte"
                    if limite else "délai de 15 jours à compter de la réception de l'avis")},
        {"texte": "Nouveau copropriétaire inscrit dans la fiche (lots, coordonnées, mode d'envoi)",
         "fait": bool(m.get("fiche_mise_a_jour")),
         "detail": "les appels exigibles après la vente lui seront adressés"},
    ]
    return {**m, "limite_opposition": limite, "du_vendeur": du_vendeur,
            "jours_restants": (date.fromisoformat(limite) - jour).days if limite else None, "etapes": etapes}


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def _pdf_base(chemin: Path, titre: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                             topMargin=20 * mm, bottomMargin=20 * mm, title=titre)


def _m(x: Decimal | None) -> str:
    from annexes import montant
    return montant(x, True) + " €" if x is not None else "non tenu dans Mitoyen"


def _colonnes_lots(ed: dict) -> list[list[int]]:
    """Les lots par groupes de 3 colonnes (le dernier groupe porte aussi le total)."""
    nums = [l["numero"] for l in ed["lots"]]
    return [nums[k:k + 3] for k in range(0, len(nums), 3)]


def generer_etat_date(fiche: dict, ed: dict, chemin: Path) -> Path:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer

    from avis_appel import S, CanevasNumerote, tableau, tampon
    nom = fiche["copropriete"]["nom"]
    lots_txt = ", ".join(f"lot {l['numero']} ({l['desc'] or l['type']})" for l in ed["lots"])
    cel = ParagraphStyle("cel_ed", parent=S["txt"], fontSize=9, leading=11.5)
    doc = _pdf_base(chemin, f"État daté – {nom}")
    h = [Paragraph("État daté", S["titre"]),
         Paragraph(f"{nom} · établi le {_fr(ed['etabli_le'])}", S["sous"]), Spacer(1, 4 * mm),
         Paragraph(f"<b>Copropriétaire cédant :</b> {ed['vendeur']['nom']} · <b>Lots :</b> {lots_txt}"
                   + (f" · <b>Acquéreur :</b> {ed['acquereur']}" if ed["acquereur"] else ""), S["txt"]),
         Paragraph("Décret n° 67-223 du 17 mars 1967, article 5. Sommes indiquées d'une manière même approximative "
                   "et sous réserve de l'apurement des comptes.", S["petit"]), Spacer(1, 5 * mm)]
    groupes = _colonnes_lots(ed)

    def partie(titre, lignes, libelle_total):
        blocs = [Paragraph(f"<b>{titre}</b>", S["txt"]), Spacer(1, 1.5 * mm)]
        for k, g in enumerate(groupes):
            dernier = k == len(groupes) - 1
            cols = [f"Lot {n}" for n in g] + (["Total"] if dernier and len(ed["lots"]) > 1 else [])
            donnees = [[""] + cols]
            for l in lignes:
                lib = (f"{l['ref']}) " if l["ref"] else "") + l["libelle"] + ("" if l["suivi"] else " *")
                vals = [_m(l["par_lot"][n]) if l["suivi"] else "—" for n in g]
                if len(cols) > len(g):
                    vals.append(_m(l["total"]) if l["suivi"] else "—")
                donnees.append([Paragraph(lib, cel)] + vals)
            tot = [_m(sum((l["par_lot"][n] for l in lignes if l["suivi"]), ZERO)) for n in g]
            if len(cols) > len(g):
                tot.append(_m(sum((l["total"] for l in lignes if l["suivi"]), ZERO)))
            donnees.append([libelle_total] + tot)
            larg_v = 30 * mm
            blocs += [tableau(donnees, [174 * mm - larg_v * len(cols)] + [larg_v] * len(cols),
                              aligner_droite_depuis=1, serre=True), Spacer(1, 2 * mm)]
        return KeepTogether(blocs + [Spacer(1, 3 * mm)])

    h.append(partie("1re partie — Sommes pouvant rester dues au syndicat par le copropriétaire cédant",
                    ed["partie_1"], "Total"))
    if ed["autres_lots_du_vendeur"]:
        h += [Paragraph(f"Le cédant conserve d'autres lots ({', '.join(map(str, ed['autres_lots_du_vendeur']))}) : "
                        "ce qu'il doit est ventilé entre tous ses lots au prorata de leurs appels de fonds. "
                        f"Total dû sur son compte : {_m(ed['du_compte'])}.", S["petit"]), Spacer(1, 3 * mm)]
    h.append(partie("2e partie — Sommes dont le syndicat pourrait être débiteur à l'égard du copropriétaire cédant",
                    ed["partie_2"], "Total"))
    if ed["solde_crediteur"] > 0:
        h += [Paragraph(f"Pour information : le compte du cédant présente un solde créditeur de "
                        f"{_m(ed['solde_crediteur'])} (sommes versées d'avance), à régulariser.", S["petit"]),
              Spacer(1, 3 * mm)]
    h.append(partie("3e partie — Sommes qui devraient incomber au nouveau copropriétaire", ed["partie_3"], "Total"))
    if ed["appels_a_echoir"]:
        h += [Paragraph("Provisions non encore exigibles : échéances du "
                        + ", ".join(_fr(d) for d in ed["appels_a_echoir"]) + ". Elles sont dues par celui qui est "
                        "copropriétaire à leur date d'exigibilité (décret du 17 mars 1967, art. 6-2).", S["petit"]),
              Spacer(1, 3 * mm)]

    nums = [l["numero"] for l in ed["lots"]]
    donnees = [["Exercice", "Lot", "Budget prévisionnel", "Dépenses hors budget"]]
    for a in ed["annexe"]:
        for n in nums:
            donnees.append([str(a["exercice"]), str(n),
                            _m(a["budget"][n]) if a["budget"] else "budget non enregistré",
                            _m(a["hors_budget"][n]) if a["hors_budget"] else "non tenu dans Mitoyen"])
    h.append(KeepTogether([Paragraph("<b>Annexe à la troisième partie — Quote-part de chaque lot dans le budget "
                                     "prévisionnel et dans le total des dépenses hors budget des deux exercices "
                                     "précédents</b>", S["txt"]), Spacer(1, 1.5 * mm),
                           tableau(donnees, [24 * mm, 16 * mm, 67 * mm, 67 * mm], aligner_droite_depuis=2,
                                   lignes_total=0, serre=True), Spacer(1, 4 * mm),
                           Paragraph("<b>Procédures en cours dans lesquelles le syndicat est partie</b>", S["txt"]),
                           Paragraph(ed["procedures"].replace("\n", "<br/>"), S["txt"])]))
    h += [Spacer(1, 6 * mm),
          Paragraph("* Rubrique que Mitoyen ne suit pas (paiement échelonné de l'article 33, emprunt collectif, "
                    "cautionnement, déchéance du terme) : à compléter par le syndic s'il y a lieu.", S["petit"]),
          Spacer(1, 3 * mm), Paragraph(ed["avertissement"], S["petit"]), Spacer(1, 3 * mm),
          Paragraph("Établi sans honoraires par le syndic bénévole. Date et signature du syndic :", S["txt"])]
    pied = f"{nom} – État daté"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


def generer_certificat(fiche: dict, ed: dict, chemin: Path) -> Path:
    """Cédant à jour : certificat de l'article 20. Sinon : décompte des créances, classé comme
    l'exige une opposition (décret 1967, art. 5-1)."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer

    from avis_appel import S, CanevasNumerote, tableau, tampon
    nom = fiche["copropriete"]["nom"]
    lots = ", ".join(str(l["numero"]) for l in ed["lots"])
    cel = ParagraphStyle("cel_dec", parent=S["txt"], fontSize=9, leading=11.5)
    if ed["libre"]:
        titre = "Certificat de l'article 20"
        doc = _pdf_base(chemin, f"{titre} – {nom}")
        h = [Paragraph(titre, S["titre"]), Paragraph(f"{nom} · loi n° 65-557 du 10 juillet 1965, art. 20", S["sous"]),
             Spacer(1, 8 * mm),
             Paragraph(f"Je soussigné, syndic de la copropriété {nom}, certifie qu'à la date du "
                       f"{_fr(ed['etabli_le'])}, {ed['vendeur']['nom']}, copropriétaire du ou des lots n° {lots}, "
                       "est libre de toute obligation à l'égard du syndicat des copropriétaires.", S["txt"]),
             Spacer(1, 4 * mm),
             Paragraph("Ce certificat doit avoir moins d'un mois de date lors de la mutation.", S["petit"])]
    else:
        titre = "Décompte des créances du syndicat"
        doc = _pdf_base(chemin, f"{titre} – {nom}")
        h = [Paragraph(titre, S["titre"]),
             Paragraph(f"{nom} · {ed['vendeur']['nom']} · lots n° {lots} · arrêté au {_fr(ed['etabli_le'])}", S["sous"]),
             Spacer(1, 6 * mm),
             Paragraph(f"{ed['vendeur']['nom']} n'est pas libre de toute obligation à l'égard du syndicat : le "
                       "certificat de l'article 20 ne peut pas être délivré. Créances liquides et exigibles à cette "
                       "date, classées comme l'exige l'article 5-1 du décret du 17 mars 1967 :", S["txt"]),
             Spacer(1, 3 * mm)]
        for g in decompte_opposition(fiche, ed):
            donnees = [["Cause", "Exigible le", "Montant"]]
            donnees += [[Paragraph(x["cause"], cel), _fr(x["date"]), _m(x["montant"])] for x in g["lignes"]]
            if not g["lignes"]:
                donnees.append(["Néant" if g["suivi"] else "Non suivi par Mitoyen : à compléter s'il y a lieu", "", ""])
            donnees.append(["Total " + g["ref"], "", _m(g["total"]) if g["suivi"] else "—"])
            h += [Paragraph(f"<b>{g['ref']} {g['libelle']}</b>", S["txt"]), Spacer(1, 1 * mm),
                  tableau(donnees, [112 * mm, 28 * mm, 34 * mm], aligner_droite_depuis=1, serre=True),
                  Spacer(1, 3 * mm)]
        h += [Paragraph(f"<b>Total des créances : {_m(ed['du_compte'])}</b>", S["txt"]), Spacer(1, 4 * mm),
              Paragraph("À réception de l'avis de mutation envoyé par le notaire, le syndic dispose de 15 jours pour "
                        "former opposition au versement du prix, par acte d'un commissaire de justice, en énonçant "
                        "ces créances (loi du 10 juillet 1965, art. 20 ; décret du 17 mars 1967, art. 5-1). "
                        "Un règlement du cédant avant la vente rend l'opposition inutile.", S["txt"])]
    h += [Spacer(1, 12 * mm), Paragraph("Date, nom et signature du syndic :", S["txt"]),
          Spacer(1, 18 * mm), Paragraph(ed["avertissement"], S["petit"])]
    pied = f"{nom} – {titre}"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


def journal_et_budgets(fiche: dict, racine_appels: Path, racine_data: Path, copro: str):
    import banque as B
    import compta
    import impayes as I
    st = charger_compta(racine_data, copro)
    ops = B.charger_operations(racine_data, copro)
    dues = I.echeances(racine_appels, racine_data, copro)
    rap = I.rapprocher(fiche, ops, dues, I.charger_affectations(racine_data, copro))
    E = compta.journal(fiche, {"ouverture": st["ouverture"], "dues": dues,
                               "ajustements": I.charger_ajustements(racine_data, copro), "operations": ops,
                               "rapprochement": rap, "factures": st["factures"], "depenses": st["depenses"]})
    return E, st, compta.budgets(fiche, racine_data, copro)


def calculer(fiche: dict, racine_appels: Path, racine_data: Path, copro: str, numeros: list[int], jour: date,
             procedures: str = "", acquereur: str = "") -> dict:
    """État daté à partir des données tenues par Mitoyen."""
    E, st, bud = journal_et_budgets(fiche, racine_appels, racine_data, copro)
    return etat_date(fiche, E, st, bud, numeros, jour, procedures, acquereur)
