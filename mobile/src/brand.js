// ============================================================================
// Logo de l'application — SOURCE UNIQUE.
//
// Le logo officiel est celui du logiciel de bureau (`ui/icons/logo.ico`, le « K »
// turquoise affiché par son écran de connexion). Il est décliné pour chaque
// plateforme par le script racine `_sync_logo.py` : ne PAS remplacer ces images
// à la main, régénérer le logo et relancer ce script.
//
// Après avoir changé le logo :
//   python _sync_logo.py          # régénère mobile/assets/*.png + web/public
//   cd mobile && npx expo prebuild   # icônes natives Android
// ============================================================================
import { Image } from 'react-native';

/** Logo carré (K turquoise sur fond blanc) — écrans de connexion, boot. */
export const LOGO = require('../assets/logo.png');

/** Même logo en 512 px : covariance si l'écran est plus dense. */
export const LOGO_512 = require('../assets/logo-512.png');

/**
 * K seul sur fond transparent : à poser sur un fond BLEU (le panneau de
 * connexion). Utiliser LOGO sur fond bleu afficherait un carré blanc.
 */
export const LOGO_TRANSPARENT = require('../assets/splash-icon.png');
