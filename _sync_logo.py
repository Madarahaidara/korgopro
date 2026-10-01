  """Génère TOUTES les déclinaisons du logo Korgo Pro depuis la source unique.

SOURCE DE VERITE
----------------
    ui/icons/logo.ico   (256x256, "K" turquoise #228980 sur fond blanc)

C'est le logo affiché par l'écran de connexion du logiciel de bureau
(`ui/views/login_view.py`). Le web, le mobile et l'icône Android n'avaient
JAMAIS reçu ce logo : ils utilisaient une lettre "K" dessinée en CSS/JSX, et
l'icône Android gardait même le "A" générique d'Expo. Ce script rend les trois
identiques a la référence.

DECLINAISONS PRODUITES
---------------------
    mobile/assets/logo.png                  1024  (master, splash)
    mobile/assets/logo-512.png               512
    mobile/assets/favicon.png                 48
    mobile/assets/icon.png                  1024  (icone Android carree)
    mobile/assets/splash-icon.png           1024
    mobile/assets/android-icon-foreground.png 512  (K centre, zone de surete)
    mobile/assets/android-icon-background.png 512
    mobile/assets/android-icon-monochrome.png 432  (icone themee)
    web/public/icons/logo.png (+16/32)         16/32
    web/public/icons/apple-touch-icon.png      180
    ui/icons/logo.ico            (.ico multi-tailles, executable Windows)

REGLE DE COMPOSITION ANDROIDE
-----------------------------
Sur Android adaptatif, le systeme rogne l'icone selon sa forme : seule la
partie centrale (~66% sur les Brumelames, losanges, cercles) reste visible. Le
K est donc ramene a 58% de la toile et centre, pour rester entier sur toutes
les formes de lanceur.

Usage : python _sync_logo.py [--check]
    --check  inventorie les declinaisons sans rien ecrire
"""
import base64
import io
import sys
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).parent
SOURCE = RACINE / "ui" / "icons" / "logo.ico"
WEB_PUBLIC = RACINE / "web" / "public" / "icons"
MOBILE_ASSETS = RACINE / "mobile" / "assets"
MOBILE_SRC_ASSETS = RACINE / "mobile" / "src" / "assets"

# Fond des icones carrees (le .ico d'origine a un fond blanc).
FOND = (255, 255, 255, 255)
# Teinte de l'application (app.json : primaryColor).
BLEU_PRO = (0x2F, 0x42, 0x55, 255)
# Turquoise du glyphe, releve dans ui/icons/logo.ico (34, 137, 128).
TURQUOISE = (34, 137, 128)
# Part du K dans le canevas adaptatif (cf. regle ci-dessus).
TAUX_ADAPTATIF = 0.58
TAUX_ICO = 0.86          # icone carree : marge de securite confortable
TAUX_SPLASH = 0.62       # splash : le logo flotte sur le fond bleu
TAUX_MONO = 0.62
# Cote du logo incorpore dans l'en-tete des factures PDF mobiles. Petit
# volontaire : le module genere pese quelques kilo-octets de base64 seulement.
TAUX_PDF = 96


def ecrire_logo_pdf(logo: Image.Image, verifier: bool) -> None:
    """Ecrit `mobile/src/assets/logoPdfData.js` : le logo en data-URI base64.

    Les factures PDF mobiles sont rendues par `expo-print` dans une WebView
    Android : une image ne peut y etre referencee de facon fiable que sous forme
    de data-URI (un `file://` distant est bloque par la WebView). Plutot que
    d'ajouter `expo-file-system`/`expo-asset` au projet, on embarque le logo
    dans le bundle sous forme d'une chaine base64 generee ICI, depuis la meme
    source de verite que toutes les autres declinaisons.
    """
    cible = MOBILE_SRC_ASSETS / "logoPdfData.js"
    if verifier:
        etat = "OK  " if cible.exists() else "MANQUE"
        print(f"{etat}  {cible.relative_to(RACINE)}")
        return

    tampon = io.BytesIO()
    composer(logo, TAUX_PDF, TAUX_ICO, FOND).save(tampon, "PNG", optimize=True)
    data = base64.b64encode(tampon.getvalue()).decode("ascii")
    contenu = (
        "// ============================================================================\n"
        "// FICHIER GENERE — ne pas editer a la main.\n"
        "// Source : ui/icons/logo.ico, via le script racine `_sync_logo.py`.\n"
        "//\n"
        "// Logo « K » turquoise encode en data-URI base64 : c'est la seule forme\n"
        "// d'image que la WebView d'`expo-print` accepte de façon fiable sur\n"
        "// Android, et cela evite d'embarquer `expo-file-system`/`expo-asset`\n"
        "// uniquement pour une image. Utilise par src/lib/invoicePdf.js\n"
        "// (en-tete des factures PDF).\n"
        "//\n"
        "// Apres un changement de logo : `python _sync_logo.py` puis reconstruire\n"
        "// l'APK (voir mobile/README.md section 6.3).\n"
        "// ============================================================================\n"
        f"export const LOGO_PDF_DATA_URI =\n  'data:image/png;base64,{data}';\n"
    )
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(contenu, encoding="utf-8")
    print(f"ecrit  {cible.relative_to(RACINE)}  ({TAUX_PDF}x{TAUX_PDF}, "
          f"{len(data) // 1024} Ko base64)")


def lire_source() -> Image.Image:
    """Logo de reference, recadre sur son contenu (marge transparente retiree)."""
    if not SOURCE.exists():
        raise SystemExit(f"KO  logo source introuvable : {SOURCE}")
    image = Image.open(SOURCE).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    return image.crop(bbox) if bbox else image


def composer(image: Image.Image, taille: int, taux: float, fond) -> Image.Image:
    """Logo centre, a `taux` de la toile, sur le fond fourni (None = transparent)."""
    canvas = Image.new("RGBA", (taille, taille), fond if fond else (0, 0, 0, 0))
    ratio = taille * taux / max(image.size)
    cible = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
    canvas.alpha_composite(image.resize(cible, Image.LANCZOS),
                           ((taille - cible[0]) // 2, (taille - cible[1]) // 2))
    return canvas


def composer_k(logo_k: Image.Image, taille: int, taux: float) -> Image.Image:
    """Logo deja detoure, centre a `taux` de la toile, sur fond transparent."""
    canvas = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    ratio = taille * taux / max(logo_k.size)
    cible = (max(1, int(logo_k.width * ratio)), max(1, int(logo_k.height * ratio)))
    canvas.alpha_composite(logo_k.resize(cible, Image.LANCZOS),
                           ((taille - cible[0]) // 2, (taille - cible[1]) // 2))
    return canvas


def monochrome(image: Image.Image, taille: int) -> Image.Image:
    """Silhouette blanche : Android la recolore selon le theme du lanceur.

    Sert aussi au splash, dont le fond (#2F4255) est sombre : un K turquoise
    y serait illisible, une silhouette blanche ressort.

    IMPORTANT : on passe par `isoler_k` et non par l'alpha de l'image. Le
    .ico d'origine a un fond blanc OPAQUE dans son cadre : utiliser son alpha
    dessinerait un CARRE BLANC au lieu de la lettre.
    """
    k = isoler_k(image, (255, 255, 255))
    return composer_k(k, taille, TAUX_MONO)


def isoler_k(image: Image.Image, couleur) -> Image.Image:
    """Le K seul, sur transparence, dans la couleur demandee.

    LE .ICO D'ORIGINE EMBARQUE UN CARRE BLANC : pose tel quel dans la couche
    `foreground`, ce carre flotterait sur le fond de l'icone adaptive (il
    serait visible en carre net sur les lanceurs ronds). On le supprime donc en
    deduisant l'alpha de la luminance :

        alpha = 255 - min(r, g, b)   (0 sur du blanc, 255 sur le turquoise)

    puis on repeint le glyphe dans la couleur unie, ce qui evite tout halo
    clair sur les bords anticrénelés.
    """
    pixels = image.load()
    sortie = Image.new("RGBA", image.size, (0, 0, 0, 0))
    cibles = sortie.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a < 8:                       # zone deja transparente
                continue
            niveau = min(r, g, b)
            alpha = max(0, min(255, int((255 - niveau) * 1.5)))
            if alpha:
                cibles[x, y] = (*couleur, alpha)
    return sortie


def main() -> int:
    verifier = "--check" in sys.argv
    logo = lire_source()
    print(f"Source : {SOURCE.relative_to(RACINE)} "
          f"({logo.width}x{logo.height} apres recadrage)\n")

    def carree(taille):
        return composer(logo, taille, TAUX_ICO, FOND)

    k_teinte = isoler_k(logo, TURQUOISE)

    travaux = [
        # Ecran de connexion / web : logo tel quel sur fond blanc.
        (MOBILE_ASSETS / "logo.png", carree(1024)),
        (MOBILE_ASSETS / "logo-512.png", carree(512)),
        (MOBILE_ASSETS / "favicon.png", carree(48)),
        (MOBILE_ASSETS / "icon.png", carree(1024)),
        # Splash mobile : fond bleu sombre (app.json) -> silhouette blanche.
        (MOBILE_ASSETS / "splash-icon.png", monochrome(logo, 1024)),
        # Icone adaptive : K turquoise seul sur le fond bleu (pas de carre
        # blanc flottant), avec la marge de surete des lanceurs arrondis.
        (MOBILE_ASSETS / "android-icon-foreground.png",
         composer_k(k_teinte, 512, TAUX_ADAPTATIF)),
        (MOBILE_ASSETS / "android-icon-background.png",
         Image.new("RGBA", (512, 512), BLEU_PRO)),
        (MOBILE_ASSETS / "android-icon-monochrome.png", monochrome(logo, 432)),
        (WEB_PUBLIC / "logo.png", carree(32)),
        (WEB_PUBLIC / "logo-16.png", carree(16)),
        (WEB_PUBLIC / "logo-32.png", carree(32)),
        (WEB_PUBLIC / "apple-touch-icon.png", carree(180)),
    ]

    for cible, image in travaux:
        if verifier:
            etat = "OK  " if cible.exists() else "MANQUE"
            print(f"{etat}  {cible.relative_to(RACINE)}")
            continue
        cible.parent.mkdir(parents=True, exist_ok=True)
        image.save(cible, "PNG", optimize=True)
        print(f"ecrit  {cible.relative_to(RACINE)}  ({image.width}x{image.height})")

    # .ico multi-tailles (icone de l'executable Windows + <link rel=icon>).
    ico = RACINE / "ui" / "icons" / "logo.ico"
    tailles = [16, 24, 32, 48, 64, 128, 256]
    if verifier:
        etat = "OK  " if ico.exists() else "MANQUE"
        print(f"{etat}  {ico.relative_to(RACINE)}")
    else:
        ico.unlink(missing_ok=True)
        carree(256).save(ico, sizes=[(t, t) for t in tailles])
        tailles_txt = ", ".join(str(t) for t in tailles)
        print(f"ecrit  {ico.relative_to(RACINE)}  (tailles {tailles_txt})")

    print("\nSuite : cd mobile && npx expo prebuild  (icones natives Android)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
