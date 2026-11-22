/*
 * app.js — L'outil du président de séance : préparer, émarger, compter, faire le bilan.
 * Tout reste dans le navigateur (localStorage). Aucune donnée n'est envoyée.
 */
import {
  electorat, decompter, bulletinsResolution, verifierMandats, lireListe, majoriteSecondVote, CHOIX,
} from "./regles.js";

const CLE = "mitoyen-seance-v1";
const MODES = [["absent", "Absent"], ["present", "Présent"], ["represente", "Représenté"], ["correspondance", "Par correspondance"]];
const LIBELLE_CHOIX = { pour: "Pour", contre: "Contre", abstention: "Abstention" };

// --------------------------------------------------------------------------- état
const vide = () => ({
  v: 1, copro: "", date: new Date().toISOString().slice(0, 10), syndic: "",
  coproprietaires: [], resolutions: [], presences: {}, votes: {}, seconds: {},
  etape: "preparer", resolutionActive: null,
});
let etat = charger();

function charger() {
  try {
    const brut = localStorage.getItem(CLE);
    if (brut) return { ...vide(), ...JSON.parse(brut) };
  } catch { /* stockage indisponible : on travaille en mémoire */ }
  return vide();
}
function sauver() {
  try { localStorage.setItem(CLE, JSON.stringify(etat)); } catch { /* idem */ }
}
function maj(f, rendu = true) { f(etat); sauver(); if (rendu) afficher(); }

let compteur = Date.now();
const nouvelId = (p) => `${p}${(compteur++).toString(36)}`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nf = (n) => new Intl.NumberFormat("fr-FR").format(n);
const parId = (id) => etat.coproprietaires.find((c) => c.id === id);

// --------------------------------------------------------------------------- rendu
const vue = document.getElementById("vue");

const CLES_FOCUS = ["champ", "copro", "attr", "res", "mandataire"];

/** Réaffiche sans faire perdre au clavier le champ où l'utilisateur vient d'aller. */
function afficherApres() {
  setTimeout(() => {
    const a = document.activeElement;
    const garde = a && vue.contains(a) && a.matches("input, select, textarea")
      ? CLES_FOCUS.filter((k) => a.dataset[k] !== undefined).map((k) => `[data-${k}="${CSS.escape(a.dataset[k])}"]`).join("")
      : "";
    const curseur = garde && typeof a.selectionStart === "number" ? [a.selectionStart, a.selectionEnd] : null;
    afficher();
    if (garde) {
      const b = vue.querySelector(garde);
      if (b) { b.focus(); if (curseur) try { b.setSelectionRange(...curseur); } catch { /* champ sans curseur */ } }
    }
  }, 0);
}

function afficher() {
  document.querySelectorAll("[data-etape]").forEach((b) => {
    b.setAttribute("aria-current", b.dataset.etape === etat.etape ? "step" : "false");
  });
  const rendus = { preparer, emargement, votes, bilan };
  vue.innerHTML = rendus[etat.etape]();
}

function preparer() {
  const voix = electorat(etat.coproprietaires);
  const total = Object.values(voix).reduce((a, b) => a + b, 0);
  return `
  <section class="bloc">
    <h1>Préparer la séance</h1>
    <p class="aide">Reprenez la convocation : la liste des copropriétaires avec leurs tantièmes, puis les résolutions et leur majorité. Comptez cinq minutes.</p>
    <div class="grille-3">
      <label class="champ">Copropriété<input data-champ="copro" value="${esc(etat.copro)}" placeholder="Résidence, adresse"></label>
      <label class="champ">Date de l’AG<input type="date" data-champ="date" value="${esc(etat.date)}"></label>
      <label class="champ">Nom du syndic<input data-champ="syndic" value="${esc(etat.syndic)}" placeholder="Il ne peut pas recevoir de pouvoir"></label>
    </div>
  </section>

  <section class="bloc">
    <div class="titre-ligne">
      <h2>Copropriétaires</h2>
      <p class="chiffre-secondaire">${etat.coproprietaires.length} copropriétaires, ${nf(total)} voix</p>
    </div>
    <label class="champ">Coller une liste, une ligne par copropriétaire : nom puis tantièmes
      <textarea id="liste" rows="4" placeholder="Mme Dupont ; 125&#10;M. Martin ; 80">${esc(etat.apercu?.texte || "")}</textarea>
    </label>
    <details class="astuce">
      <summary>Comment récupérer la liste sans tout taper</summary>
      <ul>
        <li><strong>Photo de la feuille de présence</strong> ou de la répartition des charges : sur iPhone, touchez le texte de la photo (Texte en direct) ; sur Android, utilisez Google Lens. Copiez, puis collez ici.</li>
        <li><strong>PDF ou tableur</strong> du syndic : sélectionnez les lignes et collez-les telles quelles.</li>
        <li><strong>Copie de l’an dernier</strong> : « Reprendre une liste enregistrée » ci-dessous, puis corrigez les ventes de l’année.</li>
      </ul>
      <p>Sur chaque ligne, le dernier nombre est pris comme tantièmes ; les numéros de lot sont ignorés et un copropriétaire présent sur plusieurs lignes est regroupé. Vous vérifiez la liste avant de l’ajouter.</p>
    </details>
    <div class="actions">
      <button type="button" class="btn" data-action="importer-liste">Lire la liste</button>
      <label class="btn-secondaire fichier">Reprendre une liste enregistrée<input type="file" accept="application/json" data-action="reprendre-liste"></label>
    </div>
    ${apercu()}
    ${etat.coproprietaires.length ? `
    <table class="tableau">
      <thead><tr><th scope="col">Nom</th><th scope="col" class="nb">Tantièmes</th><th scope="col" class="nb">Voix retenues</th><th scope="col"><span class="sr">Retirer</span></th></tr></thead>
      <tbody>${etat.coproprietaires.map((c) => `
        <tr>
          <td><input aria-label="Nom" data-copro="${c.id}" data-attr="nom" value="${esc(c.nom)}"></td>
          <td class="nb"><input aria-label="Tantièmes de ${esc(c.nom)}" inputmode="numeric" class="court" data-copro="${c.id}" data-attr="tantiemes" value="${esc(c.tantiemes)}"></td>
          <td class="nb">${voix[c.id] !== undefined && voix[c.id] !== Number(c.tantiemes) ? `${nf(voix[c.id])} <span class="note">réduites (art. 22)</span>` : nf(voix[c.id] ?? 0)}</td>
          <td><button type="button" class="btn-lien" data-action="retirer-copro" data-id="${c.id}">Retirer</button></td>
        </tr>`).join("")}
      </tbody>
    </table>` : ""}
    <div class="actions"><button type="button" class="btn-secondaire" data-action="ajouter-copro">Ajouter une ligne</button></div>
  </section>

  <section class="bloc">
    <h2>Résolutions</h2>
    <p class="aide">La majorité est indiquée sur la convocation, à côté de chaque résolution.</p>
    ${etat.resolutions.length ? `<ol class="resolutions">${etat.resolutions.map((r, i) => `
      <li>
        <span class="num-res">${i + 1}</span>
        <input aria-label="Intitulé de la résolution ${i + 1}" data-res="${r.id}" data-attr="titre" value="${esc(r.titre)}" placeholder="Intitulé">
        <label class="sr" for="maj-${r.id}">Majorité</label>
        <select id="maj-${r.id}" data-res="${r.id}" data-attr="majorite">
          ${["24", "25", "26"].map((m) => `<option value="${m}" ${r.majorite === m ? "selected" : ""}>Article ${m}</option>`).join("")}
        </select>
        <button type="button" class="btn-lien" data-action="retirer-res" data-id="${r.id}">Retirer</button>
      </li>`).join("")}</ol>` : ""}
    <div class="actions"><button type="button" class="btn-secondaire" data-action="ajouter-res">Ajouter une résolution</button></div>
  </section>

  <div class="suite">
    <button type="button" class="btn" data-etape-vers="emargement" ${etat.coproprietaires.length && etat.resolutions.length ? "" : "disabled"}>Passer à l’émargement</button>
    ${etat.coproprietaires.length && etat.resolutions.length ? "" : `<p class="aide">Ajoutez au moins un copropriétaire et une résolution.</p>`}
  </div>`;
}

function apercu() {
  const a = etat.apercu;
  if (!a) return "";
  const total = a.lignes.reduce((x, l) => x + l.tantiemes, 0);
  const ecart = a.base && total !== a.base;
  return `
    <div class="apercu" role="region" aria-label="Liste lue, à vérifier">
      <div class="titre-ligne"><h3>Liste lue : ${a.lignes.length} copropriétaire${a.lignes.length > 1 ? "s" : ""}</h3>
        <p class="chiffre-secondaire">Total : ${nf(total)} tantièmes${a.base ? ` sur ${nf(a.base)}` : ""}</p></div>
      ${ecart ? `<p class="alerte-ligne">Le total ne fait pas ${nf(a.base)} : une ligne manque ou a été mal lue.</p>` : ""}
      ${a.lignes.length ? `<table class="tableau"><tbody>${a.lignes.map((l, i) => `
        <tr><td>${esc(l.nom)}${l.lots > 1 ? ` <span class="note">${l.lots} lignes regroupées</span>` : ""}</td>
        <td class="nb">${nf(l.tantiemes)}</td>
        <td><button type="button" class="btn-lien" data-action="retirer-apercu" data-i="${i}">Retirer</button></td></tr>`).join("")}
      </tbody></table>` : ""}
      ${a.ignorees.length ? `<details class="corresp"><summary>Lignes ignorées (${a.ignorees.length})</summary><ul>${a.ignorees.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}
      <div class="actions">
        <button type="button" class="btn" data-action="valider-apercu" ${a.lignes.length ? "" : "disabled"}>Ajouter ces ${a.lignes.length} copropriétaires</button>
        <button type="button" class="btn-secondaire" data-action="annuler-apercu">Annuler</button>
      </div>
    </div>`;
}

function emargement() {
  const voix = electorat(etat.coproprietaires);
  const total = Object.values(voix).reduce((a, b) => a + b, 0);
  const compte = { present: [0, 0], represente: [0, 0], correspondance: [0, 0], absent: [0, 0] };
  for (const c of etat.coproprietaires) {
    const m = etat.presences[c.id]?.mode || "absent";
    compte[m][0] += 1; compte[m][1] += voix[c.id] || 0;
  }
  const alertes = verifierMandats(etat.coproprietaires, etat.presences, voix, etat.syndic);
  const noms = etat.coproprietaires.map((c) => `<option value="${esc(c.nom)}">`).join("");
  return `
  <section class="bloc">
    <h1>Émargement</h1>
    <p class="aide">Pour chaque copropriétaire : présent, représenté (avec le nom du mandataire), par correspondance ou absent. Un formulaire de vote par correspondance est écarté si son auteur est présent ou représenté (décret, art. 14-1).</p>
    <div class="compteurs">
      ${[["present", "Présents"], ["represente", "Représentés"], ["correspondance", "Par correspondance"], ["absent", "Absents"]].map(([k, l]) => `
        <div class="compteur"><p class="compteur-l">${l}</p><p class="compteur-v">${compte[k][0]}</p><p class="compteur-s">${nf(compte[k][1])} voix sur ${nf(total)}</p></div>`).join("")}
    </div>
    ${alertes.length ? `<div class="alerte" role="status"><p><strong>À vérifier</strong></p><ul>${alertes.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></div>` : ""}
  </section>
  <datalist id="noms">${noms}</datalist>
  <section class="bloc liste-emargement">
    ${etat.coproprietaires.map((c) => {
      const p = etat.presences[c.id] || { mode: "absent" };
      return `
      <div class="ligne-emarg">
        <div class="qui"><p class="nom">${esc(c.nom)}</p><p class="voix">${nf(voix[c.id] || 0)} voix</p></div>
        <div class="segments modes" role="group" aria-label="Présence de ${esc(c.nom)}">
          ${MODES.map(([m, l]) => `<button type="button" aria-pressed="${p.mode === m}" data-action="mode" data-id="${c.id}" data-mode="${m}">${l}</button>`).join("")}
        </div>
        ${p.mode === "represente" ? `<label class="champ mandataire">Mandataire<input list="noms" data-mandataire="${c.id}" value="${esc(p.mandataire || "")}" placeholder="Nom de la personne qui le représente"></label>` : ""}
        ${p.mode === "correspondance" ? `
          <div class="formulaire">
            <p class="aide">Votes du formulaire reçu</p>
            ${etat.resolutions.map((r, i) => `
              <div class="ligne-choix"><span>${i + 1}. ${esc(r.titre || "Résolution")}</span>
                <div class="segments petits" role="group" aria-label="Formulaire de ${esc(c.nom)}, résolution ${i + 1}">
                  ${CHOIX.map((ch) => `<button type="button" aria-pressed="${p.formulaire?.[r.id] === ch}" data-action="formulaire" data-id="${c.id}" data-res="${r.id}" data-choix="${ch}">${LIBELLE_CHOIX[ch]}</button>`).join("")}
                </div></div>`).join("")}
          </div>` : ""}
      </div>`;
    }).join("")}
  </section>
  <div class="suite"><button type="button" class="btn" data-etape-vers="votes">Passer aux votes</button></div>`;
}

function resultat(r) {
  const voix = electorat(etat.coproprietaires);
  const { bulletins, sansChoix } = bulletinsResolution(r, etat.presences, etat.votes[r.id], voix);
  const d = decompter(bulletins, voix, r.majorite);
  let second = null;
  if (!d.adoptee && d.passerelle && etat.seconds[r.id]) {
    const b2 = bulletinsResolution(r, etat.presences, etat.seconds[r.id].votes, voix);
    second = { ...decompter(b2.bulletins, voix, majoriteSecondVote(d.passerelle)), sansChoix: b2.sansChoix };
  }
  return { d, second, bulletins, sansChoix, voix };
}

function grilleVotes(r, cleVotes, titre) {
  const voix = electorat(etat.coproprietaires);
  const saisis = cleVotes === "seconds" ? etat.seconds[r.id]?.votes || {} : etat.votes[r.id] || {};
  const votants = etat.coproprietaires.filter((c) => ["present", "represente"].includes(etat.presences[c.id]?.mode));
  const corresp = etat.coproprietaires.filter((c) => etat.presences[c.id]?.mode === "correspondance");
  return `
    <div class="grille-votes">
      <div class="titre-ligne"><h3>${titre}</h3>
        <button type="button" class="btn-secondaire" data-action="reste-pour" data-res="${r.id}" data-cle="${cleVotes}">Les autres votent pour</button></div>
      <p class="aide">Demandez qui vote contre, puis qui s’abstient : marquez-les, puis « Les autres votent pour ».</p>
      ${votants.length ? votants.map((c) => {
        const p = etat.presences[c.id];
        return `<div class="ligne-choix">
          <span><span class="nom">${esc(c.nom)}</span> <span class="voix">${nf(voix[c.id] || 0)} voix${p.mode === "represente" ? `, représenté par ${esc(p.mandataire || "?")}` : ""}</span></span>
          <div class="segments" role="group" aria-label="Vote de ${esc(c.nom)}">
            ${CHOIX.map((ch) => `<button type="button" aria-pressed="${saisis[c.id] === ch}" data-action="vote" data-cle="${cleVotes}" data-res="${r.id}" data-id="${c.id}" data-choix="${ch}">${LIBELLE_CHOIX[ch]}</button>`).join("")}
          </div></div>`;
      }).join("") : `<p class="aide">Personne n’est noté présent ou représenté : revenez à l’émargement.</p>`}
      ${corresp.length ? `<details class="corresp"><summary>Votes par correspondance (${corresp.length})</summary>
        ${r.amendee ? `<p class="aide">Résolution amendée en séance : ces votants comptent comme défaillants.</p>` : `<ul>${corresp.map((c) => `<li>${esc(c.nom)} : ${LIBELLE_CHOIX[etat.presences[c.id].formulaire?.[r.id]] || "pas de choix sur le formulaire"}</li>`).join("")}</ul>`}
      </details>` : ""}
    </div>`;
}

function panneauResultat(d, sansChoix, intitule) {
  return `
    <div class="resultat ${d.adoptee ? "adoptee" : "rejetee"}" aria-live="polite">
      <p class="resultat-l">${intitule}</p>
      <p class="decision">${d.adoptee ? "Adoptée" : "Rejetée"}</p>
      <dl class="chiffres">
        <div><dt>Pour</dt><dd>${nf(d.pour)}</dd></div>
        <div><dt>Contre</dt><dd>${nf(d.contre)}</dd></div>
        <div><dt>Abstention</dt><dd>${nf(d.abstention)}</dd></div>
        <div><dt>Absents ou défaillants</dt><dd>${nf(d.absents)}</dd></div>
      </dl>
      <p class="regle">${esc(d.regle)}</p>
      ${sansChoix.length ? `<p class="alerte-ligne">${sansChoix.length} votant${sansChoix.length > 1 ? "s" : ""} sans choix : non compté${sansChoix.length > 1 ? "s" : ""} tant que rien n’est saisi.</p>` : ""}
    </div>`;
}

function votes() {
  if (!etat.resolutions.length) return `<section class="bloc"><h1>Votes</h1><p class="aide">Ajoutez d’abord les résolutions à l’étape 1.</p></section>`;
  const r = etat.resolutions.find((x) => x.id === etat.resolutionActive) || etat.resolutions[0];
  const i = etat.resolutions.indexOf(r);
  const { d, second, sansChoix } = resultat(r);
  return `
  <div class="votes-cadre">
    <nav class="liste-res" aria-label="Résolutions">
      ${etat.resolutions.map((x, j) => {
        const { d: dx, second: sx } = resultat(x);
        const ok = sx ? sx.adoptee : dx.adoptee;
        const touche = Object.keys(etat.votes[x.id] || {}).length;
        return `<button type="button" data-action="choisir-res" data-res="${x.id}" aria-current="${x.id === r.id}">
          <span class="num-res">${j + 1}</span><span class="t">${esc(x.titre || "Résolution")}</span>
          <span class="etat">${touche ? (ok ? "Adoptée" : "Rejetée") : "À voter"}</span></button>`;
      }).join("")}
    </nav>
    <section class="bloc">
      <p class="sur-titre">Résolution ${i + 1} sur ${etat.resolutions.length}, article ${r.majorite}</p>
      <h1>${esc(r.titre || "Résolution")}</h1>
      <label class="case"><input type="checkbox" data-action="amendee" data-res="${r.id}" ${r.amendee ? "checked" : ""}> Résolution amendée en séance</label>
      <div class="deux-colonnes">
        ${grilleVotes(r, "votes", "Vote")}
        <div>
          ${panneauResultat(d, sansChoix, `Article ${r.majorite}`)}
          ${!d.adoptee && d.passerelle ? `
            <div class="passerelle">
              <p><strong>Passerelle de l’article ${d.passerelle}</strong> : la résolution n’atteint pas la majorité de l’article ${r.majorite}, mais l’assemblée peut procéder immédiatement à un second vote à la majorité de l’article ${majoriteSecondVote(d.passerelle)}.</p>
              ${etat.seconds[r.id] ? "" : `<button type="button" class="btn" data-action="second-vote" data-res="${r.id}">Ouvrir le second vote</button>`}
            </div>` : ""}
          ${second ? panneauResultat(second, second.sansChoix, `Second vote, article ${second.majorite}`) : ""}
        </div>
      </div>
      ${second ? grilleVotes(r, "seconds", `Second vote, article ${second.majorite}`) : ""}
      <div class="suite">
        ${i > 0 ? `<button type="button" class="btn-secondaire" data-action="choisir-res" data-res="${etat.resolutions[i - 1].id}">Résolution précédente</button>` : ""}
        ${i < etat.resolutions.length - 1
          ? `<button type="button" class="btn" data-action="choisir-res" data-res="${etat.resolutions[i + 1].id}">Résolution suivante</button>`
          : `<button type="button" class="btn" data-etape-vers="bilan">Voir le bilan</button>`}
      </div>
    </section>
  </div>`;
}

function bilan() {
  const lignes = etat.resolutions.map((r, i) => {
    const { d, second, bulletins } = resultat(r);
    const final = second || d;
    const b = second ? bulletinsResolution(r, etat.presences, etat.seconds[r.id].votes, electorat(etat.coproprietaires)).bulletins : bulletins;
    const v = electorat(etat.coproprietaires);
    const nomsDe = (ch) => Object.entries(b).filter(([, c]) => c === ch)
      .map(([id]) => parId(id) && `${parId(id).nom} (${nf(v[id])} voix)`).filter(Boolean);
    return { r, i, d, second, final, contre: nomsDe("contre"), abst: nomsDe("abstention") };
  });
  const voix = electorat(etat.coproprietaires);
  const total = Object.values(voix).reduce((a, b) => a + b, 0);
  const presents = etat.coproprietaires.filter((c) => ["present", "represente", "correspondance"].includes(etat.presences[c.id]?.mode));
  return `
  <section class="bloc">
    <h1>Bilan de la séance</h1>
    <p class="aide">${esc(etat.copro || "Copropriété")}, assemblée du ${etat.date ? new Date(etat.date + "T12:00").toLocaleDateString("fr-FR", { dateStyle: "long" }) : "?"}. ${presents.length} copropriétaires présents, représentés ou ayant voté par correspondance, pour ${nf(presents.reduce((a, c) => a + (voix[c.id] || 0), 0))} voix sur ${nf(total)}.</p>
    <div class="actions">
      <button type="button" class="btn" data-action="imprimer">Imprimer le bilan</button>
      <button type="button" class="btn-secondaire" data-action="exporter">Enregistrer une copie (fichier)</button>
      <label class="btn-secondaire fichier">Reprendre une copie<input type="file" accept="application/json" data-action="importer"></label>
    </div>
  </section>
  <section class="bloc">
    <table class="tableau bilan">
      <thead><tr><th scope="col">Résolution</th><th scope="col">Majorité</th><th scope="col" class="nb">Pour</th><th scope="col" class="nb">Contre</th><th scope="col" class="nb">Abst.</th><th scope="col">Résultat</th></tr></thead>
      <tbody>${lignes.map(({ r, i, d, second, final, contre, abst }) => `
        <tr>
          <th scope="row">${i + 1}. ${esc(r.titre || "Résolution")}${r.amendee ? ` <span class="note">amendée</span>` : ""}
            ${contre.length ? `<p class="noms">Contre : ${esc(contre.join(", "))}</p>` : ""}
            ${abst.length ? `<p class="noms">Abstention : ${esc(abst.join(", "))}</p>` : ""}</th>
          <td>Art. ${r.majorite}${second ? `, puis art. ${second.majorite} (passerelle ${d.passerelle})` : ""}</td>
          <td class="nb">${nf(final.pour)}</td><td class="nb">${nf(final.contre)}</td><td class="nb">${nf(final.abstention)}</td>
          <td><span class="pastille ${final.adoptee ? "oui" : "non"}">${final.adoptee ? "Adoptée" : "Rejetée"}</span></td>
        </tr>`).join("")}
      </tbody>
    </table>
  </section>
  <section class="bloc">
    <h2>À comparer avec le procès-verbal du syndic</h2>
    <ul class="coche">
      <li>Pour chaque résolution, le résultat et la majorité appliquée sont les mêmes.</li>
      <li>Le procès-verbal nomme les copropriétaires qui ont voté contre ou se sont abstenus, avec leurs voix (décret, art. 17).</li>
      <li>Les votes par correspondance et les pouvoirs correspondent à la feuille de présence.</li>
      <li>Les seconds votes (passerelles des articles 25-1 et 26-1) figurent bien au procès-verbal.</li>
    </ul>
    <p class="aide">Le procès-verbal est signé à la fin de la séance par le président, le ou les scrutateurs et le secrétaire. En cas d’écart, signalez-le avant de signer.</p>
  </section>
  <section class="bloc non-imprime">
    <h2>Nouvelle séance</h2>
    <p class="aide">Efface tout ce qui est enregistré sur cet appareil. Pensez à enregistrer une copie avant.</p>
    <button type="button" class="btn-danger" data-action="effacer">${effacementDemande ? "Confirmer : tout effacer" : "Tout effacer"}</button>
  </section>`;
}

// --------------------------------------------------------------------------- événements
let effacementDemande = false;

document.addEventListener("click", (e) => {
  const etape = e.target.closest("[data-etape], [data-etape-vers]");
  if (etape) {
    maj((s) => { s.etape = etape.dataset.etape || etape.dataset.etapeVers; });
    vue.focus(); window.scrollTo(0, 0);
    return;
  }
  const el = e.target.closest("[data-action]");
  if (!el || el.tagName === "INPUT") return;
  const { action, id, res, choix, mode, cle } = el.dataset;
  switch (action) {
    case "importer-liste": {
      const zone = document.getElementById("liste");
      const { lignes, ignorees, base } = lireListe(zone.value);
      maj((s) => { s.apercu = { lignes, ignorees, base, texte: zone.value }; });
      break;
    }
    case "valider-apercu": maj((s) => {
      for (const l of s.apercu.lignes) s.coproprietaires.push({ id: nouvelId("c"), nom: l.nom, tantiemes: l.tantiemes });
      s.apercu = null;
    }); break;
    case "annuler-apercu": maj((s) => { s.apercu = null; }); break;
    case "retirer-apercu": maj((s) => { s.apercu.lignes.splice(Number(el.dataset.i), 1); }); break;
    case "ajouter-copro": maj((s) => s.coproprietaires.push({ id: nouvelId("c"), nom: "", tantiemes: "" })); break;
    case "retirer-copro": maj((s) => { s.coproprietaires = s.coproprietaires.filter((c) => c.id !== id); delete s.presences[id]; }); break;
    case "ajouter-res": maj((s) => s.resolutions.push({ id: nouvelId("r"), titre: "", majorite: "24", amendee: false })); break;
    case "retirer-res": maj((s) => { s.resolutions = s.resolutions.filter((r) => r.id !== id); delete s.votes[id]; delete s.seconds[id]; }); break;
    case "mode": maj((s) => { s.presences[id] = { ...(s.presences[id] || {}), mode }; }); break;
    case "formulaire": maj((s) => {
      const p = s.presences[id]; p.formulaire = { ...(p.formulaire || {}) };
      p.formulaire[res] = p.formulaire[res] === choix ? undefined : choix;
    }); break;
    case "vote": maj((s) => {
      const cible = cle === "seconds" ? (s.seconds[res].votes ||= {}) : (s.votes[res] ||= {});
      cible[id] = cible[id] === choix ? undefined : choix;
    }); break;
    case "reste-pour": maj((s) => {
      const cible = cle === "seconds" ? (s.seconds[res].votes ||= {}) : (s.votes[res] ||= {});
      for (const c of s.coproprietaires) {
        if (["present", "represente"].includes(s.presences[c.id]?.mode) && !CHOIX.includes(cible[c.id])) cible[c.id] = "pour";
      }
    }); break;
    case "second-vote": maj((s) => { s.seconds[res] = { votes: {} }; }); break;
    case "choisir-res": maj((s) => { s.resolutionActive = res; }); window.scrollTo(0, 0); break;
    case "imprimer": window.print(); break;
    case "exporter": exporter(); break;
    case "effacer":
      if (!effacementDemande) { effacementDemande = true; afficher(); break; }
      effacementDemande = false; etat = vide(); sauver(); afficher(); break;
    default: break;
  }
});

document.addEventListener("input", (e) => {
  const t = e.target;
  if (t.dataset.champ) maj((s) => { s[t.dataset.champ] = t.value; }, false);
  else if (t.dataset.copro) maj((s) => { const c = s.coproprietaires.find((x) => x.id === t.dataset.copro); if (c) c[t.dataset.attr] = t.dataset.attr === "tantiemes" ? t.value.replace(/\D/g, "") : t.value; }, false);
  else if (t.dataset.res && t.dataset.attr === "titre") maj((s) => { const r = s.resolutions.find((x) => x.id === t.dataset.res); if (r) r.titre = t.value; }, false);
  else if (t.dataset.mandataire) maj((s) => { s.presences[t.dataset.mandataire].mandataire = t.value; }, false);
});

document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.copro && t.dataset.attr === "tantiemes") afficherApres();
  else if (t.dataset.res && t.dataset.attr === "majorite") maj((s) => { s.resolutions.find((x) => x.id === t.dataset.res).majorite = t.value; });
  else if (t.dataset.action === "amendee") maj((s) => { s.resolutions.find((x) => x.id === t.dataset.res).amendee = t.checked; });
  else if (t.dataset.mandataire) afficherApres();
  else if (t.dataset.action === "importer" && t.files?.[0]) importer(t.files[0]);
  else if (t.dataset.action === "reprendre-liste" && t.files?.[0]) reprendreListe(t.files[0]);
});

function exporter() {
  const blob = new Blob([JSON.stringify(etat, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `seance-${(etat.copro || "ag").toLowerCase().replace(/[^a-z0-9]+/gi, "-")}-${etat.date || "date"}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

async function importer(fichier) {
  try {
    const donnees = JSON.parse(await fichier.text());
    if (donnees?.v !== 1 || !Array.isArray(donnees.coproprietaires)) throw new Error();
    etat = { ...vide(), ...donnees, etape: "bilan" }; sauver(); afficher();
  } catch {
    alertePassagere("Ce fichier n’est pas une copie de séance Mitoyen.");
  }
}

async function reprendreListe(fichier) {
  try {
    const d = JSON.parse(await fichier.text());
    if (d?.v !== 1 || !Array.isArray(d.coproprietaires)) throw new Error();
    maj((s) => {
      s.coproprietaires = d.coproprietaires.map((c) => ({ id: c.id, nom: c.nom, tantiemes: c.tantiemes }));
      s.resolutions = (d.resolutions || []).map((r) => ({ ...r, amendee: false }));
      s.presences = {}; s.votes = {}; s.seconds = {}; s.apercu = null;
      if (!s.copro) s.copro = d.copro || "";
      if (!s.syndic) s.syndic = d.syndic || "";
    });
    alertePassagere(`Liste reprise : ${d.coproprietaires.length} copropriétaire${d.coproprietaires.length > 1 ? "s" : ""} et ${(d.resolutions || []).length} résolution${(d.resolutions || []).length > 1 ? "s" : ""}. Vérifiez les ventes de l’année et adaptez les résolutions.`, "status");
  } catch {
    alertePassagere("Ce fichier n’est pas une copie de séance Mitoyen.");
  }
}

function alertePassagere(texte, role = "alert") {
  const p = document.createElement("p");
  p.className = "alerte"; p.setAttribute("role", role); p.textContent = texte;
  vue.prepend(p); setTimeout(() => p.remove(), 6000);
}

if ("serviceWorker" in navigator && location.protocol === "https:") {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}

afficher();
