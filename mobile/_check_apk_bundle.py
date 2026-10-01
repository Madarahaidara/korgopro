"""Verifie que l'APK autonome contient bien le code attendu.

Indispensable apres un rebuild : un bundle perime (APK reconstruit sans
regenereer les assets JS) donnerait une application qui n'a pas la
fonctionnalite annoncee, sans la moindre erreur visible a la compilation.

Usage : python _check_apk_bundle.py
"""
import sys
import zipfile
from pathlib import Path

APK = Path(__file__).with_name("dist") / "korgo-pro-terrain-standalone.apk"
BUNDLE = "assets/index.android.bundle"

# (libelle, motif attendu dans le bundle, obligatoire ?)
ATTENDU = [
    ("session unique : ouverture", "app_register_session", True),
    ("session unique : battement", "app_session_heartbeat", True),
    ("session unique : fermeture", "app_end_session", True),
    ("refus SESSION_ACTIVE", "SESSION_ACTIVE", True),
    ("plateforme 'mobile'", "'mobile'", True),
    # `SESSION_CLOSED` / `INACTIVE_PROFILE` sont produits par le SERVEUR : ils
    # n'apparaissent donc pas dans le bundle. Le client ne manipule que le code
    # du refus (« SESSION_ACTIVE ») et le drapeau `active` du battement.
    ("erreur SessionConflictError", "SessionConflictError", True),
    ("battement : lecture de active", ".active", True),
    ("animations : SuccessOverlay", "SuccessOverlay", True),
    ("caisse : createSale", "app_create_sale", True),
]


def main() -> int:
    if not APK.exists():
        print(f"KO  APK absent : {APK}")
        return 1

    taille = APK.stat().st_size
    print(f"APK     : {APK}")
    print(f"Taille  : {taille:,} octets ({taille / (1024 * 1024):.1f} Mo)")

    with zipfile.ZipFile(APK) as archive:
        if BUNDLE not in archive.namelist():
            print(f"KO  bundle absent de l'APK ({BUNDLE})")
            print("    -> regenerez les assets : expo export:embed (README 6.3)")
            return 1
        bundle = archive.read(BUNDLE).decode("utf-8", errors="ignore")

    print(f"Bundle  : {len(bundle):,} caracteres\n")
    problemes = 0
    for label, motif, requis in ATTENDU:
        present = motif in bundle
        if requis and not present:
            problemes += 1
        print(f"{'OK  ' if present else 'KO  '} {label}  ({motif})")

    if problemes:
        print(f"\n{problemes} element(s) attendu(s) MANQUANT(S) : bundle perime ?")
        return 1
    print("\nBundle a jour : toutes les fonctionnalites attendues sont presentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
