# Parité frontend desktop ↔ web — étude de faisabilité

> Étude réalisée sur le dépôt au commit `67b634a`, mesures effectuées sur le code réel
> (aucune estimation « à vue »). Objectif : déterminer **comment obtenir un frontend web
> identique au frontend desktop** (PySide6), et à quel coût.

---

## 1. Ce que « identique » peut vouloir dire : 3 niveaux

Il est indispensable de séparer trois niveaux, car leur coût varie de 1 à 20.

| Niveau | Définition | Mesurable par |
|---|---|---|
| **L1 — Identité visuelle** | Mêmes couleurs, typographie, rayons, espacements, icônes, styles de composants (boutons, tableaux, champs, cartes) | Comparaison automatique des *design tokens* (QSS ↔ CSS) : 0 écart |
| **L2 — Identité structurelle** | Mêmes écrans, mêmes libellés, même ordre de navigation, même disposition des blocs | Matrice écran ↔ écran, libellés/ordre du menu identiques |
| **L3 — Identité comportementale** | Mêmes actions disponibles **et** mêmes fonctions natives : impression, exports Excel/PDF, verrouillage de session, raccourcis, dialogues métier | Parité fonctionnelle écran par écran + tests manuels |

Le dépôt est aujourd'hui à **L1 ≈ 70 %**, **L2 ≈ 35 %**, **L3 ≈ 20 %** : le web reprend
fidèlement la palette et la structure de base, mais la surface fonctionnelle est très
inférieure (voir §2).

---

## 2. État des lieux mesuré

### 2.1 Volumétrie des interfaces

**Desktop — `ui/views/` : 17 fichiers, ≈ 17 000 lignes de Python**

| Fichier | Lignes | Rôle |
|---|---:|---|
| `stock_view.py` | 5 788 | Stock, inventaire, alertes, exports (55 références impression/Excel) |
| `admin_view.py` | 2 471 | Utilisateurs, journaux, données, sauvegarde, état serveur |
| `proforma_invoice_view.py` | 2 079 | Devis/proformas, impression (4 références) |
| `sale_view.py` | 1 572 | Ventes / point de vente |
| `settings_view.py` | 1 126 | Paramètres société, facturation, thèmes |
| `dashboard_view.py` | 839 | Tableau de bord |
| `login_view.py` | 627 | Connexion |
| `lock_screen.py` | 586 | Verrouillage de session |
| `main_window.py` | 523 | Fenêtre + menu latéral |
| `sale_widgets.py` / `sale_dialogs.py` / `sale_services.py` | 464 / 378 / 315 | Composants et services de vente |
| `treasury_view.py` | 318 | Trésorerie |
| `invoice_register_view.py` | 216 | Registre des factures |
| `sys_logs_dialog.py` | 162 | Journaux système |
| `splash_screen*.py` | 139 + 49 | Écran de démarrage |

**Web — `web/src/` : 45 fichiers, ≈ 6 300 lignes (dont `index.css` 857)**

**Répartition `web/src` (total mesuré : 6 279 lignes)**

| Domaine | Fichiers principaux | Lignes |
|---|---|---:|
| Styles | `index.css` | 857 |
| Accès données | `api/` (17 modules : `db.js` 480, `remote.js` 326, …) | 2 097 |
| Écrans | `pages/` (10) | 1 093 |
| Composants | `components/` (17, dont `admin/` 6) | 1 962 |

➡️ **Le web couvre ≈ 35 % du volume du desktop** (6 279 / 17 652 lignes). Le « delta » à
porter est massif et concentré sur `stock_view`, `admin_view`, `proforma_invoice_view`,
`sale_view`, `settings_view`.

### 2.2 Design tokens : la bonne nouvelle

| Mesure | Desktop (`ui/themes/*.qss`) | Web (`web/src/index.css`) |
|---|---:|---:|
| Lignes de style | ≈ 1 650 (8 fichiers) | 857 (1 fichier) |
| **Couleurs distinctes** | **72** | **49** |

`index.css` documente déjà l'origine : *« Couleurs extraites des feuilles QSS : main.qss,
login.qss, dashboard.qss, stock_view.qss »*. Les couleurs porteuses sont identiques
(`#2F4255` bleu marine, `#1B3A7A` sélection, `#3A6B9F` accent, `#f8fafc` fond, `#ef4444`
erreur…).

**Divergence déjà amorcée** — couleurs présentes côté web mais absentes du desktop :
`#148a4f`, `#3B82F6`, `#6d28d9`, `#fde68a`, `#a7f3d0`, `#ecfdf5`, `#ede9fe`, `#eef0f3`,
`#f3c9c9`, `#fffbeb`, `#fafbfc`, `#1e2d3d`. À l'inverse, 30+ teintes QSS n'existent pas
côté web. Sans source unique, cette dérive s'aggrave à chaque évolution : c'est le
mécanisme principal par lequel « identique » devient faux dans le temps.

### 2.3 Ressources et navigation

| Élément | Desktop | Web | Écart |
|---|---|---|---|
| Icônes | **41 SVG** (`ui/icons/`) | **38** inline (`Icon.jsx`, 211 l.) | 3 icônes non portées + 2 définitions divergentes possibles (même nom) |
| Menu | Dashboard, Vente, Document, Stock, **Registre factures**, Trésorerie, Admin, Paramètres | Tableau de bord, Ventes, Stock, Trésorerie, Proformas, Factures, **Clients**, Administration, Paramètres | « Registre factures » et « Document » ↔ « Factures »/« Proformas » : libellés et découpage différents ; « Clients » n'a pas d'entrée de menu dédiée côté desktop |
| Verrouillage session | `lock_screen.py` (586 l.) | **absent** | Fonction de sécurité non portée |
| Impression | `QtPrintSupport` + `QPrinter` | **absent** | Écart L3 majeur |
| Exports | `openpyxl` (Excel) + `reportlab` (PDF), 55 réf. dans `stock_view` | **absent** | Écart L3 majeur |
| Hors-ligne | Repli **SQLite** si `DATABASE_URL` absent | Dépend de Supabase ; cache localStorage en secours | Le desktop fonctionne sans réseau, pas le web |
| Écran de démarrage | `splash_screen*.py` (2 versions) | **absent** (le splash a été retiré : `main.jsx` monte directement) | Écart L1/L2 mineur |

### 2.4 Contraintes techniques vérifiées dans l'environnement

| Vérification | Résultat |
|---|---|
| Binding Qt | **PySide6 6.11.1** (pas de PyQt5/PyQt6) |
| `PySide6.QtWebEngineWidgets` (webview) | **DISPONIBLE** dans le venv |
| `QtPrintSupport`, `openpyxl`, `reportlab` | disponibles |
| Empaquetage | PyInstaller via `.github/workflows/build-release.yml` (Windows, Python 3.11) ; spec généré en CI avec `excludes=["tkinter","PyQt5","PyQt6",…]` |
| Base de données desktop | SQLAlchemy, `DATABASE_URL` sinon SQLite local |
| Base web | PostgREST + RLS (même base Supabase) |

---

## 3. Options techniques évaluées

### O1 — Porter les écrans un par un en React *(statu quo industrialisé)*
Chaque vue Qt est transcrite en composants React, en s'appuyant sur les tokens extraits.

- **Fidélité** : L1 très bonne, L2/L3 bonnes mais jamais garanties (deux codes à maintenir).
- **Coût** : le plus élevé en cumulé (≈ 17 000 lignes Qt à transcrire, dont 5 788 pour le
  seul `stock_view`). Ordre de grandeur : **60 à 120 jours-homme** pour viser L2+L3.
- **Risque** : divergence permanente (déjà visible sur les couleurs) ; régression silencieuse
  à chaque évolution desktop.
- **Verdict** : inévitable pour les écrans réellement utilisés dans le navigateur, mais
  inenvisageable comme moyen d'obtenir « la même interface » à court terme.

### O2 — Le desktop affiche le front web (webview QtWebEngine)
`QWebEngineView` charge le build React (`dist/`) : **un seul front, donc parité 100 % par
construction**.

- **Faisabilité vérifiée** : `PySide6.QtWebEngineWidgets` **est disponible** dans le venv
  actuel — aucun obstacle d'installation immédiat.
- **Fidélité** : L1, L2 **et** L3 visuelle garanties (c'est littéralement le même DOM/CSS).
- **Coûts/risques** :
  - **Empaquetage** : +≈ 120-180 Mo dans l'exécutable PyInstaller ; nécessite
    `hiddenimports`/`datas` supplémentaires et l'exclusion des traductions Qt inutiles.
    Le build CI (Windows) resterait possible mais plus lourd.
  - **Fonctions natives à réimplémenter ou à conserver hors webview** : impression
    (`QPrinter`), exports Excel/PDF (`openpyxl`/`reportlab`), impression de tickets.
    Solution pragmatique : garder les vues Qt **uniquement** pour ces flux et utiliser la
    webview pour le reste → deux frontends cohabitent (donc retour à un risque de
    divergence, mais limité aux flux natifs).
  - **Hors-ligne** : le desktop fonctionne aujourd'hui sans réseau (SQLite). Un front web
    piloté par PostgREST/Supabase ne le peut pas sans travail supplémentaire (cache local,
    file d'attente d'écritures). **C'est le point bloquant n°1.**
  - **Sécurité/RLS** : le web ne sait pas écrire pour un non-admin (RLS) ; le desktop écrit
    en direct via SQLAlchemy. Basculer le desktop sur le front web **réduirait** les droits
    d'écriture des caissiers → régression fonctionnelle inacceptable en l'état.
- **Verdict** : excellent pour un **mode « bureau connecté »** ou une démonstration de
  parité, **pas** comme remplacement du desktop de production tel qu'il est conçu aujourd'hui.

### O3 — Qt for WebAssembly (compiler le desktop en web) — **écarté**
Qt for WebAssembly existe officiellement, mais **uniquement pour le C++**. PySide6/PyQt
n'exposent pas de cible WASM, et Pyodide n'embarque pas Qt.
➡️ Compiler les 17 000 lignes de vues Python en WebAssembly est **techniquement impossible**
aujourd'hui.

### O4 — Conversion automatique QSS/`.ui` → CSS/JSX — **écarté**
Aucun fichier `.ui` n'existe ici : les interfaces sont construites **à la main en Python**
(`QWidget`/`QLayout`). Il n'y a donc rien à convertir automatiquement ; toute traduction
serait heuristique et de fidélité faible. QSS et CSS partagent une syntaxe de surface mais
pas le modèle de boîte Qt (`qproperty-*`, sous-contrôles `::handle`, etc.).

### O5 — Source unique de design tokens (recommandé, à faire d'abord)
Un fichier `design/tokens.json` (couleurs, typographie, rayons, espacements, ombres)
devient la **seule source de vérité**, avec deux générateurs :
`→ ui/themes/*.qss` (desktop) et `→ web/src/index.css` (web).

- **Fidélité L1** : garantie et **vérifiable automatiquement** (0 écart de tokens).
- **Coût** : faible (≈ **2 à 4 jours-homme** pour l'extraction, les générateurs et le test).
- **Risque** : très faible ; on peut commencer par les 49 couleurs communes.
- **Bénéfice** : stoppe la dérive actuelle (12 couleurs web hors palette desktop) et rend
  tout futur changement de thème propagé aux deux fronts.
- **Verdict** : **à faire en premier** quel que soit l'arbitrage final.

### O6 — Réécrire le desktop sur Tauri/Electron en réutilisant le front web
Un seul front web, empaqueté en application de bureau avec accès réseau local/base.

- **Fidélité** : 100 % (comme O2), sans le poids de QtWebEngine.
- **Coût** : le plus lourd (**100 à 200 jours-homme**) : réécrire les contrôleurs
  (SQLAlchemy, impression, exports, verrouillage, hors-ligne) hors de l'écosystème Python.
- **Verdict** : cible cohérente à long terme si le web devient le produit principal ; hors
  de portée à court/moyen terme.

### O7 — Hybride assumé : deux fronts, une seule identité visuelle
Le desktop Qt reste **la référence native** (POS, impression, exports, verrouillage,
hors-ligne) ; le web reste une **console connectée** (consultation, saisie courante,
multi-appareils). La parité exigée est **L1 (visuelle)**, pas L3.

- **Coût** : O5 + portage progressif des écrans réellement utiles au navigateur
  (≈ **20 à 40 jours-homme** pour une L2 crédible sur Ventes/Stock/Registre).
- **Verdict** : meilleur rapport valeur/risque dans l'état actuel du produit.

---

## 4. Matrice de décision

| Option | Fidélité L1 | Fidélité L2/L3 | Coût | Risque | Hors-ligne | Impression/Exports | Verdict |
|---|---|---|---|---|---|---|---|
| O1 Portage manuel | Élevée | Partielle | Très élevé | Divergence | Inchangé | À reporter | Étape nécessaire, pas une solution |
| O2 Webview QtWebEngine | **100 %** | 100 % (web) | Moyen | Élevé (offline, droits) | **Perdu** | À garder hors webview | Mode « bureau connecté » |
| O3 Qt WASM | — | — | — | — | — | — | **Impossible** |
| O4 Conversion auto | Faible | Faible | Faible | Élevé | — | — | **Écarté** |
| **O5 Tokens partagés** | **100 % garanti** | — | **Faible** | Très faible | — | — | **À faire d'abord** |
| O6 Tauri/Electron | 100 % | 100 % | Très élevé | Très élevé | À refaire | À refaire | Long terme |
| O7 Hybride + O5 | 100 % | Ciblée | Moyen | Faible | Préservé | Préservé | **Recommandé** |

---

## 5. Recommandation phasée

**Phase 0 — Geler la parité visuelle (O5)** · 2-4 j-h · *prérequis de tout le reste*
1. Extraire `design/tokens.json` des 72 couleurs QSS + typographie + rayons + espacements.
2. Écrire deux générateurs : `design/generate_qss.py` → `ui/themes/*.qss` et
   `design/generate_css.mjs` → variables de `web/src/index.css`.
3. Ajouter un test de parité (`python design/check_parity.py` : 0 token divergent) à la CI.

**Phase 1 — Parité structurelle ciblée (O1/O7)** · 20-40 j-h
Écrans à porter en priorité (volumétrie web actuelle → desktop) :
1. **Ventes / POS** : web 434 l. (`Sales.jsx` 139 + `NewSaleModal` 295) → desktop 2 729 l.
   (`sale_view` 1 572 + `sale_widgets` 464 + `sale_dialogs` 378 + `sale_services` 315)
2. **Stock** : web 265 l. (`Stock.jsx` 121 + `ProductModal` 78 + `MovementModal` 66) →
   desktop 5 788 l. — au minimum : inventaire, alertes, exports
3. **Paramètres** : web 72 l. → desktop 1 126 l.
4. **Admin** : web ≈ 566 l. (`Admin.jsx` 64 + `admin/*` 502) → desktop 2 471 l.
5. **Verrouillage de session** : `lock_screen.py` 586 l. — **aucun équivalent web** (vérifié) ;
   fonction de sécurité à ne pas oublier
6. **Registre factures** : partiel — web 133 l. (`Invoices.jsx`, route `/factures`) →
   desktop 216 l. (`invoice_register_view.py`) : à aligner (colonnes, filtres, totaux)

**Phase 2 — Décision de convergence** (à trancher explicitement)
- Si l'objectif est **« un seul front, parité stricte »** → O2 en mode bureau connecté, ou O6
  à long terme, **avec** deux chantiers préalables obligatoires : *hors-ligne* et *droits
  d'écriture non-admin*.
- Si l'objectif est **« même apparence, usages complémentaires »** → O7 suffit ; on s'arrête
  au portage ciblé et on ne duplique jamais les fonctions natives.

---

## 6. Critères d'acceptation mesurables

| Niveau | Critère | Outil |
|---|---|---|
| L1 | 0 token divergent entre `tokens.json`, QSS généré et CSS généré | `python design/check_parity.py` |
| L1 | Mêmes 41 icônes disponibles des deux côtés (mêmes noms/fichiers) | test d'inventaire `ui/icons/*.svg` ↔ `Icon.jsx` |
| L2 | Matrice écran ↔ écran : libellés et ordre de menu identiques | document `docs/parite_frontend_desktop_web.md` (annexe) |
| L2 | Captures comparées desktop/web sur 6 écrans clés | revue visuelle assistée (voir `npm run test:browser`) |
| L3 | Chaque fonction native (impression, export Excel/PDF, verrouillage, hors-ligne) a un équivalent **documenté** ou est explicitement hors périmètre web | liste de contrôle signée |

---

## 7. Décisions à prendre

1. Le web doit-il être **une copie complète** du desktop, ou **un complément connecté** ?
   (cette réponse détermine O2/O6 vs O7)
2. Le web doit-il fonctionner **hors-ligne** ? (aujourd'hui : non ; le desktop : oui)
3. Les **caissiers** doivent-ils écrire depuis le web ? (aujourd'hui la RLS le refuse)
4. L'**impression** doit-elle être disponible dans le navigateur ? (aujourd'hui : non)

Tant que ces 4 questions n'ont pas de réponse, toute « unification » du frontend reste
spéculative : c'est l'objet de la Phase 2.

---

## Annexe — Matrice écran ↔ écran

| Écran desktop (`ui/views/`) | Lignes | Équivalent web | Lignes | État de la parité |
|---|---:|---|---:|---|
| `dashboard_view.py` | 839 | `pages/Dashboard.jsx` | 109 | **Partiel** (indicateurs oui, contenus à compléter) |
| `sale_view.py` + `sale_widgets/dialogs/services` | 2 729 | `pages/Sales.jsx` + `NewSaleModal.jsx` | 434 | **Partiel** (pas de paiements/retours multi-modes) |
| `proforma_invoice_view.py` | 2 079 | `pages/Proformas.jsx` + `ProformaForm.jsx` | 270 | **Partiel** |
| `stock_view.py` | 5 788 | `pages/Stock.jsx` + 2 modales | 265 | **Très partiel** (inventaire, alertes, exports absents) |
| `invoice_register_view.py` | 216 | `pages/Invoices.jsx` | 133 | **Partiel** |
| `treasury_view.py` | 318 | `pages/Treasury.jsx` + `AccountModal`/`MovementModal` | 216 | **Partiel** |
| `admin_view.py` | 2 471 | `pages/Admin.jsx` + `components/admin/*` | 566 | **Très partiel** |
| `settings_view.py` | 1 126 | `pages/Settings.jsx` | 72 | **Très partiel** |
| `login_view.py` | 627 | `pages/Login.jsx` | 109 | **Bon visuellement** (palette + mise en page 2 colonnes) ; logique desktop plus riche (tentatives, thème, verrouillage) |
| `lock_screen.py` | 586 | — | — | **Absent** |
| `sys_logs_dialog.py` | 162 | `components/admin/ActivityTab.jsx` | 57 | **Partiel** |
| `splash_screen*.py` | 188 | — | — | **Absent** (splash retiré de `main.jsx`) |
| — (fonction dans vente/stock) | — | `pages/Customers.jsx` + `CustomerForm.jsx` | 172 | **Web en plus** (pas d'entrée de menu desktop dédiée) |
| — (fonction dans vente) | — | `pages/Login`/`SyncBanner` : état de synchro Supabase | 78 | **Web en plus** |

**Lecture** : la parité L2 est bonne sur Connexion et correcte sur Trésorerie/Factures ;
elle est faible là où le desktop concentre son volume (Stock 4 %, Admin 23 %, Paramètres
6 %) et nulle sur les fonctions natives de sécurité et d'impression.
