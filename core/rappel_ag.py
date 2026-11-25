"""
rappel_ag.py — Rappels d'assemblée générale et fichier « ajouter à mon calendrier ».

La convocation, notifiée au moins 21 jours avant, est la seule qui compte en droit.
Le rappel est une attention en plus : il ne la remplace pas et le dit.

    - J-7 : rappel, avec la date limite du vote par correspondance si elle n'est pas
      passée, et l'ordre du jour en bref ;
    - J-1 : « c'est demain », lieu et heure, lien de visio si l'AG l'a autorisée ;
    - le lendemain du dépouillement : les résultats, ce que le copropriétaire va payer
      et quand, avec « L'AG en bref » et le fichier d'agenda des échéances votées.

Chaque mail porte « L'AG en bref » de son destinataire (avant l'AG, puis après).

Chaque mail porte une pièce jointe .ics : un clic l'ajoute à l'agenda (Apple,
Google, Outlook, Thunderbird…), sans dépendre d'aucun service.

Les copropriétaires qui ont choisi le courrier ne reçoivent pas de mail : la liste
en est donnée au syndic (rappel à glisser dans la boîte aux lettres ; l'affiche du
hall annonce déjà la date). Ceux qui ont voté par correspondance sont prévenus que
leur vote est enregistré et qu'il serait remplacé s'ils venaient (art. 14-1 décret).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

RAPPELS_JOURS = (7, 1)
DUREE_DEFAUT_MIN = 120
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
# Fuseau Europe/Paris décrit dans le fichier : l'heure reste juste même pour un agenda
# qui ne connaît pas les fuseaux, et au passage à l'heure d'été.
VTIMEZONE = [
    "BEGIN:VTIMEZONE", "TZID:Europe/Paris",
    "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200", "TZNAME:CEST",
    "DTSTART:19700329T020000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
    "BEGIN:STANDARD", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100", "TZNAME:CET",
    "DTSTART:19701025T030000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
    "END:VTIMEZONE",
]


class RappelInvalide(ValueError):
    pass


def heure_de(texte: str) -> tuple[int, int]:
    """'18h30', '18:30', '18 h', '9h' -> (18, 30)."""
    m = re.match(r"^\s*(\d{1,2})\s*[hH:]\s*(\d{2})?\s*$", texte or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
        raise RappelInvalide(f"Heure de l'AG illisible : « {texte} » (attendu par exemple 18h30)")
    return int(m.group(1)), int(m.group(2) or 0)


def date_longue(d: date) -> str:
    return f"{JOURS[d.weekday()]} {d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


def _echapper(t: str) -> str:
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _plier(ligne: str) -> list[str]:
    """Lignes de 75 octets au plus (RFC 5545), sans couper un caractère UTF-8."""
    res, courant = [], ""
    for c in ligne:
        limite = 75 if not res else 74          # les suites commencent par une espace
        if len((courant + c).encode("utf-8")) > limite:
            res.append(courant)
            courant = c
        else:
            courant += c
    res.append(courant)
    return [res[0]] + [" " + x for x in res[1:]]


def generer_ics(fiche: dict, ag: dict, copro: str, maintenant: datetime | None = None) -> str:
    import ag as assemblee
    d = date.fromisoformat(ag["date"])
    h, m = heure_de(ag["heure"])
    debut = datetime(d.year, d.month, d.day, h, m)
    fin = debut + timedelta(minutes=int(ag.get("duree_minutes") or DUREE_DEFAUT_MIN))
    nom = fiche["copropriete"]["nom"]
    cal = assemblee.calendrier(fiche, ag, d - timedelta(days=30))
    odj = "\n".join(f"{r['num']}. {r['titre']}" for r in ag["resolutions"])
    desc = (f"{ag['titre']} du syndicat des copropriétaires {nom}.\n\n"
            + (f"Participation à distance : {ag['visio']}\n\n" if ag.get("visio") else "")
            + f"Ordre du jour :\n{odj}\n\n"
            + f"Vote par correspondance : formulaire à faire parvenir au syndic avant le "
              f"{date.fromisoformat(cal['limite_correspondance']):%d/%m/%Y}.\n\n"
            + "Rappel envoyé par l'assistant du syndic : il ne remplace pas la convocation officielle.")
    stamp = (maintenant or datetime.now(timezone.utc)).astimezone(timezone.utc)
    lignes = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mitoyen//Assemblee generale//FR", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", *VTIMEZONE,
        "BEGIN:VEVENT",
        f"UID:ag-{ag['id']}-{copro}@mitoyen.app",
        f"DTSTAMP:{stamp:%Y%m%dT%H%M%SZ}",
        f"DTSTART;TZID=Europe/Paris:{debut:%Y%m%dT%H%M%S}",
        f"DTEND;TZID=Europe/Paris:{fin:%Y%m%dT%H%M%S}",
        f"SUMMARY:{_echapper(ag['titre'] + ' – ' + nom)}",
        f"LOCATION:{_echapper(ag['lieu'])}",
        f"DESCRIPTION:{_echapper(desc)}",
        *([f"URL:{ag['visio']}"] if ag.get("visio", "") and ag["visio"].startswith("https://") else []),
        "STATUS:CONFIRMED", "TRANSP:OPAQUE",
        "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_echapper('Demain : ' + ag['titre'])}",
        "TRIGGER:-P1D", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(p for l in lignes for p in _plier(l)) + "\r\n"


def rappels(fiche: dict, ag: dict, copro: str, aujourd_hui: date | None = None,
            jours: tuple[int, ...] = RAPPELS_JOURS) -> dict | None:
    """Le rappel à envoyer aujourd'hui pour cette AG, ou None. Un mail par destinataire."""
    import ag as assemblee
    import papier
    jour = aujourd_hui or date.today()
    d = date.fromisoformat(ag["date"])
    ecart = (d - jour).days
    if ecart not in jours or ag.get("depouillement"):
        return None
    heure_de(ag["heure"])
    nom_copro = fiche["copropriete"]["nom"]
    limite = date.fromisoformat(assemblee.calendrier(fiche, ag, jour)["limite_correspondance"])
    quand = f"{date_longue(d)} à {ag['heure']}"
    objet = (f"C'est demain : {ag['titre'].lower()} de la {nom_copro}, {ag['heure']}" if ecart == 1 else
             f"Rappel : {ag['titre'].lower()} de la {nom_copro}, {date_longue(d)}")
    envois, courrier = [], []
    for c in fiche["coproprietaires"]:
        cid = c["id"]
        k = papier.canal(fiche, cid, jour)
        a_vote = cid in ag.get("correspondance", {})
        par_mail = k["canal"] != "courrier" and bool(c.get("email"))
        if not par_mail:
            courrier.append({"coproprietaire": cid, "nom": c["nom"]})
        lignes = [f"Bonjour {c['nom']},", "",
                  f"L'{ag['titre'].lower()} de la {nom_copro} a lieu {'demain, ' if ecart == 1 else 'le '}{quand}, "
                  f"{ag['lieu']}."]
        if ag.get("visio"):
            lignes += ["", f"Vous pouvez aussi y participer à distance : {ag['visio']}"]
        if a_vote:
            lignes += ["", "Votre vote par correspondance est bien enregistré. Si vous venez à la réunion, c'est votre "
                           "vote en séance qui comptera."]
        elif jour <= limite:
            lignes += ["", f"Vous ne pourrez pas venir ? Vous pouvez voter par correspondance avec le formulaire joint à "
                           f"la convocation, à faire parvenir au syndic au plus tard le {date_longue(limite)}, ou "
                           f"donner pouvoir à la personne de votre choix."]
        else:
            lignes += ["", "Vous ne pourrez pas venir ? Vous pouvez encore donner pouvoir à la personne de votre choix "
                           "(le délai du vote par correspondance est passé)."]
        if ecart > 1:
            lignes += ["", "À l'ordre du jour :"] + [f"  {r['num']}. {r['titre']}" for r in ag["resolutions"]]
        lignes += ["", "En pièces jointes : « L'AG en bref », une page pour savoir ce qui sera décidé et ce que "
                       "chaque décision vous coûterait, et un fichier qui ajoute la réunion à votre agenda.", "",
                   "Ce rappel ne remplace pas la convocation officielle, qui vous a été notifiée.", "",
                   "L'assistant du syndic"]
        pieces = {"fichier_ics": f"/copros/{copro}/ag/{ag['id']}/agenda.ics",
                  "fichier_pdf": f"/copros/{copro}/ag/{ag['id']}/en-bref/{cid}"}
        if par_mail:
            envois.append({"coproprietaire": cid, "nom": c["nom"], "email": c["email"], "objet": objet,
                           "texte": "\n".join(lignes), "a_vote_par_correspondance": a_vote, **pieces})
        # le proche aidant est prévenu même si le copropriétaire reçoit tout par courrier
        aidant = papier.copie_aidant(fiche, cid)
        if aidant and aidant.get("email"):
            envois.append({"coproprietaire": cid, "nom": aidant["nom"], "email": aidant["email"],
                           "objet": f"[Pour {c['nom']}] {objet}", "aidant": True,
                           "texte": "\n".join([f"Bonjour {aidant['nom']},", "",
                                               f"Pour information, avec l'accord de {c['nom']} :", ""] + lignes[2:]),
                           "a_vote_par_correspondance": a_vote, **pieces})
    return {"copro": copro, "copropriete": nom_copro, "ag": ag["id"], "date": ag["date"], "heure": ag["heure"],
            "rappel": f"J-{ecart}", "objet": objet, "envois": envois, "courrier": courrier,
            "fichier_ics": f"/copros/{copro}/ag/{ag['id']}/agenda.ics",
            "note_courrier": ("Ces copropriétaires reçoivent leurs documents par courrier : un mot dans la boîte aux "
                              "lettres suffit. L'affiche du hall annonce déjà la date de l'AG.") if courrier else None}


def resultats(fiche: dict, ag: dict, copro: str, aujourd_hui: date | None = None) -> dict | None:
    """Le lendemain du dépouillement : un mail par copropriétaire avec ce qui a été décidé.
    None les autres jours. Ne remplace pas la notification du procès-verbal."""
    import ag as assemblee
    import ag_bref
    import papier
    from avis_appel import euros
    dep_saisi = ag.get("depouillement")
    if not dep_saisi or not dep_saisi.get("le"):
        return None
    jour = aujourd_hui or date.today()
    if jour != date.fromisoformat(dep_saisi["le"]) + timedelta(days=1):
        return None
    dep = assemblee.depouiller(fiche, ag, dep_saisi["votes"], dep_saisi.get("amendees"))
    nom_copro = fiche["copropriete"]["nom"]
    d = date.fromisoformat(ag["date"])
    objet = f"Ce qu'a décidé l'assemblée générale du {d:%d/%m/%Y} – {nom_copro}"
    envois, courrier = [], []
    for c in fiche["coproprietaires"]:
        cid = c["id"]
        k = ag_bref.contenu(fiche, ag, cid, dep)
        adoptees = [p for p in k["points"] if p.get("issue") == "adoptée"]
        rejetees = [p for p in k["points"] if p.get("issue") in ("rejetée", "sans effet")]
        lignes = [f"Bonjour {c['nom']},", "",
                  f"Voici, en bref, ce qu'a décidé l'{ag['titre'].lower()} de la {nom_copro} du {date_longue(d)}.", ""]
        lignes += ["Adopté :"] + [f"  {p['num']}. {p['titre']}" for p in adoptees] if adoptees else ["Rien n'a été adopté."]
        if rejetees:
            lignes += ["", "Rejeté :"] + [f"  {p['num']}. {p['titre']}" for p in rejetees]
        if k["a_payer"] > 0:
            jour_appel, montant = k["prochain_appel"]
            lignes += ["", f"Pour les dépenses votées, votre part s'élève à {euros(k['a_payer'])}. Premier appel prévu "
                           f"le {date_longue(jour_appel)} ({euros(montant)}) : le fichier d'agenda joint en reprend "
                           f"toutes les dates. L'avis d'appel de fonds fait foi."]
        lignes += ["", "Le détail est dans « L'AG en bref », jointe à ce mail.", "",
                   "Ce message ne remplace pas le procès-verbal, qui vous sera adressé. Si vous avez voté contre une "
                   "décision ou n'étiez ni présent ni représenté, vous disposez de deux mois à compter de sa "
                   "notification pour la contester.", "", "L'assistant du syndic"]
        pieces = {"fichier_pdf": f"/copros/{copro}/ag/{ag['id']}/en-bref/{cid}",
                  "fichier_ics": f"/copros/{copro}/ag/{ag['id']}/echeances/{cid}.ics" if k["a_payer"] > 0 else ""}
        par_mail = papier.canal(fiche, cid, jour)["canal"] != "courrier" and bool(c.get("email"))
        if par_mail:
            envois.append({"coproprietaire": cid, "nom": c["nom"], "email": c["email"], "objet": objet,
                           "texte": "\n".join(lignes), **pieces})
        else:
            courrier.append({"coproprietaire": cid, "nom": c["nom"]})
        aidant = papier.copie_aidant(fiche, cid)
        if aidant and aidant.get("email"):
            envois.append({"coproprietaire": cid, "nom": aidant["nom"], "email": aidant["email"],
                           "objet": f"[Pour {c['nom']}] {objet}", "aidant": True,
                           "texte": "\n".join([f"Bonjour {aidant['nom']},", "",
                                               f"Pour information, avec l'accord de {c['nom']} :", ""] + lignes[2:]),
                           **pieces})
    return {"copro": copro, "copropriete": nom_copro, "ag": ag["id"], "date": ag["date"], "heure": ag["heure"],
            "rappel": "résultats", "objet": objet, "envois": envois, "courrier": courrier,
            "note_courrier": ("Ces copropriétaires reçoivent leurs documents par courrier : imprimez et glissez dans "
                              "leur boîte aux lettres leur « AG en bref » (page de l'AG, « Documents de… »).")
            if courrier else None}
