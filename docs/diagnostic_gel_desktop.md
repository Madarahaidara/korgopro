# Diagnostic — gel d'écran du desktop (Korgo Pro)

**Date :** 30/09/2026 · **Périmètre :** application PySide6 (`main.py`, `ui/views/*`)

## 1. Symptôme

La fenêtre du desktop se fige (« Ne répond pas » sous Windows) :

* après la connexion (l'écran de login reste affiché et ne répond plus plusieurs secondes) ;
* périodiquement sur le tableau de bord (toutes les 30 s) ;
* pendant la frappe dans les zones de recherche (Registre des factures, Pro Forma, Stock) ;
* au démarrage de l'application (rien ne s'affiche avant le splash) ;
* parfois longuement, sans retour possible, si le réseau est coupé.

## 2. Mécanisme

```
Clic / frappe / timer
   └─► slot Qt (thread UI)                     ← la boucle d'événements est ARRÊTÉE
        └─► SQLAlchemy ──► TCP/TLS ──► pooler Supabase (eu-west-1)
             └─► attend la réponse (≈147 ms par aller-retour, 9,6 s à la 1re connexion)
```

Qt ne peut ni repeindre la fenêtre ni traiter les clics tant que le slot n'est pas
revenu. **Chaque requête exécutée dans le thread UI = un gel d'au moins un
aller-retour réseau.** Les vues créent leurs requêtes dans leur constructeur, dans
les callbacks de leurs widgets et dans des `QTimer` : tout est donc exécuté sur le
thread UI.

Le projet connaît déjà ce mécanisme — voir le commentaire de `DbInfoWorker`
(`ui/views/admin_view.py:50-55`) : « *Sur PostgreSQL/Supabase, get_database_info()
fait plusieurs allers-retours réseau ; l'exécuter dans le thread UI gelait
l'interface (« Ne répond pas »)* ». Le correctif n'a été appliqué qu'à cet écran.

## 3. Mesures réelles (poste de développement, 30/09/2026)

Latence mesurée vers la base (script `_diag_db_latency.py`, lecture seule) :

| Mesure | Valeur |
| --- | --- |
| Cible | `aws-1-eu-west-1.pooler.supabase.com:5432` (PostgreSQL) |
| Ouverture d'une connexion (pool vide) | **9 618 ms** |
| 1er `SELECT 1` (pool_pre_ping inclus) | 316 ms |
| `SELECT 1` suivants | 172, 140, 140, 140, 142 ms → **147 ms de moyenne** |

Nombre de requêtes par écran + temps de thread UI gelé, mesurés avec
`_diag_freeze_desktop.py --rtt-ms 147` (base SQLite jetable, latence réelle
simulée) :

| Étape | Requêtes | Gel mesuré | Commentaire |
| --- | --- | --- | --- |
| `Base.metadata.create_all` (démarrage) | 24 | **3,5 s** | avant même l'affichage du splash |
| `ensure_default_store` (démarrage) | 6 | **0,9 s** | |
| `MainWindow` (connexion : 8 vues construites) | ~120 | **14,9 s** | `main.py:73-88` |
| Tableau de bord — timer 30 s (`refresh_data`) | 7 | **1,0 s / 30 s** | `dashboard_view.py:39-41` |
| `StockView` (ouverture / refresh) | 42 | **6,2 s** | `stock_view.py:96`, `4025` |
| Registre des factures — 1 frappe | 3 | **0,45 s / caractère** | `invoice_register_view.py:99` |
| Pro Forma — 1 frappe (recherche) | 1 | **0,15 s / caractère** | `proforma_invoice_view.py:1831` |
| Stock — 1 frappe (recherche) | 1 | **0,15 s / caractère** | `stock_view.py:1724 → 3173` |
| Battement de session — toutes les 5 min | 3 | **0,4 s / 5 min** | `main_window.py:100-102` |

Autrement dit : **~20 s de gel cumulé entre le lancement et l'ouverture de la
session** (3,5 + 0,9 + 14,9), auxquelles s'ajoute une connexion à 9,6 s si le pool
est vide (démarrage à froid, retour de veille, coupure réseau).

> **Précisions de mesure.** Les compteurs ci-dessus proviennent d'un écouteur
> SQLAlchemy (`before/after_cursor_execute`) : ils incluent le `SELECT 1` du
> `pool_pre_ping` à chaque sortie de connexion du pool (d'où de légères variations
> entre deux exécutions) et les requêtes des workers déjà existants
> (`ProductLoaderThread`, `DbInfoWorker`) qui, elles, **ne gèlent pas** l'écran —
> c'est pourquoi la colonne « Gel mesuré » est inférieure à `requêtes × 147 ms`
> sur la ligne `MainWindow` (~100 requêtes réellement sur le thread UI).



## 4. Causes, classées par gravité

### C1 — Critique : les 8 vues sont construites sur le thread UI à la connexion
`ui/views/main_window.py:262-286` instancie **toutes** les vues autorisées dans la
boucle de `_build_ui`, elle-même appelée par le constructeur de `MainWindow`, lui-même
appelé par le slot `on_login_success` (`main.py:73-88`) — donc sur le thread UI.
Chaque constructeur interroge la base :

| Vue | Requêtes sur le thread UI | Fichier |
| --- | --- | --- |
| `DashboardView` | 11 (dont `load_real_data` + `debug_sales_data`) | `dashboard_view.py:33-41`, `440-487` |
| `SaleView` | 27 (`load_filters`, `load_customers`, `generate_sale_number`) | `sale_view.py:146-149` |
| `InvoiceRegisterView` | 3-6 (`refresh`) | `invoice_register_view.py:68-69` |
| `EnhancedProformaInvoiceView` | 2 (`load_proformas`) | `proforma_invoice_view.py:1800-1801` |
| `StockView` | 42 (`load_data` + `init_ui`) | `stock_view.py:96` |
| `TreasuryView` | 4 | `treasury_view.py:15-22` |
| `AdminView` | 18-20 (`load_users_from_db`, `load_users`, `log_activity`) | `admin_view.py:121`, `179-180` |
| `SettingsView` | 0-1 | `settings_view.py:297-299` |

S'y ajoute l'import différé de `QtCharts` dans `DashboardView.setup_chart()`
(`dashboard_view.py:329`), mesuré à **1,3 s** sur ce poste, exécuté lui aussi sur
le thread UI.

### C2 — Critique : aucun garde-fou réseau (gel potentiellement illimité)
`core/database.py:56-64` ne définit ni `connect_timeout`, ni `statement_timeout`,
ni `pool_timeout` :

* une connexion perdue force `pool_pre_ping` à reconnecter → mesuré **9,6 s** ;
* si l'hôte ne répond plus (Wi-Fi coupé, veille), libpq attend la retransmission
  TCP de Windows (**≈21 s**, voire davantage) sans que l'utilisateur puisse
  interrompre ;
* une requête qui attend un verrou côté serveur (autre poste en écriture, session
  mobile/web) bloque la fenêtre **sans limite** : PostgreSQL n'applique
  `statement_timeout` par défaut (`0` = illimité) et SQLAlchemy n'en pose pas.

C'est le « gel long » irrécupérable ; les autres causes produisent des gels courts
et répétés.

### C3 — Élevé : requêtes à chaque frappe
* `ui/views/invoice_register_view.py:99` → `textChanged` → `refresh()` → 3 requêtes
  (`list_invoices` = 1 `SELECT` l. 47 ; `get_register_summary` = 2 agrégats
  l. 100 et 108), mesurées à **457 ms par caractère** avec 147 ms d'aller-retour.
* `ui/views/proforma_invoice_view.py:1831` → `textChanged` → `apply_filters` →
  `load_proformas()` → `service.list_proformas()` (l. 1911-1922).
* `ui/views/stock_view.py:1724` → `textChanged` → `filter_products()` →
  `update_stats()` → `self.db_session.query(Expense).all()` (l. 2040-2041, 3173)
  alors que le filtrage lui-même est en mémoire.

À 147 ms d'aller-retour, la saisie devient saccadée (0,15 à 0,3 s par caractère).

### C4 — Élevé : rafraîchissements périodiques côté UI
* `dashboard_view.py:39-41` : `QTimer` 30 s → `refresh_data()` → 7 requêtes →
  **1 s de gel toutes les 30 s**, en permanence, même si l'utilisateur travaille
  sur un autre écran (la vue reste vivante dans le `QStackedWidget`).
* `main_window.py:100-102` : `QTimer` 5 min → `check_single_session()` →
  `single_session.touch()` → `_call()` (`core/single_session.py:59-71`) qui ouvre
  une `SessionLocal` et fait `SELECT` **+ `COMMIT`** (2-3 allers-retours, ~0,4 s).

### C5 — Moyen : attentes bloquantes dans les slots Qt
* `sale_view.py:1031-1032` + `sale_widgets.py:149-151` :
  `ProductLoaderThread.stop()` appelle `quit()` puis **`wait(1000)`** depuis le
  thread UI. `run()` n'exécute pas de boucle d'événements, donc `quit()` est sans
  effet : le thread UI attend jusqu'à **1 s** la fin de la requête en cours.
* `core/database.py` : absence de `pool_timeout` → une connexion peut être
  attendue indéfiniment quand toutes celles du pool sont occupées.

### C6 — Moyen : session SQLAlchemy partagée entre threads
`ProductLoaderThread` reçoit le `ProductService` construit avec la session du
thread UI (`sale_view.py:135` → `sale_widgets.py:136-147`) : la même connexion
psycopg2 est utilisée par deux threads. Une session SQLAlchemy n'est pas thread-safe ;
les symptômes vont de l'erreur « *another command is already in progress* » au
blocage silencieux. Même remarque pour les autres workers qui réutilisent un
service du thread UI (`DbInfoWorker`, `DiscordBackupWorker`).

### C7 — Faible : démarrage avant tout affichage
`main.py:29-41` exécute `Base.metadata.create_all` (24 requêtes) puis
`ensure_default_store` (6 requêtes) **avant** la création du splash (`main.py:50`) :
pendant ~4,5 s l'utilisateur ne voit rien, ce qui ressemble à un démarrage
« qui ne démarre pas ». Un `StartupWorker(QThread)` existe déjà
(`core/startup_manager.py`) mais n'est pas utilisé (code mort, cf.
`RAPPORT_LOGICIEL_KORGO_PRO.txt:139`).

### C8 — Faible : bruit de diagnostic
`dashboard_view.py:440-487` (`debug_sales_data`, 4 requêtes + nombreux `print`)
et les `print()` de `load_chart_data` s'exécutent à chaque construction de la vue
et à chaque rafraîchissement.


## 5. Plan de correction (par impact/effort)

### P0 — à faire en premier (supprime 90 % du gel ressenti)

**P0.1 — Borner le réseau (`core/database.py:56-64`).** Convertit le gel illimité
en erreur contrôlée : c'est le seul correctif qui protège des coupures réseau.

```python
    statement_timeout = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "15000"))
    return create_engine(
        url,
        echo=_echo,
        pool_pre_ping=True,
        pool_recycle=int(os.environ.get("DB_POOL_RECYCLE", "300")),  # pooler Supabase
        pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT", "10")),
        pool_size=..., max_overflow=...,
        connect_args={
            "sslmode": os.environ.get("DB_SSLMODE", "require"),
            "connect_timeout": int(os.environ.get("DB_CONNECT_TIMEOUT", "10")),
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3,
            "options": f"-c statement_timeout={statement_timeout}",
        },
    )
```

> `statement_timeout` doit rester configurable (`0` = désactivé) : les exports et
> sauvegardes longues (`core/database_manager.py`) utilisent le même moteur.
> Prévoir un `try/except OperationalError` autour des rafraîchissements pour
> afficher « Connexion lente, réessayez » au lieu de figer.

**P0.2 — Construire les vues à la demande (`ui/views/main_window.py:262-286`).**
Le tableau de bord reste la seule vue construite à la connexion ; les autres le
sont au premier clic. Gain mesuré : **120 → ~11 requêtes au login** (~15 s → ~1,6 s).

```python
        self.views = {}
        self._factories = factories
        for attr, permission, view_attr, title in MENU_ENTRIES:
            button = getattr(self, attr)
            if not (view_attr == "dashboard_view" or can(role, permission)):
                continue
            if view_attr == "dashboard_view":       # écran d'accueil : immédiat
                self._show_view(view_attr, title)
            button.clicked.connect(
                lambda _c=False, k=view_attr, t=title: self._show_view(k, t))
        ...
    def _show_view(self, key, title):
        """Construit la vue au premier affichage (hors chemin de connexion)."""
        view = self.views.get(key)
        if view is None:
            view = self._factories[key]()
            self.views[key] = view
            self.stack.addWidget(view)
        self._switch_view(view, title)
```

Adapter `_check_and_switch_to_settings` (l. 305-320), qui lit
`self.views.get("settings_view")`, et le corps de `_apply_role_permissions`.

**P0.3 — Sortir les requêtes du thread UI** (même patron que `DbInfoWorker`,
`admin_view.py:50-68`) :

| Cible | Traitement |
| --- | --- |
| `dashboard_view.refresh_data` (l. 704) | worker + signal `finished(dict)` ; le `QTimer` 30 s ne fait que lancer le worker |
| `main_window.check_single_session` (l. 104) | worker (le battement n'a aucun besoin d'être synchrone) |
| `invoice_register_view.refresh` (l. 132) | worker + `QTimer` de debounce 300 ms avant le lancement |
| `proforma_invoice_view.load_proformas` (l. 1921) | idem (debounce) |
| `admin_view.refresh_data` / onglets (l. 2375, 664, 916) | worker |

**P0.4 — Ne plus bloquer sur `wait()` (`sale_widgets.py:149-151`).** Supprimer
`stop()`/`wait(1000)` du slot ; ignorer les résultats périmés avec un compteur de
génération (`self._load_id += 1` dans `load_products_async`, comparé dans
`on_products_loaded`), comme le fait déjà `ProductLoaderThread` avec ses signaux.

### P1 — supprime le gel résiduel

* **`stock_view.ensure_default_expense_categories` (l. 452-479)** : 9 `SELECT` +
  `commit` à chaque `load_data` → remplacer par **1 `SELECT name`** + insertion des
  seuls manquants, et n'exécuter ce contrôle **qu'au premier lancement**
  (drapeau dans `SettingsManager`).
* **`stock_view.update_stats` (l. 3152-3174)** : `query(Expense).all()` → agrégat
  SQL (`func.coalesce(func.sum(Expense.amount), 0)`), et **retirer
  `update_stats()` de `filter_products()`** (l. 2041) : le filtrage ne doit pas
  toucher la base.
* **`stock_view.refresh_data` (l. 4025-4033)** : passer en worker.
* **Session par thread (C6)** : chaque `QThread` crée sa propre `SessionLocal`
  dans `run()` (le service est reconstruit sur place) au lieu de recevoir un
  service du thread UI.
* **Démarrage (C7)** : afficher le splash avant `create_all`/`ensure_default_store`,
  ou déplacer ces deux appels dans `StartupWorker` (`core/startup_manager.py`,
  aujourd'hui inutilisé).
* **`main.py:29`** : `create_all` fait 24 requêtes d'inspection à chaque lancement →
  ne l'exécuter que si le schéma doit être créé (`update_db_schema.py`/`alembic`
  couvrent déjà les migrations).

### P2 — confort

* Supprimer `debug_sales_data` (`dashboard_view.py:440-487`) et les `print()` de
  `load_chart_data`.
* `AdminView` : ne charger `load_real_activities` / `load_sale_logs` /
  `load_table_data` qu'à l'ouverture de l'onglet concerné (aujourd'hui l. 664,
  916, 1294 et 179-180 dans le constructeur).
* Paginer ou limiter les `SELECT` « tous les enregistrements »
  (`StockView.load_data` charge tout le catalogue avec `joinedload(supplier)`).

## 6. Vérification

Deux scripts de mesure sont fournis (aucune écriture en production) :

```powershell
# 1) Requêtes SQL par ecran + temps de thread UI gele (base SQLite jetable)
python _diag_freeze_desktop.py --rtt-ms 147

# 2) Latence reseau reelle vers Supabase (SELECT 1, lecture seule)
python _diag_db_latency.py
```

Objectif après correction : **`MainWindow (login)` ≤ 11 requêtes**, **aucun écran
avec plus de 1-2 requêtes sur le thread UI**, et un gel borné à
`DB_CONNECT_TIMEOUT` en cas de coupure réseau. Relancer les deux scripts avant et
après chaque lot de correctifs pour objectiver le gain.

### Suivi des correctifs P0 (mesures du 30/09/2026)

| État | Correctif | Avant | Après |
| --- | --- | --- | --- |
| ✅ P0.1 | Garde-fous réseau `core/database.py` (`connect_timeout`, keepalives, `statement_timeout=60 s`, `pool_recycle`, pool paramétrable) | requête bloquée à l'infini en coupure réseau | bornée à `DB_CONNECT_TIMEOUT` |
| ✅ P0.2 | Vues paresseuses (`MainWindow._show_view` + `_view_factories`) | 8 vues construites au login | 1 vue par affichage |
| ✅ P0.3a | Dashboard : `DashboardDataWorker` + slots de rendu (`_apply_data`, `_render_chart`, `_render_top_products`, `_render_recent_sales`) | 11 req. ≈ 1,5 s à chaque tick 30 s | **0 req. thread UI** (0,0-0,1 ms) |
| ✅ P0.3b | Battement de session : `SessionHeartbeatWorker` | 1 req. toutes les 5 min sur le thread UI | **0 req. thread UI** |
| ✅ P0.3c | Registre factures : debounce 300 ms + `InvoiceRegisterWorker` | 3 req. (457 ms) par frappe | **0 req. par frappe** |
| ✅ P0.3c | Proforma : debounce + `ProformaListWorker` (session propre) | 1+ req. par frappe | **0 req. par frappe** |
| ✅ P0.3c | Admin : `ActivitiesWorker` + `SaleLogsWorker` (statistiques incluses), rendus `_render_activities` / `_render_sale_logs` | ~20 req. synchrones à l'ouverture | ~5 req. (dont courses des workers) |
| ✅ P0.4 | `sale_view.load_products_async` : compteur de génération + `_loader_refs`, plus de `stop()`/`wait(1000)` dans le slot | gel jusqu'à 1 s par frappe | **0 ms bloqué**, résultats périmés écartés |
| ✅ P0.5 | Retours visuels de latence (`ui/loading.py` : `LoadingSpinner` + `LoadingOverlay`) sur les 5 vues async | aucun signal pendant l'attente réseau | voile animé affiché après 150 ms, coût **0,4 ms** thread UI |
| ⬜ P1 | `stock_view` (43 req.), `sale_view` (25 req.), `create_all` au démarrage (24 req.), session par thread | — | — |

Sortie de `_diag_freeze_desktop.py --rtt-ms 147` après correctifs :

```text
dashboard   0 req.    48 ms UI      register   0 req.     2 ms UI
proforma    0 req.     3 ms UI      admin      5 req.   658 ms UI *
MainWindow  3 req.   436 ms UI      sale      25 req.  2263 ms UI (P1)
stock      54 req.  6845 ms UI (P1)
refresh_data (timer 30 s) : 0 req. — 0,0 ms UI
```

\* une partie du compteur provient des workers lancés à l'ouverture (le compteur
est processus-wide) : le thread UI n'attend pas ces requêtes.

Note de mesure : le script conserve désormais les vues mesurées dans `keep` —
sans cela, le GC détruit un worker en cours et Qt avorte le processus
(`QThread: Destroyed while thread is still running`).

### P0.5 — Retours visuels de latence (animations)

Les workers ont supprimé le gel, mais l'utilisateur ne recevait aucun retour
pendant l'attente réseau (0,4 à 1,5 s vers Supabase). `ui/loading.py` apporte
deux widgets partagés :

* **`LoadingSpinner`** — arc tournant peint (QTimer 30 ms, aucune image
  externe), variante réutilisable de celui de `login_view.py` ;
* **`LoadingOverlay`** — voile translucide + spinner + message posé au-dessus
  d'un widget parent, avec trois garde-fous :
  * **anti-scintillement** : affichage différé de `SHOW_DELAY_MS` (150 ms) ;
    une réponse rapide (SQLite local, cache) n'affiche jamais le voile ;
  * **profondeur** : `start()`/`stop()` s'apparient (un départ de worker /
    un résultat livré, y compris périmé pour `sale_view`) ; deux
    chargements superposés restent visibles jusqu'au dernier `stop()` ;
  * **durée écoulée** : au-delà d'une seconde, le message affiche le temps
    (« … (3 s) ») pour rendre la latence réseau explicite.

Intégrations (toujours en première ligne des slots de rendu **et** d'erreur) :

| Vue | Ancrage du voile | Déclencheur `start()` |
| --- | --- | --- |
| `dashboard_view` | vue entière | **1er chargement seulement** ; les ticks 30 s affichent « Actualisation… » dans `update_label` (pas de voile clignotant) |
| `invoice_register_view` | vue entière | `_start_refresh` (après le debounce 300 ms) |
| `proforma_invoice_view` | vue entière | `_start_load_proformas` (après le debounce) |
| `admin_view` | sur `activity_table` / `sale_logs_table` (les filtres restent actifs) | `load_real_activities` / `load_sale_logs` |
| `sale_view` | sur `products_table` (filtres et panier actifs) | `load_products_async` — `stop()` **avant** la garde de génération |

Mesures (`--rtt-ms 147`) : voile `start()+stop()` = **0,4 ms** ; voies
`refresh_data` = **0,0-0,8 ms** ; `dashboard 0 req / 48,8 ms UI` et
`refresh 0 req / 0,1 ms UI` identiques à la baseline P0. Couverture :
`_smoke_workers.py` (24 checks) valide l'anti-scintillement, l'empilement
profond, la dissimulation au dernier `stop()` et la vente des voiles après
livraison des payloads (0 échec le 30/09/2026).

Hors périmètre : `stock_view` reste synchrone (P1) — un voile ne pourrait pas
animer tant que le thread UI est bloqué par ses 54 requêtes.

## 7. Annexe — inventaire des accès base sur le thread UI

| Fichier:ligne | Déclencheur | Effet |
| --- | --- | --- |
| `main.py:29` | lancement | `create_all` (24 req.) avant le splash |
| `main.py:34-41` | lancement | `ensure_default_store` (6 req.) |
| `main.py:73-88` | signal de connexion | construit `MainWindow` → 8 vues |
| `ui/views/main_window.py:97-102` | `QTimer` 5 min | battement de session |
| `ui/views/main_window.py:104-135` | battement | `touch()` + `close()` (`SELECT` + `COMMIT`) |
| `ui/views/main_window.py:283` | connexion | construction de toutes les vues |
| `ui/views/dashboard_view.py:36-41` | construction + 30 s | `load_real_data`, `debug_sales_data`, timer |
| `ui/views/dashboard_view.py:704-714` | timer 30 s | 7 requêtes |
| `ui/views/sale_view.py:146-149` | construction | 27 requêtes |
| `ui/views/sale_view.py:1031-1041` | recherche / pagination | `wait(1000)` sur le thread UI |
| `ui/views/stock_view.py:96` | construction | `load_data` + `init_ui` (42 req.) |
| `ui/views/stock_view.py:452-479` | `load_data` | 9 `SELECT` + `commit` |
| `ui/views/stock_view.py:1724 → 2041 → 3173` | frappe | 1 requête par caractère |
| `ui/views/stock_view.py:4025-4033` | bouton Actualiser | ~20 requêtes |
| `ui/views/invoice_register_view.py:99, 105, 132` | frappe / filtre | 3 requêtes par frappe (457 ms mesurés) |
| `ui/views/proforma_invoice_view.py:1831 → 1921` | frappe | 1 requête par caractère |
| `ui/views/admin_view.py:121, 179-180, 664, 916, 1294, 2375` | construction / filtres / pagination | requêtes synchrones (sauf l. 1344 : worker) |
| `core/single_session.py:59-71` | appelé par le thread UI | `SessionLocal` + `SELECT` + `COMMIT` |

**Règle à retenir pour la suite :** aucun `session.query(...)`, `commit()` ou
`execute()` dans un constructeur de vue, un slot de widget ou un `QTimer` du
thread UI — uniquement dans un `QThread`/`QRunnable`, ou hors du chemin
d'interaction.

