# Korgo Pro — Prototype React + Tauri

Prototype desktop Korgo Pro construit avec **React 18 + Vite** côté frontend
et **Rust + Tauri 2** côté desktop. Les treize sections principales sont
accessibles depuis la navigation : tableau de bord, caisse, clients, factures,
rapports de ventes, pro formas, stock, fournisseurs, achats, trésorerie, magasins,
administration et paramètres.

> **État actuel : prototype partiellement connecté.** L’authentification,
> l’isolation par entreprise et plusieurs opérations métier utilisent Supabase.
> La parité avec l’application PySide6 reste incomplète ; vérifiez les limites
> de chaque écran avant d’utiliser l’application pour les opérations réelles.

---

## 📁 Structure du projet

```
tauri-prototype/
├── src-tauri/
│   ├── Cargo.toml          # Dépendances Tauri
│   ├── tauri.conf.json     # Configuration du shell Tauri
│   └── src/
│       ├── main.rs         # Point d'entrée Tauri; mocks Rust inactifs
│       ├── db.rs           # Base de démonstration en mémoire
│       └── commands.rs     # Commandes Tauri (db_*, auth_*)
└── web/                      # Frontend React + Vite
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.jsx         # Bootstrap (AuthProvider, Router)
        ├── App.jsx          # Routes
        ├── api/businessApi.js # Accès métier Supabase et RPC Tauri
        ├── api/tpgDb.js       # Ancien client mock Tauri
        ├── components/      # Composants UI partagés
        ├── context/
        ├── data/demoData.js # Données fictives de démonstration
        └── pages/           # Vues de l’application
```

---

## 🧱 Prérequis

- **Node.js** ≥ 18 (déjà installé : v22.17.0)
- **npm** (≥ 9)
- **Rust + Cargo** (toolchain `stable-x86_64-pc-windows-msvc`)
- **Visual Studio C++ Build Tools** avec le compilateur MSVC et le Windows SDK
- **WebView2 Runtime** (normalement présent sur Windows 10/11)
- **Tauri CLI** (installée avec npm dans `web`)

---

## 🔧 Installation & lancement

### 1. Installer Rust (si absent)
```powershell
invoke-webrequest -Uri https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe -OutFile rustup-init.exe
.\rustup-init.exe -y
refreshenv
```

### 2. Configurer l'environnement MSVC
Depuis le dossier `tauri-prototype`, dans le terminal PowerShell qui servira
au lancement :
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-env.ps1
```
Cette autorisation ne vaut que pour ce processus PowerShell. Le script detecte
Visual Studio, initialise les chemins MSVC de la session et confirme que
`cl.exe` et `link.exe` sont disponibles. Apres `npm install`, lancez Tauri
comme indique a l'etape 5. Le mode direct est aussi disponible avec
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-env.ps1 -Mode dev`
(remplacez `dev` par `build` pour compiler l'installeur NSIS).

### 3. Installer les dépendances du frontend
```powershell
cd tauri-prototype\web
npm install
```

### 4. Supabase

Le frontend Tauri réutilise la configuration publique de `web/.env`
(`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` ou
`VITE_SUPABASE_PUBLISHABLE_KEY`, et `VITE_SUPABASE_SCHEMA`) sans recopier ses
valeurs dans le prototype. Seule la clé publique est utilisée : ne placez
jamais `DATABASE_URL`, une clé `service_role` ou un mot de passe dans le
frontend ou dans le bundle de l’application.

La connexion accepte l’adresse e-mail ou le nom d’utilisateur du compte
Supabase Auth via la fonction `login-with-identifier`. Déployez-la avec la
Supabase CLI depuis la racine du dépôt après avoir lié le projet (`supabase
login`, puis `supabase link --project-ref <project-ref>`) :
`supabase functions deploy login-with-identifier`. La connexion par e-mail
continue d’utiliser directement Supabase Auth ; le déploiement est requis pour
la connexion par nom d’utilisateur. La fonction utilise la clé de service
uniquement côté serveur pour résoudre le nom ; elle n’est jamais intégrée à
l’application. Le profil actif est ensuite lu avec la session de l’utilisateur,
donc sous les règles RLS. Les vues caisse, factures, pro formas, stock,
trésorerie, administration et paramètres utilisent les appels Supabase
disponibles dans `web/src/api/businessApi.js` et les RPC de
`supabase_tauri_business.sql`. Certaines opérations de ces vues ne sont pas
encore implémentées : consultez les actions disponibles à l’écran et ne
supposez pas que toutes les fonctions PySide6 sont portées.

La caisse enregistre maintenant le montant reçu en espèces et calcule la
monnaie à rendre. Le paiement différé accepte un acompte et inscrit le solde
restant comme crédit client ; le RPC refuse un règlement incomplet déclaré
avec un autre mode de paiement. Toute somme restant due exige un client dont
la limite de crédit couvre le nouveau solde. Les pro formas Tauri exigent un
client actif; la conversion revérifie sa limite avant de créer la facture.

Pour activer les outils d’administration, appliquez
`supabase_tauri_business.sql` au projet Supabase (par exemple dans le SQL
Editor), puis déployez la fonction Edge ci-dessous.

Le menu Clients utilise aussi les RPC `app_tauri_save_customer` et
`app_tauri_set_customer_active` du même script. Appliquez la version courante
du script avant d'activer cette vue. La désactivation conserve les factures,
les paiements et l'historique du client.

Le thème d’affichage des paramètres s’applique à l’ensemble des écrans Tauri.
Le choix « Système » suit le thème clair ou sombre du système d’exploitation.

La vue Magasins permet aux rôles `manage_stores` de créer et modifier les
magasins, ainsi que de réactiver ou désactiver les magasins vides. Le premier
magasin devient le magasin par défaut pour les anciennes données sans
affectation; le magasin par défaut, tout magasin avec du stock et tout magasin
avec ventes ou mouvements d’inventaire ne peuvent pas être désactivés.

La gestion du catalogue utilise aussi les RPC `app_tauri_update_product` et
`app_tauri_set_product_active`. La désactivation d'un produit exige un stock
nul ; les mouvements sont conservés et ne peuvent pas être modifiés par le
formulaire de fiche produit.

La section Fournisseurs permet de créer, modifier, désactiver et réactiver les
fiches de l'entreprise active. Elle est réservée aux utilisateurs ayant la
permission `manage_stock`; les codes fournisseurs restent uniques au sein de
chaque entreprise. Les produits peuvent être reliés à un fournisseur actif;
la fiche conserve un lien déjà existant même si le fournisseur est désactivé.

La section Achats permet de créer une commande auprès d'un fournisseur actif,
de l'annuler avant toute réception et d'enregistrer plusieurs réceptions
partielles. Chaque réception met à jour le stock du magasin actif et crée un
mouvement d'inventaire avec le coût et la référence de commande. Les RPC
`app_tauri_create_purchase_order`, `app_tauri_receive_purchase_order` et
`app_tauri_cancel_purchase_order` sont définies dans le script métier; elles
nécessitent `manage_stock`. Une commande entièrement réceptionnée peut être
réglée en plusieurs fois par un utilisateur ayant `manage_treasury`. Chaque
paiement crée une sortie liée à la commande dans le journal de trésorerie,
déduit le compte choisi et vérifie le montant restant ainsi que le solde
disponible. Le RPC `app_tauri_pay_purchase_order` utilise le mode de paiement
et les notes dans le libellé du mouvement. La vue Trésorerie permet également
de créer des comptes de caisse, de banque et de mobile money, avec un solde
initial et un compte par défaut. La création exige `manage_treasury`; la devise
du compte est reprise de celle de l’entreprise active.
La trésorerie affiche l’aperçu des ventes, encaissements, crédits et dépenses
du mois courant et conserve les clôtures mensuelles. La clôture est réservée à
`manage_treasury`; ses totaux et soldes sont figés dans `monthly_closures`.

Le registre des factures permet aussi l'annulation d'une vente aux rôles qui
ont `cancel_sales`. Un motif est obligatoire ; le RPC restaure le stock,
compense les encaissements sur leurs comptes d'origine, recalcule le crédit
client et conserve la vente ainsi que son journal d'audit.

La vue Administration permet, après déploiement des RPC de
`supabase_tauri_business.sql`, d’associer un compte Auth existant, d’inviter un
utilisateur par courriel, d’envoyer un lien de réinitialisation de mot de
passe, de modifier son rôle ou son accès, et de le retirer de l’entreprise
active sans supprimer son compte Auth. Elle expose aussi les journaux
filtrables, le nettoyage des journaux système de plus de 30 jours et une
matrice de permissions modifiable par entreprise. ADMIN conserve les
permissions `manage_users` et `manage_database`; elles ne peuvent pas être
accordées à un autre rôle.

L’invitation et la réinitialisation nécessitent le déploiement de la fonction
Edge `admin-user-management` depuis la racine du dépôt :
`supabase functions deploy admin-user-management`. Vérifiez la configuration
du courriel d’invitation et du lien de réinitialisation dans Supabase Auth;
`PASSWORD_RESET_REDIRECT_URL` peut être défini comme secret de la fonction
pour personnaliser la redirection. La clé `service_role` n’est utilisée que
côté serveur. Le retrait d’un membre ne supprime ni son compte Auth ni ses
appartenances à d’autres entreprises.

L’onglet Base de données propose une consultation en lecture seule des tables
métier autorisées, filtrées sur l’entreprise active, jusqu’à 200 lignes par
page. Il n’expose ni requête SQL libre ni `VACUUM`. Le nettoyage concerne
uniquement les journaux système de l’entreprise active et est irréversible.

La sauvegarde/restauration JSON globale est disponible après déploiement des
fonctions `app_tauri_can_manage_all_database`, `app_tauri_export_all_data` et
`app_tauri_restore_all_data` du même fichier SQL. L’utilisateur doit être
ADMIN actif de **toutes** les entreprises, y compris les entreprises inactives.
Les opérations verrouillent temporairement les écritures métier. Une
restauration remplace les données des tables métier ayant `organization_id`,
dans une transaction ; elle exige que le fichier corresponde exactement au
même ensemble d’entreprises et au schéma courant. Les profils, membres,
entreprises et journaux système sont préservés. Avant de restaurer, l’interface
télécharge une sauvegarde de sécurité et demande une confirmation explicite.
La restauration accepte uniquement les sauvegardes JSON créées par cette
fonction Tauri, pas les anciens fichiers SQLite/PySide. Les fichiers JSON ne
sont pas chiffrés : conservez-les dans un emplacement sûr.
Les requêtes SQL arbitraires et l’envoi de sauvegardes à un service tiers ne
sont pas exposés dans l’application.

### 5. Lancer le prototype
```powershell
.\web\node_modules\.bin\tauri.cmd dev
```
Depuis le dossier `tauri-prototype`, cette commande démarre Vite et ouvre
l'application dans une fenêtre desktop Tauri. Pour compiler l'application,
utilisez `.\web\node_modules\.bin\tauri.cmd build`.

---

## 📡 Anciennes commandes Tauri (désactivées)

Ces anciens mocks Rust ne sont pas enregistrés par `main.rs`. Ils restent dans
les sources pour référence et ne sont pas utilisés par les écrans de
l'application. L'authentification Supabase JS décrite plus haut est le seul
parcours de connexion actif.

---

## ⚠️ Notes

- Les données métier chargées ou créées par les opérations raccordées sont
  conservées dans Supabase ; les interactions non raccordées ne doivent pas
  être considérées comme persistantes.
- Le registre des factures propose un aperçu imprimable et l'enregistrement
  au format PDF via la boîte de dialogue d'impression du système.
- Le rapport des ventes filtre les factures par dates, magasin et recherche,
  calcule le chiffre d'affaires hors annulations, les encaissements et les
  soldes restant dus, puis exporte les lignes filtrées en CSV.
- La parité avec PySide6 reste partielle, notamment pour les retours et
  remboursements de ventes, les rapports
  de marge et d'inventaire et plusieurs paramètres de facturation. L’administration Tauri expose les opérations
  documentées ci-dessus; les requêtes SQL libres, `VACUUM` et les exports vers
  des services tiers restent volontairement indisponibles.

- Les pro formas peuvent aussi etre imprimees, changer de statut et, apres
  acceptation, etre converties en facture. La creation accepte plusieurs
  produits et fige les prix du catalogue dans chaque ligne. La conversion
  controle le stock du
  magasin choisi, conserve les prix du devis, met a jour le stock et le solde
  client, et garde le lien vers la pro forma source. Elle requiert les RPC
  `app_tauri_set_proforma_status` et `app_tauri_convert_proforma` du script SQL.

Les vues factures, pro formas, stock et tresorerie proposent aussi un export
CSV local pour les roles disposant de `export_data`. Les exports reprennent la
liste filtree de l'ecran courant et ne transmettent pas les fichiers a un tiers.

## Note sur le runtime (20 novembre 2026)

Le point d'entree Rust demarre uniquement la fenetre Tauri et le plugin opener.
Il n'enregistre pas les anciennes commandes de `src-tauri/src/commands.rs` :
elles utilisent un mock en memoire et ne doivent jamais recevoir de donnees
reelles. L'authentification et les operations metier actives passent par
Supabase JS et les RPC `app_tauri_*`, sous les politiques RLS. La CSP desktop
autorise les connexions HTTPS et WebSocket vers `*.supabase.co`.
