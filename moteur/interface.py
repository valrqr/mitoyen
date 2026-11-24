"""
interface.py — L'interface web du syndic.

Des pages HTML servies par le moteur lui-même (Jinja2), rendues vivantes par htmx :
un clic sur « Confirmer » met à jour la ligne sans recharger la page. Pas de
framework JavaScript, pas de service externe : la police et htmx sont servis par
l'application.

Connexion : un mot de passe (INTERFACE_MOT_DE_PASSE, à défaut MOTEUR_TOKEN) ouvre une
session signée de 8 heures. Les PDF sont ceux des routes existantes de l'API, qui
acceptent la session du syndic à la place de la clé.

Les écrans de séance d'AG sur tablette et le suivi de chantier relèvent du dépôt privé.
"""

from __future__ import annotations

import hmac
import json
import os
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import api as A

ICI = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(ICI / "templates"))
routeur = APIRouter(prefix="/app", include_in_schema=False)
statiques = StaticFiles(directory=str(ICI / "static"))

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


# --------------------------------------------------------------------------- #
# Outils de présentation
# --------------------------------------------------------------------------- #
def euros(m) -> str:
    from avis_appel import euros as e
    return e(Decimal(str(m)))


def euros_rond(m) -> str:
    from avis_appel import euros_rond as e
    return e(Decimal(str(m)))


def date_fr(d, longue: bool = False) -> str:
    if not d:
        return ""
    d = date.fromisoformat(d) if isinstance(d, str) else d
    if longue:
        return f"{JOURS[d.weekday()]} {d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


templates.env.filters.update(euros=euros, euros_rond=euros_rond, date_fr=date_fr)


# --------------------------------------------------------------------------- #
# Points d'extension, pour les modules complémentaires
# --------------------------------------------------------------------------- #
RUBRIQUES_EXTENSIONS: list[tuple[str, str, str]] = []   # (onglet, chemin sous /app/<copro>, libellé)
TACHES_EXTENSIONS: list = []                              # fonctions (copro, fiche, jour) -> liste de tâches
LIENS_AG_EXTENSIONS: list[tuple[str, str]] = []           # (libellé, chemin sous /app/<copro>/ag/<id>)


def ajouter_module(rubriques=(), taches=(), gabarits: Path | None = None, liens_ag=()) -> None:
    """Un module complémentaire ajoute ses rubriques, ses tâches du tableau de bord et ses gabarits.
    Ses gabarits passent avant ceux du moteur, mais ne doivent pas en reprendre les noms."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    RUBRIQUES_EXTENSIONS.extend(r for r in rubriques if r not in RUBRIQUES_EXTENSIONS)
    TACHES_EXTENSIONS.extend(t for t in taches if t not in TACHES_EXTENSIONS)
    LIENS_AG_EXTENSIONS.extend(l for l in liens_ag if l not in LIENS_AG_EXTENSIONS)
    if gabarits is not None:
        templates.env.loader = ChoiceLoader([FileSystemLoader(str(gabarits)), templates.env.loader])


templates.env.globals["rubriques_extensions"] = RUBRIQUES_EXTENSIONS
templates.env.globals["liens_ag_extensions"] = LIENS_AG_EXTENSIONS


def aujourdhui(request: Request) -> date:
    """La date du jour, ou celle de la démonstration (?au=2027-05-20, gardée en session)."""
    au = request.query_params.get("au")
    if au:
        try:
            request.session["au"] = date.fromisoformat(au).isoformat()
        except ValueError:
            pass
    if request.query_params.get("au") == "":
        request.session.pop("au", None)
    return date.fromisoformat(request.session["au"]) if request.session.get("au") else date.today()


def connecte(request: Request) -> bool:
    return bool(request.session.get("syndic"))


def page(request: Request, gabarit: str, copro: str | None = None, **ctx) -> HTMLResponse:
    fiche = A.fiche_de(copro) if copro else None
    ctx.setdefault("onglet", gabarit.split(".")[0])
    return templates.TemplateResponse(request, gabarit, {
        "copro": copro, "fiche": fiche, "copros": A.lister_copros(), "jour": aujourdhui(request),
        "jour_demo": request.session.get("au"), "message": request.session.pop("message", None), **ctx})


def exiger(request: Request, copro: str | None = None) -> None:
    if not connecte(request):
        raise HTTPException(303, headers={"Location": "/app/connexion"})
    if copro is not None:
        if copro not in A.lister_copros():
            raise HTTPException(404, "Copropriété inconnue")


def retour(chemin: str, message: str | None = None, request: Request | None = None) -> RedirectResponse:
    if message and request is not None:
        request.session["message"] = message
    return RedirectResponse(chemin, status_code=303)


def mot_de_passe_attendu() -> str:
    return os.getenv("INTERFACE_MOT_DE_PASSE") or A.TOKEN


# --------------------------------------------------------------------------- #
# Connexion
# --------------------------------------------------------------------------- #
@routeur.get("/connexion", response_class=HTMLResponse)
def connexion_page(request: Request):
    return page(request, "connexion.html", erreur=None)


@routeur.post("/connexion", response_class=HTMLResponse)
def connexion(request: Request, mot_de_passe: str = Form(...)):
    attendu = mot_de_passe_attendu()
    if attendu and hmac.compare_digest(mot_de_passe.encode(), attendu.encode()):
        request.session.clear()
        request.session["syndic"] = True
        return retour("/app", None)
    return page(request, "connexion.html", erreur="Mot de passe incorrect.")


@routeur.post("/deconnexion")
def deconnexion(request: Request):
    request.session.clear()
    return retour("/app/connexion")


@routeur.get("", response_class=HTMLResponse)
def accueil(request: Request):
    exiger(request)
    copros = A.lister_copros()
    if len(copros) == 1:
        return retour(f"/app/{copros[0]}")
    return page(request, "choix.html", onglet="choix")


# --------------------------------------------------------------------------- #
# Tableau de bord : ce qui est à faire
# --------------------------------------------------------------------------- #
def _etat_impayes(fiche, copro, jour):
    if not A.banque.charger_operations(A.DOSSIER_DATA, copro):
        return None
    return A.impayes.etat(fiche, A.DOSSIER_SORTIE, A.DOSSIER_DATA, copro, jour)


def _appels(fiche, copro):
    import json
    ex = fiche["budget_previsionnel"]["exercice"]
    res = []
    for t, mmjj in enumerate(fiche["appels_de_fonds"]["dates_exigibilite"], 1):
        mm, jj = (int(x) for x in mmjj.split("-"))
        f = A.dossier_appel(A.DOSSIER_SORTIE, copro, ex, t) / "envoi.json"
        e = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
        res.append({"trimestre": t, "exercice": ex, "date": date(ex, mm, jj), "statut": e["statut"] if e else None,
                    "total": e.get("total") if e else None, "nb": len(e["avis"]) if e else 0})
    return res


def _prochaine_ag(copro, jour):
    futures = [a for a in A.assemblee.lister_ag(A.DOSSIER_DATA, copro)
               if a["date"] >= jour.isoformat() and not a["depouillee"]]
    return futures[0] if futures else None


@routeur.get("/{copro}", response_class=HTMLResponse)
def tableau_de_bord(request: Request, copro: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    ech = A.rapport_echeancier(copro, fiche, jour, 120)
    imp = _etat_impayes(fiche, copro, jour)
    ag = _prochaine_ag(copro, jour)
    a_faire = []
    if imp:
        n = sum(1 for p in imp["relances"] if p["etat"] == "a_preparer")
        if imp["a_confirmer"]:
            n_c = len(imp["a_confirmer"])
            a_faire.append({"texte": f"{n_c} paiement{'s' if n_c > 1 else ''} à confirmer",
                            "detail": "Des virements reconnus par le nom ou le montant attendent votre accord.",
                            "lien": f"/app/{copro}/impayes#a-confirmer", "niveau": "urgent"})
        if n:
            a_faire.append({"texte": f"{n} relance{'s' if n > 1 else ''} à préparer", "detail": "Mitoyen a préparé la liste ; la lettre "
                            "se génère en un clic.", "lien": f"/app/{copro}/impayes#relances", "niveau": "urgent"})
        for p in imp["relances"]:
            if p["etat"] == "delai_expire":
                a_faire.append({"texte": f"Mise en demeure sans effet : {p['nom']}", "detail": p["message"],
                                "lien": f"/app/{copro}/impayes#relances", "niveau": "urgent"})
    if ag:
        cal = A.assemblee.calendrier(fiche, A.ag_de(copro, ag["id"]), jour)
        limite = date.fromisoformat(cal["limite_notification"])
        if 0 <= (limite - jour).days <= 14:
            a_faire.append({"texte": "Convocations de l'AG à notifier",
                            "detail": f"Au plus tard le {date_fr(limite)} pour l'AG du {date_fr(ag['date'])}, avec le "
                                      "formulaire de vote par correspondance.",
                            "lien": f"/app/{copro}/ag/{ag['id']}",
                            "niveau": "urgent" if (limite - jour).days <= 7 else "important"})
    for a in _appels(fiche, copro):
        if a["statut"] != "valide" and 0 <= (a["date"] - jour).days <= 45:
            a_faire.append({"texte": f"Appel de fonds du {a['trimestre']}{'er' if a['trimestre'] == 1 else 'e'} "
                                     f"trimestre à {'valider' if a['statut'] else 'préparer'}",
                            "detail": f"Exigible le {date_fr(a['date'])}.", "lien": f"/app/{copro}/appels",
                            "niveau": "urgent" if (a["date"] - jour).days <= 21 else "important"})
            break
    for al in ech["alertes"]:
        if al["type"] == "impayes":
            continue
        if al["niveau"] in ("urgent", "important") or len(a_faire) < 6:
            a_faire.append({"texte": al["titre"], "detail": al["message"],
                            "date": al.get("date"), "lien": None, "niveau": al["niveau"]})
    a_faire.extend(A.signalements.taches(A.DOSSIER_DATA, copro, fiche, jour))
    for ext in TACHES_EXTENSIONS:
        a_faire.extend(ext(copro, fiche, jour))
    ordre = {"urgent": 0, "important": 1}
    a_faire.sort(key=lambda x: ordre.get(x["niveau"], 2))
    solde_ft = (fiche["fonds_travaux"].get("solde") or {}).get("montant")
    return page(request, "tableau.html", copro, a_faire=a_faire[:10], reste=max(0, len(a_faire) - 10), imp=imp,
                ag=ag, solde_ft=solde_ft, appels=_appels(fiche, copro))


# --------------------------------------------------------------------------- #
# Impayés
# --------------------------------------------------------------------------- #
@routeur.get("/{copro}/impayes", response_class=HTMLResponse)
def impayes_page(request: Request, copro: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    imp = _etat_impayes(fiche, copro, jour)
    regs = {r["id"]: r for r in A.impayes.charger_relances(A.DOSSIER_DATA, copro)}
    return page(request, "impayes.html", copro, imp=imp, relances_reg=regs,
                coproprietaires=sorted(fiche["coproprietaires"], key=lambda c: c["nom"]))


@routeur.post("/{copro}/impayes/releve")
async def impayes_releve(request: Request, copro: str, fichier: UploadFile = File(...)):
    exiger(request, copro)
    contenu = await fichier.read(A.banque.TAILLE_MAX + 1)
    try:
        r = A.banque.importer(A.DOSSIER_DATA, copro, contenu, fichier.filename or "releve.csv", aujourdhui(request))
    except A.banque.ReleveInvalide as e:
        return retour(f"/app/{copro}/impayes", f"Relevé refusé : {e}", request)
    msg = (f"Relevé importé : {r['nouvelles']} opération(s) nouvelle(s)"
           + (f", {r['deja_connues']} déjà connue(s)" if r["deja_connues"] else "")
           + (f", {len(r['ignorees'])} ligne(s) illisible(s)" if r["ignorees"] else "") + ".")
    return retour(f"/app/{copro}/impayes", msg, request)


@routeur.post("/{copro}/impayes/operations/{op_id}", response_class=HTMLResponse)
def impayes_affecter(request: Request, copro: str, op_id: str, statut: str = Form(...),
                     coproprietaire: str | None = Form(None)):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    try:
        A.impayes.affecter(fiche, A.DOSSIER_DATA, copro, op_id, statut, coproprietaire, aujourdhui(request))
    except A.impayes.RecouvrementInvalide as e:
        return HTMLResponse(f'<tr><td colspan="5" class="erreur">{e}</td></tr>')
    nom = next((c["nom"] for c in fiche["coproprietaires"] if c["id"] == coproprietaire), "")
    texte = f"Rattaché à {nom}." if statut == "confirme" else "Ignoré : sans rapport avec les charges."
    return templates.TemplateResponse(request, "_ligne_faite.html", {"texte": texte, "colonnes": 5,
                                                                     "copro": copro, "op_id": op_id})


@routeur.post("/{copro}/impayes/relances/{cid}", response_class=HTMLResponse)
def impayes_preparer(request: Request, copro: str, cid: str):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    jour = aujourdhui(request)
    try:
        A.impayes.preparer_relance(fiche, A.DOSSIER_SORTIE, A.DOSSIER_DATA, copro, cid,
                                   A.DOSSIER_SORTIE / copro / "recouvrement", jour)
    except A.impayes.RecouvrementInvalide as e:
        return HTMLResponse(f'<tr><td colspan="5" class="erreur">{e}</td></tr>')
    return _ligne_relance(request, copro, cid, jour)


@routeur.post("/{copro}/impayes/relances/{cid}/envoi", response_class=HTMLResponse)
def impayes_envoyee(request: Request, copro: str, cid: str, relance: str = Form(...), envoyee_le: date = Form(...),
                    moyen: str = Form("email"), presentee_le: str = Form("")):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    try:
        A.impayes.marquer(fiche, A.DOSSIER_DATA, copro, relance, "envoyee", envoyee_le, moyen,
                          date.fromisoformat(presentee_le) if presentee_le else None)
    except (A.impayes.RecouvrementInvalide, ValueError) as e:
        return HTMLResponse(f'<tr><td colspan="5" class="erreur">{e}</td></tr>')
    return _ligne_relance(request, copro, cid, aujourdhui(request))


def _ligne_relance(request, copro, cid, jour):
    fiche = A.fiche_de(copro)
    imp = A.impayes.etat(fiche, A.DOSSIER_SORTIE, A.DOSSIER_DATA, copro, jour)
    p = next((x for x in imp["relances"] if x["coproprietaire"] == cid), None)
    regs = {r["id"]: r for r in A.impayes.charger_relances(A.DOSSIER_DATA, copro)}
    return templates.TemplateResponse(request, "_ligne_relance.html",
                                      {"p": p, "copro": copro, "relances_reg": regs, "jour": jour})


# --------------------------------------------------------------------------- #
# Appels de fonds
# --------------------------------------------------------------------------- #
@routeur.get("/{copro}/appels", response_class=HTMLResponse)
def appels_page(request: Request, copro: str):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    return page(request, "appels.html", copro, appels=_appels(fiche, copro))


@routeur.post("/{copro}/appels/{trimestre}")
def appels_generer(request: Request, copro: str, trimestre: int, final: bool = Form(False)):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    try:
        r = A.generer_appel(fiche, copro, trimestre, A.DOSSIER_SORTIE, final)
    except A.FicheInvalide as e:
        return retour(f"/app/{copro}/appels", "Fiche invalide : " + " ; ".join(e.erreurs[:3]), request)
    msg = (f"{len(r['avis'])} avis {'validés et prêts à envoyer' if final else 'générés en version PROJET : relisez le récapitulatif'}"
           f" ({r['total']}).")
    return retour(f"/app/{copro}/appels", msg, request)


# --------------------------------------------------------------------------- #
# Assemblées générales
# --------------------------------------------------------------------------- #
@routeur.get("/{copro}/ag", response_class=HTMLResponse)
def ag_page(request: Request, copro: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    ags = A.assemblee.lister_ag(A.DOSSIER_DATA, copro)
    return page(request, "ag.html", copro, ags=sorted(ags, key=lambda a: a["date"], reverse=True),
                odj=A.odj_type(copro)["resolutions"], date_conseillee=(jour + timedelta(days=45)).isoformat())


@routeur.post("/{copro}/ag")
def ag_creer(request: Request, copro: str, date_ag: date = Form(...), heure: str = Form(...), lieu: str = Form(...),
             titre: str = Form("Assemblée générale ordinaire"), visio: str = Form(""), odj_type: bool = Form(False),
             autres: str = Form("")):
    exiger(request, copro)
    resolutions = []
    if odj_type:
        resolutions += [A.ResolutionAG(**{k: r[k] for k in ("titre", "majorite") if k in r}, texte=r.get("texte", ""))
                        for r in A.odj_type(copro)["resolutions"]]
    resolutions += [A.ResolutionAG(titre=l.strip()[:200]) for l in autres.splitlines() if len(l.strip()) >= 3]
    try:
        corps = A.NouvelleAG(date=date_ag, heure=heure, lieu=lieu, titre=titre, visio=visio or None,
                             resolutions=resolutions)
        a = A.creer_ag(corps, copro)
    except HTTPException as e:
        return retour(f"/app/{copro}/ag", f"AG non créée : {e.detail}", request)
    except ValueError as e:
        return retour(f"/app/{copro}/ag", f"AG non créée : {e}", request)
    msg = "AG préparée." + (" " + " ".join(a["points_ajoutes"]) + "." if a.get("points_ajoutes") else "")
    return retour(f"/app/{copro}/ag/{a['id']}", msg, request)


@routeur.get("/{copro}/ag/{ag_id}", response_class=HTMLResponse)
def ag_detail(request: Request, copro: str, ag_id: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    a = A.ag_de(copro, ag_id)
    cal = A.assemblee.calendrier(fiche, a, jour)
    rap = A.rappel_ag.rappels(fiche, a, copro, jour)
    return page(request, "ag_detail.html", copro, onglet="ag", a=a, cal=cal, rappel=rap,
                coproprietaires=sorted(fiche["coproprietaires"], key=lambda c: c["nom"]))


# --------------------------------------------------------------------------- #
# Copropriétaires : le tableau d'interphone
# --------------------------------------------------------------------------- #
ETAGES = {-1: "Sous-sol", 0: "Rez-de-chaussée"}


@routeur.get("/{copro}/coproprietaires", response_class=HTMLResponse)
def coproprietaires_page(request: Request, copro: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    imp = _etat_impayes(fiche, copro, jour)
    syndic = fiche["gouvernance"]["syndic"]["coproprietaire_id"]
    conseil = set(fiche["gouvernance"].get("conseil_syndical", []))
    mt = {d["coproprietaire"] for d in A.meubles_tourisme.actives(A.meubles_tourisme.charger(A.DOSSIER_DATA, copro), jour)}
    cartes = []
    for c in fiche["coproprietaires"]:
        lots = sorted((l for l in fiche["lots"] if l["proprietaire"] == c["id"]), key=lambda l: l["numero"])
        hab = [l for l in lots if l["type"] not in ("cave", "parking")] or lots
        canal = A.papier.canal(fiche, c["id"], jour)["canal"]
        cartes.append({"c": c, "lots": lots, "etage": max((l.get("etage", 0) for l in hab), default=0),
                       "canal": canal, "role": "Syndic" if c["id"] == syndic else "Conseil syndical" if c["id"] in conseil else None,
                       "impaye": imp["comptes"][c["id"]]["impaye"] if imp else None, "meuble_tourisme": c["id"] in mt})
    etages = {}
    for k in sorted(cartes, key=lambda k: (-k["etage"], k["lots"][0]["numero"] if k["lots"] else 0)):
        nom = ETAGES.get(k["etage"], f"{k['etage']}{'er' if k['etage'] == 1 else 'e'} étage")
        etages.setdefault(nom, []).append(k)
    return page(request, "coproprietaires.html", copro, etages=etages)


# --------------------------------------------------------------------------- #
# Travaux : dossiers et devis
# --------------------------------------------------------------------------- #
QUI_DECIDE = {"assemblee_generale": "L'assemblée générale", "conseil_syndical": "Le conseil syndical",
              "syndic": "Le syndic", "syndic_urgence": "Le syndic (urgence)", "a_determiner": "À déterminer"}


def _fourchette(comp) -> tuple | None:
    montants = [d["montant_ttc"] for d in comp["devis"] if not d["expire"]] or [d["montant_ttc"] for d in comp["devis"]]
    return (min(montants), max(montants)) if montants else None


@routeur.get("/{copro}/travaux", response_class=HTMLResponse)
def travaux_page(request: Request, copro: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    dossiers = []
    for x in reversed(A.travaux.lister_dossiers(A.DOSSIER_DATA, copro)):
        d = A.travaux.charger_dossier(A.travaux.dossier_dir(A.DOSSIER_DATA, copro, x["id"]))
        synth = A.travaux.synthese(fiche, d, jour)
        dossiers.append({**x, "fourchette": _fourchette(synth["comparatif"]),
                         "qui": QUI_DECIDE.get(synth["aiguillage"]["circuit"], ""),
                         "nb_alertes": len(synth["comparatif"]["alertes"]), "plan_ligne": d.get("plan_ligne")})
    return page(request, "travaux.html", copro, dossiers=dossiers, natures=A.travaux.NATURES,
                cles=fiche["cles_repartition"], a_un_plan=bool(A.plan_travaux.plan_de(fiche)))


@routeur.post("/{copro}/travaux")
def travaux_creer(request: Request, copro: str, titre: str = Form(...), description: str = Form(""),
                  nature: str = Form("reparation"), cle: str = Form("generales"), urgence: bool = Form(False)):
    exiger(request, copro)
    try:
        d = A.travaux.creer_dossier(A.DOSSIER_DATA, copro, A.fiche_de(copro), titre[:120], description[:4000],
                                    nature, urgence, cle, aujourdhui(request))
    except A.travaux.DossierInvalide as e:
        return retour(f"/app/{copro}/travaux", f"Dossier non créé : {e}", request)
    return retour(f"/app/{copro}/travaux/{d['id']}", "Dossier ouvert. Ajoutez les devis au fur et à mesure.", request)


def _dossier(copro: str, dossier_id: str) -> dict:
    chemin = A.travaux.dossier_dir(A.DOSSIER_DATA, copro, dossier_id)
    if "/" in dossier_id or ".." in dossier_id or not (chemin / "dossier.yaml").is_file():
        raise HTTPException(404, "Dossier de travaux introuvable")
    return A.travaux.charger_dossier(chemin)


@routeur.get("/{copro}/travaux/{dossier_id}", response_class=HTMLResponse)
def travaux_dossier(request: Request, copro: str, dossier_id: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    synth = A.travaux.synthese(fiche, _dossier(copro, dossier_id), jour)
    comp = synth["comparatif"]
    # Les devis dans leur ordre d'arrivée : l'interface ne classe ni ne met en avant aucun devis
    devis = sorted(comp["devis"], key=lambda x: int(x["id"][1:]))
    for x in devis:
        alertes = (x.get("verification") or {}).get("alertes") or []
        x["verif"] = (None if not x.get("verification") else
                      f"{len(alertes)} point{'s' if len(alertes) > 1 else ''} à regarder" if alertes else "Vérifiée")
    ordre = [x["id"] for x in devis]
    fourchette = _fourchette(comp)
    ecart_plan = None
    if synth["dossier"].get("estimation_plan") and fourchette:   # rapportée à l'estimation, sans désigner de devis
        est = Decimal(synth["dossier"]["estimation_plan"])
        ecart_plan = [((m - est) / est * 100).quantize(Decimal("1")) for m in fourchette]
    return page(request, "travaux_dossier.html", copro, onglet="travaux", d=synth["dossier"], comp=comp,
                devis=devis, ordre=ordre, aig=synth["aiguillage"], fourchette=fourchette, ecart_plan=ecart_plan,
                qui=QUI_DECIDE.get(synth["aiguillage"]["circuit"], ""), natures=A.travaux.NATURES)


@routeur.post("/{copro}/travaux/{dossier_id}/devis")
async def travaux_devis(request: Request, copro: str, dossier_id: str, entreprise: str = Form(...),
                        montant_ht: str = Form(...), taux_tva: str = Form("10"), delai_jours: str = Form(""),
                        valide_jusqu_au: str = Form(""), remarques: str = Form(""),
                        fichier: UploadFile | None = File(None)):
    exiger(request, copro)
    d = _dossier(copro, dossier_id)
    pdf = None
    if fichier is not None and fichier.filename:
        pdf = await fichier.read(A.travaux.TAILLE_MAX_PDF + 1)
    try:
        validite = date.fromisoformat(valide_jusqu_au) if valide_jusqu_au else None
        delai = int(delai_jours) if delai_jours.strip() else None
        x = A.travaux.ajouter_devis(A.DOSSIER_DATA, copro, d, entreprise[:120], montant_ht, taux_tva, delai,
                                    validite, remarques[:2000], pdf, aujourdhui(request))
    except (A.travaux.DossierInvalide, ValueError) as e:
        return retour(f"/app/{copro}/travaux/{dossier_id}#ajouter", f"Devis non ajouté : {e}", request)
    return retour(f"/app/{copro}/travaux/{dossier_id}", f"Devis {x['id']} de {x['entreprise']} ajouté.", request)


# --------------------------------------------------------------------------- #
# Plan pluriannuel de travaux
# --------------------------------------------------------------------------- #
def _graphique(proj) -> dict:
    """Les barres du graphique : par année, la part prise sur le fonds et l'appel en plus."""
    annees = proj["annees"]
    haut = max([a["montant_travaux"] for a in annees] + [Decimal(1)])
    barres = []
    for a in annees:
        barres.append({"annee": a["annee"], "travaux": a["montant_travaux"], "fonds": a["pris_sur_fonds"],
                       "appel": a["appel_complementaire"], "solde": a["solde_fin"],
                       "h_fonds": float(a["pris_sur_fonds"] / haut * 100),
                       "h_appel": float(a["appel_complementaire"] / haut * 100)})
    return {"barres": barres, "haut": haut}


def _simulation(fiche, suivi, cotisation, indexation) -> dict:
    proj = A.plan_travaux.projection(fiche, suivi, cotisation, indexation)
    lissage = A.plan_travaux.cotisation_lissee(fiche, suivi, indexation)
    cmin = A.plan_travaux.cotisation_minimale(fiche)
    return {"proj": proj, "lissage": lissage, "cmin": cmin, "graphique": _graphique(proj),
            "en_bref": A.plan_travaux.en_bref(fiche, proj, lissage, cmin),
            "appels": proj["totaux"]["appels_complementaires"]}


def _decimal(texte: str | None, defaut=None):
    if texte is None or not str(texte).strip():
        return defaut
    try:
        v = Decimal(str(texte).replace(",", ".").replace(" ", "").replace(" ", ""))
    except Exception:
        return defaut
    return v if v >= 0 else defaut


@routeur.get("/{copro}/plan", response_class=HTMLResponse)
def plan_page(request: Request, copro: str):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    if not A.plan_travaux.plan_de(fiche):
        return page(request, "plan.html", copro, plan=None)
    erreurs = A.plan_travaux.valider_plan(fiche)
    if erreurs:
        return page(request, "plan.html", copro, plan=None, erreurs=erreurs)
    suivi = A.plan_travaux.charger_suivi(A.DOSSIER_DATA, copro)
    sim = _simulation(fiche, suivi, None, 0)
    return page(request, "plan.html", copro, plan=A.plan_travaux.plan_de(fiche),
                lignes=A.plan_travaux.lignes(fiche, suivi), statuts=A.plan_travaux.STATUTS,
                conformite=A.plan_travaux.conformite(fiche, aujourdhui(request), suivi),
                sim=sim, cotisation=sim["proj"]["cotisation"], indexation=0)


@routeur.get("/{copro}/plan/simulation", response_class=HTMLResponse)
def plan_simulation(request: Request, copro: str, cotisation: str = "", indexation: str = ""):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    if not A.plan_travaux.plan_de(fiche):
        raise HTTPException(404, "Pas de plan de travaux")
    suivi = A.plan_travaux.charger_suivi(A.DOSSIER_DATA, copro)
    idx = min(_decimal(indexation, Decimal(0)), Decimal(20))
    sim = _simulation(fiche, suivi, _decimal(cotisation), idx)
    return templates.TemplateResponse(request, "_plan_simulation.html", {"copro": copro, "sim": sim,
                                      "indexation": idx})


@routeur.post("/{copro}/plan/lignes/{ligne}/dossier")
def plan_ouvrir_dossier(request: Request, copro: str, ligne: str):
    exiger(request, copro)
    try:
        d = A.plan_travaux.ouvrir_dossier(A.DOSSIER_DATA, copro, A.fiche_de(copro), ligne, aujourdhui(request))
    except (A.plan_travaux.PlanInvalide, A.travaux.DossierInvalide) as e:
        return retour(f"/app/{copro}/plan#lignes", f"Dossier non ouvert : {e}", request)
    return retour(f"/app/{copro}/travaux/{d['id']}", "Dossier ouvert depuis le plan de travaux : les devis seront "
                  "comparés à son estimation.", request)


@routeur.post("/{copro}/plan/lignes/{ligne}")
def plan_suivre_ligne(request: Request, copro: str, ligne: str, statut: str = Form(...), annee: str = Form(""),
                      montant_reel: str = Form(""), note: str = Form("")):
    exiger(request, copro)
    try:
        A.plan_travaux.mettre_a_jour_ligne(A.DOSSIER_DATA, copro, A.fiche_de(copro), ligne, statut,
                                           int(annee) if annee.strip() else None, _decimal(montant_reel),
                                           note[:500], aujourdhui(request))
    except (A.plan_travaux.PlanInvalide, ValueError) as e:
        return retour(f"/app/{copro}/plan#lignes", f"Ligne non mise à jour : {e}", request)
    return retour(f"/app/{copro}/plan#lignes", f"Ligne {ligne} mise à jour.", request)


# --------------------------------------------------------------------------- #
# Règlement de copropriété en clair
# --------------------------------------------------------------------------- #
@routeur.get("/{copro}/reglement", response_class=HTMLResponse)
def reglement_page(request: Request, copro: str):
    exiger(request, copro)
    r = A.reglement.charger(A.DOSSIER_DATA, copro)
    textes = {k: A.reglement.en_texte(v) for k, v in (r or {}).get("themes", {}).items()}
    return page(request, "reglement.html", copro, onglet="documents", r=r, themes=A.reglement.THEMES, textes=textes,
                ia=bool(os.getenv("MISTRAL_API_KEY")), si_non_respect=A.reglement.SI_NON_RESPECT,
                points=(r or {}).get("points_a_verifier", []))


@routeur.post("/{copro}/reglement/import")
async def reglement_import(request: Request, copro: str, fichier: UploadFile = File(...)):
    exiger(request, copro)
    try:
        r = A.reglement.importer(A.DOSSIER_DATA, copro, await fichier.read(A.reglement.TAILLE_MAX_PDF + 1),
                                 fichier.filename or "reglement.pdf", aujourdhui(request))
    except A.reglement.ReglementInvalide as e:
        return retour(f"/app/{copro}/reglement", f"Règlement non importé : {e}", request)
    return retour(f"/app/{copro}/reglement", f"{len(r['articles'])} articles trouvés. Lancez la rédaction de la "
                  "version en clair.", request)


@routeur.post("/{copro}/reglement/redaction")
def reglement_redaction(request: Request, copro: str):
    exiger(request, copro)
    r = A.reglement.charger(A.DOSSIER_DATA, copro)
    if not r:
        return retour(f"/app/{copro}/reglement", "Importez d'abord le règlement.", request)
    try:
        r = A.reglement.rediger(A.DOSSIER_DATA, copro, r)
    except A.resume_ia.IAIndisponible as e:
        return retour(f"/app/{copro}/reglement", f"Rédaction impossible : {e}", request)
    n = sum(len(v) for v in r["themes"].values())
    return retour(f"/app/{copro}/reglement", f"{n} règles rédigées et vérifiées contre le texte. Relisez chaque "
                  "thème avant de valider.", request)


@routeur.post("/{copro}/reglement")
async def reglement_enregistrer(request: Request, copro: str):
    exiger(request, copro)
    form = await request.form()
    r = A.reglement.charger(A.DOSSIER_DATA, copro)
    if not r:
        raise HTTPException(404)
    try:
        A.reglement.modifier(A.DOSSIER_DATA, copro, r, {k: str(form.get(f"t_{k}", "")) for k in A.reglement.THEMES
                                                         if f"t_{k}" in form})
        if form.get("action") == "valider":
            A.reglement.valider(A.DOSSIER_DATA, copro, r, aujourdhui(request))
    except A.reglement.ReglementInvalide as e:
        return retour(f"/app/{copro}/reglement", f"Non enregistré : {e}", request)
    return retour(f"/app/{copro}/reglement", "Version validée : elle rejoint les packs nouvel arrivant."
                  if form.get("action") == "valider" else "Enregistré.", request)


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
@routeur.get("/{copro}/documents", response_class=HTMLResponse)
def documents_page(request: Request, copro: str):
    exiger(request, copro)
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    reg = A.meubles_tourisme.charger(A.DOSSIER_DATA, copro)
    par_proprio = {}
    for l in fiche["lots"]:
        par_proprio.setdefault(l["proprietaire"], []).append(l)
    noms = {c["id"]: c["nom"] for c in fiche["coproprietaires"]}
    groupes = [{"nom": noms[cid], "lots": sorted(ls, key=lambda l: l["numero"])}
               for cid, ls in sorted(par_proprio.items(), key=lambda x: noms[x[0]])]
    logements = [l for l in fiche["lots"] if l["type"] not in ("cave", "parking")]
    return page(request, "documents.html", copro, groupes=groupes, logements=logements,
                reglement=A.reglement.charger(A.DOSSIER_DATA, copro),
                telechargement=request.session.pop("telechargement", None),
                mt=reg, mt_actives=len(A.meubles_tourisme.actives(reg, jour)),
                eligibilite=A.meubles_tourisme.eligibilite(fiche))


@routeur.post("/{copro}/documents/vente")
def documents_vente(request: Request, copro: str, lots: list[int] = Form(...)):
    exiger(request, copro)
    try:
        r = A.vente.generer_dossier(A.fiche_de(copro), lots, A.DOSSIER_SORTIE / copro / "ventes", A.DOSSIER_DATA,
                                    copro, None, False, aujourdhui(request))
    except A.vente.VenteInvalide as e:
        return retour(f"/app/{copro}/documents", f"Dossier non créé : {e}", request)
    request.session["telechargement"] = f"/copros/{copro}/ventes/{r['id']}.zip"
    a_completer = len(r["a_completer"])
    return retour(f"/app/{copro}/documents#vente", "Dossier de vente prêt"
                  + (f", {a_completer} rubrique(s) à compléter d'après vos comptes." if a_completer else "."), request)


@routeur.get("/{copro}/transmission", response_class=HTMLResponse)
def transmission_page(request: Request, copro: str, erreur: str | None = None, form: dict | None = None):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    base = A.DOSSIER_SORTIE / copro / "transmission"
    precedents = []
    for f in sorted(base.glob("*/transmission.json"), reverse=True):
        r = json.loads(f.read_text(encoding="utf-8"))
        precedents.append({**r, "dossier": f.parent.name})
    cs = (fiche.get("appels_de_fonds") or {}).get("compte_separe") or {}
    return page(request, "transmission.html", copro, onglet="documents", precedents=precedents, erreur=erreur, f=form or {},
                compte=cs, fonds_travaux=fiche.get("fonds_travaux") or {})


@routeur.post("/{copro}/transmission")
async def transmission_creer(request: Request, copro: str):
    exiger(request, copro)
    form = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    try:
        r = A.preparer_transmission(copro, form, aujourdhui(request))
    except A.transmission.TransmissionInvalide as e:
        return transmission_page(request, copro, erreur=str(e), form=form)
    return retour(f"/app/{copro}/transmission", f"Dossier de transfert prêt ({r['fichiers_archives']} fichiers "
                  "d'archives).", request)


@routeur.get("/{copro}/transmission/{dossier}/{nom}.zip")
def transmission_zip(request: Request, copro: str, dossier: str, nom: str):
    exiger(request, copro)
    if not re.fullmatch(r"\d{8}", dossier) or not re.fullmatch(r"dossier_transfert_[a-z0-9_-]+_\d{8}", nom):
        raise HTTPException(404)
    chemin = A.DOSSIER_SORTIE / copro / "transmission" / dossier / f"{nom}.zip"
    if not chemin.is_file():
        raise HTTPException(404)
    return FileResponse(chemin, media_type="application/zip", filename=chemin.name)


@routeur.post("/{copro}/documents/meubles-tourisme")
def documents_mt(request: Request, copro: str, lot: int = Form(...), recue_le: date = Form(...),
                 residence_principale: str = Form("")):
    exiger(request, copro)
    try:
        A.meubles_tourisme.enregistrer(A.fiche_de(copro), A.DOSSIER_DATA, copro, lot, recue_le, "proprietaire",
                                       {"oui": True, "non": False}.get(residence_principale))
    except A.meubles_tourisme.DeclarationInvalide as e:
        return retour(f"/app/{copro}/documents#meubles", f"Déclaration refusée : {e}", request)
    return retour(f"/app/{copro}/documents#meubles", "Déclaration enregistrée. Le point d'information sera ajouté "
                  "à la prochaine AG que vous préparerez.", request)


# --------------------------------------------------------------------------- #
# Signalements des copropriétaires
# --------------------------------------------------------------------------- #
SID = re.compile(r"^S\d{14}[0-9a-f]{4}$")


def _sid(sid: str) -> str:
    if not SID.match(sid):
        raise HTTPException(404, "Signalement inconnu")
    return sid


@routeur.get("/{copro}/signalements", response_class=HTMLResponse)
def signalements_page(request: Request, copro: str, tous: int = 0):
    exiger(request, copro)
    S = A.signalements
    fiche = A.fiche_de(copro)
    donnees = S.charger(A.DOSSIER_DATA, copro)
    liste = [x for x in donnees["signalements"] if tous or x["statut"] in S.OUVERTS]
    rang = {"recu": 0, "en_cours": 1}
    liste.sort(key=lambda x: (rang.get(x["statut"], 2), x["niveau"] != "urgent"))   # stable : plus récents d'abord
    for x in liste:
        x["limite_assurance"] = S.limite_declaration(fiche, x)
    return page(request, "signalements.html", copro, liste=liste, tous=tous, lien=A.lien_signalement(copro),
                categories=S.CATEGORIES, statuts=S.STATUTS, niveaux=S.NIVEAUX,
                nb_fermes=sum(1 for x in donnees["signalements"] if x["statut"] not in S.OUVERTS),
                astreintes=S.astreintes(fiche))


@routeur.get("/{copro}/signalements/affiche.pdf")
def signalements_affiche(request: Request, copro: str):
    exiger(request, copro)
    pdf = A.signalements.affiche(A.fiche_de(copro), A.lien_signalement(copro))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="affiche_signalements_{copro}.pdf"',
                             "Cache-Control": "no-store"})


@routeur.post("/{copro}/signalements/lien")
def signalements_nouveau_lien(request: Request, copro: str):
    exiger(request, copro)
    A.signalements.jeton(A.DOSSIER_DATA, copro, renouveler=True)
    return retour(f"/app/{copro}/signalements", "Nouveau lien créé : l'ancien ne fonctionne plus. Imprimez la nouvelle "
                  "affiche et remplacez celle du hall.", request)


@routeur.post("/{copro}/signalements/{sid}")
def signalements_maj(request: Request, copro: str, sid: str, statut: str = Form(...), note_publique: str = Form("")):
    exiger(request, copro)
    try:
        A.signalements.mettre_a_jour(A.DOSSIER_DATA, copro, _sid(sid), statut, note_publique)
    except KeyError:
        raise HTTPException(404, "Signalement inconnu")
    except A.signalements.SignalementInvalide as e:
        return retour(f"/app/{copro}/signalements#{sid}", str(e), request)
    return retour(f"/app/{copro}/signalements#{sid}", "Signalement mis à jour.", request)


@routeur.post("/{copro}/signalements/{sid}/assurance")
def signalements_assurance(request: Request, copro: str, sid: str):
    exiger(request, copro)
    try:
        A.signalements.marquer_declare(A.DOSSIER_DATA, copro, _sid(sid))
    except StopIteration:
        raise HTTPException(404, "Signalement inconnu")
    return retour(f"/app/{copro}/signalements#{sid}", "Déclaration à l'assurance notée.", request)


@routeur.get("/{copro}/signalements/{sid}/photo.jpg")
def signalements_photo(request: Request, copro: str, sid: str):
    exiger(request, copro)
    chemin = A.signalements.chemin_photo(A.DOSSIER_DATA, copro, _sid(sid))
    if chemin is None:
        raise HTTPException(404, "Pas de photo")
    return FileResponse(chemin, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


# --------------------------------------------------------------------------- #
# Comptabilité en partie double
# --------------------------------------------------------------------------- #
COMPTE = re.compile(r"^\d{2,4}(\.[A-Z0-9-]{1,30})?$")


def _montant(texte: str | None) -> Decimal | None:
    """Un montant saisi à la française, signe compris : « -1 234,50 » ; vide = None."""
    if texte is None or not str(texte).strip():
        return None
    t = str(texte).replace(" ", "").replace(" ", "").replace(" ", "").replace("€", "").replace(",", ".")
    try:
        return Decimal(t)
    except Exception:
        raise A.compta.ComptaInvalide(f"Montant illisible : « {texte} »")


def _comptes_charge() -> list[tuple[str, str]]:
    return [(c, l) for c, l in A.compta.PLAN.items() if c.startswith("6")]


def _balance_groupee(bal: dict) -> list[dict]:
    """La balance par classe, chaque compte avec ses comptes auxiliaires (4501.CP03…) repliés dessous."""
    C = A.compta
    comptes: dict[str, dict] = {}
    for c, v in bal.items():
        racine = c.split(".")[0]
        g = comptes.setdefault(racine, {"compte": racine, "libelle": C.libelle_compte(racine), "debit": C.ZERO,
                                        "credit": C.ZERO, "aux": []})
        g["debit"] += v["debit"]
        g["credit"] += v["credit"]
        if "." in c:
            g["aux"].append({"compte": c, "libelle": c.split(".", 1)[1], **v})
    classes: dict[str, dict] = {}
    for racine in sorted(comptes):
        g = comptes[racine]
        g["solde"] = g["debit"] - g["credit"]
        cl = classes.setdefault(racine[0], {"classe": racine[0], "libelle": C.CLASSES.get(racine[0], ""), "comptes": []})
        cl["comptes"].append(g)
    return list(classes.values())


def _noms_aux(fiche: dict) -> dict:
    """4501.CP03 -> « 4501 · Mme Rossi » : les comptes des copropriétaires par leur nom."""
    return {c["id"]: c["nom"] for c in fiche["coproprietaires"]}


@routeur.get("/{copro}/comptes", response_class=HTMLResponse)
def comptes_page(request: Request, copro: str):
    exiger(request, copro)
    C = A.compta
    jour = aujourdhui(request)
    fiche = A.fiche_de(copro)
    st = C.charger(A.DOSSIER_DATA, copro)
    e = C.etat(fiche, A.DOSSIER_SORTIE, A.DOSSIER_DATA, copro, jour)
    reglees = {a.get("facture") for a in st["depenses"].values() if a.get("facture")}
    a_affecter, recettes = [], []
    for x in e["journal"]:
        if x["source"] != "attente":
            continue
        banque = next(l for l in x["lignes"] if l["compte"] == "512")
        ligne = {"id": x["piece"], "date": x["date"], "libelle": x["libelle"], "montant": banque["debit"] - banque["credit"]}
        (a_affecter if ligne["montant"] < 0 else recettes).append(ligne)
    bal = e["balance"]
    total_d = sum((v["debit"] for v in bal.values()), C.ZERO)
    total_c = sum((v["credit"] for v in bal.values()), C.ZERO)
    factures = sorted(st["factures"], key=lambda f: f["date"], reverse=True)
    for f in factures:
        f["reglee"] = f["id"] in reglees
    noms = _noms_aux(fiche)
    for cl in (classes := _balance_groupee(bal)):
        for g in cl["comptes"]:
            for a in g["aux"]:
                a["libelle"] = noms.get(a["libelle"], a["libelle"].replace("-", " ").title())
    controles = [{**c, "detail": re.sub(r"-?\d+\.\d{2}", lambda m: euros(m.group()), c["detail"])}
                 for c in e["controles"]]
    return page(request, "comptes.html", copro, e=e, controles=controles, ouverture=st["ouverture"],
                factures=factures, a_affecter=a_affecter, recettes=recettes, classes=classes,
                total_debit=total_d, total_credit=total_c, comptes_charge=_comptes_charge(),
                factures_ouvertes=[f for f in factures if not f["reglee"]],
                coproprietaires=sorted(fiche["coproprietaires"], key=lambda c: c["nom"]),
                ouverture_ok=st["ouverture"] is not None, tout_ok=all(c["ok"] for c in e["controles"]))


@routeur.post("/{copro}/comptes/ouverture")
async def comptes_ouverture(request: Request, copro: str):
    exiger(request, copro)
    fiche = A.fiche_de(copro)
    f = await request.form()
    try:
        jour = date.fromisoformat(str(f.get("date", "")))
    except ValueError:
        return retour(f"/app/{copro}/comptes#ouverture", "Soldes non enregistrés : indiquez la date de reprise.", request)
    try:
        soldes = {c["id"]: _montant(f.get(f"solde_{c['id']}")) or 0 for c in fiche["coproprietaires"]}
        fournisseurs = {}
        for ligne in str(f.get("fournisseurs", "")).splitlines():
            if ligne.strip():
                nom, _, m = ligne.rpartition(";")
                if not nom.strip():
                    raise A.compta.ComptaInvalide(f"Ligne fournisseur illisible : « {ligne.strip()} » (attendu : Nom ; montant)")
                fournisseurs[nom.strip()] = _montant(m) or 0
        A.compta.definir_ouverture(A.DOSSIER_DATA, copro, jour, _montant(f.get("banque")) or 0, soldes,
                                   _montant(f.get("fonds_travaux")) or 0, fournisseurs)
    except A.compta.ComptaInvalide as e:
        return retour(f"/app/{copro}/comptes#ouverture", f"Soldes non enregistrés : {e}", request)
    return retour(f"/app/{copro}/comptes", "Soldes d'ouverture enregistrés.", request)


@routeur.post("/{copro}/comptes/factures")
def comptes_facture(request: Request, copro: str, fournisseur: str = Form(...), jour: date = Form(..., alias="date"),
                    montant: str = Form(...), compte: str = Form(...), libelle: str = Form("")):
    exiger(request, copro)
    try:
        f = A.compta.ajouter_facture(A.DOSSIER_DATA, copro, fournisseur, jour, _montant(montant) or 0, compte,
                                     libelle or A.compta.libelle_compte(compte))
    except A.compta.ComptaInvalide as e:
        return retour(f"/app/{copro}/comptes#factures", f"Facture non enregistrée : {e}", request)
    return retour(f"/app/{copro}/comptes#factures", f"Facture {f['id']} enregistrée : {euros(f['montant'])} "
                  f"chez {f['fournisseur']}.", request)


@routeur.post("/{copro}/comptes/depenses/{op_id}", response_class=HTMLResponse)
def comptes_affecter(request: Request, copro: str, op_id: str, choix: str = Form(...), fournisseur: str = Form("")):
    exiger(request, copro)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", op_id):
        raise HTTPException(404)
    C = A.compta
    try:
        if choix.startswith("facture:"):
            fid = choix.split(":", 1)[1]
            fac = next((f for f in C.charger(A.DOSSIER_DATA, copro)["factures"] if f["id"] == fid), None)
            if fac is None:
                raise C.ComptaInvalide("Facture inconnue")
            C.affecter_depense(A.DOSSIER_DATA, copro, op_id, facture=fid)
            texte = f"Rattaché à la facture {fid} ({fac['fournisseur']})."
        elif choix.startswith("compte:"):
            cpt = choix.split(":", 1)[1]
            C.affecter_depense(A.DOSSIER_DATA, copro, op_id, compte=cpt, fournisseur=fournisseur)
            texte = f"Dépense directe : {cpt} {C.libelle_compte(cpt)}."
        else:
            raise C.ComptaInvalide("Choisissez une facture ou un compte de charge")
    except C.ComptaInvalide as e:
        return HTMLResponse(f'<tr><td colspan="4" class="erreur">{e}</td></tr>')
    return templates.TemplateResponse(request, "_ligne_faite.html", {"texte": texte, "colonnes": 4,
                                                                     "copro": copro, "op_id": op_id})


@routeur.get("/{copro}/comptes/compte/{compte}", response_class=HTMLResponse)
def comptes_grand_livre(request: Request, copro: str, compte: str):
    exiger(request, copro)
    if not COMPTE.match(compte):
        raise HTTPException(404, "Compte inconnu")
    C = A.compta
    fiche = A.fiche_de(copro)
    e = C.etat(fiche, A.DOSSIER_SORTIE, A.DOSSIER_DATA, copro, aujourdhui(request))
    mouvements = C.grand_livre(e["journal"], compte)
    racine, _, aux = compte.partition(".")
    nom = _noms_aux(fiche).get(aux, aux.replace("-", " ").title()) if aux else ""
    return page(request, "grand_livre.html", copro, onglet="comptes", compte=compte,
                libelle=C.libelle_compte(racine) + (f" — {nom}" if nom else ""), mouvements=mouvements,
                solde=mouvements[-1]["solde"] if mouvements else C.ZERO, au=e["au"])
