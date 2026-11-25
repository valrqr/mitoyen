"""
quote_part.py — « Combien ça me coûte ? » : la part de chaque copropriétaire, résolution par résolution.

Avant de voter, chaque copropriétaire voit ce qu'une résolution lui coûterait à lui :
le montant total, sa part (répartie lot par lot selon la clé de la résolution, comme
sur un avis d'appel de fonds) et, à titre indicatif, les échéances.

D'où vient le montant d'une résolution :
    - un montant saisi avec la résolution (travaux, contrat…), payable en une ou
      plusieurs échéances ;
    - le devis d'un dossier de travaux (une résolution par devis) ;
    - la cotisation annuelle au fonds de travaux (fiche) ;
    - le budget prévisionnel : faute de projet chiffré dans la fiche, la part est
      calculée sur le budget de l'exercice en cours et présentée comme telle.

Les échéances suivent les dates d'exigibilité habituelles des appels de fonds de la
fiche, à partir de la première qui suit l'assemblée (pour le budget et le fonds de
travaux, votés pour l'exercice suivant : à partir du début de cet exercice). Elles sont indicatives : c'est
l'assemblée qui fixe le calendrier des appels.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from fiche_copro import CENT, repartir

MAX_ECHEANCES = 12
MONTANT_MAX = Decimal("10000000")
AVERTISSEMENT = ("Montants indicatifs, calculés selon les tantièmes de la clé de répartition de chaque résolution. "
                 "Les dates des appels sont celles des échéances habituelles : l'assemblée générale fixe le "
                 "calendrier définitif. Seuls les appels de fonds envoyés après le vote sont exigibles.")


class MontantInvalide(ValueError):
    pass


def lire_montant(v) -> Decimal | None:
    """Montant saisi (« 4 800 », « 4800,50 € ») : Decimal au centime, None si vide."""
    if v is None or v == "":
        return None
    t = str(v).replace(" ", "").replace(" ", "").replace(" ", "").replace("€", "").replace(",", ".")
    try:
        m = Decimal(t).quantize(CENT)
    except Exception:
        raise MontantInvalide(f"« {v} » n'est pas un montant")
    if m <= 0 or m > MONTANT_MAX:
        raise MontantInvalide(f"Montant hors limites : {v}")
    return m


# --------------------------------------------------------------------------- #
# Répartition
# --------------------------------------------------------------------------- #
def parts(fiche: dict, montant: Decimal, cle: str) -> dict[str, Decimal]:
    """Part de chaque copropriétaire : répartition lot par lot (comme l'avis d'appel),
    puis somme des lots de chacun. Les non-concernés (0 tantième) n'apparaissent pas."""
    poids = {l["numero"]: l["tantiemes"].get(cle, 0) for l in fiche["lots"] if l["tantiemes"].get(cle, 0) > 0}
    proprio = {l["numero"]: l["proprietaire"] for l in fiche["lots"]}
    res: dict[str, Decimal] = defaultdict(Decimal)
    for numero, m in repartir(montant, poids).items():
        res[proprio[numero]] += m
    return dict(res)


def _budget_par_cle(fiche: dict) -> dict[str, Decimal]:
    par_cle: dict[str, Decimal] = defaultdict(Decimal)
    for p in fiche["budget_previsionnel"]["postes"]:
        par_cle[p["cle"]] += Decimal(str(p["montant"]))
    return dict(par_cle)


def _nb_appels(fiche: dict) -> int:
    return len(fiche["appels_de_fonds"]["dates_exigibilite"])


def cout(fiche: dict, r: dict) -> dict | None:
    """Ce que coûte une résolution : composantes (montant, clé), nombre d'échéances, nature.
    None si la résolution n'est pas chiffrée (désignation, point d'information…)."""
    if r.get("majorite") == "info":
        return None
    if r.get("cout") == "budget":
        comp = [(m, c) for c, m in _budget_par_cle(fiche).items() if m > 0]
        return {"composantes": comp, "echeances": _nb_appels(fiche), "nature": "annuel", "source": "budget_actuel",
                "exercice": fiche["budget_previsionnel"]["exercice"]}
    if r.get("cout") == "fonds_travaux":
        ft = fiche["fonds_travaux"]
        return {"composantes": [(Decimal(str(ft["cotisation_annuelle"])).quantize(CENT), ft["cle"])],
                "echeances": _nb_appels(fiche), "nature": "annuel", "source": "fonds_travaux"}
    if r.get("montant"):
        return {"composantes": [(Decimal(str(r["montant"])).quantize(CENT), r.get("cle", "generales"))],
                "echeances": int(r.get("echeances") or 1), "nature": "unique",
                "source": "devis" if r.get("devis") else "saisi"}
    return None


def echeances(fiche: dict, apres: date, n: int) -> list[date]:
    """Les n prochaines dates d'exigibilité habituelles, strictement après l'AG."""
    mmjj = sorted(fiche["appels_de_fonds"]["dates_exigibilite"])
    res, annee = [], apres.year
    while len(res) < n:
        for x in mmjj:
            m, j = (int(v) for v in x.split("-"))
            d = date(annee, m, j)
            if d > apres and len(res) < n:
                res.append(d)
        annee += 1
    return res


def _decouper(part: Decimal, n: int) -> list[Decimal]:
    """Part découpée en n échéances égales ; les centimes restants vont à la première."""
    base = (part / n).quantize(CENT, rounding=ROUND_DOWN)
    return [part - base * (n - 1)] + [base] * (n - 1)


def resolution(fiche: dict, ag: dict, r: dict, cid: str) -> dict | None:
    """La ligne « votre part » d'une résolution pour un copropriétaire."""
    c = cout(fiche, r)
    if c is None:
        return None
    total = sum((m for m, _ in c["composantes"]), Decimal(0))
    part = Decimal(0)
    for m, cle in c["composantes"]:
        part += parts(fiche, m, cle).get(cid, Decimal(0))
    n = c["echeances"]
    depart = date.fromisoformat(ag["date"])
    if c["nature"] == "annuel":         # budget et fonds de travaux votés pour l'exercice suivant
        depart = max(depart, date(fiche["budget_previsionnel"]["exercice"], 12, 31))
    dates = echeances(fiche, depart, n)
    return {"num": r["num"], "titre": r["titre"], "dossier": r.get("dossier"), "total": total, "part": part, "concerne": part > 0,
            "nature": c["nature"], "source": c["source"], "exercice": c.get("exercice"),
            "echeances": list(zip(dates, _decouper(part, n))) if part > 0 else []}


def votre_part(fiche: dict, ag: dict, cid: str) -> dict:
    """Toutes les résolutions chiffrées de l'AG, pour un copropriétaire."""
    lignes = [x for x in (resolution(fiche, ag, r, cid) for r in ag["resolutions"]) if x]
    # Devis concurrents d'un même dossier : un seul sera retenu, on compte le plus cher.
    ponctuel = sum((x["part"] for x in lignes if x["nature"] == "unique" and not x["dossier"]), Decimal(0))
    par_dossier: dict[str, Decimal] = {}
    for x in lignes:
        if x["nature"] == "unique" and x["dossier"]:
            par_dossier[x["dossier"]] = max(par_dossier.get(x["dossier"], Decimal(0)), x["part"])
    ponctuel += sum(par_dossier.values(), Decimal(0))
    return {"cid": cid, "lignes": lignes, "total_travaux": ponctuel, "avertissement": AVERTISSEMENT}


# --------------------------------------------------------------------------- #
# Textes
# --------------------------------------------------------------------------- #
def resume(x: dict, euros) -> tuple[str, str]:
    """(chiffre, suite) : « 1 920,00 € », « en 4 appels de 480,00 € ». Le chiffre seul est
    mis en valeur ; euros = fonction de mise en forme."""
    if not x["concerne"]:
        return "", "vous n'êtes pas concerné, vous ne payez rien"
    n = len(x["echeances"])
    if x["nature"] == "annuel":
        suite = "par an"
        if n > 1:
            suite += f", en {n} appels d'environ {euros(x['echeances'][-1][1])}"
        if x["source"] == "budget_actuel":
            suite += f" (sur la base du budget de l'exercice {x['exercice']} ; voir le projet joint)"
        return euros(x["part"]), suite
    if n == 1:
        return euros(x["part"]), ""
    montants = {m for _, m in x["echeances"]}
    if len(montants) == 1:
        return euros(x["part"]), f"en {n} appels de {euros(x['echeances'][0][1])}"
    return euros(x["part"]), f"en {n} appels d'environ {euros(x['echeances'][-1][1])}"


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def generer_pdf(fiche: dict, ag: dict, cid: str, chemin: Path) -> Path:
    """Une page par copropriétaire, à joindre à la convocation."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    import papier
    from avis_appel import FOND, ORANGE_HTML, CanevasNumerote, euros, styles, tableau, tampon
    c = next(x for x in fiche["coproprietaires"] if x["id"] == cid)
    au_courrier = papier.canal(fiche, cid)["canal"] == "courrier"
    S = styles(False, au_courrier)
    ident = fiche["copropriete"]
    d = date.fromisoformat(ag["date"])
    vp = votre_part(fiche, ag, cid)

    def e(t):
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm, title="Ce que chaque résolution vous coûterait")
    h = [Paragraph("Ce que chaque résolution vous coûterait", S["titre"]),
         Paragraph(f"{e(ag['titre'])} du {d:%d/%m/%Y} · {e(ident['nom'])} · {e(c['nom'])}", S["sous"]),
         Spacer(1, 5 * mm)]
    if not vp["lignes"]:
        h.append(Paragraph("Aucune résolution de cette assemblée n'est chiffrée.", S["txt"]))
    else:
        h.append(Paragraph("Pour chaque résolution qui engage une dépense, voici votre part, calculée selon vos "
                           "tantièmes. Elle ne sera appelée que si la résolution est adoptée.", S["txt"]))
        h.append(Spacer(1, 4 * mm))
        lignes = [["Résolution", "Montant total", "Votre part", "Échéances indicatives"]]
        for x in vp["lignes"]:
            if x["concerne"]:
                part = Paragraph(f"<font color='{ORANGE_HTML}'><b>{euros(x['part'])}</b></font>"
                                 + (" par an" if x["nature"] == "annuel" else ""), S["txt"])
                ech = Paragraph("<br/>".join(f"{dt:%d/%m/%Y} : {euros(m)}" for dt, m in x["echeances"]), S["txt"])
            else:
                part, ech = Paragraph("Non concerné", S["txt"]), ""
            note = ""
            if x["source"] == "budget_actuel":
                note = (f"<br/><font size='8' color='#5C5C5C'>Calculé sur le budget de l'exercice {x['exercice']} : "
                        f"comparez avec le projet joint à la convocation.</font>")
            lignes.append([Paragraph(f"n° {x['num']} · {e(x['titre'])}{note}", S["txt"]),
                           euros(x["total"]) + (" par an" if x["nature"] == "annuel" else ""), part, ech])
        h.append(tableau(lignes, [70 * mm, 30 * mm, 32 * mm, 42 * mm], aligner_droite_depuis=1, lignes_total=0,
                         papier=au_courrier))
        if vp["total_travaux"] > 0:
            h += [Spacer(1, 4 * mm),
                  Paragraph(f"Si toutes les dépenses ponctuelles sont adoptées, votre part s'élève à "
                            f"<font color='{ORANGE_HTML}'><b>{euros(vp['total_travaux'])}</b></font>."
                            + (" Quand plusieurs devis sont proposés pour les mêmes travaux, un seul sera retenu : "
                               "ce total compte le plus cher." if any(x["dossier"] for x in vp["lignes"]) else ""),
                            S["txt"])]
    encadre = Table([[Paragraph(AVERTISSEMENT, S["petit"])]], colWidths=[174 * mm])
    encadre.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FOND), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                 ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    h += [Spacer(1, 6 * mm), encadre]
    pied = f"{ident['nom']} – AG du {d:%d/%m/%Y} – {c['nom']}"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


# --------------------------------------------------------------------------- #
# Après le vote : les échéances des dépenses adoptées, pour son agenda
# --------------------------------------------------------------------------- #
def adoptees(fiche: dict, ag: dict, dep: dict, cid: str) -> list[dict]:
    """Les dépenses ponctuelles adoptées (et retenues) : ce que le copropriétaire va payer.
    Le budget et le fonds de travaux sont exclus : ils passent déjà par les appels
    trimestriels habituels, que l'on ne compte pas deux fois."""
    issue = {r["num"]: r for r in dep["resolutions"]}
    res = []
    for r in ag["resolutions"]:
        d = issue.get(r["num"])
        if not d or not d.get("adoptee") or d.get("retenue") is False:
            continue
        x = resolution(fiche, ag, r, cid)
        if x and x["nature"] == "unique" and x["concerne"]:
            res.append(x)
    return res


def generer_ics(fiche: dict, ag: dict, dep: dict, cid: str, copro: str, maintenant=None) -> str:
    """Un événement d'une journée par échéance, avec une alerte une semaine avant."""
    from datetime import datetime, timedelta, timezone

    from avis_appel import euros
    from rappel_ag import _echapper, _plier
    nom = fiche["copropriete"]["nom"]
    stamp = (maintenant or datetime.now(timezone.utc)).astimezone(timezone.utc)
    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mitoyen//Echeances votees//FR", "CALSCALE:GREGORIAN",
              "METHOD:PUBLISH", f"X-WR-CALNAME:{_echapper('Appels de fonds – ' + nom)}"]
    for x in adoptees(fiche, ag, dep, cid):
        n = len(x["echeances"])
        for i, (jour, montant) in enumerate(x["echeances"], 1):
            titre = f"Appel de fonds {euros(montant)} – {x['titre']}"
            desc = (f"Votre part de la résolution n° {x['num']} adoptée par l'AG du "
                    f"{date.fromisoformat(ag['date']):%d/%m/%Y} ({nom}) : {euros(x['part'])}"
                    + (f", échéance {i} sur {n}" if n > 1 else "") + ".\n\n"
                    "Date et montant indicatifs : l'avis d'appel de fonds envoyé par le syndic fait foi.")
            lignes += ["BEGIN:VEVENT", f"UID:echeance-{ag['id']}-{x['num']}-{i}-{cid}-{copro}@mitoyen.app",
                       f"DTSTAMP:{stamp:%Y%m%dT%H%M%SZ}", f"DTSTART;VALUE=DATE:{jour:%Y%m%d}",
                       f"DTEND;VALUE=DATE:{jour + timedelta(days=1):%Y%m%d}",
                       f"SUMMARY:{_echapper(titre)}", f"DESCRIPTION:{_echapper(desc)}", "TRANSP:TRANSPARENT",
                       "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_echapper('Dans une semaine : ' + titre)}",
                       "TRIGGER:-P7D", "END:VALARM", "END:VEVENT"]
    lignes.append("END:VCALENDAR")
    return "\r\n".join(p for l in lignes for p in _plier(l)) + "\r\n"
