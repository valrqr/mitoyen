/*
 * regles.js — Les règles de vote de l'assemblée générale, pour l'outil du président de séance.
 *
 * Même logique que core/vote.py (le moteur Python de Mitoyen) ; un test vérifie que les deux
 * donnent les mêmes résultats (tests/test_seance_parite.py).
 *
 *   art. 24   : majorité des voix exprimées (pour > contre)
 *   art. 25   : majorité des voix de tous les copropriétaires
 *   art. 25-1 : art. 25 manqué mais au moins 1/3 des voix de tous → second vote immédiat à l'art. 24
 *   art. 26   : majorité des copropriétaires représentant au moins 2/3 des voix
 *   art. 26-1 : art. 26 manqué mais la moitié des votants et au moins 1/3 des voix
 *               → second vote immédiat à l'art. 25
 *   art. 22   : un copropriétaire qui a plus de la moitié des voix est réduit à la somme des autres ;
 *               un mandataire reçoit au plus 3 délégations, sauf si le total de ses voix
 *               et des voix de ses mandants ne dépasse pas 10 % des voix ; le syndic ne peut pas être mandataire
 *   décret, art. 14-1 : le formulaire de vote par correspondance est écarté si le copropriétaire
 *               est présent ou représenté
 *   loi, art. 17-1 A : si la résolution est amendée en séance, le votant par correspondance compte comme défaillant
 *
 * Aide au calcul : seul le procès-verbal signé fait foi.
 */

export const MAJORITES = ["24", "25", "26"];
export const CHOIX = ["pour", "contre", "abstention"];
export const MAX_DELEGATIONS = 3;

/** Voix de chaque copropriétaire, réduction de l'article 22 appliquée. */
export function electorat(coproprietaires) {
  const voix = {};
  for (const c of coproprietaires) {
    const t = Number(c.tantiemes) || 0;
    if (t > 0) voix[c.id] = (voix[c.id] || 0) + t;
  }
  const total = Object.values(voix).reduce((a, b) => a + b, 0);
  for (const id of Object.keys(voix)) {
    const autres = total - voix[id];
    if (voix[id] > autres) voix[id] = autres;
  }
  return voix;
}

/** bulletins : { id: "pour" | "contre" | "abstention" } ; les absents n'y figurent pas. */
export function decompter(bulletins, voix, majorite = "24") {
  if (!MAJORITES.includes(majorite)) throw new Error(`Majorité inconnue : ${majorite}`);
  for (const [id, choix] of Object.entries(bulletins)) {
    if (!(id in voix)) throw new Error(`Votant hors électorat : ${id}`);
    if (!CHOIX.includes(choix)) throw new Error(`Choix invalide pour ${id} : ${choix}`);
  }
  const somme = (c) => Object.entries(bulletins).filter(([, ch]) => ch === c).reduce((a, [id]) => a + voix[id], 0);
  const pour = somme("pour"), contre = somme("contre"), abstention = somme("abstention");
  const total = Object.values(voix).reduce((a, b) => a + b, 0);
  const votants = Object.keys(bulletins).length;
  const nbPour = Object.values(bulletins).filter((c) => c === "pour").length;
  const nbCopro = Object.keys(voix).length;

  const r = {
    majorite, pour, contre, abstention, absents: total - pour - contre - abstention,
    total, votants, nbPour, nbCopro, adoptee: false, passerelle: null, regle: "",
  };
  if (majorite === "24") {
    r.adoptee = pour > contre;
    r.regle = `Pour (${pour}) doit dépasser Contre (${contre}). Abstentions et absents ne comptent pas.`;
  } else if (majorite === "25") {
    r.adoptee = pour * 2 > total;
    r.regle = `Pour (${pour}) doit dépasser la moitié de toutes les voix (${total} / 2).`;
    if (!r.adoptee && pour * 3 >= total) r.passerelle = "25-1";
  } else {
    r.adoptee = nbPour * 2 > nbCopro && pour * 3 >= total * 2;
    r.regle = `Il faut la majorité des copropriétaires (${nbPour} pour sur ${nbCopro}) `
      + `et les 2/3 des voix (${pour} pour sur ${total}).`;
    if (!r.adoptee && votants && nbPour * 2 >= votants && pour * 3 >= total) r.passerelle = "26-1";
  }
  return r;
}

/** Majorité du second vote ouvert par une passerelle. */
export function majoriteSecondVote(passerelle) {
  return passerelle === "25-1" ? "24" : passerelle === "26-1" ? "25" : null;
}

/**
 * Bulletins d'une résolution.
 * presences : { id: { mode: "absent"|"present"|"represente"|"correspondance", formulaire: {resId: choix} } }
 * seance    : { id: choix } saisis en séance pour les présents et représentés
 * Renvoie { bulletins, sansChoix: [ids présents ou représentés sans choix] }.
 */
export function bulletinsResolution(resolution, presences, seance, voix) {
  const bulletins = {}, sansChoix = [];
  for (const id of Object.keys(voix)) {
    const p = presences[id] || { mode: "absent" };
    if (p.mode === "present" || p.mode === "represente") {
      const c = seance?.[id];
      if (CHOIX.includes(c)) bulletins[id] = c; else sansChoix.push(id);
    } else if (p.mode === "correspondance" && !resolution.amendee) {
      const c = p.formulaire?.[resolution.id];
      if (CHOIX.includes(c)) bulletins[id] = c;
    }
  }
  return { bulletins, sansChoix };
}

/**
 * Contrôles des mandats (art. 22). mandataire : nom libre (copropriétaire présent ou tiers).
 * Renvoie une liste de messages.
 */
export function verifierMandats(coproprietaires, presences, voix, syndic = "") {
  const total = Object.values(voix).reduce((a, b) => a + b, 0);
  const nomVersId = {};
  for (const c of coproprietaires) nomVersId[norm(c.nom)] = c.id;
  const parMandataire = {};
  for (const c of coproprietaires) {
    const p = presences[c.id];
    if (p?.mode !== "represente") continue;
    const m = (p.mandataire || "").trim();
    if (!m) continue;
    (parMandataire[norm(m)] ||= { nom: m, mandants: [] }).mandants.push(c);
  }
  const messages = [];
  for (const c of coproprietaires) {
    const p = presences[c.id];
    if (p?.mode === "represente" && !(p.mandataire || "").trim()) {
      messages.push(`${c.nom} est représenté : indiquez le nom du mandataire.`);
    }
  }
  for (const { nom, mandants } of Object.values(parMandataire)) {
    if (syndic && norm(nom) === norm(syndic)) {
      messages.push(`${nom} est le syndic : il ne peut pas recevoir de mandat (loi, art. 22).`);
    }
    const idMandataire = nomVersId[norm(nom)];
    if (idMandataire && presences[idMandataire]?.mode !== "present") {
      messages.push(`${nom} reçoit des mandats mais n'est pas noté présent.`);
    }
    if (mandants.length > MAX_DELEGATIONS) {
      const cumul = (voix[idMandataire] || 0) + mandants.reduce((a, c) => a + (voix[c.id] || 0), 0);
      if (cumul * 10 > total) {
        messages.push(`${nom} reçoit ${mandants.length} mandats pour ${cumul} voix sur ${total} : `
          + `au-delà de 3 mandats, le total ne doit pas dépasser 10 % des voix (loi, art. 22).`);
      }
    }
  }
  return messages;
}

/**
 * Lit une liste collée (convocation, feuille de présence, tableur, texte d'une photo).
 * Sur chaque ligne, le DERNIER nombre est pris comme tantièmes (« 125 », « 125/1000 », « 125 tantièmes ») ;
 * le reste, débarrassé des numéros de lot ou de compte, devient le nom.
 * Un même nom sur plusieurs lignes (plusieurs lots) est regroupé et ses tantièmes additionnés.
 * Renvoie { lignes: [{nom, tantiemes, lots}], ignorees: [texte], base: dénominateur repéré ou null }.
 */
export function lireListe(texte) {
  const parNom = new Map(), ignorees = [], bases = new Set();
  for (const brute of texte.split(/\r?\n/)) {
    const ligne = brute.replace(/\u00a0/g, " ").trim();
    if (!ligne) continue;
    const nombres = [...ligne.matchAll(/(\d+(?:[.,]\d+)?)(?:\s*\/\s*(\d+))?/g)];
    const dernier = nombres[nombres.length - 1];
    if (!dernier || !/[a-zà-ÿ]/i.test(ligne)) { ignorees.push(ligne); continue; }
    const t = Number(dernier[1].replace(",", "."));
    if (!Number.isInteger(t) || t <= 0) { ignorees.push(ligne); continue; }
    if (dernier[2]) bases.add(Number(dernier[2]));
    let nom = (ligne.slice(0, dernier.index) + " " + ligne.slice(dernier.index + dernier[0].length))
      .replace(/tanti[eè]mes?|voix|millièmes?/gi, " ")
      .replace(/\blots?\s*(?:n[°o]\s*)?\d+\b/gi, " ")   // « Lot 12 »
      .replace(/^\s*\d{2,}\b/, " ")                     // numéro de compte en tête (« 00270 »)
      .replace(/[;|\t]+/g, " ")
      .replace(/\s[-–—]\s/g, " ")
      .replace(/^[\s\-–—:.,]+|[\s\-–—:.,]+$/g, "")
      .replace(/\s{2,}/g, " ")
      .trim();
    if (!nom || !/[a-zà-ÿ]/i.test(nom) || /^(sous[- ]?)?(total|totaux)\b/i.test(nom)) { ignorees.push(ligne); continue; }
    const cle = norm(nom);
    const deja = parNom.get(cle);
    if (deja) { deja.tantiemes += t; deja.lots += 1; } else parNom.set(cle, { nom, tantiemes: t, lots: 1 });
  }
  return { lignes: [...parNom.values()], ignorees, base: bases.size === 1 ? [...bases][0] : null };
}

function norm(s) {
  return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}
