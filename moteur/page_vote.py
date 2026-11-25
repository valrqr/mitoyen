"""
page_vote.py — La page web que chaque copropriétaire ouvre depuis son lien personnel.

Volontairement simple : HTML généré côté serveur, aucun JavaScript, lisible sur téléphone,
accessible au clavier et aux lecteurs d'écran. Toute donnée affichée est échappée.
"""

from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal
from html import escape
from pathlib import Path

_ICONE = Path(__file__).resolve().parent.parent / "core" / "ressources" / "icone_64.png"
# Icône intégrée à la page (data URI) : aucune requête vers un autre fichier ou un autre site
ICONE_URI = ("data:image/png;base64," + base64.b64encode(_ICONE.read_bytes()).decode()) if _ICONE.is_file() else ""


def _euros(m) -> str:
    m = Decimal(str(m))
    entier, dec = f"{m:,.2f}".split(".")
    return f"{entier.replace(',', ' ')},{dec} €"


def _date(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d:%d/%m/%Y à %Hh%M}"


STYLE = """
@font-face{font-family:Atkinson;src:url(/statique/polices/atkinson-hyperlegible-latin-400-normal.woff2) format("woff2");font-weight:400;font-display:swap}@font-face{font-family:Atkinson;src:url(/statique/polices/atkinson-hyperlegible-latin-700-normal.woff2) format("woff2");font-weight:700;font-display:swap}*{box-sizing:border-box}body{margin:0;font-family:Atkinson,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
background:#F7F6F2;color:#1E1E1E;line-height:1.5}
main{max-width:640px;margin:0 auto;padding:24px 16px 48px}
header{display:flex;align-items:center;gap:10px;margin-bottom:20px}
.marque{font-weight:800;font-size:22px;letter-spacing:.3px}
h1{font-size:24px;line-height:1.25;margin:0 0 6px}
.sous{color:#5F5E5A;margin:0 0 18px;font-size:15px}
.note{background:#FFF7ED;border-radius:10px;padding:12px 14px;font-size:14px;color:#7C2D12;margin:0 0 18px}
.bref{background:#fff;border:1px solid #E3E1DA;border-radius:12px;padding:14px 16px;margin:0 0 18px;font-size:15px}
.bref small{display:block;color:#5F5E5A;margin-top:6px;font-size:12px}
fieldset{border:0;padding:0;margin:0 0 18px}legend{font-weight:700;font-size:17px;margin-bottom:10px}
.option{display:flex;gap:12px;align-items:flex-start;background:#fff;border:2px solid #E3E1DA;border-radius:12px;
padding:14px;margin-bottom:10px;cursor:pointer}
.option:has(input:checked){border-color:#1E1E1E}
.option input{margin-top:4px;width:20px;height:20px;flex:none;accent-color:#1E1E1E}
.titre{font-weight:700}.detail{font-size:14px;color:#4A4945}.qp{font-weight:700;color:#1E1E1E}
button{width:100%;min-height:48px;border:0;border-radius:10px;background:#1E1E1E;color:#fff;font-size:16px;
font-weight:700;cursor:pointer}button:focus-visible,.option:focus-within{outline:3px solid #C2410C;outline-offset:2px}
.ok{background:#E6F4EA;color:#14532D;border-radius:10px;padding:12px 14px;margin:0 0 18px;font-weight:600}
.erreur{background:#FDE7E5;color:#7A1A12;border-radius:10px;padding:12px 14px;margin:0 0 18px}
a{color:#1E1E1E}footer{margin-top:28px;font-size:12px;color:#6B6A66}
"""


def page(titre: str, corps: str) -> str:
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="noindex, nofollow"><title>{escape(titre)} – Mitoyen</title>'
            + (f'<link rel="icon" type="image/png" href="{ICONE_URI}">' if ICONE_URI else "") +
            f'<style>{STYLE}</style></head><body><main>'
            f'<header>' + (f'<img src="{ICONE_URI}" alt="" width="34" height="32">' if ICONE_URI else "")
            + f'<span class="marque">Mitoyen</span></header>{corps}'
            f'<footer>Lien personnel : ne le transférez pas. Page préparée par l\'assistant Mitoyen pour le syndic '
            f'de votre copropriété.</footer></main></body></html>')


def page_sondage(copropriete: str, dossier: dict, sondage: dict, cid: str, nom: str, comp: dict,
                 resume: dict | None, lien_pdf: str, message: str | None = None, ouvert: bool = True) -> str:
    choix_actuel = sondage["electeurs"][cid]["choix"]
    parts = next((q["parts"] for q in comp["quotes_parts"] if q["coproprietaire"] == cid), {})
    devis = {d["id"]: d for d in comp["devis"]}

    h = [f'<h1>{escape(dossier["titre"])}</h1>',
         f'<p class="sous">{escape(copropriete)} · Bonjour {escape(nom)}</p>',
         '<p class="note"><strong>Sondage consultatif.</strong> Votre avis aide le syndic à préparer la décision, '
         'mais ne vaut pas vote. Les travaux seront décidés selon les règles de la copropriété '
         f'(syndic, conseil syndical ou assemblée générale). Clôture le {_date(sondage["clos_le"])}.</p>']
    if message:
        h.append(f'<p class="ok" role="status">{escape(message)}</p>')
    if resume and resume.get("statut") == "valide" and not resume.get("obsolete"):
        h.append(f'<div class="bref"><strong>En bref</strong><br>{escape(resume["resume"])}'
                 f'<small>Résumé rédigé par une IA à partir des devis, relu et validé par le syndic.</small></div>')

    if not ouvert:
        h.append('<p class="erreur">Ce sondage est clos : il n\'est plus possible de répondre.</p>')
        return page(dossier["titre"], "".join(h))

    opts = []
    for did in sondage["options"]:
        d = devis[did]
        coche = " checked" if choix_actuel == did else ""
        qp = f'Votre part : <span class="qp">{_euros(parts[did])}</span> · ' if did in parts else ""
        delai = f' · délai {d["delai_jours"]} jours' if d.get("delai_jours") else ""
        opts.append(f'<label class="option"><input type="radio" name="choix" value="{escape(did)}" required{coche}>'
                    f'<span><span class="titre">{escape(did)} · {escape(d["entreprise"])}</span><br>'
                    f'<span class="detail">{qp}total {_euros(d["montant_ttc"])} TTC{delai}</span></span></label>')
    for val, lib in (("aucun", "Aucun de ces devis"), ("sans_avis", "Sans avis")):
        coche = " checked" if choix_actuel == val else ""
        opts.append(f'<label class="option"><input type="radio" name="choix" value="{val}"{coche}>'
                    f'<span class="titre">{lib}</span></label>')

    h.append(f'<form method="post"><fieldset><legend>Quel devis a votre préférence ?</legend>{"".join(opts)}'
             f'</fieldset><button type="submit">Enregistrer mon avis</button></form>')
    h.append(f'<p style="margin-top:16px"><a href="{escape(lien_pdf)}">Voir le comparatif complet des devis (PDF)</a>'
             f'{" · Vous pouvez changer d’avis jusqu’à la clôture." if choix_actuel else ""}</p>')
    return page(dossier["titre"], "".join(h))


def page_erreur(message: str) -> str:
    return page("Lien invalide", f'<h1>Lien invalide</h1><p class="erreur">{escape(message)}</p>')


def page_consultation(copropriete: str, c: dict, nom: str, choix: str | None, vote_le: str | None,
                      repondre_avant: str, ouverte: bool, message: str | None = None) -> str:
    """Consultation écrite d'une petite copropriété : un vote, une seule fois, à l'unanimité."""
    from datetime import date as _d
    limite = _d.fromisoformat(repondre_avant).strftime("%d/%m/%Y")
    h = [f'<h1>{escape(c["titre"])}</h1>',
         f'<p class="sous">{escape(copropriete)} · consultation des copropriétaires · {escape(nom)}</p>']
    if message:
        h.append(f'<p class="ok">{escape(message)}</p>')
    h.append(f'<div class="bref"><strong>Décision proposée</strong><br>{escape(c["resolution"]).replace(chr(10), "<br>")}'
             '<small>Elle n’est prise que si tous les copropriétaires votent pour. Une abstention ou une absence de '
             'réponse l’empêche ; la question peut alors être soumise à une assemblée générale.</small></div>')
    libelles = {"pour": "Pour", "contre": "Contre", "abstention": "Abstention"}
    if choix:
        h.append(f'<p class="ok">Votre vote : <strong>{libelles.get(choix, choix)}</strong>, enregistré le '
                 f'{_date(vote_le)}. Il ne peut plus être modifié.</p>')
    elif not ouverte:
        h.append('<p class="erreur">La consultation est close.</p>')
    else:
        opts = "".join(f'<label class="option"><input type="radio" name="choix" value="{v}" required>'
                       f'<span class="titre">{l}</span></label>' for v, l in libelles.items())
        h.append(f'<p class="note">Réponse attendue au plus tard le {limite}. Votre vote est définitif : '
                 f'vérifiez-le avant de l’enregistrer.</p>'
                 f'<form method="post"><fieldset><legend>Votre vote</legend>{opts}</fieldset>'
                 f'<button type="submit">Enregistrer mon vote</button></form>')
    return page(c["titre"], "".join(h))
