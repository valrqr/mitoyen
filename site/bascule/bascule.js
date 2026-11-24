/* Mitoyen · passer à un syndic bénévole.
   Le courrier pour l'ordre du jour (article 10 du décret du 17 mars 1967) et le kit de présentation,
   préparés dans le navigateur : rien n'est envoyé ni enregistré. Textes repris du module « bascule » du moteur. */
"use strict";

var AVERTISSEMENT = "Document d’information préparé avec Mitoyen. Ce n’est pas un conseil juridique : pour un cas " +
  "particulier, l’ADIL de votre département vous répond gratuitement.";
var MODES = { benevole: "syndic bénévole", cooperatif: "syndic coopératif" };
var QUALITES = { coproprietaire: "copropriétaire", conseil: "membre du conseil syndical",
                 president: "président du conseil syndical" };
var QUESTIONS = [
  ["Est-ce permis ?", "Oui. La loi du 10 juillet 1965 prévoit le syndic non professionnel : un copropriétaire élu par l’assemblée générale (syndic bénévole), ou le président du conseil syndical dans un syndicat coopératif."],
  ["Qui décide ?", "Toujours l’assemblée générale : budget, travaux, choix des entreprises. Le syndic exécute ses décisions, le conseil syndical l’assiste et le contrôle."],
  ["Et l’argent de la copropriété ?", "Il reste sur un compte bancaire séparé, au nom du syndicat des copropriétaires. Les comptes sont présentés chaque année à l’assemblée, pièces à l’appui."],
  ["Et si le syndic bénévole fait une erreur ?", "Comme tout syndic, il engage sa responsabilité. Une assurance de responsabilité civile, payée par la copropriété, est proposée au vote pour le couvrir."],
  ["Et s’il arrête un jour ?", "L’assemblée générale en désigne un autre, bénévole ou professionnel. Tout est documenté et les comptes s’exportent en entier : la copropriété n’est jamais prisonnière d’un outil."],
  ["Et les gros travaux ?", "Les devis sont présentés côte à côte, sans en recommander aucun ; l’assemblée choisit. Pendant le chantier, chacun reçoit les comptes rendus des réunions."],
  ["Et ceux qui n’ont pas internet ?", "Ils reçoivent tout par courrier, gratuitement, en grands caractères s’ils le souhaitent."]
];
var ETAPES = [
  "Une demande d’inscription à l’ordre du jour est envoyée au syndic actuel (article 10 du décret de 1967).",
  "L’assemblée générale vote la désignation du syndic bénévole, à la majorité de l’article 25.",
  "À la fin du mandat en cours, le nouveau syndic prend ses fonctions et ouvre le compte bancaire du syndicat.",
  "L’ancien syndic remet la trésorerie sous 15 jours, les archives sous un mois, puis le solde des fonds et l’état des comptes dans les deux mois suivants (article 18-2 de la loi de 1965).",
  "Le nouveau syndic met à jour l’immatriculation de la copropriété au registre national."
];

/* ------------------------------------------------------------------ outils */
function Saisie(message) { this.message = message; }

function texte(v, libelle, obligatoire, maxi) {
  v = (v || "").trim();
  if (obligatoire !== false && !v) throw new Saisie(libelle + " : à remplir.");
  if (v.length > (maxi || 300)) throw new Saisie(libelle + " : " + (maxi || 300) + " caractères au plus.");
  return v;
}

/* « 1 234,50 € » -> 123450 (centimes) ; vide -> null. */
function montant(v, libelle, obligatoire) {
  var t = (v || "").replace(/[\s  €]/g, "").replace(",", ".");
  if (!t) { if (obligatoire) throw new Saisie(libelle + " : indiquez un montant."); return null; }
  if (!/^-?\d+(\.\d+)?$/.test(t)) throw new Saisie(libelle + " : « " + v.trim() + " » n’est pas un montant.");
  var c = Math.round(parseFloat(t) * 100);
  if (Math.abs(c) > 1000000000) throw new Saisie(libelle + " : montant trop élevé.");
  return c;
}

function milliers(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
function euros(c) {
  var s = c < 0 ? "-" : "", a = Math.abs(c);
  return s + milliers(Math.floor(a / 100)) + "," + String(a % 100).padStart(2, "0") + " €";
}
function eurosRond(c) { var s = c < 0 ? "-" : ""; return s + milliers(Math.round(Math.abs(c) / 100)) + " €"; }
function dateFr(iso) { var p = iso.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }
function aujourdhui() {
  var d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}
function pluriel(liste) { return liste.indexOf(",") >= 0 || liste.indexOf(" et ") >= 0 ? "s" : ""; }

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
function lignes(t) {   /* un texte saisi sur plusieurs lignes */
  var out = [];
  t.split("\n").forEach(function (l, i) { if (i) out.push(h("br")); out.push(l); });
  return out;
}

/* ------------------------------------------------------------------ courrier */
function validerCourrier(f) {
  var d = {
    expediteur_nom: texte(f.expediteur_nom, "Votre nom", true, 120),
    expediteur_adresse: texte(f.expediteur_adresse, "Votre adresse", true, 300),
    expediteur_lots: texte(f.expediteur_lots, "Vos numéros de lots", false, 60),
    qualite: f.qualite || "coproprietaire",
    syndic_nom: texte(f.syndic_nom, "Nom du syndic actuel", true, 120),
    syndic_adresse: texte(f.syndic_adresse, "Adresse du syndic actuel", true, 300),
    residence_nom: texte(f.residence_nom, "Nom de la résidence", true, 120),
    residence_adresse: texte(f.residence_adresse, "Adresse de la résidence", true, 300),
    mode: f.mode || "benevole",
    candidat: texte(f.candidat, "Candidat", false, 120),
    prise_de_fonction: f.prise_de_fonction || "fin_mandat",
    lieu: texte(f.lieu, "Lieu", false, 80),
    assurance: !!f.assurance,
    prime_max: montant(f.prime_max, "Prime d’assurance annuelle"),
    mention_outil: !!f.mention_outil,
    duree_mois: parseInt(f.duree_mois || "36", 10),
    date: aujourdhui()
  };
  if (!QUALITES[d.qualite]) throw new Saisie("Qualité de l’expéditeur inconnue.");
  if (!MODES[d.mode]) throw new Saisie("Choisissez un syndic bénévole ou coopératif.");
  d.candidat = d.candidat || d.expediteur_nom;
  if (!(d.duree_mois >= 1 && d.duree_mois <= 36)) throw new Saisie("Durée du mandat : entre 1 et 36 mois (trois ans au plus).");
  if (d.prime_max !== null && d.prime_max < 0) throw new Saisie("Prime d’assurance annuelle : un montant positif.");
  if (d.prise_de_fonction === "date") {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(f.date_prise || "")) throw new Saisie("Date de prise de fonction : choisissez une date.");
    d.date_prise = f.date_prise;
  } else if (d.prise_de_fonction !== "fin_mandat") {
    throw new Saisie("Prise de fonction : à la fin du mandat en cours, ou à une date.");
  }
  return d;
}

function debut(d) {
  return d.prise_de_fonction === "date" ? "à compter du " + dateFr(d.date_prise)
    : "à compter de l’expiration du mandat du syndic actuellement en fonction";
}

function resolutions(d) {
  var m = d.duree_mois;
  var duree = m % 12 ? m + " mois" : (m / 12) + " an" + (m > 12 ? "s" : "");
  var art25 = "Majorité de l’article 25 de la loi du 10 juillet 1965 ; à défaut, second vote possible à la majorité de l’article 24 (article 25-1).";
  var res = [];
  if (d.mode === "benevole") {
    res.push({ titre: "Désignation d’un syndic non professionnel (syndic bénévole)",
      texte: "L’assemblée générale désigne " + d.candidat + ", copropriétaire, en qualité de syndic bénévole du syndicat des copropriétaires de la résidence " + d.residence_nom + ", pour une durée de " + duree + " " + debut(d) + ". Le mandat est exercé à titre gratuit ; seuls les frais réellement engagés pour le compte du syndicat sont remboursés, sur justificatifs. Le syndic ouvre un compte bancaire séparé au nom du syndicat.",
      majorite: art25 });
  } else {
    res.push({ titre: "Adoption de la forme coopérative du syndicat",
      texte: "L’assemblée générale décide que le syndicat des copropriétaires de la résidence " + d.residence_nom + " adopte la forme coopérative " + debut(d) + ". Le conseil syndical élit son président parmi ses membres ; celui-ci exerce les fonctions de syndic. Le syndic ouvre un compte bancaire séparé au nom du syndicat.",
      majorite: art25 });
    res.push({ titre: "Désignation d’un membre du conseil syndical",
      texte: "L’assemblée générale désigne " + d.candidat + ", copropriétaire, en qualité de membre du conseil syndical, pour une durée de " + duree + ", en vue de son élection à la présidence du conseil.",
      majorite: "Majorité de l’article 25 de la loi du 10 juillet 1965." });
  }
  if (d.assurance) {
    var plafond = d.prime_max ? ", dans la limite d’une prime annuelle de " + euros(d.prime_max) : "";
    res.push({ titre: "Assurance de responsabilité civile du syndic non professionnel",
      texte: "L’assemblée générale décide de souscrire, pour le compte du syndicat, une assurance couvrant la responsabilité civile du syndic non professionnel" + plafond + ". La prime est répartie en charges communes générales et inscrite au budget prévisionnel.",
      majorite: "Majorité de l’article 24 de la loi du 10 juillet 1965." });
  }
  return res;
}

function courrier(d) {
  var res = resolutions(d);
  var lots = d.expediteur_lots ? " (lot" + pluriel(d.expediteur_lots) + " n° " + d.expediteur_lots + ")" : "";
  var p1 = h("article", { "class": "page lettre", "aria-label": "Page 1 : la lettre" },
    h("div", { "class": "entete" },
      h("p", null, h("strong", null, d.expediteur_nom), h("br"), lignes(d.expediteur_adresse)),
      h("p", { "class": "destinataire" }, h("strong", null, d.syndic_nom), h("br"), lignes(d.syndic_adresse))),
    h("p", { "class": "droite" }, (d.lieu ? d.lieu + ", le " : "Le ") + dateFr(d.date)),
    h("p", { "class": "petit" }, h("strong", null, "Lettre recommandée avec demande d’avis de réception")),
    h("p", null, h("strong", null, "Objet : demande d’inscription de questions à l’ordre du jour de la prochaine assemblée générale"),
      " (article 10 du décret n° 67-223 du 17 mars 1967)"),
    h("p", null, "Madame, Monsieur,"),
    h("p", null, "En ma qualité de " + QUALITES[d.qualite] + lots + " de la résidence " + d.residence_nom + ", " +
      d.residence_adresse.replace(/\n/g, ", ") + ", et en application de l’article 10 du décret du 17 mars 1967, je vous demande d’inscrire à l’ordre du jour de la prochaine assemblée générale les questions suivantes. Le projet de résolution de chacune est joint en annexe."),
    h("ol", null, res.map(function (r) { return h("li", null, r.titre + "."); })),
    h("p", null, "Si la date de réception de cette demande ne permettait pas de les inscrire à la prochaine assemblée, je vous remercie de les porter à l’ordre du jour de l’assemblée suivante, comme le prévoit le même article."),
    d.mention_outil ? h("p", null, "Pour information, le syndic désigné s’appuiera sur Mitoyen, un outil de gestion libre, pour préparer les appels de fonds, les assemblées générales et la comptabilité du syndicat.") : null,
    h("p", null, "Je vous remercie de bien vouloir m’accuser réception de cette demande."),
    h("p", null, "Je vous prie d’agréer, Madame, Monsieur, l’expression de mes salutations distinguées."),
    h("p", { "class": "signature" }, d.expediteur_nom),
    h("p", { "class": "petit" }, "Pièce jointe : projet" + (res.length > 1 ? "s" : "") + " de résolution (" + res.length + ")."),
    h("p", { "class": "pied" }, d.residence_nom + " – demande d’inscription à l’ordre du jour"));
  var p2 = h("article", { "class": "page", "aria-label": "Page 2 : les projets de résolution" },
    h("h3", { "class": "titre-doc" }, "Annexe : projets de résolution"),
    h("p", { "class": "sous" }, "Résidence " + d.residence_nom + " · demande de " + d.expediteur_nom + " du " + dateFr(d.date)),
    res.map(function (r, i) {
      return h("section", { "class": "resolution" },
        h("h4", null, "Projet de résolution n° " + (i + 1) + " : " + r.titre),
        h("p", null, r.texte), h("p", { "class": "petit" }, r.majorite));
    }),
    h("p", { "class": "petit avert" }, AVERTISSEMENT),
    h("p", { "class": "pied" }, d.residence_nom + " – demande d’inscription à l’ordre du jour"));
  return [p1, p2];
}

/* ------------------------------------------------------------------ kit */
function validerKit(f) {
  var d = {
    residence_nom: texte(f.residence_nom, "Nom de la résidence", true, 120),
    mode: f.mode || "benevole",
    honoraires: montant(f.honoraires, "Honoraires annuels du syndic actuel", true),
    frais_annexes: montant(f.frais_annexes, "Frais facturés en plus du forfait") || 0,
    assurance: montant(f.assurance, "Assurance du syndic bénévole") || 0,
    frais_postaux: montant(f.frais_postaux, "Frais postaux") || 0,
    outil: montant(f.outil, "Coût de l’outil de gestion") || 0,
    autres: montant(f.autres, "Autres frais") || 0,
    candidats: texte(f.candidats, "Candidat(s)", false, 200),
    contact: texte(f.contact, "Contact", false, 200),
    grand: !!f.grand,
    lots: parseInt(f.lots || "0", 10)
  };
  if (!MODES[d.mode]) throw new Saisie("Choisissez un syndic bénévole ou coopératif.");
  if (!(d.lots >= 2 && d.lots <= 500)) throw new Saisie("Nombre de lots : entre 2 et 500.");
  ["honoraires", "frais_annexes", "assurance", "frais_postaux", "outil", "autres"].forEach(function (k) {
    if (d[k] < 0) throw new Saisie("Les montants sont positifs.");
  });
  return d;
}

function tableau(entete, rangs, total) {
  return h("table", { "class": "chiffres-doc" },
    h("thead", null, h("tr", null, entete.map(function (c, i) { return h("th", i ? { "class": "n" } : null, c); }))),
    h("tbody", null, rangs.map(function (r, j) {
      return h("tr", total && j === rangs.length - 1 ? { "class": "total" } : null,
        r.map(function (c, i) { return h("td", i && entete.length === 2 ? { "class": "n" } : null, c); }));
    })));
}

function kit(d) {
  var actuel = d.honoraires + d.frais_annexes;
  var benevole = d.assurance + d.frais_postaux + d.outil + d.autres;
  var eco = actuel - benevole, qui = MODES[d.mode];
  var cles = [["Syndic actuel", eurosRond(actuel), "par an, honoraires et frais"],
              ["Gestion bénévole", eurosRond(benevole), "par an, estimation"]];
  if (eco > 0) cles.push(["Économie", eurosRond(eco), "par an, soit " + eurosRond(Math.round(eco / d.lots)) + " par lot"]);
  var lignes1 = [["Honoraires du syndic actuel (dernier exercice)", euros(d.honoraires)]];
  if (d.frais_annexes) lignes1.push(["Frais facturés en plus du forfait", euros(d.frais_annexes)]);
  lignes1.push(["Coût actuel", euros(actuel)]);
  var lignes2 = [["Assurance de responsabilité civile du syndic", euros(d.assurance)],
                 ["Frais postaux et fournitures", euros(d.frais_postaux)],
                 ["Outil de gestion", d.outil ? euros(d.outil) : "gratuit (logiciel libre)"]];
  if (d.autres) lignes2.push(["Autres frais", euros(d.autres)]);
  lignes2.push(["Coût estimé en gestion bénévole", euros(benevole)]);
  var pied = d.residence_nom + " – proposition de gestion bénévole";
  var p1 = h("article", { "class": "page", "aria-label": "Page 1 : les chiffres" },
    h("p", { "class": "bandeau" }, "Mitoyen"),
    h("h3", { "class": "titre-doc" }, "Et si nous gérions notre copropriété nous-mêmes ?"),
    h("p", { "class": "sous" }, "Résidence " + d.residence_nom + " · " + d.lots + " lots · proposition d’un " + qui),
    h("div", { "class": "essentiel" }, cles.map(function (c, i) {
      return h("div", i === 2 ? { "class": "eco" } : null, h("span", null, c[0]), h("b", null, c[1]), h("small", null, c[2]));
    })),
    h("p", null, "Aujourd’hui, le syndic coûte à la copropriété ", h("strong", null, euros(actuel)), " par an, soit " +
      euros(Math.round(actuel / d.lots)) + " par lot en moyenne. Un " + qui + " ne prend pas d’honoraires : il ne reste que les frais réels, détaillés ci-dessous."),
    h("h4", null, "D’où viennent ces chiffres"),
    tableau(["", "Par an"], lignes1, true),
    tableau(["", "Par an"], lignes2, true),
    h("p", { "class": "petit" }, "Les frais de la gestion bénévole sont des estimations, à confirmer par des devis (assurance notamment). Les dépenses de l’immeuble (eau, électricité, entretien, travaux) ne changent pas : seul le coût de la gestion change."),
    h("h4", null, "Ce qui change, ce qui ne change pas"),
    tableau(["", "Aujourd’hui", "Avec un " + qui], [
      ["Qui gère", "Un cabinet", "Un copropriétaire élu"],
      ["Qui décide", "L’assemblée générale", "L’assemblée générale"],
      ["Le compte bancaire", "Au nom du syndicat", "Au nom du syndicat"],
      ["Le contrôle", "Le conseil syndical", "Le conseil syndical"],
      ["Le coût de la gestion", eurosRond(actuel) + " par an", eurosRond(benevole) + " par an"]], false),
    h("p", { "class": "pied" }, pied));
  var p2 = h("article", { "class": "page", "aria-label": "Page 2 : les questions et le calendrier" },
    h("h4", null, "Les questions qu’on se pose"),
    QUESTIONS.map(function (q) { return h("div", { "class": "question" }, h("p", null, h("strong", null, q[0])), h("p", null, q[1])); }),
    h("h4", null, "Comment se passe la bascule"),
    h("ol", null, ETAPES.map(function (e) { return h("li", null, e); })),
    (d.candidats || d.contact) ? h("h4", null, "Qui contacter") : null,
    d.candidats ? h("p", null, "Candidat" + pluriel(d.candidats) + " : ", h("strong", null, d.candidats)) : null,
    d.contact ? h("p", null, "Pour en parler : " + d.contact) : null,
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

function brancher(idForm, valider, fabriquer, grandCle) {
  var form = document.getElementById(idForm);
  if (!form) return;
  var erreur = form.querySelector(".erreur");
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    erreur.hidden = true;
    var d;
    try { d = valider(lireFormulaire(form)); }
    catch (e) {
      if (!(e instanceof Saisie)) throw e;
      erreur.textContent = e.message; erreur.hidden = false; erreur.focus && erreur.scrollIntoView({ block: "center" });
      return;
    }
    var doc = document.getElementById("document");
    doc.textContent = "";
    doc.className = "document" + (grandCle && d[grandCle] ? " grand" : "");
    fabriquer(d).forEach(function (p) { doc.appendChild(p); });
    var apercu = document.getElementById("apercu");
    apercu.hidden = false;
    apercu.dataset.source = idForm;
    document.getElementById("apercu-titre").focus({ preventScroll: true });
    apercu.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("apercu-titre").setAttribute("tabindex", "-1");
  brancher("form-courrier", validerCourrier, courrier);
  brancher("form-kit", validerKit, kit, "grand");
  document.getElementById("imprimer").addEventListener("click", function () { window.print(); });
  document.getElementById("modifier").addEventListener("click", function () {
    var src = document.getElementById("apercu").dataset.source;
    document.getElementById(src).scrollIntoView();
  });
});
