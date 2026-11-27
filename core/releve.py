"""
releve.py — Le plan de relève : si le syndic bénévole s'arrête du jour au lendemain, la copropriété
ne reste pas sans gestion.

Il n'y a qu'un syndic, seul responsable de sa gestion. La loi prévoit en revanche qui prend le relais
(loi du 10 juillet 1965 ; articles à vérifier sur Légifrance) :
    - syndicat coopératif : le conseil syndical élit le syndic parmi ses membres, et peut élire un
      vice-président qui le supplée en cas d'empêchement (art. 17-1) ;
    - syndic bénévole « classique » : en cas d'empêchement du syndic, le président du conseil syndical
      peut convoquer l'assemblée générale pour désigner un nouveau syndic (art. 18) ;
    - sans conseil syndical, il reste à saisir le tribunal judiciaire pour faire désigner un
      administrateur provisoire.

Mitoyen prépare cette relève :
1. un ou deux suppléants désignés dans la fiche, avec la date de leur accord ;
2. une liste « Relève prête ? » qui signale ce qui manque ;
3. une page privée du suppléant (lien désactivé par défaut, renouvelable) : la marche à suivre, le
   projet de convocation prérempli et, s'il siège au conseil syndical (qui peut consulter toutes les
   pièces de la copropriété), le dossier de passation fabriqué à la demande, donc toujours à jour.
   Chaque téléchargement est noté et visible par le syndic.

Stockage : data/<copro>/releve.json.
"""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime
from pathlib import Path

ROLES = {
    "president_cs": "président du conseil syndical",
    "vice_president": "vice-président du conseil syndical",
    "membre_cs": "membre du conseil syndical",
    "autre": "copropriétaire hors conseil syndical",
}
MAX_SUPPLEANTS = 2
MANDAT_ALERTE_JOURS = 92
DOSSIER_VERIFIE_JOURS = 183


class ReleveInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Stockage
# --------------------------------------------------------------------------- #
def _fichier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "releve.json"


def charger(racine: Path, copro: str) -> dict:
    f = _fichier(racine, copro)
    r = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    return {"suppleants": [], "jeton": None, "actif": False, "telechargements": [], **r}


def _sauver(racine: Path, copro: str, r: dict) -> dict:
    f = _fichier(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


def _cs(fiche: dict) -> list[str]:
    return list(fiche["gouvernance"].get("conseil_syndical") or [])


def _syndic(fiche: dict) -> str:
    return fiche["gouvernance"]["syndic"]["coproprietaire_id"]


def cooperatif(fiche: dict) -> bool:
    return fiche["gouvernance"].get("mode_gestion") == "cooperatif"


def enregistrer(racine: Path, copro: str, fiche: dict, saisie: dict, jour: date) -> dict:
    """saisie : suppleant1, role1, accord1 (AAAA-MM-JJ), et de même suppleant2, role2, accord2."""
    from fiche_copro import actuels
    ids = {c["id"]: c for c in actuels(fiche)}
    cs = _cs(fiche)
    sup, vus = [], set()
    for i in range(1, MAX_SUPPLEANTS + 1):
        cid = str(saisie.get(f"suppleant{i}") or "").strip()
        if not cid:
            continue
        if cid not in ids:
            raise ReleveInvalide("Ce suppléant n'est pas un copropriétaire actuel")
        if cid == _syndic(fiche):
            raise ReleveInvalide("Le syndic ne peut pas être son propre suppléant")
        if cid in vus:
            raise ReleveInvalide("Le même copropriétaire est indiqué deux fois")
        vus.add(cid)
        role = str(saisie.get(f"role{i}") or "")
        if role not in ROLES:
            raise ReleveInvalide("Indiquez le rôle du suppléant")
        if role != "autre" and cid not in cs:
            raise ReleveInvalide(f"{ids[cid]['nom']} n'est pas au conseil syndical dans la fiche : "
                                 "corrigez la fiche ou choisissez « hors conseil syndical »")
        if role == "autre" and cid in cs:
            role = "membre_cs"
        try:
            accord = date.fromisoformat(str(saisie.get(f"accord{i}") or ""))
        except ValueError:
            raise ReleveInvalide(f"Date de l'accord de {ids[cid]['nom']} : demandez-lui d'abord s'il accepte")
        if accord > jour:
            raise ReleveInvalide("La date de l'accord est dans le futur")
        sup.append({"id": cid, "role": role, "accord_le": accord.isoformat()})
    if not sup:
        raise ReleveInvalide("Indiquez au moins un suppléant")
    r = charger(racine, copro)
    r["suppleants"] = sup
    r["modifie_le"] = jour.isoformat()
    return _sauver(racine, copro, r)


def partager(racine: Path, copro: str, actif: bool, renouveler: bool = False) -> dict:
    r = charger(racine, copro)
    if actif and not r["suppleants"]:
        raise ReleveInvalide("Désignez d'abord un suppléant")
    if actif and (renouveler or not r.get("jeton")):
        r["jeton"] = secrets.token_urlsafe(16)
    r["actif"] = bool(actif)
    return _sauver(racine, copro, r)


def jeton_valide(racine: Path, copro: str, propose: str) -> bool:
    r = charger(racine, copro)
    return bool(r.get("actif") and r.get("jeton") and r["suppleants"]) and \
        secrets.compare_digest(r["jeton"], propose or "")


def noter_telechargement(racine: Path, copro: str, quoi: str, par: str, quand: datetime | None = None) -> None:
    """quoi : dossier | convocation ; par : syndic | suppleant. Le syndic voit chaque téléchargement."""
    r = charger(racine, copro)
    r["telechargements"] = (r["telechargements"] + [
        {"le": (quand or datetime.now()).replace(microsecond=0).isoformat(), "quoi": quoi, "par": par}])[-20:]
    _sauver(racine, copro, r)


def acces_dossier(fiche: dict, r: dict) -> bool:
    """Le dossier complet (comptes, coordonnées) n'est remis qu'à un suppléant membre du conseil syndical."""
    cs = _cs(fiche)
    return any(s["id"] in cs for s in r["suppleants"])


# --------------------------------------------------------------------------- #
# Relève prête ?
# --------------------------------------------------------------------------- #
def etat(fiche: dict, r: dict, jour: date) -> list[dict]:
    """La liste « Relève prête ? » : [{ok (bool), titre, detail}]."""
    noms = {c["id"]: c for c in fiche["coproprietaires"]}
    cs = _cs(fiche)
    sup = r["suppleants"]
    roles = {s["role"] for s in sup}
    l = []

    def ajout(ok, titre, detail):
        l.append({"ok": bool(ok), "titre": titre, "detail": detail})

    ajout(sup, "Un suppléant a donné son accord",
          ", ".join(f"{noms[s['id']]['nom']} ({ROLES[s['role']]}, d'accord le {s['accord_le'][8:]}/"
                    f"{s['accord_le'][5:7]}/{s['accord_le'][:4]})" for s in sup)
          if sup else "Personne n'est désigné : choisissez un voisin de confiance, de préférence au conseil syndical.")
    if cooperatif(fiche):
        ok = "vice_president" in roles
        ajout(ok, "Un vice-président peut suppléer le syndic",
              "Il supplée le syndic en cas d'empêchement (syndicat coopératif, art. 17-1, à vérifier)." if ok else
              "Syndicat coopératif : le conseil syndical peut élire un vice-président qui supplée le syndic en cas "
              "d'empêchement (art. 17-1, à vérifier). Faites-le élire et indiquez-le comme suppléant.")
    else:
        ok = "president_cs" in roles
        ajout(ok, "Le président du conseil syndical est suppléant",
              ("Si le syndic est empêché, c'est lui qui peut convoquer l'assemblée générale pour désigner un "
               "nouveau syndic (art. 18, à vérifier).") if ok else
              ("Si le syndic est empêché, seul le président du conseil syndical peut convoquer l'assemblée générale "
               "pour désigner un nouveau syndic (art. 18, à vérifier) : désignez-le comme suppléant."))
    ajout(cs, "La copropriété a un conseil syndical",
          f"{len(cs)} membre{'s' if len(cs) > 1 else ''}." if cs else
          "Sans conseil syndical, seul le tribunal peut désigner un administrateur provisoire si le syndic "
          "disparaît. Proposez d'en élire un à la prochaine AG.")
    joignables = [s for s in sup if noms[s["id"]].get("email") or noms[s["id"]].get("adresse")
                  or noms[s["id"]].get("envoi") == "courrier"]
    ajout(sup and len(joignables) == len(sup), "Les suppléants sont joignables",
          "Coordonnées présentes dans la fiche." if sup and len(joignables) == len(sup)
          else "Complétez leurs coordonnées dans la fiche.")
    ajout(r.get("actif") and r.get("jeton"), "Le suppléant a son lien",
          "Envoyez-lui le lien de sa page : sans lui, il ne pourra rien récupérer si vous êtes injoignable."
          if not r.get("actif") else "Lien actif. Vous pouvez le renouveler à tout moment.")
    fin = fiche["gouvernance"]["syndic"].get("fin_mandat")
    fin = date.fromisoformat(str(fin)) if fin else None
    ajout(fin and (fin - jour).days > MANDAT_ALERTE_JOURS, "Le mandat du syndic court encore",
          f"Fin du mandat le {fin:%d/%m/%Y}." + ("" if fin and (fin - jour).days > MANDAT_ALERTE_JOURS
                                                   else " Inscrivez son renouvellement à la prochaine AG.")
          if fin else "Date de fin du mandat absente de la fiche.")
    vus = [t for t in r["telechargements"] if t["quoi"] == "dossier"]
    recent = vus and (jour - date.fromisoformat(vus[-1]["le"][:10])).days <= DOSSIER_VERIFIE_JOURS
    ajout(recent, "Le dossier de passation a été vérifié",
          f"Dernier téléchargement le {vus[-1]['le'][8:10]}/{vus[-1]['le'][5:7]}/{vus[-1]['le'][:4]}." if vus
          else "Téléchargez-le une fois pour vérifier qu'il contient bien tout. Il est fabriqué à la demande, "
               "donc toujours à jour.")
    return l


# --------------------------------------------------------------------------- #
# La marche à suivre et le projet de convocation
# --------------------------------------------------------------------------- #
def marche_a_suivre(fiche: dict) -> list[str]:
    if cooperatif(fiche):
        return [
            "Vérifiez que le syndic est vraiment empêché : maladie, décès, départ, silence prolongé malgré vos relances.",
            "Le vice-président assure la suppléance. Réunissez le conseil syndical pour élire un nouveau syndic "
            "parmi ses membres (syndicat coopératif, art. 17-1).",
            "Prévenez la banque de la copropriété, avec le procès-verbal de la réunion.",
            "Récupérez le dossier de passation ci-dessous : comptes, contrats, procès-verbaux, coordonnées.",
            "Informez les copropriétaires du changement.",
        ]
    return [
        "Vérifiez que le syndic est vraiment empêché : maladie, décès, départ, silence prolongé malgré vos relances.",
        "Le président du conseil syndical convoque l'assemblée générale pour désigner un nouveau syndic "
        "(art. 18). Le projet de convocation ci-dessous est prérempli : complétez la date et le lieu.",
        "La convocation part au moins 21 jours avant la réunion, par lettre recommandée, remise contre émargement "
        "ou courrier électronique pour ceux qui l'ont accepté.",
        "Récupérez le dossier de passation ci-dessous et remettez-le au nouveau syndic dès sa désignation.",
        "En cas d'urgence pour l'immeuble pendant ce temps : les numéros d'astreinte de la copropriété.",
    ]


def generer_convocation(fiche: dict, r: dict, jour: date, chemin: Path) -> Path:
    """Projet de convocation prérempli (AG, ou réunion du conseil syndical en coopératif)."""
    from html import escape as _e

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from avis_appel import FOND, CanevasNumerote, styles, tampon
    from fiche_copro import actuels
    S = styles()
    ident = fiche["copropriete"]
    noms = {c["id"]: c["nom"] for c in fiche["coproprietaires"]}
    coop = cooperatif(fiche)
    pres = next((s for s in r["suppleants"] if s["role"] == ("vice_president" if coop else "president_cs")),
                (r["suppleants"] or [None])[0])
    signataire = noms[pres["id"]] if pres else "[nom]"
    qualite = ("vice-président du conseil syndical" if coop else "président du conseil syndical")
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm, title="Projet de convocation")
    if coop:
        titre = "Convocation du conseil syndical"
        objet = ("Le syndic ne pouvant plus exercer ses fonctions, le conseil syndical est réuni pour élire un "
                 "nouveau syndic parmi ses membres (loi du 10 juillet 1965, art. 17-1).")
        odj = ["Constat de l'empêchement du syndic.",
               "Élection du syndic parmi les membres du conseil syndical ; il en devient le président.",
               "Élection, s'il y a lieu, d'un vice-président suppléant.",
               "Remise du dossier de passation au nouveau syndic."]
        dest = [noms[c] for c in _cs(fiche) if c != _syndic(fiche)]
    else:
        titre = "Convocation à l'assemblée générale"
        objet = ("Le syndic étant empêché d'exercer ses fonctions, le président du conseil syndical convoque "
                 "l'assemblée générale afin de désigner un nouveau syndic (loi du 10 juillet 1965, art. 18).")
        odj = ["Désignation du président de séance, du secrétaire et, s'il y a lieu, des scrutateurs (art. 24).",
               "Information sur l'empêchement du syndic.",
               "Désignation d'un nouveau syndic et fixation de la durée de son mandat (art. 25, et 25-1 à défaut).",
               "Mandat au nouveau syndic pour obtenir la remise des fonds, documents et archives (art. 18-2)."]
        dest = [c["nom"] for c in actuels(fiche)]
    h = [Paragraph(titre, S["titre"]),
         Paragraph(f"{_e(ident['nom'])} · {_e(ident.get('adresse', ''))}", S["sous"]), Spacer(1, 5 * mm),
         Paragraph(_e(objet), S["txt"]), Spacer(1, 4 * mm),
         Paragraph("<b>Date et heure :</b> [à compléter]<br/><b>Lieu :</b> [à compléter]", S["txt"]),
         Spacer(1, 4 * mm), Paragraph("<b>Ordre du jour</b>", S["txt"]), Spacer(1, 1 * mm)]
    t = Table([[Paragraph(f"{i}.", S["txt"]), Paragraph(_e(x), S["txt"])] for i, x in enumerate(odj, 1)],
              colWidths=[10 * mm, 164 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, -1), 0),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.3, FOND)]))
    h += [t, Spacer(1, 5 * mm),
          Paragraph(f"<b>Destinataires</b> ({len(dest)}) : {_e(', '.join(dest))}.", S["txt"]), Spacer(1, 5 * mm),
          Paragraph(f"Fait le [date], {_e(signataire)}, {qualite}.", S["txt"]), Spacer(1, 6 * mm)]
    note = ("Projet préparé avec Mitoyen. À vérifier avant envoi"
            + ("" if coop else " : délai d'au moins 21 jours, envoi par lettre recommandée, remise contre "
               "émargement ou courrier électronique pour ceux qui l'ont accepté ; joindre le formulaire de vote "
               "par correspondance et les candidatures connues")
            + ". Pas un conseil juridique : l'ADIL de votre département vous renseigne gratuitement.")
    bloc = Table([[Paragraph(_e(note), S["petit"])]], colWidths=[174 * mm])
    bloc.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FOND), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    h.append(bloc)
    pied = f"{ident['nom']} – Projet de convocation (relève du syndic)"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(True, pied), onLaterPages=tampon(True, pied))
    return chemin


def parametres_dossier(jour: date) -> dict:
    """Paramètres du dossier de transfert quand le successeur n'est pas encore connu."""
    return {"successeur": "Nouveau syndic, à désigner", "successeur_adresse": "", "cessation": jour,
            "date_soldes": None, "solde_courant": None, "solde_fonds_travaux": None}
