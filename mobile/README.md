# Korgo Pro Terrain — application mobile (React Native / Expo)

Version mobile du logiciel de gestion **Korgo Pro**, destinée au travail sur le
terrain : **caisse (encaissement d'une vente)**, **encaissement des factures à
crédit** et **inventaire (mouvements de stock)**.

L'application travaille sur **la même base Supabase** que la version web et que
la version desktop : aucune donnée n'est dupliquée, aucun serveur intermédiaire
n'est nécessaire.

---

## 1. Périmètre

| Écran | Rôle | Permission requise |
|---|---|---|
| **Caisse** | Recherche produit, panier, remise, moyen de paiement, monnaie rendue, vente à crédit | `create_sales` |
| **Encaissement** | Factures impayées / partiellement payées, saisie d'un règlement | `create_sales` ou `manage_treasury` |
| **Inventaire** | Consultation du stock, alertes, entrées/sorties/ajustements de stock | `view_stock` (lecture) / `manage_stock` (écriture) |
| **Compte** | Identité, magasin actif, droits (terminal vs serveur), diagnostic | — |

La matrice de permissions est celle de `core/permissions.py` (source unique du
dépôt), recopiée dans `src/lib/permissions.js` **et** vérifiée côté serveur par
`app_security.can()` (voir §4).

---

## 2. Installation

```bash
cd mobile
npm install                     # dépendances (Expo SDK 57, React Native)

copy .env.example .env          # puis renseigner les 2 variables Supabase
#   EXPO_PUBLIC_SUPABASE_URL=https://<REF>.supabase.co
#   EXPO_PUBLIC_SUPABASE_ANON_KEY=<clé publique>

npm start                       # ouvre Expo (QR code pour téléphone réel)
```

* `npm run android` / `npm run ios` : lance sur un émulateur.
* Sur téléphone réel, **Expo Go** suffit pour tester ; un APK autonome se
  construit ensuite (§6).
* Sans `.env`, l'application démarre mais l'écran de connexion affiche la
  procédure de configuration (aucune donnée n'est accessible : les RLS
  interdisent toute lecture au rôle anonyme).

### Variables d'environnement

| Variable | Rôle |
|---|---|
| `EXPO_PUBLIC_SUPABASE_URL` | URL du projet Supabase (identique à `web/.env`) |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Clé **publique** (anon / publishable). Jamais de `service_role`. |
| `EXPO_PUBLIC_SUPABASE_SCHEMA` | Schéma exposé (défaut `public`) |
| `EXPO_PUBLIC_CURRENCY` | Devise envoyée à chaque vente (`sales.currency`), défaut `FCFA` |
| `EXPO_PUBLIC_TAX_RATE` | Taux de TVA par défaut de la caisse, défaut `0` |

---

## 3. Étapes d'installation côté Supabase (obligatoire)

Les politiques RLS livrées (`supabase_rls_policies.sql`) réservent l'écriture de
`sales`, `sale_items`, `payments`, `products`, `treasury_*` et
`inventory_movements` **aux administrateurs**. Un caissier reçoit donc une
erreur `42501` s'il écrit en direct en PostgREST.

L'application mobile écrit donc via des fonctions **`SECURITY DEFINER`** qui
vérifient le rôle côté serveur et réalisent l'opération dans une seule
transaction :

| RPC | Objet |
|---|---|
| `app_create_sale` | Vente + lignes + décrément du stock + `payments` + trésorerie + `sale_logs` |
| `app_register_payment` | Règlement d'une facture + trésorerie + `sale_logs` |
| `app_cancel_sale` | Annulation : stock remis + dette crédit effacée + caisse remboursée (OUT) + `sale_logs` |
| `app_stock_movement` | Mouvement de stock (`IN`, `OUT`, `ADJUST`, `LOSS`) + `inventory_movements` |
| `app_mobile_context` | Droits vus par le serveur (écran Compte) |

Installation, au choix :

```bash
python _apply_mobile_rpc.py     # via DATABASE_URL du .env racine
```

ou copier/coller `supabase_mobile_rpc.sql` dans le **SQL Editor** du dashboard
Supabase (script idempotent, terminé par une vérification des fonctions).

> Tant que ce script n'est pas exécuté, les écrans de consultation fonctionnent
> mais toute écriture renvoie un message explicite (« droit insuffisant » /
> fonction inconnue).
>
> Vérifiez que la base ciblée est bien **le même projet** que celui de
> `mobile/.env`, puis rechargez le cache de PostgREST
> (`python _reload_postgrest_cache.py`, ou Dashboard → Settings → API →
> *Reload schema*). Un RPC absente de ce cache provoque
> `Could not find the function public.app_* in the schema cache` (code
> `PGRST202`) **même si la fonction existe en base**.

---

## 4. Architecture du code

```
mobile/
├── App.js                        fournisseurs + navigation (boot / login / onglets)
├── .env.example                  configuration Supabase
└── src
    ├── config.js                 lecture de .env (EXPO_PUBLIC_*)
    ├── theme.js                  palette identique au desktop/web
    ├── lib
    │   ├── permissions.js        copie de core/permissions.py (rôles -> permissions)
    │   └── format.js             montants / dates
    ├── api
    │   ├── supabase.js           client PostgREST + erreurs traduites en français
    │   ├── authApi.js            Supabase Auth (login par email ou nom d'utilisateur)
    │   ├── sessionApi.js         session unique (ouverture, battement, fermeture)
    │   ├── dataApi.js            lectures (produits, clients, ventes, comptes)
    │   └── rpc.js                écritures -> app_create_sale / app_register_payment / app_stock_movement / app_cancel_sale
    ├── context
    │   ├── AuthContext.js        session + droits
    │   └── StoreContext.js       magasins + magasin actif (AsyncStorage)
    ├── components/ui.js          composants (carte, bouton, champ, puces, bandeau…)
    ├── components/Feedback.js    animations (coche, confirmation plein écran, pulsation)
    ├── navigation/MainTabs.js    onglets filtrés par permission
    └── screens/*.js              Login, Caisse, Paiements, Inventaire, Compte
```

### Différences assumées avec la version web

| Sujet | Web (`web/`) | Mobile (`mobile/`) |
|---|---|---|
| Chargement des données | toutes les tables téléchargées au login (`hydrateAll`) | requêtes **à la demande**, recherche côté serveur, limites 20–200 lignes |
| Écriture | « push » de collections entières (parcours des tables) | **RPC transactionnelles** `app_*` |
| Colonnes | renommage camelCase ↔ snake_case | noms PostgreSQL directs (`sale_number`, `amount_paid`…) |
| Rôle non-admin | l'écriture directe est refusée par RLS | encadrée par `app_security.can()` dans les RPC |
| Cache hors-ligne | localStorage (dernière copie connue) | aucun cache : une écriture part toujours d'un état frais |

La numérotation des factures suit le format **desktop** `FAC-AAAA-NNNNNN`
(généré côté serveur, avec verrou pour éviter les doublons).

### Animations de validation (retour utilisateur)

Chaque action validée (vente, encaissement, annulation, mouvement de stock) est
confirmée par une animation. Tout repose sur l'API `Animated` du cœur React
Native (`useNativeDriver` → transformation/opacité exécutées côté natif) : **aucune
dépendance supplémentaire** à installer ou à configurer — voir
`src/components/Feedback.js`.

| Animation | Utilisée par | Effet |
|---|---|---|
| `SuccessOverlay` | Caisse, Paiements, Inventaire, Ventes, Factures | voile assombri, carte qui « pop » (ressort) + coche animée ; se ferme au toucher ou après 1,8 s |
| `AnimatedCheck` | bandeaux de succès (`ui.js`) | coche qui surgit en ressort |
| `FadeSlideIn` | tous les `Banner` | fondu + glissement à chaque nouveau message (succès comme erreur) |
| `PulseOnChange` | total du jour (Caisse), reste à encaisser (Paiements) | pulsation discrète quand la valeur change |
| `Btn` | tous les boutons | compression à l'appui, retour élastique au relâchement |

Sur **Ventes** / **Factures**, la modale de détail se referme d'abord : la
confirmation animée est déclenchée ~350 ms plus tard (`OVERLAY_DELAY`) pour
laisser le fondu de fermeture se terminer (deux `Modal` Android ne doivent pas
se chevaucher).

---

## 4 bis. Session unique : un seul appareil connecté par compte

Un même compte (ex. « caissier ») ne peut plus être ouvert **simultanément** sur le
logiciel de bureau, la version web et l'application mobile : plus de ventes en
double ni de caisse incohérente.

### Ce qui a été mis en place

| Couche | Fichier | Rôle |
|---|---|---|
| Base | `supabase_single_session.sql` | table `public.user_sessions` + **index unique** (une session ouverte par compte) |
| Base | `supabase_mobile_rpc.sql` | toute écriture mobile est refusée si la session a été reprise ailleurs |
| Web | `web/src/api/sessionApi.js` | ouverture, battement de cœur, fermeture |
| Mobile | `mobile/src/api/sessionApi.js` | idem (miroir exact) |
| Desktop | `core/single_session.py` | idem via `app_desktop_session_*` (PySide6) ; refus + « Déconnecter l'autre appareil » dans `ui/views/login_view.py` |

Installation en base (idempotent) :

```bash
python _apply_single_session.py   # verrou + RPC de session
python _apply_mobile_rpc.py       # garde d'écriture dans les RPC métier
```

puis recharger le cache PostgREST (`python _reload_postgrest_cache.py`).

### Comment ça fonctionne

1. **Identité de session** : chaque session Supabase Auth porte un claim
   `session_id` (également présent dans `auth.sessions.id`). Il est **lu dans le
   jeton par le serveur** : un client ne peut pas déclarer une session qui n'est
   pas la sienne. Le desktop, sans JWT, transmet un UUID local (réservé au rôle
   technique de l'application, inaccessible à `authenticated`).
2. **Le verrou** : un index unique partiel (`user_id` où `ended_at IS NULL`)
   garantit au niveau base qu'une seule session peut être ouverte. La protection
   ne dépend pas du code applicatif.
3. **Battement de cœur** : chaque client prévient le serveur toutes les 60 s
   (mobile/web) ou 5 min (desktop). Une session sans battement depuis 15 min est
   réputée abandonnée (téléphone éteint, navigateur fermé, panne) et libérée
   automatiquement.
4. **Refus explicite** : la connexion affiche l'appareil déjà connecté
   (« application mobile (Android 13) — depuis 12 min ») et propose
   **« Déconnecter l'autre appareil et se connecter »**. L'autre session est
   alors fermée et se déconnecte d'elle-même au battement suivant (≤ 60 s).
5. **Déblocage administrateur** : `public.admin_revoke_sessions(email)` ferme les
   sessions d'un compte sans toucher au mot de passe.

### Robustesse (fail-open assumé)

* Réseau coupé ou RPC non installées → **jamais** de déconnexion ni de blocage :
  la protection ne doit pas devenir une panne qui empêche de travailler.
* Un client ancien (APK non mis à jour) n'appelle pas ces RPC : il n'est pas
  suivi et reste autorisé — la compatibilité ascendante est préservée.
* La **lecture** PostgREST d'une session déjà ouverte n'est pas bloquée si le
  client ignore la consigne de déconnexion ; en revanche toute **écriture**
  métier est refusée (`code: SESSION_CLOSED`).

### Logo (identité visuelle unique)

Le logo officiel est celui du logiciel de bureau : le **« K » turquoise**
affiché par son écran de connexion. C'est la **source de vérité** unique
(`ui/icons/logo.ico`).

Ni le web ni le mobile ne l'avaient jamais reçu : ils dessinaient une lettre
« K » en CSS/JSX, et l'icône Android gardait même le « A » générique d'Expo.
Tous les écrans sont désormais alignés.

```bash
python _sync_logo.py     # régénère toutes les déclinaisons
python _sync_logo.py --check   # inventorie sans rien écrire
python _planche_logo.py        # planche de contrôle visuelle (4 formes Android)
```

| Emplacement | Fichier | Rendu |
|---|---|---|
| Desktop (login, splash, `.exe`) | `ui/icons/logo.ico` | K turquoise sur blanc, multi-tailles |
| Web — écran de connexion | `web/public/icons/apple-touch-icon.png` | K turquoise sur blanc |
| Web — favicon / PWA | `web/public/icons/logo-16.png`, `logo-32.png` | idem |
| Mobile — boot + connexion | `mobile/assets/logo.png` (via `src/brand.js`) | K turquoise sur blanc |
| Mobile — splash | `mobile/assets/splash-icon.png` | silhouette **blanche** (fond bleu) |
| Android — icône du launcher | `android-icon-{foreground,background,monochrome}.png` | K turquoise sur fond bleu, zone de sûreté |
| Android — icône carrée | `mobile/assets/icon.png`, `favicon.png` | K turquoise sur blanc |

> **Après un changement de logo** : `python _sync_logo.py`, puis
> `cd mobile && npx expo prebuild` pour régénérer les icônes natives, puis
> **relancer `npx expo export:embed`** (voir 6.3 : `prebuild` efface le bundle
> embarqué), puis reconstruire l'APK. Sans `prebuild`, le launcher garde
> l'ancienne icône.
>
> ⚠️ **`npx expo prebuild` réécrit `mobile/android/local.properties` et
> `mobile/android/gradle.properties`**, qui ne sont pas versionnés. Après un
> prebuild, le build échoue sur `SDK location not found` et repart sur les
> réglages par défaut (les 4 architectures, `parallel=true`, 2 Go de RAM) :
> **il faut les recréer** (valeurs en 6.4). Un build qui n'échoue pas mais
> dure 1 h au lieu de 4 min est le symptôme de ces réglages perdus.
>
> La couche `foreground` Android ne contient **que le K détouré** : le `.ico`
> d'origine embarque un carré blanc opaque qui flotterait visiblement sur les
> lanceurs ronds. Le K est réduit à 58 % de la toile pour survivre au rognage
> circulaire des Brumelames, losanges et carrés arrondis.

---

## 5. Vérifications effectuées

* Analyse statique : chaque fichier `src/**/*.js` a été transformé par
  `esbuild --loader:.jsx=jsx` (aucune erreur de syntaxe).
* Les RPC ont été comparées ligne à ligne avec la logique existante :
  `ui/views/sale_services.py` (vente), `core/invoice_register_manager.py`
  (règlement), `ui/views/stock_view.py` (mouvements), `web/src/api/salesApi.js`.
* Matrice de permissions comparée à `core/permissions.py` (7 rôles/19 clés) et
  répliquée dans `supabase_mobile_rpc.sql` (`app_security.can`).

À tester manuellement une première fois (nécessite `.env` + SQL appliqué) :
connexion caissier, vente espèces avec monnaie rendue, vente à crédit,
règlement partiel, entrée/sortie de stock, refus d'un montant supérieur au
reste dû.

### 5.1 Contrôles automatisés (à relancer après toute modification)

| Commande | Ce qu'elle prouve |
|---|---|
| `python _check_mobile_rpc_sql.py` | variable locale non déclarée + colonnes citées inexistantes — **avant** tout déploiement |
| `python _dry_run_mobile_rpc.py` | le SQL des RPC s'applique (transaction annulée) et refuse un appel non authentifié |
| `python _test_mobile_rpc_live.py` | vente réelle par rôle, avec stock / trésorerie / `sale_logs` vérifiés (transaction annulée) |
| `python _check_mobile_matrix.py` | matrice de droits identique entre `core/permissions.py`, le SQL et `src/lib/permissions.js` |
| `python _test_single_session.py` | verrou multi-appareils : refus, reprise, expiration, garde d'écriture, chemin desktop (transaction annulée) |
| `python _diag_user_sessions.py` | structure de `auth.sessions` + présence réelle du claim `session_id` dans un JWT |
| `npm run test:rpc` (dans `mobile/`) | les 4 RPC sont effectivement résolues par PostgREST (sinon `PGRST202`) |
| `npm run check` (dans `mobile/`) | syntaxe, imports et références du code mobile |

> Une fonction PL/pgSQL est créée même si son corps contient une variable
> inexistante : l'erreur n'apparaît qu'à la première vente. D'où le contrôle
> statique de la première ligne, qui a déjà rattrapé un `v_currency` manquant.

---

## 6. Construire et installer l'application (APK 100 % autonome)

### 6.1 APK produit disponible (prêt à installer)

Un APK autonome (contenant tout le code JavaScript, les assets et les composants natifs arm64-v8a) a été compilé avec succès :

```
mobile\dist\korgo-pro-terrain-standalone.apk (72,6 Mo / 76 075 901 octets, reconstruit le 29/09/2026 à 18:18)
```

Cette version embarque :
* le **nouveau logo « K » turquoise** issu de `ui/icons/logo.ico` (voir
  « Identité visuelle : une seule source de logo ») : écran de connexion, splash,
  icône du launcher Android, icône carrée et favicon ;
* les **animations de validation** (voir « Animations de validation (retour
  utilisateur) ») : `SuccessOverlay`, coche animée, bandeaux animés, pulsation
  des totaux ;
* la **session unique** (voir « Session unique : un seul appareil connecté par
  compte ») : la connexion est refusée si le compte est déjà ouvert sur un autre
  appareil, avec un bouton « Déconnecter l'autre appareil et se connecter », et
  l'application se ferme d'elle-même si le compte est repris ailleurs.

> Après chaque reconstruction, relancez `python _check_apk_bundle.py` (dans
> `mobile/`) : il vérifie que le bundle embarqué contient bien la session unique
> et les animations. Un APK reconstruit **sans** regénérer les assets JS
> compilerait sans erreur tout en embarquant l'ancien code.

**Cet APK fonctionne à 100 % sur un smartphone Android sans ordinateur ni serveur Metro.**

### 6.2 Comment l'installer sur un smartphone Android

#### Option A — Transfert direct (recommandé et rapide)
1. Copiez le fichier `mobile\dist\korgo-pro-terrain-standalone.apk` sur votre smartphone (via câble USB, WhatsApp, Telegram, Google Drive, carte SD...).
2. Sur votre smartphone, ouvrez le fichier avec le gestionnaire de fichiers.
3. Si le système vous avertit, activez l'autorisation **« Installer des applications inconnues »** pour votre gestionnaire de fichiers.
4. Cliquez sur **Installer** puis ouvrez **Korgo Pro Terrain**.

#### Option B — En ligne de commande (câble USB avec débogage USB activé)
```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r mobile\dist\korgo-pro-terrain-standalone.apk
```

---

### 6.3 Procédure pour régénérer l'APK autonome après des modifications de code

Quand vous modifiez le code JavaScript/React (`App.js`, `src/...`) et voulez régénérer l'APK autonome :

```powershell
cd mobile

# 1. Générer le bundle JS autonome dans les assets de l'application
npx expo export:embed --entry-file index.js --platform android --dev false --reset-cache --bundle-output android/app/src/main/assets/index.android.bundle --assets-dest android/app/src/main/res

# 2. Reconstruire l'APK signé
cd android
.\gradlew.bat assembleDebug --console=plain

# 3. Récupérer l'APK produit
Copy-Item .\app\build\outputs\apk\debug\app-debug.apk ..\dist\korgo-pro-terrain-standalone.apk
```

### 6.4 Réglages mémoire et environnement

Ces deux fichiers ne sont **pas** versionnés (ils décrivent votre machine) et
`npx expo prebuild` les réécrit. À recréer après tout prebuild, sinon Gradle
échoue sur `SDK location not found`.

`mobile/android/local.properties` :

```properties
sdk.dir=C:/Users/HP/AppData/Local/Android/Sdk
```

`mobile/android/gradle.properties` — corriger les 4 lignes ci-dessous (le
prebuild remet les valeurs Expo par défaut) :

```properties
org.gradle.jvmargs=-Xmx1536m -XX:MaxMetaspaceSize=512m
org.gradle.parallel=false
org.gradle.workers.max=1
reactNativeArchitectures=arm64-v8a
kotlin.compiler.execution.strategy=in-process
```

- JDK 21 LTS : `C:\Program Files\Android\openjdk\jdk-21.0.8` (évite les bugs Prefab de JDK 24+)
- Android SDK : `C:\Users\HP\AppData\Local\Android\Sdk`
- Architecture ciblée : `arm64-v8a` (divise par 4 le temps de compilation native)
- Mémoire JVM : `-Xmx1536m -XX:MaxMetaspaceSize=512m` avec `parallel=false`,
  un seul worker et compilation Kotlin `in-process` : sur cette machine ~8 Go,
  le build complet (bundle inclus) prend ~4 min ; avec les valeurs par défaut
  du prebuild il dépasse 1 h.
- Penser à utiliser le JDK 21 pour Gradle :
  `$env:JAVA_HOME='C:\Program Files\Android\openjdk\jdk-21.0.8'`

> Ordre obligatoire après une modification de logo **ou** de code :
> `_sync_logo.py` (optionnel) → `npx expo prebuild` → `npx expo export:embed`
> → `gradlew assembleDebug`. `prebuild` efface le bundle embarqué, donc
> `export:embed` doit **toujours** passer après.


---

## 7. Limites connues et suites possibles

* **Hors-ligne** : l'application exige le réseau (aucune file d'attente
  d'écritures). Une vente hors-ligne doit attendre la reconnexion. Prochaine
  étape naturelle : file d'attente locale (AsyncStorage/SQLite) + rejeu des RPC.
* **Impression de reçu** : absente (le desktop utilise reportlab/QPrinter). À
  ajouter via génération PDF + partage, ou une imprimante thermique
  Bluetooth (ESC/POS).
* **Scan de code-barres** : la recherche accepte déjà un code-barres saisi au
  clavier ; l'appareil photo (`expo-camera`) reste à brancher.
* **Modification de produits/clients** : volontairement hors périmètre du
  mobile (desktop/web s'en chargent) ; l'inventaire se limite aux mouvements.
* **Renommage de colonnes** : si `core/models/*.py` évolue, mettre à jour
  `src/api/dataApi.js` (noms de colonnes) et `supabase_mobile_rpc.sql`.
