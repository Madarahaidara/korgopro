"""Planche de controle : rend toutes les declinaisons du logo côte a côte.

Vérifie d'un coup d'oeil ce que l'œil ne peut pas juger sur un nom de fichier :
le K correctly detoure, la marge de surete Android, et le rendu sur fond clair
comme sur fond bleu (facon dont le systeme dessine l'icone).

Sortie : ui/icons/_logo_planche.png (hors depot, usage de diagnostic)
Usage : python _planche_logo.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

RACINE = Path(__file__).parent
SORTIE = RACINE / "ui" / "icons" / "_logo_planche.png"

CAS = [
    ("mobile icon.png", RACINE / "mobile/assets/icon.png", (240, 244, 248)),
    ("mobile favicon", RACINE / "mobile/assets/favicon.png", (240, 244, 248)),
    ("splash (fond bleu)", RACINE / "mobile/assets/splash-icon.png", (0x2F, 0x42, 0x55)),
    ("web logo-32", RACINE / "web/public/icons/logo-32.png", (240, 244, 248)),
    ("web apple-touch", RACINE / "web/public/icons/apple-touch-icon.png", (240, 244, 248)),
]


def icone_adaptive(dossier: Path, forme: str) -> Image.Image:
    """Compose l'icone adaptive comme le systeme Android le fera.

    Masques de reference : cercle, carré arrondi, « Brume » (goutte), losange.
    C'est exactement le rognage qui fait que le K doit avoir une marge.
    """
    fond = Image.open(dossier / "android-icon-background.png").convert("RGBA")
    devant = Image.open(dossier / "android-icon-foreground.png").convert("RGBA")
    image = Image.alpha_composite(fond, devant)

    masque = Image.new("L", image.size, 0)
    dessin = ImageDraw.Draw(masque)
    w, h = image.size
    if forme == "cercle":
        dessin.ellipse((0, 0, w, h), fill=255)
    elif forme == "carre arrondi":
        dessin.rounded_rectangle((0, 0, w, h), radius=int(w * 0.22), fill=255)
    elif forme == "goutte":
        # Rectangle superieur plein + demi-cercle inferieur (Brume Android).
        dessin.rectangle((0, 0, w, int(h * 0.62)), fill=255)
        dessin.ellipse((0, int(h * 0.12), w, h + int(h * 0.5)), fill=255)
    elif forme == "losange":
        dessin.polygon([(w // 2, 0), (w, h // 2), (w // 2, h), (0, h // 2)], fill=255)
    image.putalpha(Image.composite(
        image.getchannel("A"), Image.new("L", image.size, 0), masque))
    return image


def main() -> int:
    cadre, etiquette, pas = 20, 16, 150
    formes = ["cercle", "carre arrondi", "goutte", "losange"]
    largeur = pas * (len(CAS) + len(formes)) + cadre
    hauteur = pas * 2 + cadre * 2
    planche = Image.new("RGB", (largeur, hauteur), (255, 255, 255))
    dessin = ImageDraw.Draw(planche)

    for i, (nom, chemin, fond) in enumerate(CAS):
        if not chemin.exists():
            continue
        x = cadre + i * pas
        y = cadre
        dessin.rectangle((x, y, x + pas - 20, y + pas - 20), fill=fond)
        img = Image.open(chemin).convert("RGBA")
        img.thumbnail((pas - 30, pas - 30), Image.LANCZOS)
        planche.paste(img, (x + 10, y + 10), img)
        dessin.text((x, y + pas - 16), nom[:22], fill=(60, 70, 80))

    dossier = RACINE / "mobile" / "assets"
    for j, forme in enumerate(formes):
        x = cadre + (len(CAS) + j) * pas
        y = cadre
        img = icone_adaptive(dossier, forme)
        img.thumbnail((pas - 20, pas - 20), Image.LANCZOS)
        planche.paste(img, (x + 10, y + 10), img)
        dessin.text((x, y + pas - 16), f"adaptive: {forme}", fill=(60, 70, 80))

    planche.save(SORTIE)
    print(f"Planche ecrite : {SORTIE}")
    print("A verifier : le K est entier (non coupe) dans les 4 formes, aucun")
    print("carre blanc ne doit flotter sur le fond bleu de l'icone adaptive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
