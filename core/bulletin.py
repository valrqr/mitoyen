"""
bulletin.py — Le bulletin de santé de la copropriété.

Une page de faits, chacun rapproché d'un repère (souvent légal), que le syndic partage avec
les copropriétaires et qu'un vendeur peut joindre à son annonce : une copropriété bien tenue
se vend mieux. Pas de note, pas de « label » : un fait comparé à la loi ne se conteste pas,
une note si.

Rien de personnel : les impayés sont donnés en tranches, jamais en montant ni par personne
(dans une petite copropriété, un montant exact suffirait à deviner qui doit).

Le lien public est désactivé par défaut : le syndic l'active, le renouvelle ou le coupe.

⚠️ Informations établies à partir des données tenues par le syndic. Ce n'est ni une
expertise de l'immeuble ni un conseil juridique.
"""

from __future__ import annotations

import json
import secrets
import statistics
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ZERO = Decimal("0")
AVERTISSEMENT = ("Faits établis à partir des données tenues par le syndic, à la date indiquée. Ce n'est ni une "
                 "expertise de l'immeuble ni un conseil juridique.")
TRANCHES_IMPAYES = [(Decimal("5"), "moins de 5 % du budget"), (Decimal("10"), "entre 5 et 10 % du budget"),
                    (Decimal("25"), "entre 10 et 25 % du budget"), (None, "25 % du budget ou plus")]
OK, ATTENTION, INCONNU = "ok", "attention", "inconnu"


def _d(x) -> Decimal:
    return Decimal(str(x))


def _fr(d: date | str) -> str:
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return d.strftime("%d/%m/%Y")


def _eur(m: Decimal) -> str:
    return f"{Decimal(m):,.0f}".replace(",", " ") + " €"


def tranche_impayes(impayes: Decimal, budget: Decimal) -> tuple[str, Decimal]:
    pct = (impayes / budget * 100) if budget else ZERO
    for seuil, lib in TRANCHES_IMPAYES:
        if seuil is None or pct < seuil:
            return lib, pct
    return TRANCHES_IMPAYES[-1][1], pct


# --------------------------------------------------------------------------- #
# Les indicateurs
# --------------------------------------------------------------------------- #
def indicateurs(fiche: dict, jour: date, *, E: list | None = None, st: dict | None = None,
                budgets: dict | None = None, ags: list | None = None, signalements: list | None = None,
                suivi_plan: dict | None = None) -> list[dict]:
    """Chaque indicateur : theme, valeur, detail, repere, etat (ok | attention | inconnu)."""
    import annexes
    from compta import balance
    from fiche_copro import ajouter_mois, echeances
    res = []
    gouv = fiche.get("gouvernance") or {}
    budget = sum((_d(p["montant"]) for p in fiche.get("budget_previsionnel", {}).get("postes", [])), ZERO)
    ouv = (st or {}).get("ouverture")

    # 1. Comptes approuvés dans les 6 mois suivant la clôture
    ca = fiche.get("comptes_approuves") or {}
    delai = gouv.get("ag_annuelle_delai_mois", 6)
    if ca.get("fin") and ca.get("ag_approbation"):
        fin = ca["fin"] if isinstance(ca["fin"], date) else date.fromisoformat(str(ca["fin"]))
        ag = ca["ag_approbation"] if isinstance(ca["ag_approbation"], date) else date.fromisoformat(str(ca["ag_approbation"]))
        a_temps = ag <= ajouter_mois(fin, delai)
        res.append({"theme": "Comptes approuvés", "valeur": f"exercice {ca.get('exercice')}",
                    "detail": f"approuvés en AG le {_fr(ag)}",
                    "repere": f"AG dans les {delai} mois suivant la clôture (loi du 10 juillet 1965, art. 14-1)", "etat": OK if a_temps else ATTENTION})
    else:
        res.append({"theme": "Comptes approuvés", "valeur": "non renseigné", "detail": "",
                    "repere": f"AG dans les {delai} mois suivant la clôture", "etat": INCONNU})

    # 2. Fonds de travaux
    ft = fiche.get("fonds_travaux") or {}
    solde = None
    if E is not None and ouv and ouv["date"] <= jour.isoformat():
        solde = -balance([e for e in E if e["date"] <= jour.isoformat()]).get("105", {}).get("solde", ZERO)
        source = f"au {_fr(jour)}"
    elif ft.get("solde"):
        solde, source = _d(ft["solde"]["montant"]), f"au {_fr(ft['solde']['au'])}"
    cot = _d(ft.get("cotisation_annuelle", 0))
    pct_cot = (cot / budget * 100) if budget else ZERO
    res.append({"theme": "Fonds de travaux",
                "valeur": _eur(solde) if solde is not None else "non renseigné",
                "detail": (f"{source} ; " if solde is not None else "")
                + f"cotisation annuelle {_eur(cot)}, soit {pct_cot:.0f} % du budget",
                "repere": "cotisation d'au moins 5 % du budget prévisionnel (loi du 10 juillet 1965, art. 14-2-1)",
                "etat": OK if pct_cot >= 5 else ATTENTION})

    # 3. Impayés, en tranches
    if E is not None and ouv and ouv["date"] <= jour.isoformat() and budget:
        b = balance([e for e in E if e["date"] <= jour.isoformat()])
        par_copro: dict[str, Decimal] = {}
        for c, v in b.items():
            if c.startswith("450") and "." in c:
                cp = c.split(".", 1)[1]
                par_copro[cp] = par_copro.get(cp, ZERO) + v["solde"]
        imp = sum((m for m in par_copro.values() if m > 0), ZERO)
        lib, pct = tranche_impayes(imp, budget)
        res.append({"theme": "Charges impayées", "valeur": lib, "detail": f"au {_fr(jour)}",
                    "repere": "seuil d'alerte légal : 25 % des sommes exigibles (loi du 10 juillet 1965, art. 29-1 A)",
                    "etat": OK if pct < 10 else ATTENTION})
    elif ca.get("impayes") is not None and budget:
        lib, pct = tranche_impayes(_d(ca["impayes"]), budget)
        res.append({"theme": "Charges impayées", "valeur": lib, "detail": f"à la clôture de l'exercice {ca.get('exercice')}",
                    "repere": "seuil d'alerte légal : 25 % des sommes exigibles (loi du 10 juillet 1965, art. 29-1 A)",
                    "etat": OK if pct < 10 else ATTENTION})
    else:
        res.append({"theme": "Charges impayées", "valeur": "non renseigné", "detail": "",
                    "repere": "seuil d'alerte légal : 25 % des sommes exigibles", "etat": INCONNU})

    # 4. Budget tenu : dernier exercice clos entièrement tenu dans Mitoyen
    tenu = None
    if E is not None and ouv:
        N = jour.year
        for n in (N, N - 1, N - 2):
            du, au = annexes.periode(fiche, n)
            if au < jour.isoformat() and ouv["date"] <= du and (budgets or {}).get(n):
                r = annexes.realise(fiche, E, du, au, annexes._cle_par_compte(budgets[n]))
                reel = sum(r["charges"].values(), ZERO)
                vote = sum((_d(p["montant"]) for p in budgets[n]), ZERO)
                if vote:
                    tenu = (n, reel, vote, (reel - vote) / vote * 100)
                break
    if tenu:
        n, reel, vote, ecart = tenu
        res.append({"theme": "Budget tenu", "valeur": f"{ecart:+.0f} % en {n}",
                    "detail": f"dépenses courantes {_eur(reel)} pour un budget voté de {_eur(vote)}",
                    "repere": "écart entre le réalisé et le budget voté", "etat": OK if abs(ecart) <= 10 else ATTENTION})
    else:
        res.append({"theme": "Budget tenu", "valeur": "pas encore d'exercice clos dans Mitoyen", "detail": "",
                    "repere": "écart entre le réalisé et le budget voté", "etat": INCONNU})

    # 5. Contrats, assurance et diagnostics
    alertes = echeances(fiche, jour, suivi_plan=suivi_plan)
    depasses = [a for a in alertes if a.get("niveau") == "depasse"]
    assurances = [c for c in fiche.get("contrats", []) if "assurance" in c.get("objet", "").lower()]
    assure = any(c.get("tacite_reconduction") or c["echeance"] >= jour for c in assurances)
    res.append({"theme": "Contrats et obligations",
                "valeur": "à jour" if not depasses and assure else
                f"{len(depasses)} échéance(s) dépassée(s)" if depasses else "assurance à vérifier",
                "detail": f"{len(fiche.get('contrats', []))} contrats suivis ; assurance de l'immeuble "
                          + ("en cours" if assure else "non renseignée"),
                "repere": "assurance responsabilité civile obligatoire (loi du 10 juillet 1965, art. 9-1) ; "
                          "aucune échéance légale dépassée", "etat": OK if not depasses and assure else ATTENTION})

    # 6. Plan de travaux
    pt = fiche.get("plan_travaux")
    if pt:
        prochaines = sorted((l for l in pt.get("lignes", []) if l["annee"] >= jour.year), key=lambda l: l["annee"])[:2]
        etat_plan = {"adopte": "adopté en AG", "projet": "élaboré, à soumettre à l'AG"}.get(pt.get("statut"), pt.get("statut"))
        res.append({"theme": "Plan pluriannuel de travaux", "valeur": etat_plan,
                    "detail": "prochains : " + "; ".join(f"{l['intitule'].lower()} ({l['annee']})" for l in prochaines)
                    if prochaines else "",
                    "repere": "obligatoire pour les immeubles de plus de 15 ans (loi du 10 juillet 1965, art. 14-2)",
                    "etat": OK if pt.get("statut") == "adopte" else ATTENTION})
    else:
        res.append({"theme": "Plan pluriannuel de travaux", "valeur": "non renseigné", "detail": "",
                    "repere": "obligatoire pour les immeubles de plus de 15 ans", "etat": INCONNU})

    # 7. Assemblée générale
    if ags:
        derniere = max(a["date"] for a in ags if str(a["date"]) <= jour.isoformat()) if any(
            str(a["date"]) <= jour.isoformat() for a in ags) else None
        if derniere:
            d = derniere if isinstance(derniere, date) else date.fromisoformat(str(derniere))
            res.append({"theme": "Assemblée générale", "valeur": f"dernière le {_fr(d)}",
                        "detail": f"{len(ags)} AG tenues avec Mitoyen",
                        "repere": "au moins une AG par an", "etat": OK if (jour - d).days <= 15 * 31 else ATTENTION})
    if not any(i["theme"] == "Assemblée générale" for i in res) and ca.get("ag_approbation"):
        d = ca["ag_approbation"] if isinstance(ca["ag_approbation"], date) else date.fromisoformat(str(ca["ag_approbation"]))
        res.append({"theme": "Assemblée générale", "valeur": f"dernière le {_fr(d)}",
                    "detail": "celle qui a approuvé les comptes", "repere": "au moins une AG par an",
                    "etat": OK if (jour - d).days <= 15 * 31 else ATTENTION})
    if not any(i["theme"] == "Assemblée générale" for i in res):
        res.append({"theme": "Assemblée générale", "valeur": "aucune tenue avec Mitoyen", "detail": "",
                    "repere": "au moins une AG par an", "etat": INCONNU})

    # 8. Signalements : délai de prise en charge sur 12 mois
    if signalements is not None:
        recents = [s for s in signalements if (jour - datetime.fromisoformat(s["cree_le"]).date()).days <= 365]
        delais = []
        for s in recents:
            h = s.get("historique") or []
            if h:
                delais.append((datetime.fromisoformat(h[0]["le"]) - datetime.fromisoformat(s["cree_le"])).total_seconds() / 86400)
        if recents:
            med = statistics.median(delais) if delais else None
            res.append({"theme": "Signalements", "valeur": f"{len(recents)} sur 12 mois",
                        "detail": (f"pris en charge en {med:.0f} jour(s) en médiane" if med is not None
                                   else "aucun encore pris en charge"),
                        "repere": "délai entre le signalement et sa prise en charge par le syndic",
                        "etat": OK if med is not None and med <= 7 else ATTENTION})
        else:
            res.append({"theme": "Signalements", "valeur": "aucun sur 12 mois", "detail": "",
                        "repere": "délai entre le signalement et sa prise en charge par le syndic", "etat": OK})
    return res


def bulletin(fiche: dict, jour: date, **sources) -> dict:
    ident = fiche["copropriete"]
    ind = indicateurs(fiche, jour, **sources)
    nb_lots = sum(1 for l in fiche["lots"] if l["type"] not in ("cave", "parking"))
    return {"copropriete": ident["nom"], "ville": (ident.get("adresse") or {}).get("ville", "") if isinstance(
                ident.get("adresse"), dict) else "",
            "lots_principaux": nb_lots, "nb_lots": len(fiche["lots"]),
            "construction": ident.get("periode_construction"),
            "gestion": {"benevole": "syndic bénévole", "cooperatif": "syndicat coopératif"}.get(
                (fiche.get("gouvernance") or {}).get("mode_gestion"), "syndic non professionnel"),
            "etabli_le": jour.isoformat(), "indicateurs": ind,
            "nb_ok": sum(1 for i in ind if i["etat"] == OK), "avertissement": AVERTISSEMENT}


def depuis_mitoyen(fiche: dict, racine_appels: Path, racine_data: Path, copro: str, jour: date) -> dict:
    import ag as AG
    import plan_travaux
    import signalements as SIG
    from etat_date import journal_et_budgets
    E, st, bud = journal_et_budgets(fiche, racine_appels, racine_data, copro)
    return bulletin(fiche, jour, E=E, st=st, budgets=bud, ags=AG.lister_ag(racine_data, copro),
                    signalements=SIG.charger(racine_data, copro)["signalements"],
                    suivi_plan=plan_travaux.charger_suivi(racine_data, copro))


# --------------------------------------------------------------------------- #
# Lien public (désactivé par défaut)
# --------------------------------------------------------------------------- #
def _fichier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "bulletin.json"


def reglages(racine: Path, copro: str) -> dict:
    f = _fichier(racine, copro)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {"jeton": None, "actif": False}


def partager(racine: Path, copro: str, actif: bool, renouveler: bool = False) -> dict:
    r = reglages(racine, copro)
    if actif and (renouveler or not r.get("jeton")):
        r["jeton"] = secrets.token_urlsafe(16)
    r["actif"] = bool(actif)
    f = _fichier(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r), encoding="utf-8")
    return r


def jeton_valide(racine: Path, copro: str, propose: str) -> bool:
    r = reglages(racine, copro)
    return bool(r.get("actif") and r.get("jeton")) and secrets.compare_digest(r["jeton"], propose or "")


# --------------------------------------------------------------------------- #
# PDF (une page A4)
# --------------------------------------------------------------------------- #
def generer_pdf(b: dict, chemin: Path) -> Path:
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.pagesizes import A4

    from avis_appel import ENCRE, FILET, GRIS, ORANGE, S, CanevasNumerote, tampon
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm, title=f"Bulletin de santé – {b['copropriete']}")
    theme = ParagraphStyle("bth", parent=S["txt"], fontName="Helvetica-Bold", fontSize=10.5, leading=13)
    valeur = ParagraphStyle("bva", parent=S["txt"], fontName="Helvetica-Bold", fontSize=12, leading=15)
    petit = ParagraphStyle("bpe", parent=S["petit"], fontSize=8.5, leading=11)
    marque = {OK: ("OK", ENCRE), ATTENTION: ("!", ORANGE), INCONNU: ("?", GRIS)}
    h = [Paragraph("Bulletin de santé de la copropriété", S["titre"]),
         Paragraph(f"{b['copropriete']} · {b['lots_principaux']} logements et locaux, {b['nb_lots']} lots · "
                   f"{b['gestion']} · établi le {_fr(b['etabli_le'])}", S["sous"]), Spacer(1, 6 * mm)]
    rows, style = [], [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, FILET),
                       ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
    for k, i in enumerate(b["indicateurs"]):
        sym, coul = marque[i["etat"]]
        rows.append([Paragraph(f'<font color="{coul.hexval().replace("0x", "#")}"><b>{sym}</b></font>', valeur),
                     [Paragraph(i["theme"], theme), Paragraph(i["repere"], petit)],
                     [Paragraph(i["valeur"], valeur), Paragraph(i["detail"], petit)]])
    t = Table(rows, colWidths=[11 * mm, 84 * mm, 79 * mm])
    t.setStyle(TableStyle(style))
    h += [t, Spacer(1, 6 * mm),
          Paragraph("OK conforme au repère · ! point d'attention · ? information non disponible. Aucune note : "
                    "chaque fait est rapproché de son repère, à chacun d'en juger.", petit), Spacer(1, 3 * mm),
          Paragraph(b["avertissement"], petit), Spacer(1, 3 * mm),
          Paragraph("Établi avec Mitoyen, l'outil open source des syndics bénévoles : mitoyen.app", petit)]
    pied = f"{b['copropriete']} – Bulletin de santé"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin
