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
from fiche_copro import appel_par_lot, repartir, rubriques

AVERTISSEMENT = ("Document préparé avec Mitoyen à partir des comptes tenus par le syndic. Contenu établi d'après "
                 "l'article 5 du décret du 17 mars 1967 : à comparer avec le texte sur Légifrance. Le notaire "
                 "vérifie le dossier ; ce n'est pas un conseil juridique. L'ADIL renseigne gratuitement.")
DELAI_OPPOSITION = 15          # jours à compter de la réception de l'avis de mutation (loi 1965, art. 20)
COMPTES_COPRO = {"4501": "budget", "4502": "hors_budget", "4505": "fonds_travaux", "4503": "avances"}


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


def situation_vendeur(E: list[dict], cid: str, jour: str, debut_exercice: str) -> dict:
    """Soldes des comptes du copropriétaire, par nature, à une date. Les paiements apurent
    d'abord les dettes les plus anciennes : ce qui reste dû d'avant l'exercice est isolé."""
    res = {}
    for racine, nature in COMPTES_COPRO.items():
        cpt = f"{racine}.{cid}"
        anciens = [e for e in E if e["date"] < debut_exercice or e["source"] == "ouverture"]
        recents = [e for e in E if debut_exercice <= e["date"] <= jour and e["source"] != "ouverture"]
        avant = sum((l["debit"] - l["credit"] for e in anciens for l in e["lignes"] if l["compte"] == cpt), ZERO)
        credits = sum((l["credit"] for e in recents for l in e["lignes"] if l["compte"] == cpt), ZERO)
        solde = sum((l["debit"] - l["credit"] for e in E if e["date"] <= jour
                     for l in e["lignes"] if l["compte"] == cpt), ZERO)
        anterieur = max(ZERO, avant - credits) if avant > 0 else ZERO
        anterieur = min(anterieur, max(solde, ZERO))
        res[nature] = {"solde": solde, "anterieur": anterieur, "exercice": max(solde, ZERO) - anterieur}
    return res


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
        sit = situation_vendeur(E, cid, jour.isoformat(), annexes.periode(fiche, N)[0])
        res["impayes_vendeur"] = str(sum((max(s["solde"], ZERO) for s in sit.values()), ZERO))
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
def _appels_a_echoir(fiche: dict, budgets: dict, nums: set[int], jour: date) -> list[dict]:
    """Provisions de l'exercice en cours pas encore exigibles : elles incomberont à l'acquéreur,
    copropriétaire à leur date d'exigibilité (décret 1967, art. 6-2)."""
    N = exercice_de(fiche, jour)
    adf = fiche["appels_de_fonds"]
    nb = len(adf["dates_exigibilite"])
    if fiche["budget_previsionnel"].get("exercice") == N:
        par_lot = appel_par_lot(fiche)
        lignes = defaultdict(Decimal)
        for rub in rubriques(fiche):
            lignes[rub["libelle"]] = sum((m for (rid, n), m in par_lot.items() if rid == rub["id"] and n in nums), ZERO)
        source = "budget voté et cotisation au fonds de travaux"
    elif budgets.get(N):
        lignes = defaultdict(Decimal)
        par_cle = defaultdict(Decimal)
        for p in budgets[N]:
            par_cle[p["cle"]] += _d(p["montant"])
        for k, m in par_cle.items():
            lignes[f"Budget – {fiche['cles_repartition'][k]['libelle'].lower()}"] = (part_lots(fiche, nums, m, k) / nb).quantize(Decimal("0.01"))
        ft = fiche["fonds_travaux"]
        lignes["Fonds de travaux"] = (part_lots(fiche, nums, _d(ft["cotisation_annuelle"]), ft["cle"]) / nb).quantize(Decimal("0.01"))
        source = f"budget {N} enregistré (montant par appel arrondi)"
    else:
        return []
    res = []
    import annexes
    du, _ = annexes.periode(fiche, N)
    annee_debut = int(du[:4])
    for mmjj in adf["dates_exigibilite"]:
        mm, jj = (int(x) for x in mmjj.split("-"))
        d = date(annee_debut if f"{annee_debut}-{mmjj}" >= du else annee_debut + 1, mm, jj)
        if d > jour:
            for lib, m in lignes.items():
                if m:
                    res.append({"date": d.isoformat(), "libelle": lib, "montant": m, "source": source})
    return res


def _travaux_a_appeler(fiche: dict, E: list[dict], operations: list[dict], nums: set[int], cid: str,
                       jour: str) -> list[dict]:
    """Travaux votés pas encore entièrement appelés : estimation de la part des lots."""
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
                        "part_lots": part_lots(fiche, nums, reste, o["cle"])})
    return res


def etat_date(fiche: dict, E: list[dict], st: dict, budgets: dict, numeros: list[int], jour: date,
              procedures: str = "", acquereur: str = "") -> dict:
    import annexes
    cid, lots = lots_du_vendeur(fiche, numeros)
    nums = {l["numero"] for l in lots}
    ouv = st.get("ouverture")
    if not ouv or ouv["date"] > jour.isoformat():
        raise EtatDateInvalide("Les comptes ne sont pas tenus dans Mitoyen à cette date : saisir d'abord les "
                               "soldes d'ouverture (Comptabilité)")
    vendeur = next(c for c in fiche["coproprietaires"] if c["id"] == cid)
    N = exercice_de(fiche, jour)
    debut = annexes.periode(fiche, N)[0]
    sit = situation_vendeur([e for e in E if e["date"] <= jour.isoformat()], cid, jour.isoformat(), debut)
    autres_lots = [l["numero"] for l in fiche["lots"] if l["proprietaire"] == cid and l["numero"] not in nums]

    # Un même copropriétaire : ce qu'il a versé en trop sur un compte apure ce qu'il doit sur un
    # autre, en commençant par les dettes les plus anciennes
    reserve = -sum((min(s["solde"], ZERO) for s in sit.values()), ZERO)

    def apurer(m: Decimal) -> Decimal:
        nonlocal reserve
        pris = min(m, reserve)
        reserve -= pris
        return m - pris
    anterieur = apurer(sit["budget"]["anterieur"] + sit["hors_budget"]["anterieur"])
    fonds = apurer(max(sit["fonds_travaux"]["solde"], ZERO))
    hors = apurer(sit["hors_budget"]["exercice"])
    courant = apurer(sit["budget"]["exercice"])
    avances_dues = apurer(max(sit["avances"]["solde"], ZERO))
    p1 = [("Provisions exigibles du budget prévisionnel, exercice en cours", courant),
          ("Provisions exigibles hors budget (travaux, opérations exceptionnelles)", hors),
          ("Charges impayées des exercices antérieurs", anterieur),
          ("Cotisations exigibles au fonds de travaux", fonds),
          ("Avances exigibles", avances_dues)]
    du_vendeur = sum((m for _, m in p1), ZERO)
    trop = reserve
    b = balance([e for e in E if e["date"] <= jour.isoformat()])
    avances_syndicat = -sum((v["solde"] for c, v in b.items() if c.split(".")[0] == "103"), ZERO)
    avances_lots = part_lots(fiche, nums, avances_syndicat, annexes._cle_defaut(fiche)) if avances_syndicat > 0 else ZERO
    p2 = [("Sommes versées d'avance ou trop-perçues, à régulariser", trop),
          ("Avances à rembourser au vendeur (part des lots vendus)", avances_lots)]

    a_echoir = _appels_a_echoir(fiche, budgets, nums, jour)
    travaux = _travaux_a_appeler(fiche, E, st.get("operations_votees") or [], nums, cid, jour.isoformat())
    p3 = [("Reconstitution des avances", avances_lots)]

    # Annexe : quote-part des lots dans les budgets et les dépenses hors budget des deux exercices précédents
    annexe = []
    for n in (N - 2, N - 1):
        postes = budgets.get(n)
        vote = None
        if postes:
            par_cle = defaultdict(Decimal)
            for p in postes:
                par_cle[p["cle"]] += _d(p["montant"])
            vote = sum((part_lots(fiche, nums, m, k) for k, m in par_cle.items()), ZERO)
        reel = charges_exercice(fiche, E, ouv, nums, n, budgets, st.get("operations_votees") or [])
        annexe.append({"exercice": n, "budget_vote": vote,
                       "charges_reelles": reel["budget"] if reel else None,
                       "hors_budget": reel["hors_budget"] if reel else None})

    return {
        "etabli_le": jour.isoformat(), "exercice": N,
        "vendeur": {"id": cid, "nom": vendeur["nom"]}, "acquereur": acquereur.strip()[:120],
        "lots": [{"numero": l["numero"], "type": l["type"], "desc": l.get("desc", ""),
                  "tantiemes": {k: l["tantiemes"].get(k, 0) for k in fiche["cles_repartition"]}} for l in lots],
        "autres_lots_du_vendeur": autres_lots,
        "partie_1": p1, "total_1": du_vendeur,
        "partie_2": p2, "total_2": sum((m for _, m in p2), ZERO),
        "partie_3": p3, "appels_a_echoir": a_echoir, "travaux_a_appeler": travaux,
        "total_3": sum((m for _, m in p3), ZERO) + sum((a["montant"] for a in a_echoir), ZERO)
        + sum((t["part_lots"] for t in travaux), ZERO),
        "annexe": annexe, "procedures": procedures.strip()[:2000] or "Aucune procédure en cours connue du syndic.",
        "libre": du_vendeur == 0, "avertissement": AVERTISSEMENT,
    }


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


def generer_etat_date(fiche: dict, ed: dict, chemin: Path) -> Path:
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer

    from avis_appel import S, CanevasNumerote, tableau, tampon
    nom = fiche["copropriete"]["nom"]
    lots_txt = ", ".join(f"lot {l['numero']} ({l['desc'] or l['type']})" for l in ed["lots"])
    doc = _pdf_base(chemin, f"État daté – {nom}")
    h = [Paragraph("État daté", S["titre"]),
         Paragraph(f"{nom} · établi le {_fr(ed['etabli_le'])}", S["sous"]), Spacer(1, 4 * mm),
         Paragraph(f"<b>Vendeur :</b> {ed['vendeur']['nom']} · <b>Lots vendus :</b> {lots_txt}"
                   + (f" · <b>Acquéreur :</b> {ed['acquereur']}" if ed["acquereur"] else ""), S["txt"]),
         Paragraph("Article 5 du décret n° 67-223 du 17 mars 1967. Sommes arrêtées à la date ci-dessus.", S["petit"]),
         Spacer(1, 5 * mm)]

    def partie(titre, lignes, total, libelle_total):
        donnees = [["", "Montant"]] + [[Paragraph(l, S["txt"]), _m(m)] for l, m in lignes] + [[libelle_total, _m(total)]]
        return KeepTogether([Paragraph(f"<b>{titre}</b>", S["txt"]), Spacer(1, 1.5 * mm),
                             tableau(donnees, [134 * mm, 40 * mm], aligner_droite_depuis=1), Spacer(1, 5 * mm)])

    h.append(partie("1re partie — Sommes dues par le vendeur au syndicat des copropriétaires",
                    ed["partie_1"], ed["total_1"], "Total dû par le vendeur"))
    if ed["autres_lots_du_vendeur"]:
        h += [Paragraph(f"Le vendeur conserve d'autres lots ({', '.join(map(str, ed['autres_lots_du_vendeur']))}) : "
                        "les sommes ci-dessus sont celles de son compte de copropriétaire.", S["petit"]), Spacer(1, 3 * mm)]
    h.append(partie("2e partie — Sommes dont le syndicat pourrait être débiteur envers le vendeur",
                    ed["partie_2"], ed["total_2"], "Total"))
    lignes3 = list(ed["partie_3"])
    lignes3 += [(f"Provision exigible le {_fr(a['date'])} — {a['libelle']}", a["montant"]) for a in ed["appels_a_echoir"]]
    lignes3 += [(f"Travaux votés le {_fr(t['vote_le'])} restant à appeler — {t['libelle']} (estimation)", t["part_lots"])
                for t in ed["travaux_a_appeler"]]
    h.append(partie("3e partie — Sommes qui incomberont au nouveau copropriétaire", lignes3, ed["total_3"],
                    "Total à la charge de l'acquéreur"))
    h += [Paragraph("Les provisions sont dues par celui qui est copropriétaire à la date de leur exigibilité "
                    "(décret du 17 mars 1967, art. 6-2). Vendeur et acquéreur peuvent convenir entre eux d'une "
                    "autre répartition, sans effet à l'égard du syndicat.", S["petit"]), Spacer(1, 5 * mm)]

    donnees = [["Exercice", "Budget voté (part des lots)", "Charges réelles", "Hors budget"]]
    donnees += [[str(a["exercice"]), _m(a["budget_vote"]), _m(a["charges_reelles"]), _m(a["hors_budget"])]
                for a in ed["annexe"]]
    h.append(KeepTogether([Paragraph("<b>Annexe — Quote-part des lots dans le budget prévisionnel et les dépenses "
                                     "hors budget des deux exercices précédents</b>", S["txt"]), Spacer(1, 1.5 * mm),
                           tableau(donnees, [24 * mm, 54 * mm, 50 * mm, 46 * mm], aligner_droite_depuis=1,
                                   lignes_total=0), Spacer(1, 4 * mm),
                           Paragraph("<b>Procédures en cours impliquant le syndicat</b>", S["txt"]),
                           Paragraph(ed["procedures"].replace("\n", "<br/>"), S["txt"])]))
    h += [Spacer(1, 8 * mm), Paragraph(ed["avertissement"], S["petit"]), Spacer(1, 3 * mm),
          Paragraph("Établi sans honoraires par le syndic bénévole. Date et signature du syndic :", S["txt"])]
    pied = f"{nom} – État daté"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


def generer_certificat(fiche: dict, ed: dict, chemin: Path) -> Path:
    """Vendeur à jour : certificat de l'article 20. Sinon : décompte des sommes exigibles."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer

    from avis_appel import S, CanevasNumerote, tableau, tampon
    nom = fiche["copropriete"]["nom"]
    lots = ", ".join(str(l["numero"]) for l in ed["lots"])
    if ed["libre"]:
        titre = "Certificat de l'article 20"
        doc = _pdf_base(chemin, f"{titre} – {nom}")
        h = [Paragraph(titre, S["titre"]), Paragraph(f"{nom} · loi n° 65-557 du 10 juillet 1965, art. 20", S["sous"]),
             Spacer(1, 8 * mm),
             Paragraph(f"Je soussigné, syndic de la copropriété {nom}, certifie qu'à la date du "
                       f"{_fr(ed['etabli_le'])}, {ed['vendeur']['nom']}, copropriétaire du ou des lots n° {lots}, "
                       "est libre de toute obligation à l'égard du syndicat des copropriétaires.", S["txt"]),
             Spacer(1, 4 * mm),
             Paragraph("Ce certificat est valable un mois à compter de sa date.", S["petit"])]
    else:
        titre = "Décompte des sommes dues par le vendeur"
        doc = _pdf_base(chemin, f"{titre} – {nom}")
        donnees = [["Nature", "Montant"]] + [[Paragraph(l, S["txt"]), _m(m)] for l, m in ed["partie_1"] if m] + \
                  [["Total liquide et exigible", _m(ed["total_1"])]]
        h = [Paragraph(titre, S["titre"]),
             Paragraph(f"{nom} · lots n° {lots} · arrêté au {_fr(ed['etabli_le'])}", S["sous"]), Spacer(1, 6 * mm),
             Paragraph(f"{ed['vendeur']['nom']} n'est pas libre de toute obligation à l'égard du syndicat : le "
                       "certificat de l'article 20 ne peut pas être délivré. Sommes liquides et exigibles :", S["txt"]),
             Spacer(1, 3 * mm), tableau(donnees, [134 * mm, 40 * mm], aligner_droite_depuis=1), Spacer(1, 5 * mm),
             Paragraph("À réception de l'avis de mutation envoyé par le notaire, le syndic dispose de 15 jours pour "
                       "former opposition au versement du prix, par acte d'un commissaire de justice, dans la limite "
                       "de ces sommes (loi du 10 juillet 1965, art. 20 ; décret du 17 mars 1967, art. 5-1). "
                       "Un règlement du vendeur avant la vente rend l'opposition inutile.", S["txt"])]
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
