"""Pièces justificatives et comptes consultables. python -m pytest tests/test_pieces.py"""
import io
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))

import pieces as P  # noqa: E402

JOUR = date(2027, 3, 1)


def _jpeg_avec_gps() -> bytes:
    from PIL import Image
    im = Image.new("RGB", (40, 30), "white")
    exif = Image.Exif()
    exif[0x010F] = "Telephone Exemple"               # fabricant
    exif[0x8825] = {1: "N", 2: (43.0, 42.0, 0.0)}    # GPS
    b = io.BytesIO()
    im.save(b, "JPEG", exif=exif)
    return b.getvalue()


def _pdf() -> bytes:
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(200, 200)
    w.add_metadata({"/Author": "Dupont Jean"})
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def test_formats_et_taille():
    assert P.nature(b"%PDF-1.7 ...") == "pdf"
    with pytest.raises(P.PieceInvalide, match="Format"):
        P.nature(b"MZ\x90\x00 exe")
    with pytest.raises(P.PieceInvalide, match="trop lourd"):
        P.ajouter(Path("/tmp"), "x", "facture:F0001", b"%PDF-" + b"0" * P.TAILLE_MAX, "a.pdf", JOUR)
    with pytest.raises(P.PieceInvalide, match="inconnue"):
        P.ajouter(Path("/tmp"), "x", "../../etc", b"%PDF-", "a.pdf", JOUR)


def test_metadonnees_retirees(tmp_path):
    from PIL import Image
    brut = _jpeg_avec_gps()
    assert Image.open(io.BytesIO(brut)).getexif()
    p = P.ajouter(tmp_path, "c", "depense:OP12", brut, "photo.jpg", JOUR)
    f, mime = P.fichier(tmp_path, "c", "depense:OP12")
    assert mime == "image/jpeg" and not Image.open(f).getexif()            # plus de GPS ni d'appareil
    P.ajouter(tmp_path, "c", "facture:F0001", _pdf(), "facture.pdf", JOUR)
    from pypdf import PdfReader
    f, _ = P.fichier(tmp_path, "c", "facture:F0001")
    assert "Dupont" not in str(PdfReader(str(f)).metadata or {})
    assert p["nom"] == "photo.jpg" and not p["privee"]


def test_remplacer_privee_retirer(tmp_path):
    P.ajouter(tmp_path, "c", "facture:F0001", _pdf(), "v1.pdf", JOUR)
    premier = P.fichier(tmp_path, "c", "facture:F0001")[0]
    P.ajouter(tmp_path, "c", "facture:F0001", _pdf(), "v2.pdf", JOUR)
    assert not premier.exists() and P.charger(tmp_path, "c")["facture:F0001"]["nom"] == "v2.pdf"
    assert P.rendre_privee(tmp_path, "c", "facture:F0001", True)["privee"]
    P.retirer(tmp_path, "c", "facture:F0001")
    assert P.charger(tmp_path, "c") == {} and P.fichier(tmp_path, "c", "facture:F0001") is None


def test_charges_et_pieces():
    E = [
        {"date": "2027-01-10", "source": "facture", "piece": "F0001", "libelle": "x",
         "lignes": [{"compte": "614", "debit": Decimal("300"), "credit": 0}, {"compte": "401.ASC", "debit": 0, "credit": Decimal("300")}]},
        {"date": "2027-01-15", "source": "banque", "piece": "OP7", "libelle": "VIR M DUPONT REMBOURSEMENT",
         "lignes": [{"compte": "627", "debit": Decimal("12.50"), "credit": 0}, {"compte": "512", "debit": 0, "credit": Decimal("12.50")}]},
        {"date": "2027-01-20", "source": "banque", "piece": "OP8", "libelle": "paiement",
         "lignes": [{"compte": "512", "debit": Decimal("100"), "credit": 0}, {"compte": "4501.CP01", "debit": 0, "credit": Decimal("100")}]},
        {"date": "2026-12-20", "source": "facture", "piece": "F0000", "libelle": "hors période",
         "lignes": [{"compte": "614", "debit": Decimal("50"), "credit": 0}, {"compte": "401.X", "debit": 0, "credit": Decimal("50")}]},
    ]
    st = {"factures": [{"id": "F0001", "fournisseur": "Ascenseurs Exemple", "libelle": "Entretien"}],
          "depenses": {"OP7": {"compte": "627", "fournisseur": "Banque Exemple"}}}
    idx = {"facture:F0001": {"type": "pdf", "privee": False, "nom": "f.pdf"}}
    c = P.charges(E, st, idx, "2027-01-01", "2027-12-31")
    assert c["nb"] == 2 and c["justifiees"] == 1 and c["total"] == Decimal("312.50")
    assert [x["fournisseur"] for x in c["lignes"]] == ["Ascenseurs Exemple", "Banque Exemple"]
    assert all("DUPONT" not in str(x) for x in c["lignes"])                 # le libellé bancaire n'apparaît pas
    assert c["montant_justifie"] == Decimal("300")


def test_lien_desactive_par_defaut(tmp_path):
    assert not P.jeton_valide(tmp_path, "c", "nimporte")
    r = P.partager(tmp_path, "c", True)
    assert P.jeton_valide(tmp_path, "c", r["jeton"])
    r2 = P.partager(tmp_path, "c", True, renouveler=True)
    assert not P.jeton_valide(tmp_path, "c", r["jeton"]) and P.jeton_valide(tmp_path, "c", r2["jeton"])
    P.partager(tmp_path, "c", False)
    assert not P.jeton_valide(tmp_path, "c", r2["jeton"])
