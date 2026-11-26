"""
reglement.py — Le règlement de copropriété en clair.

Un règlement de copropriété fait souvent 40 pages de langage notarial, et peu de
copropriétaires l'ont lu. Mitoyen en tire une version lisible, rangée par thèmes (animaux,
bruit, travaux, location…), dont chaque règle renvoie à l'article d'origine :

1. le syndic charge le PDF du règlement ; Mitoyen en extrait le texte, article par article ;
2. l'IA (Mistral) rédige la version en clair, avec pour chaque règle une courte citation
   du texte ;
3. Mitoyen vérifie que chaque citation figure bien dans l'article cité, et écarte les règles
   qui ne s'appuient sur rien ;
4. le syndic relit, corrige, valide ; la version validée rejoint le pack nouvel arrivant.

La version en clair ne remplace pas le règlement : en cas de doute, c'est le texte du
règlement qui fait foi. Pas un conseil juridique.

Stockage : data/<copro>/reglement/ (le PDF d'origine, reglement.json, partage.json).

Le syndic peut partager le tout par un lien (désactivé par défaut, renouvelable) : la version en
clair validée et, s'il le choisit, le texte intégral.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import unicodedata
from datetime import date, datetime
from pathlib import Path

import resume_ia

THEMES = {
    "destination": "Destination de l'immeuble et usage des logements",
    "location": "Location, meublés de tourisme, activités professionnelles",
    "parties_communes": "Usage des parties communes",
    "travaux": "Travaux dans les logements",
    "aspect": "Façades, fenêtres et balcons",
    "nuisances": "Bruit et tranquillité",
    "animaux": "Animaux",
    "stationnement": "Stationnement, caves et locaux annexes",
    "securite": "Sécurité et entretien",
    "charges": "Charges et leur répartition",
}
TAILLE_MAX_PDF = 20 * 1024 * 1024
MAX_CITATION = 220                # caractères

SI_NON_RESPECT = [
    ("Le syndic fait respecter le règlement",
     "La loi du 10 juillet 1965 (art. 18) charge le syndic d'assurer l'exécution du règlement. Il commence par un "
     "rappel amiable, puis une mise en demeure."),
    ("Une action en justice se décide en AG",
     "Pour agir en justice au nom de la copropriété, le syndic doit y être autorisé par l'assemblée générale, à la "
     "majorité de l'article 24 (décret du 17 mars 1967, art. 55), sauf exceptions comme le référé."),
    ("Chaque copropriétaire peut agir seul",
     "Un copropriétaire peut aussi agir lui-même pour ce qui touche à la jouissance de son lot, par exemple en cas de "
     "trouble anormal de voisinage."),
    ("Les locataires sont tenus aussi",
     "Le règlement s'impose à tous les occupants. Le propriétaire qui loue doit le faire respecter par son locataire, "
     "et en répond envers la copropriété."),
    ("Les frais peuvent être mis à la charge du fautif",
     "Les frais engagés à cause d'un manquement (remise en état, frais de procédure décidés par le juge) peuvent être "
     "mis à la charge de celui qui en est à l'origine, plutôt qu'à celle de tous."),
]

AVERTISSEMENT = ("Version simplifiée, établie par l'assistant du syndic et relue par lui. Elle ne remplace pas le "
                 "règlement de copropriété : en cas de doute, c'est le texte du règlement qui fait foi. "
                 "Pas un conseil juridique : l'ADIL de votre département répond gratuitement.")


class ReglementInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Stockage
# --------------------------------------------------------------------------- #
def dossier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "reglement"


def charger(racine: Path, copro: str) -> dict | None:
    f = dossier(racine, copro) / "reglement.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def sauver(racine: Path, copro: str, r: dict) -> None:
    d = dossier(racine, copro)
    d.mkdir(parents=True, exist_ok=True)
    (d / "reglement.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


def valide(racine: Path, copro: str) -> dict | None:
    r = charger(racine, copro)
    return r if r and r.get("valide_le") else None


# --------------------------------------------------------------------------- #
# 1. Le texte, article par article
# --------------------------------------------------------------------------- #
ARTICLE = re.compile(r"^\s*(?:ARTICLE|Article|Art\.)\s+(\d+(?:[-\s]?(?:bis|ter|\d+))?)\b\s*[.:–—-]?\s*(.*)$", re.M)


def _normaliser(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).replace("’", "'").replace(" ", " ").replace(" ", " ")
    t = re.sub(r"-\s*\n\s*", "", t)                     # mots coupés en fin de ligne
    return re.sub(r"\s+", " ", t).strip().lower()


def decouper(texte: str) -> list[dict]:
    """Les articles du règlement : numéro, titre éventuel, texte. Un renvoi à un article déjà
    vu (« Article 12 ci-dessus » en début de ligne) reste dans le texte de l'article en cours."""
    reperes, vus = [], set()
    for m in ARTICLE.finditer(texte):
        num = re.sub(r"\s+", " ", m.group(1)).strip()
        if num not in vus:
            vus.add(num)
            reperes.append((num, m))
    articles = []
    for i, (num, m) in enumerate(reperes):
        fin = reperes[i + 1][1].start() if i + 1 < len(reperes) else len(texte)
        articles.append({"num": num, "titre": m.group(2).strip()[:120], "texte": texte[m.end():fin].strip()})
    return articles


def importer(racine: Path, copro: str, pdf: bytes, nom_fichier: str = "reglement.pdf",
             aujourd_hui: date | None = None) -> dict:
    if not pdf or not pdf.startswith(b"%PDF"):
        raise ReglementInvalide("Le fichier n'est pas un PDF")
    if len(pdf) > TAILLE_MAX_PDF:
        raise ReglementInvalide("PDF trop volumineux (20 Mo au plus)")
    d = dossier(racine, copro)
    d.mkdir(parents=True, exist_ok=True)
    (d / "reglement.pdf").write_bytes(pdf)
    texte = resume_ia.extraire_texte(d / "reglement.pdf")
    articles = decouper(texte)
    if len(articles) < 3:
        raise ReglementInvalide("Articles introuvables dans ce PDF : est-ce un document scanné ? Il faut un PDF "
                                "dont le texte se sélectionne")
    r = {"source": nom_fichier[:120], "empreinte": hashlib.sha256(pdf).hexdigest(),
         "importe_le": (aujourd_hui or date.today()).isoformat(), "articles": articles,
         "themes": {}, "redaction": None, "points_a_verifier": [], "valide_le": None}
    sauver(racine, copro, r)
    return r


# --------------------------------------------------------------------------- #
# 2. La version en clair, par l'IA
# --------------------------------------------------------------------------- #
CONSIGNES = """Tu aides le syndic bénévole d'une petite copropriété à rendre son règlement de copropriété lisible \
par tous les copropriétaires et locataires.

Règles absolues :
1. N'invente rien : chaque règle vient d'un article fourni, et tu cites l'article.
2. Pour chaque règle, recopie à l'identique une courte citation de l'article (une phrase ou un morceau de phrase, \
moins de 200 caractères) qui la prouve. Pas de paraphrase dans la citation.
3. Écris les règles en langage courant, au présent, en une phrase courte chacune (« Les animaux sont admis s'ils \
ne causent aucune gêne. »). Pas de jargon notarial.
4. Ne juge pas la validité d'une clause, ne donne aucun conseil juridique, ne cite aucune loi.
5. Ne recopie jamais un code d'accès, de digicode ou d'alarme.
6. Un thème sur lequel le règlement ne dit rien : liste vide.

Thèmes (clés) : """ + ", ".join(f"{k} ({v})" for k, v in THEMES.items()) + """.

Réponds en JSON strict :
{"themes": {"<clé>": [{"regle": "...", "articles": ["12"], "citation": "..."}]}}"""


def messages(r: dict) -> list[dict]:
    corps = "\n\n".join(f"ARTICLE {a['num']}" + (f" – {a['titre']}" if a["titre"] else "") + f"\n{a['texte']}"
                        for a in r["articles"])
    return [{"role": "system", "content": CONSIGNES},
            {"role": "user", "content": "Règlement de copropriété, article par article :\n<<<\n" + corps[:120000] + "\n>>>"}]


def controler(r: dict, themes: dict) -> tuple[dict, list[str]]:
    """Garde chaque règle dont la citation figure dans l'un des articles cités ; signale les autres."""
    par_num = {a["num"]: _normaliser(a["texte"]) for a in r["articles"]}
    gardees, points = {}, []
    for cle, regles in (themes or {}).items():
        if cle not in THEMES or not isinstance(regles, list):
            continue
        for x in regles:
            if not isinstance(x, dict) or not str(x.get("regle", "")).strip():
                continue
            arts = [str(a).strip() for a in (x.get("articles") or []) if str(a).strip()]
            citation = str(x.get("citation", "")).strip()[:MAX_CITATION]
            inconnus = [a for a in arts if a not in par_num]
            trouvee = bool(citation) and any(_normaliser(citation).strip(" .«»\"") in par_num.get(a, "") for a in arts)
            regle = str(x["regle"]).strip()[:400]
            if not arts or inconnus:
                points.append(f"« {regle} » : article {', '.join(inconnus) or 'non indiqué'} introuvable, règle écartée")
                continue
            if not trouvee:
                points.append(f"« {regle} » : la citation ne figure pas dans l'article {', '.join(arts)}, règle écartée")
                continue
            gardees.setdefault(cle, []).append({"regle": regle, "articles": arts, "citation": citation})
    return gardees, points


def rediger(racine: Path, copro: str, r: dict, ia=None) -> dict:
    fournisseur = ia or resume_ia.fournisseur()
    brut = fournisseur.completer(messages(r))              # lève resume_ia.IAIndisponible
    try:
        d = json.loads(brut)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", brut, re.S)
        if not m:
            raise resume_ia.IAIndisponible("Réponse de l'IA illisible")
        d = json.loads(m.group(0))
    themes, points = controler(r, d.get("themes") or {})
    r.update({"themes": themes, "redaction": "ia", "points_a_verifier": points, "valide_le": None})
    sauver(racine, copro, r)
    return r


# --------------------------------------------------------------------------- #
# 3. Relecture et validation par le syndic
# --------------------------------------------------------------------------- #
LIGNE = re.compile(r"^\s*[-•]?\s*(.+?)\s*\((?:art\.?|articles?)\s*([\w\s,-]+)\)\s*$", re.I)


def en_texte(regles: list[dict]) -> str:
    """Une règle par ligne, terminée par ses articles : la forme que le syndic édite."""
    return "\n".join(f"- {x['regle']} (art. {', '.join(x['articles'])})" for x in regles)


def depuis_texte(r: dict, cle: str, texte: str) -> list[dict]:
    par_num = {a["num"] for a in r["articles"]}
    anciennes = {x["regle"]: x for x in r["themes"].get(cle, [])}
    regles = []
    for ligne in (texte or "").splitlines():
        if not ligne.strip():
            continue
        m = LIGNE.match(ligne)
        if not m:
            raise ReglementInvalide(f"« {ligne.strip()[:80]} » : terminez la ligne par les articles, par exemple (art. 12)")
        arts = [a.strip() for a in re.split(r"[,\s]+(?:et\s+)?", m.group(2)) if a.strip() and a.strip() != "et"]
        inconnus = [a for a in arts if a not in par_num]
        if inconnus:
            raise ReglementInvalide(f"Article {', '.join(inconnus)} absent du règlement")
        regle = m.group(1).strip().lstrip("-• ").strip()
        citation = anciennes[regle]["citation"] if regle in anciennes else ""
        regles.append({"regle": regle[:400], "articles": arts, "citation": citation})
    return regles


def modifier(racine: Path, copro: str, r: dict, textes: dict[str, str]) -> dict:
    themes = {}
    for cle in THEMES:
        if cle in textes:
            regles = depuis_texte(r, cle, textes[cle])
            if regles:
                themes[cle] = regles
        elif cle in r["themes"]:
            themes[cle] = r["themes"][cle]
    r.update({"themes": themes, "redaction": "syndic", "valide_le": None})
    sauver(racine, copro, r)
    return r


def valider(racine: Path, copro: str, r: dict, aujourd_hui: date | None = None) -> dict:
    if not r.get("themes"):
        raise ReglementInvalide("Rien à valider : la version en clair est vide")
    r["valide_le"] = (aujourd_hui or date.today()).isoformat()
    sauver(racine, copro, r)
    return r


# --------------------------------------------------------------------------- #
# 4. Le document « Le règlement en clair »
# --------------------------------------------------------------------------- #
USAGE_LOCATAIRE = ("destination", "parties_communes", "aspect", "nuisances", "animaux", "stationnement", "securite")


def generer_pdf(fiche: dict, r: dict, chemin: Path, themes: tuple[str, ...] | None = None,
                grand: bool = False) -> Path:
    """themes=None : tous ; USAGE_LOCATAIRE : ce qui concerne l'occupant."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer
    from avis_appel import CanevasNumerote, essentiel, styles, tampon
    from html import escape
    S = styles(grand)
    c = fiche["copropriete"]
    choisis = [k for k in THEMES if k in r["themes"] and (themes is None or k in themes)]
    n_regles = sum(len(r["themes"][k]) for k in choisis)
    puce = S["txt"].clone("puce_regl", leftIndent=12, bulletIndent=0, spaceAfter=3)
    titre_theme = S["titre"].clone("theme_regl", fontSize=15 if not grand else 18, leading=19 if not grand else 22,
                                   spaceBefore=4)
    date_rc = fiche["copropriete"].get("date_reglement")
    h = [Paragraph("Le règlement de copropriété en clair", S["titre"]),
         Paragraph(f"{escape(c['nom'])}, {escape(c['adresse'])}"
                   + (" · extraits sur l'usage de l'immeuble" if themes else ""), S["sous"]), Spacer(1, 4 * mm),
         essentiel([("Règlement du", f"{date_rc:%d/%m/%Y}" if hasattr(date_rc, "strftime") else (str(date_rc) if date_rc else "—"),
                     f"{len(r['articles'])} articles"),
                    ("Règles résumées", str(n_regles), f"en {len(choisis)} thèmes"),
                    ("Version relue", f"{date.fromisoformat(r['valide_le']):%d/%m/%Y}" if r.get("valide_le") else "à valider",
                     "par le syndic")], grand=grand),
         Spacer(1, 4 * mm),
         Paragraph("Chaque règle renvoie à l'article du règlement d'où elle vient. Le règlement s'applique à tous les "
                   "occupants, propriétaires comme locataires.", S["txt"]), Spacer(1, 4 * mm)]
    for k in choisis:
        bloc = [Paragraph(THEMES[k], titre_theme), Spacer(1, 1.5 * mm)]
        for x in r["themes"][k]:
            bloc.append(Paragraph(f"{escape(x['regle'])} <font color='#5C5C5C'>(art. {escape(', '.join(x['articles']))})</font>",
                                  puce, bulletText="•"))
        h += [KeepTogether(bloc), Spacer(1, 3 * mm)]
    h += [Spacer(1, 2 * mm), Paragraph("Si une règle n'est pas respectée", titre_theme), Spacer(1, 1.5 * mm)]
    for t, txt in SI_NON_RESPECT:
        h.append(Paragraph(f"<b>{escape(t)}.</b> {escape(txt)}", puce, bulletText="•"))
    h += [Spacer(1, 5 * mm), Paragraph(AVERTISSEMENT, S["petit"])]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    pied = f"{c['nom']} – le règlement en clair"
    SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm,
                      bottomMargin=18 * mm, title="Règlement en clair").build(
        h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


# --------------------------------------------------------------------------- #
# 5. Le lien de consultation pour les copropriétaires (désactivé par défaut)
# --------------------------------------------------------------------------- #
def _partage(racine: Path, copro: str) -> Path:
    return dossier(racine, copro) / "partage.json"


def reglages(racine: Path, copro: str) -> dict:
    f = _partage(racine, copro)
    r = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    return {"jeton": None, "actif": False, "integral": False, **r}


def partager(racine: Path, copro: str, actif: bool, renouveler: bool = False, integral: bool | None = None) -> dict:
    """Crée, renouvelle ou coupe le lien. integral : joindre aussi le texte intégral (PDF d'origine)."""
    p = reglages(racine, copro)
    if integral is not None:
        p["integral"] = bool(integral)
    r = charger(racine, copro)
    if actif and not (r and (r.get("valide_le") or p["integral"])):
        raise ReglementInvalide("Rien à partager : validez d'abord la version en clair, ou joignez le texte intégral")
    if actif and (renouveler or not p.get("jeton")):
        p["jeton"] = secrets.token_urlsafe(16)
    p["actif"] = bool(actif)
    p["modifie_le"] = datetime.now().replace(microsecond=0).isoformat()
    f = _partage(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(p), encoding="utf-8")
    return p


def jeton_valide(racine: Path, copro: str, propose: str) -> bool:
    p = reglages(racine, copro)
    return bool(p.get("actif") and p.get("jeton")) and secrets.compare_digest(p["jeton"], propose or "")


def texte_integral(racine: Path, copro: str) -> Path | None:
    """Le PDF d'origine, réenregistré sans ses propriétés (auteur, logiciel) ; None s'il n'est pas partagé."""
    if not reglages(racine, copro)["integral"]:
        return None
    d = dossier(racine, copro)
    source, public = d / "reglement.pdf", d / "reglement_public.pdf"
    if not source.is_file():
        return None
    if not public.is_file() or public.stat().st_mtime < source.stat().st_mtime:
        from pieces import nettoyer
        public.write_bytes(nettoyer(source.read_bytes(), "pdf")[0])
    return public
