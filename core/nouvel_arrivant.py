"""
nouvel_arrivant.py — Le pack de bienvenue, en deux versions.

PROPRIÉTAIRE. Il devient membre du syndicat : il doit savoir qui gère, ce qu'il paiera
et quand, ce que représentent le fonds et le plan de travaux pour ses lots, et
choisir comment recevoir ses documents. Depuis le décret n° 2025-1292, la
notification électronique est la règle et chacun doit communiquer son adresse
électronique s'il n'a pas choisi le courrier : le pack se termine par un bulletin
de choix à rendre au syndic (mail ou courrier, prélèvement, proche aidant).
Un seul PDF : lettre et guide, fiche synthétique, bulletin.

LOCATAIRE. Il n'a aucun lien juridique avec le syndicat. Le pack est remis par son
BAILLEUR, qui doit lui communiquer les extraits du règlement sur la destination de
l'immeuble et l'usage des parties privatives et communes, et la quote-part du lot loué
dans chaque catégorie de charges (loi n° 89-462 du 6 juillet 1989, art. 3). Mitoyen
calcule ces quotes-parts et donne la vie de l'immeuble ; les extraits du règlement
restent à joindre par le bailleur. Aucune donnée du locataire n'entre dans Mitoyen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from vente import lots_vendus, pre_etat_date

AVERTISSEMENT = ("Document d'accueil préparé par l'assistant du syndic. Les informations pratiques ne remplacent pas le "
                 "règlement de copropriété, qui seul fait foi.")


class PackInvalide(ValueError):
    pass


def _syndic(fiche: dict) -> dict:
    sid = fiche["gouvernance"]["syndic"]["coproprietaire_id"]
    return next(c for c in fiche["coproprietaires"] if c["id"] == sid)


def _prochaine_ag(racine: Path | None, copro: str | None, jour: date) -> dict | None:
    if not (racine and copro):
        return None
    import ag as assemblee
    futures = [a for a in assemblee.lister_ag(racine, copro) if a["date"] >= jour.isoformat() and not a["depouillee"]]
    if not futures:
        return None
    a = assemblee.charger_ag(racine, copro, futures[0]["id"])
    return {"date": date.fromisoformat(a["date"]), "heure": a["heure"], "lieu": a["lieu"]}


def _doc(chemin: Path, titre: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    chemin.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm,
                             bottomMargin=18 * mm, title=titre)


def _vie_immeuble(fiche: dict, S, tableau, mm, Paragraph):
    items = fiche.get("vie_immeuble") or []
    if not items:
        return []
    from reportlab.platypus import Table, TableStyle

    from avis_appel import FILET
    lignes = [[Paragraph(f"<b>{i['theme']}</b>", S["txt"]), Paragraph(i["texte"], S["txt"])] for i in items]
    t = Table(lignes, colWidths=[42 * mm, 132 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, FILET), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [t]


# --------------------------------------------------------------------------- #
# Propriétaire
# --------------------------------------------------------------------------- #
def pack_proprietaire(fiche: dict, numeros: list[int], nom: str, chemin: Path, racine: Path | None = None,
                      copro: str | None = None, aujourd_hui: date | None = None, grand: bool = False) -> Path:
    from pypdf import PdfWriter
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

    import papier
    import vente
    from ag import _case
    from avis_appel import CanevasNumerote, essentiel, euros, styles, tableau, tampon
    nom = (nom or "").strip()[:80]
    if not nom:
        raise PackInvalide("Indiquer le nom du nouveau copropriétaire")
    try:
        lots_vendus(fiche, numeros)
    except vente.VenteInvalide as e:
        raise PackInvalide(str(e))
    jour = aujourd_hui or date.today()
    pre = pre_etat_date(fiche, numeros, racine, copro, None, jour)
    S = styles(grand)
    c = fiche["copropriete"]
    gouv = fiche["gouvernance"]
    syndic = _syndic(fiche)
    mode = "coopératif" if gouv["mode_gestion"] == "cooperatif" else "bénévole"
    conseil = [x["nom"] for x in fiche["coproprietaires"] if x["id"] in gouv.get("conseil_syndical", [])]
    ag = _prochaine_ag(racine, copro, jour)
    lots_txt = ", ".join(f"lot {l['numero']} ({l['desc'] or l['type']})" for l in pre["lots"])
    import reglement
    regl = reglement.valide(racine, copro) if racine and copro else None
    a_echoir = [e for e in pre["echeancier"] if e["statut"] == "à échoir"]

    h = [Paragraph(f"Bienvenue à la {c['nom']}", S["titre"]),
         Paragraph(f"{nom} · {lots_txt}", S["sous"]), Spacer(1, 4 * mm),
         Paragraph(f"Vous voici copropriétaire. La copropriété est gérée par un syndic {mode} : un copropriétaire, "
                   f"{syndic['nom']}, élu par l'assemblée générale et assisté d'un conseil syndical. Ce guide réunit "
                   "ce qu'il faut savoir pour bien démarrer"
                   + (" ; le règlement de copropriété en clair le suit." if regl else "."), S["txt"]), Spacer(1, 5 * mm)]
    chiffres = [("Vos charges par an", euros(pre["total_annuel_lots"]),
                 f"en {len(pre['echeancier'])} appels, budget {pre['exercice']}")]
    if a_echoir:
        chiffres.append(("Prochaine échéance", a_echoir[0]["date_fr"], euros(a_echoir[0]["montant"])))
    if ag:
        chiffres.append(("Prochaine AG", f"{ag['date']:%d/%m/%Y}", f"{ag['heure']}, {ag['lieu']}"))
    h += [essentiel(chiffres, grand=grand), Spacer(1, 6 * mm)]

    # 1. Qui fait quoi
    qui = [["Rôle", "Qui et comment"],
           [Paragraph("<b>Le syndic</b>", S["txt"]),
            Paragraph(f"{syndic['nom']}" + (f", {syndic['email']}" if syndic.get("email") else "")
                      + f". Mandat jusqu'au {gouv['syndic']['fin_mandat']:%d/%m/%Y}.", S["txt"])],
           [Paragraph("<b>Le conseil syndical</b>", S["txt"]), Paragraph(", ".join(conseil) or "—", S["txt"])],
           [Paragraph("<b>L'assemblée générale</b>", S["txt"]),
            Paragraph("Une fois par an au moins, tous les copropriétaires y votent le budget, les travaux et les "
                      "règles communes. Vous recevrez la convocation au moins 21 jours avant, avec un formulaire pour "
                      "voter par correspondance si vous ne pouvez pas venir.", S["txt"])]]
    h += [Paragraph("1. Qui fait quoi", S["sous"]), Spacer(1, 2 * mm),
          tableau(qui, [42 * mm, 132 * mm], aligner_droite_depuis=2, lignes_total=0, grand=grand), Spacer(1, 6 * mm)]

    # 2. Vos charges
    ch = [["Rubrique", "Par appel", "Par an"]] + [[r["libelle"], euros(r["par_appel"]), euros(r["annuel"])]
                                                  for r in pre["budget_annuel_lots"]]
    ch.append(["Total", euros(sum((r["par_appel"] for r in pre["budget_annuel_lots"]), Decimal("0"))),
               euros(pre["total_annuel_lots"])])
    dates = ", ".join(e["date_fr"] for e in pre["echeancier"])
    cs = fiche["appels_de_fonds"]["compte_separe"]
    h += [KeepTogether([
        Paragraph("2. Vos charges", S["sous"]), Spacer(1, 2 * mm),
        tableau(ch, [104 * mm, 34 * mm, 36 * mm], aligner_droite_depuis=1, grand=grand), Spacer(1, 2 * mm),
        Paragraph(f"Échéances de l'exercice : {dates}. Chaque appel arrive avec un avis détaillé. On paie par "
                  f"virement sur le compte du syndicat ({cs['titulaire']}, IBAN {cs['iban']}) avec la référence "
                  "indiquée sur l'avis, par chèque, ou par prélèvement automatique si vous le choisissez dans le bulletin joint.",
                  S["txt"])]), Spacer(1, 6 * mm)]

    # 3. Fonds et plan de travaux
    f = pre["fonds_travaux"]
    txt = (f"La copropriété met de côté chaque année pour ses futurs travaux. Votre cotisation au fonds de travaux est "
           f"comprise dans vos charges : {euros(f['derniere_cotisation_annuelle'])} par an.")
    if pre["plan"]:
        lourde = max(pre["plan"]["annees"], key=lambda a: a["total"])
        txt += (f" Le plan pluriannuel de travaux prévoit les grands travaux des dix prochaines années : pour vos lots, "
                f"{euros(pre['plan']['total'])} au total, dont {euros(lourde['total'])} en {lourde['annee']} "
                f"({lourde['travaux'] or 'cotisation'}). Ce sont des estimations, à confirmer en assemblée générale.")
    h += [KeepTogether([Paragraph("3. Les travaux à venir", S["sous"]), Spacer(1, 2 * mm), Paragraph(txt, S["txt"])]),
          Spacer(1, 6 * mm)]

    # 4. Vie de l'immeuble
    vie = _vie_immeuble(fiche, S, tableau, mm, Paragraph)
    if vie:
        h += [KeepTogether([Paragraph("4. La vie de l'immeuble", S["sous"]), Spacer(1, 2 * mm), *vie]),
              Spacer(1, 4 * mm)]
    # 5. Ce qui passe par un vote de l'assemblée générale, et comment le demander
    n_vote = 5 if vie else 4
    cas = ["<b>Des travaux chez vous qui touchent les parties communes ou l'aspect extérieur de l'immeuble</b> : "
           "percer un mur porteur, poser un climatiseur en façade, fermer un balcon ou une loggia, changer "
           "fenêtres ou volets pour un autre modèle ou une autre couleur.",
           "<b>Utiliser ou modifier une partie commune</b>, même un bout de couloir ou de jardin, même à vos frais.",
           "<b>Diviser ou réunir des lots</b> : la nouvelle répartition des charges est votée par l'assemblée.",
           "<b>Changer l'usage de votre lot</b> (un logement en local professionnel, par exemple) quand le règlement "
           "de copropriété l'encadre."]
    h += [KeepTogether([
        Paragraph(f"{n_vote}. Ce qui passe par un vote de l'assemblée générale", S["sous"]), Spacer(1, 2 * mm),
        Paragraph("Chez vous, vous êtes libre, sauf quand une décision touche à ce qui appartient à tous. Il faut "
                  "alors l'accord de l'assemblée générale <b>avant</b> de commencer. Les cas les plus courants :",
                  S["txt"]), Spacer(1, 1.5 * mm),
        *[Paragraph(f"• {x}", S["txt"]) for x in cas], Spacer(1, 1.5 * mm),
        Paragraph("Des travaux faits sans autorisation peuvent devoir être défaits à vos frais. En cas de doute, "
                  "demandez au syndic avant de commencer"
                  + (" ; le règlement en clair, joint, donne les règles propres à l'immeuble." if regl else "."),
                  S["txt"]), Spacer(1, 3 * mm),
        Paragraph("<b>Demander un vote.</b> À tout moment, vous pouvez demander au syndic d'inscrire une question à "
                  "l'ordre du jour de la prochaine assemblée (décret du 17 mars 1967, art. 10). Envoyez-lui votre "
                  "demande en lettre recommandée, papier ou électronique, avec le texte de la résolution que vous "
                  "proposez et, pour des travaux, un document qui en précise l'implantation et la consistance (plan, "
                  "devis). Une demande arrivée trop tard pour la prochaine assemblée est inscrite à la suivante. "
                  "Le syndic peut vous aider à rédiger la résolution ; un modèle de courrier gratuit est aussi "
                  "proposé sur mitoyen.app/demande.", S["txt"])]), Spacer(1, 6 * mm)]
    h += [Paragraph("Joints à ce guide : la fiche synthétique de la copropriété et, en dernière page, le bulletin de vos choix "
                    "à rendre au syndic. Le règlement de copropriété vous a été remis lors de la vente ; il s'applique "
                    "à vous comme à vos éventuels locataires.", S["txt"]), Spacer(1, 3 * mm),
          Paragraph(AVERTISSEMENT, S["petit"])]

    # Bulletin de choix
    def ligne(texte):
        return [_case(), Paragraph(texte, S["txt"])]

    bulletin = [
        ligne("Je reçois les documents de la copropriété <b>par mail</b>, à l'adresse : "
              "..........................................................................."),
        ligne("Je reçois les documents <b>par courrier</b> (lettre recommandée pour les notifications), à l'adresse : "
              "..........................................................................."),
        ligne("Je souhaite les documents <b>en grands caractères</b>"),
        ligne("Je choisis le <b>prélèvement automatique</b> de mes charges : le syndic me remet un mandat SEPA à signer"),
        ligne("Je souhaite qu'un <b>proche aidant</b> reçoive une copie de mes documents (sans droit de vote) : "
              "nom et contact ......................................................................"),
    ]
    tb = Table(bulletin, colWidths=[10 * mm, 164 * mm])
    tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    b = [Paragraph("Bulletin de choix", S["titre"]),
          Paragraph(f"À rendre au syndic, {syndic['nom']}" + (f" ({syndic['email']})" if syndic.get("email") else ""),
                    S["sous"]), Spacer(1, 4 * mm),
          Paragraph(f"Nom : <b>{nom}</b> · {lots_txt}", S["txt"]), Spacer(1, 4 * mm),
          Paragraph("Depuis le décret n° 2025-1292 du 22 décembre 2025, les notifications de la copropriété se font "
                    "par voie électronique, sauf si vous demandez le courrier. Dans le premier cas, vous devez "
                    "communiquer votre adresse électronique au syndic.", S["txt"]), Spacer(1, 4 * mm),
          tb, Spacer(1, 6 * mm),
          Paragraph("Fait à ............................................, le ...... / ...... / ............", S["txt"]),
          Spacer(1, 3 * mm), Paragraph("Signature :", S["txt"]), Spacer(1, 16 * mm),
          Paragraph(papier.MENTION_PAPIER, S["petit"])]

    # Trois documents, chacun avec sa numérotation, réunis dans un seul PDF :
    # le guide, la fiche synthétique, puis le bulletin, à détacher et rendre au syndic.
    from pypdf import PdfReader
    tmp = [chemin.with_suffix(f".{x}.pdf") for x in ("guide", "fiche") + (("reglement",) if regl else ()) + ("bulletin",)]
    pied = f"{c['nom']} – bienvenue – {nom}"
    _doc(tmp[0], "Bienvenue").build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied),
                                    onLaterPages=tampon(False, pied))
    vente.generer_fiche_synthetique(fiche, tmp[1], jour)
    if regl:
        reglement.generer_pdf(fiche, regl, tmp[2], grand=grand)
    pied_b = f"{c['nom']} – bulletin de choix – {nom}"
    _doc(tmp[-1], "Bulletin de choix").build(b, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied_b),
                                            onLaterPages=tampon(False, pied_b))
    w = PdfWriter()
    for t in tmp:
        for p in PdfReader(str(t)).pages:
            w.add_page(p)
    w.add_metadata({"/Title": f"Bienvenue à la {c['nom']}"})
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "wb") as fh:
        w.write(fh)
    for t in tmp:
        t.unlink()
    return chemin


# --------------------------------------------------------------------------- #
# Locataire (remis par le bailleur)
# --------------------------------------------------------------------------- #
def quotes_parts(fiche: dict, numeros: list[int]) -> list[dict]:
    """Quote-part des lots dans chaque catégorie de charges (loi 1989, art. 3)."""
    res = []
    for cle, v in fiche["cles_repartition"].items():
        t = sum(l["tantiemes"].get(cle, 0) for l in fiche["lots"] if l["numero"] in numeros)
        if t:
            res.append({"cle": cle, "libelle": v["libelle"], "tantiemes": t, "base": v["base"],
                        "pourcentage": (Decimal(t) * 100 / Decimal(v["base"])).quantize(Decimal("0.01"))})
    return res


def pack_locataire(fiche: dict, numeros: list[int], chemin: Path, racine: Path | None = None,
                   copro: str | None = None, aujourd_hui: date | None = None, grand: bool = False) -> Path:
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer

    from avis_appel import CanevasNumerote, styles, tableau, tampon
    par_num = {l["numero"]: l for l in fiche["lots"]}
    inconnus = [n for n in numeros if n not in par_num]
    if not numeros or inconnus:
        raise PackInvalide(f"Lot(s) inconnu(s) : {', '.join(map(str, inconnus))}" if inconnus else "Indiquer le lot loué")
    if len({par_num[n]["proprietaire"] for n in numeros}) > 1:
        raise PackInvalide("Les lots indiqués appartiennent à plusieurs propriétaires")
    if not any(par_num[n]["type"] in ("appartement", "maison", "studio", "habitation") for n in numeros):
        raise PackInvalide("Le pack locataire concerne un logement")
    S = styles(grand)
    c = fiche["copropriete"]
    syndic = _syndic(fiche)
    lots_txt = ", ".join(f"lot {n} ({par_num[n].get('desc') or par_num[n]['type']})" for n in sorted(numeros))
    h = [Paragraph(f"Bienvenue à la {c['nom']}", S["titre"]),
         Paragraph(f"{c['adresse']} · {lots_txt}", S["sous"]), Spacer(1, 4 * mm),
         Paragraph("Ce document vous est remis par votre bailleur. Il présente l'immeuble et ses règles de vie.",
                   S["txt"]), Spacer(1, 5 * mm)]
    qui = [["Pour…", "Contactez"],
           [Paragraph("Votre logement : loyer, réparations, équipements, assurance", S["txt"]),
            Paragraph("Votre bailleur", S["txt"])],
           [Paragraph("Les parties communes : hall, ascenseur, jardin, éclairage, propreté", S["txt"]),
            Paragraph(f"Le syndic, {syndic['nom']}" + (f" ({syndic['email']})" if syndic.get("email") else ""),
                      S["txt"])]]
    h += [Paragraph("Qui contacter", S["sous"]), Spacer(1, 2 * mm),
          tableau(qui, [104 * mm, 70 * mm], aligner_droite_depuis=2, lignes_total=0, grand=grand), Spacer(1, 6 * mm)]
    vie = _vie_immeuble(fiche, S, tableau, mm, Paragraph)
    if vie:
        h += [KeepTogether([Paragraph("La vie de l'immeuble", S["sous"]), Spacer(1, 2 * mm), *vie]), Spacer(1, 6 * mm)]
    h += [Paragraph("Les décisions de l'assemblée générale qui concernent les occupants sont affichées dans le hall.",
                    S["txt"]), Spacer(1, 6 * mm)]
    qp = [["Catégorie de charges", "Tantièmes", "Quote-part"]] + [
        [q["libelle"], f"{q['tantiemes']} / {q['base']}", f"{q['pourcentage']} %".replace(".", ",")]
        for q in quotes_parts(fiche, numeros)]
    h += [KeepTogether([
        Paragraph("Quote-part du logement dans chaque catégorie de charges", S["sous"]), Spacer(1, 2 * mm),
        tableau(qp, [104 * mm, 36 * mm, 34 * mm], aligner_droite_depuis=1, lignes_total=0, grand=grand),
        Spacer(1, 2 * mm),
        Paragraph("Information que le bailleur doit vous communiquer (loi n° 89-462 du 6 juillet 1989, art. 3), avec "
                  "les extraits du règlement de copropriété sur la destination de l'immeuble et l'usage des parties "
                  "privatives et communes, qu'il joint à ce document.", S["petit"])]),
          Spacer(1, 4 * mm), Paragraph(AVERTISSEMENT, S["petit"])]
    pied = f"{c['nom']} – bienvenue – document remis par le bailleur"
    import reglement
    regl = reglement.valide(racine, copro) if racine and copro else None
    cible = chemin.with_suffix(".guide.pdf") if regl else chemin
    _doc(cible, "Bienvenue").build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied),
                                   onLaterPages=tampon(False, pied))
    if regl:     # les règles de vie en clair, à la suite (les extraits officiels restent à joindre)
        from pypdf import PdfReader, PdfWriter
        extraits = chemin.with_suffix(".reglement.pdf")
        reglement.generer_pdf(fiche, regl, extraits, reglement.USAGE_LOCATAIRE, grand=grand)
        w = PdfWriter()
        for t in (cible, extraits):
            for pg in PdfReader(str(t)).pages:
                w.add_page(pg)
        w.add_metadata({"/Title": f"Bienvenue à la {c['nom']}"})
        with open(chemin, "wb") as fh:
            w.write(fh)
        cible.unlink()
        extraits.unlink()
    return chemin
