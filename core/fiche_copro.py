"""
fiche_copro.py — Charge, valide et exploite une fiche de configuration de copropriété.

Usage :
    python core/fiche_copro.py config/mimosas.yaml
    python core/fiche_copro.py config/mimosas.yaml --date 2027-02-15

Ce que fait le script :
    1. Charge la fiche YAML
    2. Vérifie sa cohérence (tantièmes, références, règles légales simples)
    3. Liste les alertes de l'échéancier (contrats à dénoncer, diagnostics manquants)
    4. Calcule l'appel de fonds trimestriel par copropriétaire, au centime près

Rappel : l'agent PRÉPARE, le syndic VALIDE. Rien n'est envoyé par ce script.
"""

from __future__ import annotations

import argparse
import calendar
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import yaml

CENT = Decimal("0.01")
TAUX_MIN_FONDS_TRAVAUX = Decimal("0.05")   # 5 % du budget prévisionnel
DUREE_MAX_MANDAT_ANS = 3
HORIZON_ALERTES_JOURS = 120


# --------------------------------------------------------------------------- #
# Chargement
# --------------------------------------------------------------------------- #
def actuels(fiche: dict) -> list[dict]:
    """Les copropriétaires actuels : les anciens (lots vendus) restent dans la fiche pour leurs
    comptes, mais ne reçoivent plus les envois de la copropriété."""
    return [c for c in fiche["coproprietaires"] if not c.get("ancien")]


def charger_fiche(chemin: str | Path) -> dict:
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------- #
# Validation : chaque contrôle ajoute une erreur lisible par un humain
# --------------------------------------------------------------------------- #
@dataclass
class Rapport:
    erreurs: list[str] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erreurs


def valider(fiche: dict) -> Rapport:
    r = Rapport()
    cles = fiche["cles_repartition"]
    lots = fiche["lots"]
    copros = {c["id"]: c for c in fiche["coproprietaires"]}
    contrats = {c["id"] for c in fiche.get("contrats", [])}

    # 1. Nombre de lots déclaré = nombre de lots décrits
    ident = fiche["copropriete"]
    if ident["nb_lots_total"] != len(lots):
        r.erreurs.append(f"nb_lots_total = {ident['nb_lots_total']} mais {len(lots)} lots décrits")
    nb_apparts = sum(1 for l in lots if l["type"] == "appartement")
    if ident["nb_lots_principaux"] != nb_apparts:
        r.erreurs.append(f"nb_lots_principaux = {ident['nb_lots_principaux']} mais {nb_apparts} appartements")

    # 2. Tantièmes : chaque lot a chaque clé, et chaque clé somme à sa base
    for cle, info in cles.items():
        manquants = [l["numero"] for l in lots if cle not in l["tantiemes"]]
        if manquants:
            r.erreurs.append(f"Clé '{cle}' absente des lots {manquants}")
        total = sum(l["tantiemes"].get(cle, 0) for l in lots)
        if total != info["base"]:
            r.erreurs.append(f"Clé '{cle}' : somme des tantièmes = {total}, base attendue = {info['base']}")

    # 3. Références croisées
    for l in lots:
        if l["proprietaire"] not in copros:
            r.erreurs.append(f"Lot {l['numero']} : propriétaire inconnu {l['proprietaire']}")
    proprietaires_avec_lot = {l["proprietaire"] for l in lots}
    for cid, c in copros.items():
        if cid not in proprietaires_avec_lot and not c.get("ancien"):
            r.erreurs.append(f"Copropriétaire {cid} ne possède aucun lot")
        if cid in proprietaires_avec_lot and c.get("ancien"):
            r.erreurs.append(f"Copropriétaire {cid} marqué ancien alors qu'il possède encore un lot")
    for c in copros.values():
        if c["envoi"] == "email" and not c.get("email") and not c.get("ancien"):
            r.erreurs.append(f"{c['id']} : envoi par email demandé mais aucune adresse")
    for e in fiche.get("equipements", []):
        if e["cle"] not in cles:
            r.erreurs.append(f"Équipement '{e['id']}' : clé inconnue {e['cle']}")
        if e.get("contrat") and e["contrat"] not in contrats:
            r.erreurs.append(f"Équipement '{e['id']}' : contrat inconnu {e['contrat']}")
    for p in fiche["budget_previsionnel"]["postes"]:
        if p["cle"] not in cles:
            r.erreurs.append(f"Poste '{p['libelle']}' : clé inconnue {p['cle']}")

    # 4. Gouvernance
    gouv = fiche["gouvernance"]
    if gouv["syndic"]["coproprietaire_id"] not in copros:
        r.erreurs.append("Le syndic désigné n'est pas un copropriétaire")
    debut, fin = gouv["syndic"]["debut_mandat"], gouv["syndic"]["fin_mandat"]
    if (fin - debut).days > DUREE_MAX_MANDAT_ANS * 366:
        r.erreurs.append(f"Mandat du syndic supérieur à {DUREE_MAX_MANDAT_ANS} ans")
    for cid in gouv.get("conseil_syndical", []):
        if cid not in copros:
            r.erreurs.append(f"Membre du conseil syndical inconnu : {cid}")

    # 5. Fonds de travaux >= 5 % du budget prévisionnel
    budget = total_budget(fiche)
    cotisation = Decimal(str(fiche["fonds_travaux"]["cotisation_annuelle"]))
    minimum = (budget * TAUX_MIN_FONDS_TRAVAUX).quantize(CENT)
    if cotisation < minimum:
        r.erreurs.append(f"Fonds de travaux : {cotisation} € < minimum légal {minimum} € (5 % de {budget} €)")

    # 5 ter. Accessibilité et papier : courrier, grands caractères, aidant, paiement
    import papier
    err_p, alertes_p = papier.valider_papier(fiche)
    r.erreurs += err_p
    r.alertes += alertes_p

    # 5 bis. Plan pluriannuel de travaux : cohérence, et 2,5 % des travaux une fois adopté
    import plan_travaux
    erreurs_plan = plan_travaux.valider_plan(fiche)
    r.erreurs += erreurs_plan
    if not erreurs_plan and plan_travaux.plan_de(fiche):
        cmin = plan_travaux.cotisation_minimale(fiche)
        if cmin["plan_adopte"] and cotisation < cmin["minimum_plan"]:
            r.erreurs.append(f"Fonds de travaux : {cotisation} € < minimum légal {cmin['minimum_plan']} € "
                             f"(2,5 % des {cmin['montant_plan']} € de travaux du plan adopté)")
        elif not cmin["plan_adopte"] and not cmin["conforme_si_adopte"]:
            r.alertes.append(f"Si le plan de travaux est adopté, la cotisation au fonds de travaux devra "
                             f"passer à au moins {cmin['minimum_si_adopte']} € par an")

    # 6. Seuils de décision (facultatifs, mais cohérents s'ils sont présents)
    seuils = fiche.get("seuils") or {}
    for nom in ("consultation_conseil_syndical", "mise_en_concurrence"):
        v = seuils.get(nom)
        if v is not None and (not isinstance(v, (int, float)) or v < 0):
            r.erreurs.append(f"Seuil « {nom} » invalide : {v!r} (montant positif attendu)")
    deleg = seuils.get("delegation_conseil_syndical") or {}
    if deleg.get("active"):
        if len(gouv.get("conseil_syndical", [])) < 3:
            r.erreurs.append("Délégation au conseil syndical : il faut au moins 3 membres")
        if not deleg.get("plafond_par_depense"):
            r.erreurs.append("Délégation au conseil syndical : le plafond par dépense voté en AG est obligatoire")

    return r


# --------------------------------------------------------------------------- #
# Échéancier : ce que l'agent signalera au syndic
# --------------------------------------------------------------------------- #
SEUIL_URGENT_JOURS = 30
DELAI_CONVOCATION_AG_JOURS = 21   # convocation au moins 21 jours avant l'AG (décret de 1967, art. 9)


def ajouter_mois(d: date, n: int) -> date:
    """Ajoute (ou retire si n < 0) n mois à une date, en gardant le jour quand il existe :
    31/03 - 1 mois = 28/02 (ou 29/02)."""
    total = d.year * 12 + (d.month - 1) + n
    annee, mois = divmod(total, 12)
    mois += 1
    return date(annee, mois, min(d.day, calendar.monthrange(annee, mois)[1]))


def _niveau(jours: int | None) -> str:
    if jours is None:
        return "a_prevoir"
    if jours < 0:
        return "depasse"
    return "urgent" if jours <= SEUIL_URGENT_JOURS else "a_prevoir"


def _alerte(type_: str, titre: str, message: str, echeance: date | None, aujourd_hui: date,
            niveau: str | None = None) -> dict:
    jours = (echeance - aujourd_hui).days if echeance else None
    return {"type": type_, "titre": titre, "message": message,
            "date": echeance.isoformat() if echeance else None,
            "date_fr": f"{echeance:%d/%m/%Y}" if echeance else None,
            "jours": jours, "niveau": niveau or _niveau(jours)}


def echeances(fiche: dict, aujourd_hui: date, horizon: int = HORIZON_ALERTES_JOURS,
              suivi_plan: dict | None = None) -> list[dict]:
    """Toutes les échéances à signaler au syndic, de la plus proche à la plus lointaine.
    niveau : urgent (≤ 30 j) | a_prevoir | depasse | info
    suivi_plan : suivi du plan de travaux (data/), pour ne pas signaler une ligne déjà engagée."""
    res: list[dict] = []

    # 1. Contrats : date limite pour résilier avant la reconduction
    for c in fiche.get("contrats", []):
        ech: date = c["echeance"]
        if not c.get("tacite_reconduction"):
            # Pas de reconduction : le contrat s'arrête seul, il faut le renouveler à temps
            if 0 <= (ech - aujourd_hui).days <= horizon:
                res.append(_alerte("contrat", c["objet"],
                                   f"Se termine le {ech:%d/%m/%Y} sans reconduction : "
                                   f"renouveler ou choisir un nouveau prestataire", ech, aujourd_hui))
            continue
        limite = ajouter_mois(ech, -c["preavis_mois"])
        jours = (limite - aujourd_hui).days
        if 0 <= jours <= horizon:
            res.append(_alerte("contrat", c["objet"],
                               f"Résilier avant le {limite:%d/%m/%Y} pour changer de prestataire "
                               f"(préavis {c['preavis_mois']} mois, échéance le {ech:%d/%m/%Y})",
                               limite, aujourd_hui))
        elif jours < 0 <= (ech - aujourd_hui).days:
            res.append(_alerte("contrat", c["objet"],
                               f"Préavis dépassé : reconduction automatique le {ech:%d/%m/%Y}",
                               ech, aujourd_hui, niveau="info"))

    # 2. Diagnostics : manquants ou bientôt périmés
    for d in fiche.get("diagnostics", []):
        if d["realise_le"] is None:
            res.append(_alerte("diagnostic", d["libelle"],
                               "Non réalisé : à inscrire à l'ordre du jour de la prochaine AG", None, aujourd_hui))
        elif d.get("validite_ans"):
            fin = ajouter_mois(d["realise_le"], 12 * d["validite_ans"])
            if (fin - aujourd_hui).days <= horizon:
                res.append(_alerte("diagnostic", d["libelle"], f"Validité jusqu'au {fin:%d/%m/%Y} : à renouveler",
                                   fin, aujourd_hui))

    # 3. AG annuelle : dans les N mois suivant la clôture de l'exercice
    gouv = fiche["gouvernance"]
    mm, jj = (int(x) for x in gouv["exercice"]["fin"].split("-"))
    cloture = date(aujourd_hui.year, mm, jj)
    if cloture > aujourd_hui:
        cloture = date(aujourd_hui.year - 1, mm, jj)
    limite_ag = ajouter_mois(cloture, gouv.get("ag_annuelle_delai_mois", 6))
    jours_ag = (limite_ag - aujourd_hui).days
    if 0 <= jours_ag <= horizon:
        convoc = limite_ag - timedelta(days=DELAI_CONVOCATION_AG_JOURS)
        res.append(_alerte("ag", "Assemblée générale annuelle",
                           f"À tenir avant le {limite_ag:%d/%m/%Y} (exercice clos le {cloture:%d/%m/%Y}). "
                           f"Convocations à envoyer au plus tard le {convoc:%d/%m/%Y}",
                           limite_ag, aujourd_hui))

    # 4. Mandat du syndic
    fin_mandat: date = gouv["syndic"]["fin_mandat"]
    if 0 <= (fin_mandat - aujourd_hui).days <= horizon:
        res.append(_alerte("mandat", "Mandat du syndic",
                           f"Se termine le {fin_mandat:%d/%m/%Y} : prévoir le renouvellement à l'ordre du jour de l'AG",
                           fin_mandat, aujourd_hui))

    # 5. Plan de travaux : lignes de cette année ou de l'an prochain sans dossier ouvert
    import plan_travaux
    if not plan_travaux.valider_plan(fiche):
        res += plan_travaux.alertes_plan(fiche, aujourd_hui, suivi_plan)

    ordre ={"urgent": 0, "a_prevoir": 1, "info": 2, "depasse": 3}
    res.sort(key=lambda a: (ordre[a["niveau"]], a["date"] or "9999"))
    return res


def alertes_echeancier(fiche: dict, aujourd_hui: date) -> list[str]:
    """Version texte, pour la ligne de commande."""
    return [f"[{a['titre']}] {a['message']}" for a in echeances(fiche, aujourd_hui)]


# --------------------------------------------------------------------------- #
# Appel de fonds
# --------------------------------------------------------------------------- #
def total_budget(fiche: dict) -> Decimal:
    return sum((Decimal(str(p["montant"])) for p in fiche["budget_previsionnel"]["postes"]), Decimal("0"))


def montants_par_cle(fiche: dict) -> dict[str, Decimal]:
    """Budget annuel par clé, fonds de travaux inclus."""
    par_cle: dict[str, Decimal] = defaultdict(Decimal)
    for p in fiche["budget_previsionnel"]["postes"]:
        par_cle[p["cle"]] += Decimal(str(p["montant"]))
    ft = fiche["fonds_travaux"]
    par_cle[ft["cle"]] += Decimal(str(ft["cotisation_annuelle"]))
    return dict(par_cle)


def repartir(montant: Decimal, poids: dict[str, int]) -> dict[str, Decimal]:
    """Répartit un montant au prorata des poids, au centime près, sans perte :
    on arrondit vers le bas puis on distribue les centimes restants aux plus
    gros restes (méthode du plus fort reste). La somme tombe toujours juste."""
    total_poids = sum(poids.values())
    bruts = {k: montant * v / total_poids for k, v in poids.items()}
    arrondis = {k: b.quantize(CENT, rounding=ROUND_DOWN) for k, b in bruts.items()}
    reste = int(((montant - sum(arrondis.values())) / CENT).to_integral_value())
    for k in sorted(bruts, key=lambda k: bruts[k] - arrondis[k], reverse=True)[:reste]:
        arrondis[k] += CENT
    return arrondis


def rubriques(fiche: dict) -> list[dict]:
    """Rubriques appelées : le budget par clé, puis le fonds de travaux à part
    (il doit apparaître distinctement sur l'avis)."""
    cles = fiche["cles_repartition"]
    budget_par_cle: dict[str, Decimal] = defaultdict(Decimal)
    for p in fiche["budget_previsionnel"]["postes"]:
        budget_par_cle[p["cle"]] += Decimal(str(p["montant"]))
    res = [
        {"id": f"budget:{cle}", "libelle": f"Budget – {cles[cle]['libelle'].lower()}", "cle": cle, "annuel": m}
        for cle, m in budget_par_cle.items()
    ]
    ft = fiche["fonds_travaux"]
    res.append({"id": "fonds_travaux", "libelle": "Fonds de travaux", "cle": ft["cle"],
                "annuel": Decimal(str(ft["cotisation_annuelle"]))})
    return res


def appel_par_lot(fiche: dict) -> dict[tuple[str, int], Decimal]:
    """Montant de l'appel trimestriel pour chaque (rubrique, lot).
    La répartition se fait lot par lot : c'est ce qui figure sur l'avis."""
    nb_appels = len(fiche["appels_de_fonds"]["dates_exigibilite"])
    resultat: dict[tuple[str, int], Decimal] = {}
    for rub in rubriques(fiche):
        montant_appel = (rub["annuel"] / nb_appels).quantize(CENT)
        poids = {l["numero"]: l["tantiemes"][rub["cle"]] for l in fiche["lots"] if l["tantiemes"][rub["cle"]] > 0}
        for numero, m in repartir(montant_appel, poids).items():
            resultat[(rub["id"], numero)] = m
    return resultat


def appel_trimestriel(fiche: dict) -> dict[str, Decimal]:
    """Montant de l'appel trimestriel par copropriétaire (somme de ses lots)."""
    proprio = {l["numero"]: l["proprietaire"] for l in fiche["lots"]}
    resultat: dict[str, Decimal] = defaultdict(Decimal)
    for (_, numero), m in appel_par_lot(fiche).items():
        resultat[proprio[numero]] += m
    return dict(resultat)


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Valide une fiche copro et calcule l'appel de fonds.")
    parser.add_argument("fiche", help="Chemin de la fiche YAML")
    parser.add_argument("--date", help="Date de référence AAAA-MM-JJ (défaut : aujourd'hui)")
    args = parser.parse_args()

    fiche = charger_fiche(args.fiche)
    ref = date.fromisoformat(args.date) if args.date else date.today()
    nom = fiche["copropriete"]["nom"]

    print(f"\n=== {nom} — {fiche['copropriete']['nb_lots_total']} lots ===\n")

    rapport = valider(fiche)
    if not rapport.ok:
        print("❌ Fiche invalide :")
        for e in rapport.erreurs:
            print(f"   - {e}")
        return 1
    print("✅ Fiche valide : tantièmes, références et règles de base vérifiés\n")

    alertes = alertes_echeancier(fiche, ref)
    print(f"--- Échéancier au {ref:%d/%m/%Y} ---")
    for a in alertes or ["Aucune alerte"]:
        print(f"   • {a}")

    budget = total_budget(fiche)
    ft = Decimal(str(fiche["fonds_travaux"]["cotisation_annuelle"]))
    print(f"\n--- Budget {fiche['budget_previsionnel']['exercice']} ---")
    print(f"   Budget prévisionnel : {budget:>10,.2f} €")
    print(f"   Fonds de travaux    : {ft:>10,.2f} €  ({ft / budget:.1%} du budget)")
    for cle, m in montants_par_cle(fiche).items():
        print(f"   dont clé {cle:<11}: {m:>10,.2f} €")

    appel = appel_trimestriel(fiche)
    copros = {c["id"]: c for c in fiche["coproprietaires"]}
    print("\n--- Appel de fonds trimestriel (projet à valider par le syndic) ---")
    print(f"   {'ID':<5} {'Copropriétaire':<20} {'Envoi':<9} {'Montant':>10}")
    for cid in sorted(appel):
        c = copros[cid]
        print(f"   {cid:<5} {c['nom']:<20} {c['envoi']:<9} {appel[cid]:>9,.2f} €")
    total = sum(appel.values())
    attendu = sum((r["annuel"] / len(fiche['appels_de_fonds']['dates_exigibilite'])).quantize(CENT)
                  for r in rubriques(fiche))
    print(f"   {'':<36}{'-' * 10}")
    print(f"   {'TOTAL':<36}{total:>9,.2f} €  (attendu : {attendu:,.2f} €)")
    assert total == attendu, "Écart d'arrondi : la répartition doit tomber juste"
    return 0


if __name__ == "__main__":
    sys.exit(main())
