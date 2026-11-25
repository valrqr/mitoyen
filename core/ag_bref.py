"""
ag_bref.py — « L'AG en bref » : une page par copropriétaire, avant et après l'assemblée.

La plupart des copropriétaires ne lisent ni la convocation ni le procès-verbal : trop longs,
trop juridiques. Cette page dit l'essentiel en une minute.

    AVANT (à joindre à la convocation) : quand et où, jusqu'à quand voter par
    correspondance, ce qui sera décidé, ce que chaque décision coûterait au lecteur,
    et les trois façons de participer.

    APRÈS (dès le dépouillement) : ce qui a été adopté ou rejeté, ce que le lecteur va
    payer et quand (avec le fichier d'agenda des échéances), et ce qui se passe ensuite.

Le texte est construit à partir des résultats, sans IA : aucune reformulation ne peut
trahir une décision. La page dit qu'elle ne remplace ni la convocation ni le
procès-verbal signé, seuls documents qui font foi.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import quote_part

MAJORITES_SIMPLES = {
    "24": "majorité des voix exprimées",
    "25": "majorité des voix de tous les copropriétaires",
    "26": "double majorité (en nombre et deux tiers des voix)",
}


def _e(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def contenu(fiche: dict, ag: dict, cid: str, dep: dict | None = None) -> dict:
    """Le contenu de la page, sans mise en forme (testable, réutilisable dans un mail)."""
    import ag as assemblee
    from avis_appel import euros
    d = date.fromisoformat(ag["date"])
    cal = assemblee.calendrier(fiche, ag, d)
    issue = {r["num"]: r for r in (dep or {}).get("resolutions", [])}
    points = []
    for r in ag["resolutions"]:
        x = quote_part.resolution(fiche, ag, r, cid)
        p = {"num": r["num"], "titre": r["titre"], "info": r["majorite"] == "info",
             "majorite": MAJORITES_SIMPLES.get(r["majorite"], "")}
        if x:
            chiffre, suite = quote_part.resume(x, euros)
            p["part"] = (chiffre, suite)
            p["budget"] = x["source"] == "budget_actuel"
        if dep is not None and not p["info"]:
            res = issue.get(r["num"], {})
            if res.get("retenue") is False:
                p["issue"] = "sans effet"
            else:
                p["issue"] = "adoptée" if res.get("adoptee") else "rejetée"
            if p["issue"] != "adoptée":
                p.pop("part", None)
        points.append(p)
    out = {"moment": "apres" if dep is not None else "avant", "date": d, "heure": ag["heure"], "lieu": ag["lieu"],
           "visio": ag.get("visio"), "limite_correspondance": date.fromisoformat(cal["limite_correspondance"]),
           "points": points}
    if dep is None:
        vp = quote_part.votre_part(fiche, ag, cid)
        out["si_tout_adopte"] = vp["total_travaux"]
    else:
        ad = quote_part.adoptees(fiche, ag, dep, cid)
        out["a_payer"] = sum((x["part"] for x in ad), Decimal(0))
        ech = sorted((e for x in ad for e in x["echeances"]), key=lambda e: e[0])
        out["prochain_appel"] = ech[0] if ech else None
        out["adoptees"] = sum(1 for p in points if p.get("issue") == "adoptée")
        out["rejetees"] = sum(1 for p in points if p.get("issue") == "rejetée")
    return out


def generer_pdf(fiche: dict, ag: dict, cid: str, chemin: Path, dep: dict | None = None) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    import papier
    from avis_appel import FOND, CanevasNumerote, essentiel, euros, euros_rond, styles, tampon
    from rappel_ag import date_longue
    c = next(x for x in fiche["coproprietaires"] if x["id"] == cid)
    au_courrier = papier.canal(fiche, cid)["canal"] == "courrier"
    grand = bool(c.get("grands_caracteres"))
    S = styles(grand, au_courrier)
    k = contenu(fiche, ag, cid, dep)
    ident = fiche["copropriete"]
    d = k["date"]
    avant = k["moment"] == "avant"

    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm, title="L'AG en bref")
    if avant:
        h = [Paragraph("L'assemblée générale en bref", S["titre"]),
             Paragraph(f"{_e(ident['nom'])} · ce qui sera décidé le {date_longue(d)}", S["sous"]), Spacer(1, 4 * mm)]
        chiffres = [("Quand", f"{d:%d/%m}", f"{_e(k['heure'])}, {_e(k['lieu'])}"),
                    ("Vote par correspondance", f"{k['limite_correspondance']:%d/%m}",
                     "dernier jour de réception par le syndic")]
        if k["si_tout_adopte"] > 0:
            chiffres.append(("Votre part des dépenses", euros_rond(k["si_tout_adopte"]),
                             "si tout est adopté (hors budget courant)"))
    else:
        h = [Paragraph("Ce qu'a décidé l'assemblée générale", S["titre"]),
             Paragraph(f"{_e(ident['nom'])} · assemblée du {date_longue(d)}", S["sous"]), Spacer(1, 4 * mm)]
        chiffres = [("Décisions", f"{k['adoptees']} adoptée{'s' if k['adoptees'] > 1 else ''}",
                     f"{k['rejetees']} rejetée{'s' if k['rejetees'] > 1 else ''}")]
        if k["a_payer"] > 0:
            chiffres.append(("Vous paierez", euros_rond(k["a_payer"]), "pour les dépenses votées"))
        if k["prochain_appel"]:
            jour, m = k["prochain_appel"]
            chiffres.append(("Prochain appel", f"{jour:%d/%m/%Y}", f"{euros(m)}, date indicative"))
    h += [essentiel(chiffres, grand, papier=au_courrier), Spacer(1, 5 * mm),
          Paragraph("<b>Ce qui sera décidé</b>" if avant else "<b>Les décisions</b>", S["txt"]), Spacer(1, 2 * mm)]

    lignes = []
    for p in k["points"]:
        if p["info"]:
            detail = "Point d'information, sans vote."
            etiquette = "Info"
        else:
            if avant:
                etiquette = f"n° {p['num']}"
            else:
                etiquette = (f"<b>{p['issue'].capitalize()}</b>" if p["issue"] == "adoptée"
                             else f"<font color='#5C5C5C'>{p['issue'].capitalize()}</font>")
            if not avant and p.get("budget"):
                detail = "Votre part figurera sur vos avis d'appel de fonds habituels."
            elif "part" in p:
                chiffre, suite = p["part"]
                detail = "Votre part : " + " ".join(x for x in (f"<b>{_e(chiffre)}</b>" if chiffre else "", _e(suite)) if x) + "."
            elif avant or p["issue"] == "adoptée":
                detail = "Pas de dépense directe pour vous."
            else:
                detail = "Rien ne change."
        lignes.append([Paragraph(etiquette, S["txt"]),
                       Paragraph(f"{_e(p['titre'])}<br/><font color='#5C5C5C'>{detail}</font>", S["txt"])])
    t = Table(lignes, colWidths=[26 * mm, 148 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, FOND),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (0, -1), 0)]))
    h += [t, Spacer(1, 5 * mm)]

    if avant:
        visio = f" ; ou à distance : {_e(k['visio'])}" if k.get("visio") else ""
        suite = ("<b>Comment donner votre avis</b><br/>"
                 f"• Venir à l'assemblée le {d:%d/%m/%Y} à {_e(k['heure'])}, {_e(k['lieu'])}{visio}.<br/>"
                 "• Ou confier un pouvoir écrit à la personne de votre choix (pas au syndic).<br/>"
                 f"• Ou voter par correspondance : le formulaire joint doit être reçu par le syndic au plus tard le "
                 f"<b>{k['limite_correspondance']:%d/%m/%Y}</b>.<br/>"
                 "Sans vote de votre part, la décision est prise par ceux qui votent.")
        mention = ("Résumé préparé avec Mitoyen pour faciliter la lecture. Il ne remplace pas la convocation "
                   "officielle et ses documents joints, qui seuls font foi.")
    else:
        suite = ("<b>Et maintenant ?</b><br/>"
                 + ("• Les dépenses votées vous seront appelées par avis d'appel de fonds ; le fichier d'agenda joint "
                    "en reprend les dates.<br/>" if k["a_payer"] > 0 else "")
                 + "• Le procès-verbal vous sera adressé ou mis à disposition ; c'est lui qui fait foi.<br/>"
                 "• Si vous avez voté contre une décision, ou si vous n'étiez ni présent ni représenté, vous pouvez "
                 "la contester en justice dans les deux mois suivant la notification du procès-verbal (loi du "
                 "10 juillet 1965, art. 42). L'ADIL de votre département vous renseigne gratuitement.")
        mention = ("Résumé établi d'après les résultats du dépouillement, avant signature du procès-verbal. "
                   "Seul le procès-verbal signé fait foi.")
    bloc = Table([[Paragraph(suite, S["txt"])]], colWidths=[174 * mm])
    bloc.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FOND), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    h += [KeepTogether([bloc]), Spacer(1, 4 * mm), Paragraph(mention, S["petit"])]
    pied = f"{ident['nom']} – AG du {d:%d/%m/%Y} en bref – {c['nom']}"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin
