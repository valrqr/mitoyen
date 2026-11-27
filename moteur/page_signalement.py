"""
page_signalement.py — La page que les copropriétaires ouvrent depuis le QR code du hall.

Même esprit que la page de vote : HTML servi par le moteur, aucun JavaScript, lisible sur téléphone,
accessible au clavier. Les urgences passent avant le formulaire ; la liste visible de tous ne montre
ni description, ni photo, ni contact.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from .page_vote import ICONE_URI, STYLE

STYLE_SIGNALEMENT = """
.urgence{background:#fff;border:2px solid #1E1E1E;border-radius:12px;padding:12px 16px;margin:0 0 20px}
.urgence h2{font-size:17px;margin:0 0 6px}.urgence ul{margin:0;padding-left:18px}.urgence li{margin:4px 0}
.urgence a{font-weight:700}
.absence{background:#F1F2EF;border-radius:12px;padding:12px 16px;margin:0 0 20px}
label.champ{display:block;font-weight:700;margin:0 0 6px}
.aide{font-size:14px;color:#4A4945;margin:-2px 0 8px}
input[type=text],textarea,input[type=file]{width:100%;font:inherit;padding:12px;border:2px solid #E3E1DA;border-radius:10px;
background:#fff;margin:0 0 16px}textarea{min-height:110px}
input[type=text]:focus,textarea:focus{outline:3px solid #C2410C;outline-offset:1px}
.niveaux{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.piege{position:absolute;left:-9999px}
h2.suivi{font-size:19px;margin:28px 0 10px}
.ligne{background:#fff;border:1px solid #E3E1DA;border-radius:12px;padding:12px 14px;margin:0 0 8px}
.ligne .etat{display:inline-block;font-size:13px;font-weight:700;border:1.5px solid #1E1E1E;border-radius:999px;padding:1px 9px}
.ligne .etat.regle{background:#1E1E1E;color:#fff}
.ligne .quand{font-size:13px;color:#5F5E5A}
"""


def _page(titre: str, copropriete: str, corps: str) -> str:
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="noindex, nofollow"><title>{escape(titre)} – Mitoyen</title>'
            + (f'<link rel="icon" type="image/png" href="{ICONE_URI}">' if ICONE_URI else "") +
            f'<style>{STYLE}{STYLE_SIGNALEMENT}</style></head><body><main>'
            f'<header>' + (f'<img src="{ICONE_URI}" alt="" width="34" height="32">' if ICONE_URI else "")
            + f'<span class="marque">Mitoyen</span></header>{corps}'
            f'<footer>{escape(copropriete)}. Ce lien est réservé aux habitants de l’immeuble : ne le diffusez pas en dehors. '
            f'Page préparée par Mitoyen pour le syndic de votre copropriété.</footer></main></body></html>')


def _quand(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d:%d/%m/%Y}"


def page_signaler(copropriete: str, categories: dict, niveaux: dict, urgences: list[tuple[str, str]],
                  suivi: list[dict], message: str | None = None, erreur: str | None = None,
                  saisie: dict | None = None, absence: dict | None = None) -> str:
    saisie = saisie or {}
    if absence and absence.get("contact"):
        urgences = urgences + [(absence["contact"]["libelle"], absence["contact"]["telephone"])]
    h = ['<h1>Signaler un problème</h1>',
         f'<p class="sous">{escape(copropriete)}. Votre message arrive directement au syndic.</p>']
    if message:
        h.append(f'<p class="ok" role="status">{escape(message)}</p>')
    if erreur:
        h.append(f'<p class="erreur" role="alert">{escape(erreur)}</p>')
    if absence:
        h.append(f'<p class="absence">{escape(absence["texte"])}</p>')

    tel = "".join(f'<li><a href="tel:{escape(n.replace(" ", ""))}">{escape(n)}</a> : {escape(l)}</li>' for l, n in urgences)
    h.append('<section class="urgence" aria-labelledby="t-urgence"><h2 id="t-urgence">Danger immédiat ? Appelez d’abord</h2>'
             f'<ul>{tel}</ul></section>')

    cats = "".join(
        f'<label class="option"><input type="radio" name="categorie" value="{escape(k)}" required'
        f'{" checked" if saisie.get("categorie") == k else ""}><span class="titre">{escape(v["libelle"])}</span></label>'
        for k, v in categories.items())
    nivs = "".join(
        f'<label class="option"><input type="radio" name="niveau" value="{escape(k)}" required'
        f'{" checked" if saisie.get("niveau", "genant") == k else ""}><span class="titre">{escape(v)}</span></label>'
        for k, v in niveaux.items())
    h.append(
        '<form method="post" enctype="multipart/form-data">'
        f'<fieldset><legend>De quoi s’agit-il ?</legend>{cats}</fieldset>'
        '<label class="champ" for="lieu">Où ?</label>'
        '<p class="aide" id="aide-lieu">Bâtiment, étage, cave, local poubelles, porte du parking…</p>'
        f'<input type="text" id="lieu" name="lieu" required maxlength="120" aria-describedby="aide-lieu" value="{escape(saisie.get("lieu", ""))}">'
        '<label class="champ" for="description">Qu’avez-vous constaté ?</label>'
        '<p class="aide" id="aide-desc">Décrivez ce qui est abîmé ou en panne. Ne nommez personne : un signalement '
        'décrit des faits.</p>'
        f'<textarea id="description" name="description" required maxlength="2000" aria-describedby="aide-desc">{escape(saisie.get("description", ""))}</textarea>'
        f'<fieldset><legend>Est-ce urgent ?</legend><div class="niveaux">{nivs}</div></fieldset>'
        '<label class="champ" for="photo">Une photo (facultatif)</label>'
        '<p class="aide" id="aide-photo">Photographiez le problème, pas les personnes. La position GPS de la photo est effacée.</p>'
        '<input type="file" id="photo" name="photo" accept="image/*" aria-describedby="aide-photo">'
        '<label class="champ" for="contact">Pour vous recontacter (facultatif)</label>'
        '<p class="aide" id="aide-contact">Votre nom ou votre appartement. Seul le syndic le voit.</p>'
        f'<input type="text" id="contact" name="contact" maxlength="120" aria-describedby="aide-contact" value="{escape(saisie.get("contact", ""))}">'
        '<label class="piege" aria-hidden="true">Ne pas remplir<input type="text" name="site_web" tabindex="-1" autocomplete="off"></label>'
        '<button type="submit">Envoyer au syndic</button></form>')

    h.append('<h2 class="suivi">Déjà signalé</h2>')
    if suivi:
        h.append('<p class="aide">Si votre problème y figure déjà, inutile de le signaler à nouveau.</p>')
        for s in suivi:
            cls = "etat regle" if s["statut"] == "regle" else "etat"
            note = f'<br><span class="detail">{escape(s["note"])}</span>' if s.get("note") else ""
            h.append(f'<div class="ligne"><span class="{cls}">{escape(s["statut_libelle"])}</span> '
                     f'<strong>{escape(s["categorie"])}</strong>, {escape(s["lieu"])}<br>'
                     f'<span class="quand">Signalé le {_quand(s["cree_le"])}</span>{note}</div>')
    else:
        h.append('<p class="aide">Aucun signalement en cours.</p>')
    return _page("Signaler un problème", copropriete, "".join(h))


def page_lien_invalide() -> str:
    return _page("Lien invalide", "",
                 '<h1>Lien invalide</h1><p class="erreur">Ce lien n’est plus valable. Le syndic l’a peut-être renouvelé : '
                 'utilisez le QR code affiché dans le hall, ou déposez un mot dans sa boîte aux lettres.</p>')
