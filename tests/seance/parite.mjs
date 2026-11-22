// Lit des cas JSON sur l'entrée standard et renvoie les résultats de regles.js (utilisé par test_seance_parite.py).
import { electorat, decompter, lireListe } from "../../seance/regles.js";
let entree = "";
for await (const morceau of process.stdin) entree += morceau;
const cas = JSON.parse(entree);
const sortie = cas.map(({ coproprietaires, bulletins, majorite }) => {
  const voix = electorat(coproprietaires);
  const r = decompter(bulletins, voix, majorite);
  return { voix, adoptee: r.adoptee, passerelle: r.passerelle, pour: r.pour, contre: r.contre, abstention: r.abstention };
});
process.stdout.write(JSON.stringify({ sortie, liste: lireListe("Nom Tantièmes\nMme Dupont ; 125\nM. Martin\t80\nSCI Les Pins 45 tantièmes\nLot 12 – GARNIER Paul – 150/1000\n00270 M. ROUQUIER 50\nLot 13 – GARNIER Paul – 20\nTotal 470\nM. Zéro ; 0") }));
