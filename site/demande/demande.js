/* Mitoyen · demander un vote à la prochaine assemblée générale.
   Le courrier au syndic (article 10 du décret du 17 mars 1967), le projet de résolution et la liste
   des pièces à joindre, préparés dans le navigateur : rien n'est envoyé ni enregistré. */
"use strict";

var AVERTISSEMENT = "Document d’information préparé avec Mitoyen (mitoyen.app). La majorité est indiquée à titre " +
  "indicatif ; le règlement de copropriété peut prévoir des règles propres à l’immeuble. Ce n’est pas un conseil " +
  "juridique : pour un cas particulier, l’ADIL de votre département vous répond gratuitement.";
var QUALITES = { coproprietaire: "copropriétaire", conseil: "membre du conseil syndical",
                 president: "président du conseil syndical" };

/* Chaque type de demande : une aide, un modèle de résolution, la majorité, les pièces à joindre. */
var TYPES = {
  travaux_prives: {
    aide: "Percer un mur porteur, poser un climatiseur en façade, fermer un balcon, changer fenêtres ou volets pour un autre modèle… Ces travaux, faits à vos frais, demandent l’accord de l’assemblée avant de commencer.",
    montant: false,
    resolution: function (d) {
      return "L’assemblée générale autorise " + d.expediteur_nom + (d.expediteur_lots ? ", copropriétaire du lot " + d.expediteur_lots : "") +
        ", à faire réaliser à ses frais exclusifs les travaux suivants, qui affectent les parties communes ou l’aspect extérieur de l’immeuble : " +
        (d.description || d.objet) + ". Les travaux seront conformes au document joint, qui en précise l’implantation et la consistance. " +
        "Ils seront réalisés dans les règles de l’art par une entreprise assurée, après information du syndic. " +
        d.expediteur_nom + " en assumera l’entretien et la responsabilité, ainsi que la remise en état des parties communes si nécessaire.";
    },
    majorite: "Majorité de l’article 25 b de la loi du 10 juillet 1965 ; à défaut, second vote possible à la majorité de l’article 24 (article 25-1).",
    pieces: [["Un document qui précise l’implantation et la consistance des travaux : plan, croquis ou descriptif technique", "obligatoire (article 10 du décret)"],
             ["Le devis de l’entreprise et son attestation d’assurance", "conseillé"],
             ["Une photo de l’emplacement", "conseillé"]]
  },
  travaux_communs: {
    aide: "Une réparation, un entretien ou une amélioration des parties communes que vous souhaitez faire voter.",
    montant: true,
    resolution: function (d) {
      return "L’assemblée générale décide de faire réaliser les travaux suivants sur les parties communes : " + (d.description || d.objet) +
        (d.montant ? ", pour un montant maximum de " + euros(d.montant) + " TTC" : "") +
        ". Le coût est réparti entre les copropriétaires selon la clé de répartition applicable à ces travaux. " +
        "L’assemblée mandate le syndic pour passer commande auprès de l’entreprise retenue et pour appeler les fonds nécessaires selon l’échéancier voté.";
    },
    majorite: "Majorité de l’article 24 de la loi du 10 juillet 1965 pour l’entretien et la conservation de l’immeuble ; majorité de l’article 25 pour une amélioration. À confirmer avec le syndic.",
    pieces: [["Un ou, mieux, deux devis", "conseillé : l’assemblée vote sur des conditions précises"],
             ["Une photo ou un descriptif du problème", "conseillé"]]
  },
  partie_commune: {
    aide: "Installer un équipement dans une partie commune, en avoir l’usage exclusif, ou l’acheter : il faut l’accord de l’assemblée.",
    montant: false,
    resolution: function (d) {
      return "L’assemblée générale autorise " + d.expediteur_nom + (d.expediteur_lots ? ", copropriétaire du lot " + d.expediteur_lots : "") +
        ", à " + (d.description || d.objet) + ", dans les conditions précisées au document joint. " +
        "Cette autorisation n’emporte aucun transfert de propriété ; " + d.expediteur_nom + " prend à sa charge les frais qui en résultent " +
        "et remettra les lieux en état si l’autorisation prend fin.";
    },
    majorite: "La majorité dépend de ce qui est demandé : un usage ponctuel, un droit de jouissance exclusif ou l’achat d’une partie commune ne relèvent pas des mêmes règles (articles 24, 25 ou 26 de la loi du 10 juillet 1965). À confirmer avec le syndic.",
    pieces: [["Un plan ou une photo de la partie commune concernée", "conseillé"]]
  },
  autre: {
    aide: "Toute autre question : la rédiger aussi précisément que possible, sous la forme d’une décision que l’assemblée peut adopter ou rejeter.",
    montant: true,
    resolution: function (d) {
      return "L’assemblée générale décide " + (d.description || d.objet) + (d.montant ? ", pour un montant maximum de " + euros(d.montant) + " TTC" : "") + ".";
    },
    majorite: "Majorité à préciser selon l’objet de la question ; le syndic peut vous l’indiquer.",
    pieces: [["Tout document utile à la décision", "conseillé"]]
  }
};

/* ------------------------------------------------------------------ outils */
function Saisie(message) { this.message = message; }

function texte(v, libelle, obligatoire, maxi) {
  v = (v || "").trim();
  if (obligatoire !== false && !v) throw new Saisie(libelle + " : à remplir.");
  if (v.length > (maxi || 300)) throw new Saisie(libelle + " : " + (maxi || 300) + " caractères au plus.");
  return v;
}

function montant(v, libelle) {
  var t = (v || "").replace(/[\s  €]/g, "").replace(",", ".");
  if (!t) return null;
  if (!/^\d+(\.\d+)?$/.test(t)) throw new Saisie(libelle + " : « " + v.trim() + " » n’est pas un montant.");
  var c = Math.round(parseFloat(t) * 100);
  if (c > 1000000000) throw new Saisie(libelle + " : montant trop élevé.");
  return c;
}

function milliers(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
function euros(c) { return milliers(Math.floor(c / 100)) + "," + String(c % 100).padStart(2, "0") + " €"; }
function dateFr(iso) { var p = iso.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }
function aujourdhui() {
  var d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}
function pluriel(liste) { return liste.indexOf(",") >= 0 || liste.indexOf(" et ") >= 0 ? "s" : ""; }
/* minuscule initiale, point final retiré : pour insérer une saisie dans une phrase */
function enPhrase(t) { t = t.trim().replace(/[.\s]+$/, ""); return t.charAt(0).toLowerCase() + t.slice(1); }

/* Construit un élément ; les textes passent par des nœuds texte, jamais par innerHTML. */
function h(tag, attrs) {
  var el = document.createElement(tag);
  if (attrs) for (var k in attrs) el.setAttribute(k, attrs[k]);
  for (var i = 2; i < arguments.length; i++) {
    var c = arguments[i];
    if (c === null || c === undefined || c === false) continue;
    if (Array.isArray(c)) c.forEach(function (x) { el.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
    else el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return el;
}
function lignes(t) {
  var out = [];
  t.split("\n").forEach(function (l, i) { if (i) out.push(h("br")); out.push(l); });
  return out;
}

/* ------------------------------------------------------------------ courrier */
function brouillon(f) {
  /* les champs utiles au modèle de résolution, sans contrôle : sert au préremplissage */
  return { expediteur_nom: (f.expediteur_nom || "").trim() || "[votre nom]",
           expediteur_lots: (f.expediteur_lots || "").trim(),
           objet: enPhrase(f.objet || "") || "[votre demande]",
           description: f.description ? enPhrase(f.description) : "",
           montant: (function () { try { return montant(f.montant, "Montant"); } catch (e) { return null; } })() };
}

function valider(f) {
  var d = {
    type: f.type,
    objet: texte(f.objet, "Votre demande, en quelques mots", true, 120),
    description: texte(f.description, "Description", false, 1200),
    montant: montant(f.montant, "Montant estimé"),
    resolution: texte(f.resolution, "Projet de résolution", true, 3000),
    expediteur_nom: texte(f.expediteur_nom, "Votre nom", true, 120),
    expediteur_adresse: texte(f.expediteur_adresse, "Votre adresse", true, 300),
    expediteur_lots: texte(f.expediteur_lots, "Vos numéros de lots", false, 60),
    qualite: f.qualite || "coproprietaire",
    lieu: texte(f.lieu, "Ville", false, 80),
    syndic_nom: texte(f.syndic_nom, "Nom du syndic", true, 120),
    syndic_adresse: texte(f.syndic_adresse, "Adresse du syndic", true, 300),
    residence_nom: texte(f.residence_nom, "Nom de la résidence", true, 120),
    residence_adresse: texte(f.residence_adresse, "Adresse de la résidence", true, 300),
    grand: !!f.grand,
    date: aujourdhui()
  };
  if (!TYPES[d.type]) throw new Saisie("Choisissez ce que vous demandez.");
  if (!QUALITES[d.qualite]) throw new Saisie("Qualité de l’expéditeur inconnue.");
  if (/\[votre (nom|demande)\]/.test(d.resolution)) throw new Saisie("Projet de résolution : remplacez les passages entre crochets.");
  return d;
}

function courrier(d) {
  var t = TYPES[d.type];
  var lots = d.expediteur_lots ? " (lot" + pluriel(d.expediteur_lots) + " n° " + d.expediteur_lots + ")" : "";
  var pied = d.residence_nom + " – demande d’inscription à l’ordre du jour";
  var p1 = h("article", { "class": "page lettre", "aria-label": "Page 1 : la lettre" },
    h("div", { "class": "entete" },
      h("p", null, h("strong", null, d.expediteur_nom), h("br"), lignes(d.expediteur_adresse)),
      h("p", { "class": "destinataire" }, h("strong", null, d.syndic_nom), h("br"), lignes(d.syndic_adresse))),
    h("p", { "class": "droite" }, (d.lieu ? d.lieu + ", le " : "Le ") + dateFr(d.date)),
    h("p", { "class": "petit" }, h("strong", null, "Lettre recommandée avec demande d’avis de réception")),
    h("p", null, h("strong", null, "Objet : demande d’inscription d’une question à l’ordre du jour de la prochaine assemblée générale"),
      " (article 10 du décret n° 67-223 du 17 mars 1967)"),
    h("p", null, "Madame, Monsieur,"),
    h("p", null, "En ma qualité de " + QUALITES[d.qualite] + lots + " de la résidence " + d.residence_nom + ", " +
      d.residence_adresse.replace(/\n/g, ", ") + ", et en application de l’article 10 du décret du 17 mars 1967, je vous demande d’inscrire à l’ordre du jour de la prochaine assemblée générale la question suivante :"),
    h("p", { "class": "question-ag" }, h("strong", null, d.objet.charAt(0).toUpperCase() + d.objet.slice(1).replace(/[.\s]+$/, "") + ".")),
    d.description ? h("p", null, lignes(d.description)) : null,
    h("p", null, "Le projet de résolution est joint en annexe, avec la liste des pièces qui l’accompagnent. Je vous remercie de le joindre à la convocation."),
    h("p", null, "Si la date de réception de cette demande ne permettait pas de l’inscrire à la prochaine assemblée, je vous remercie de la porter à l’ordre du jour de l’assemblée suivante, comme le prévoit le même article."),
    h("p", null, "Je vous remercie de bien vouloir m’accuser réception de cette demande."),
    h("p", null, "Je vous prie d’agréer, Madame, Monsieur, l’expression de mes salutations distinguées."),
    h("p", { "class": "signature" }, d.expediteur_nom),
    h("p", { "class": "petit" }, "Pièces jointes : projet de résolution et documents listés en annexe."),
    h("p", { "class": "pied" }, pied));
  var p2 = h("article", { "class": "page", "aria-label": "Page 2 : le projet de résolution et les pièces" },
    h("h3", { "class": "titre-doc" }, "Annexe : projet de résolution"),
    h("p", { "class": "sous" }, "Résidence " + d.residence_nom + " · demande de " + d.expediteur_nom + " du " + dateFr(d.date)),
    h("section", { "class": "resolution" },
      h("h4", null, d.objet.charAt(0).toUpperCase() + d.objet.slice(1).replace(/[.\s]+$/, "")),
      h("p", null, lignes(d.resolution)), h("p", { "class": "petit" }, t.majorite)),
    h("h4", null, "Pièces jointes"),
    h("table", { "class": "chiffres-doc" },
      h("tbody", null, t.pieces.map(function (p) { return h("tr", null, h("td", null, "☐ " + p[0]), h("td", { "class": "n" }, p[1])); }))),
    h("p", { "class": "petit avert" }, AVERTISSEMENT),
    h("p", { "class": "pied" }, pied));
  return [p1, p2];
}

/* ------------------------------------------------------------------ page */
function lireFormulaire(form) {
  var f = {};
  Array.prototype.forEach.call(form.elements, function (el) {
    if (!el.name) return;
    f[el.name] = el.type === "checkbox" ? el.checked : el.value;
  });
  return f;
}

document.addEventListener("DOMContentLoaded", function () {
  var form = document.getElementById("form-demande");
  var erreur = form.querySelector(".erreur");
  var zone = form.elements.resolution;
  var aide = document.getElementById("aide-type");
  var champMontant = document.getElementById("champ-montant");
  var retouche = false;           /* le texte de la résolution a été modifié à la main : on n'y touche plus */
  document.getElementById("apercu-titre").setAttribute("tabindex", "-1");

  function proposer() {
    var f = lireFormulaire(form), t = TYPES[f.type];
    aide.textContent = t.aide;
    champMontant.hidden = !t.montant;
    if (!retouche) zone.value = t.resolution(brouillon(f));
  }
  zone.addEventListener("input", function () { retouche = zone.value.trim() !== ""; });
  ["type", "objet", "description", "montant", "expediteur_nom", "expediteur_lots"].forEach(function (n) {
    form.elements[n].addEventListener("input", proposer);
    form.elements[n].addEventListener("change", proposer);
  });
  proposer();

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    erreur.hidden = true;
    if (!retouche) zone.value = TYPES[form.elements.type.value].resolution(brouillon(lireFormulaire(form)));
    var d;
    try { d = valider(lireFormulaire(form)); }
    catch (e) {
      if (!(e instanceof Saisie)) throw e;
      erreur.textContent = e.message; erreur.hidden = false; erreur.scrollIntoView({ block: "center" });
      return;
    }
    var doc = document.getElementById("document");
    doc.textContent = "";
    doc.className = "document" + (d.grand ? " grand" : "");
    courrier(d).forEach(function (p) { doc.appendChild(p); });
    var apercu = document.getElementById("apercu");
    apercu.hidden = false;
    document.getElementById("apercu-titre").focus({ preventScroll: true });
    apercu.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
  document.getElementById("imprimer").addEventListener("click", function () { window.print(); });
  document.getElementById("modifier").addEventListener("click", function () { form.scrollIntoView(); });
});
