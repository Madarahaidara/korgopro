# -*- coding: utf-8 -*-
"""P0.3c admin : scission requête/rendu pour les journaux (worker + rendu).

Remplace uniquement les EN-TÊTES des méthodes de chargement ; les corps de
rendu sont conservés à l'identique. Vérifie chaque remplacement (count == 1)
avant d'écrire.
"""
import ast

PATH = "ui/views/admin_view.py"
src = open(PATH, encoding="utf-8").read()
initial = src


def replace_once(old, new, label):
    global src
    n = src.count(old)
    assert n == 1, f"{label}: {n} occurrence(s) (attendu 1)"
    src = src.replace(old, new, 1)
    print(f"OK  {label}")


# 1) Attributs des workers dans __init__ ------------------------------------
replace_once(
    "        self.sale_logs_per_page = 50\n        \n        self.init_ui()",
    "        self.sale_logs_per_page = 50\n"
    "\n"
    "        # Workers de chargement (anti-gel) : les requêtes réseau partent en\n"
    "        # arrière-plan ; le thread UI ne fait que le rendu des résultats.\n"
    "        self._activities_worker = None\n"
    "        self._activities_pending = False\n"
    "        self._sale_logs_worker = None\n"
    "        self._sale_logs_pending = False\n"
    "\n"
    "        self.init_ui()",
    "worker attrs __init__",
)

# 2) load_real_activities : en-tête -> worker + _render_activities -----------
MARK_A = "    def load_real_activities(self):"
SUCCESS = "        if result['success']:"
i0 = src.index(MARK_A)
assert src.count(MARK_A) == 1
i1 = src.index(SUCCESS, i0) + len(SUCCESS)
new_a = '''    def load_real_activities(self):
        """Prépare les filtres puis lance le chargement dans un worker.

        get_logs() + get_statistics() coûtent 2 requêtes réseau (~300 ms) :
        exécutées dans le thread UI (bouton « Filtrer », pagination,
        ouverture de l'onglet), elles gelaient la fenêtre.
        """
        filters = {}

        username = self.username_filter.text().strip()
        if username:
            filters['username'] = username

        action = self.action_filter.currentText()
        if action != "Toutes les actions":
            filters['action'] = action

        start_date = self.start_date.date().toPython()
        end_date = self.end_date.date().toPython()
        if start_date:
            filters['start_date'] = datetime.combine(start_date, datetime.min.time())
        if end_date:
            filters['end_date'] = datetime.combine(end_date, datetime.max.time())

        if (self._activities_worker is not None
                and self._activities_worker.isRunning()):
            # Chargement en cours : on relancera à la fin (filtres récents).
            self._activities_pending = True
            return
        self._activities_worker = ActivitiesWorker(
            self.log_manager, filters, self.logs_per_page,
            self.current_logs_page * self.logs_per_page, parent=self)
        self._activities_worker.loaded.connect(self._render_activities)
        self._activities_worker.failed.connect(self._on_activities_error)
        self._activities_worker.finished.connect(self._on_activities_finished)
        self._activities_worker.start()

    def _on_activities_finished(self):
        if self._activities_pending:
            self._activities_pending = False
            self.load_real_activities()

    def _on_activities_error(self, message):
        QMessageBox.warning(self, "Erreur",
                            f"Impossible de charger les logs: {message}")

    def _render_activities(self, payload):
        """Rendu du journal système (aucune requête : données du worker)."""
        result = payload['result']
        if result['success']:'''
src = src[:i0] + new_a + src[i1:]
print("OK  load_real_activities -> worker")

# 3) Statistiques d'activités : payload du worker ---------------------------
replace_once(
    "            self.update_logs_statistics()\n        else:",
    "            self.update_logs_statistics(payload['stats'])\n        else:",
    "stats activities payload",
)

# 4) update_logs_statistics : paramètre stats optionnel ----------------------
MARK_U = "    def update_logs_statistics(self):"
STATS_SUCCESS = "        if stats['success']:"
# 5) load_sale_logs : en-tête -> worker + _render_sale_logs ------------------
MARK_S = "    def load_sale_logs(self):"
i0 = src.index(MARK_S)
assert src.count(MARK_S) == 1
i1 = src.index(SUCCESS, i0) + len(SUCCESS)
new_s = '''    def load_sale_logs(self):
        """Prépare les filtres puis lance le chargement dans un worker.

        get_sale_logs() + get_sale_statistics() sortent du thread UI : le
        thread ne fait que le rendu (`_render_sale_logs`).
        """
        filters = {}

        sale_number = self.sale_number_filter.text().strip()
        if sale_number:
            filters['sale_number'] = sale_number

        action = self.sale_action_filter.currentText()
        if action != "Toutes les actions":
            filters['action'] = action

        username = self.sale_cashier_filter.text().strip()
        if username:
            filters['username'] = username

        customer_name = self.sale_customer_filter.text().strip()
        if customer_name:
            filters['customer_name'] = customer_name

        start_date = self.sale_start_date.date().toPython()
        if start_date:
            filters['start_date'] = datetime.combine(start_date, datetime.min.time())

        end_date = self.sale_end_date.date().toPython()
        if end_date:
            filters['end_date'] = datetime.combine(end_date, datetime.max.time())

        if (self._sale_logs_worker is not None
                and self._sale_logs_worker.isRunning()):
            # Chargement en cours : on relancera à la fin (filtres récents).
            self._sale_logs_pending = True
            return
        self._sale_logs_worker = SaleLogsWorker(
            self.sale_log_manager, filters, self.sale_logs_per_page,
            self.current_sale_logs_page * self.sale_logs_per_page, parent=self)
        self._sale_logs_worker.loaded.connect(self._render_sale_logs)
        self._sale_logs_worker.failed.connect(self._on_sale_logs_error)
        self._sale_logs_worker.finished.connect(self._on_sale_logs_finished)
        self._sale_logs_worker.start()

    def _on_sale_logs_finished(self):
        if self._sale_logs_pending:
            self._sale_logs_pending = False
            self.load_sale_logs()

    def _on_sale_logs_error(self, message):
        QMessageBox.warning(
            self, "Erreur",
            f"Impossible de charger les logs de ventes: {message}")

    def _render_sale_logs(self, payload):
        """Rendu du journal des ventes (aucune requête : données du worker)."""
        result = payload['result']
        if result['success']:'''
src = src[:i0] + new_s + src[i1:]
print("OK  load_sale_logs -> worker")

# 6) Statistiques de ventes : payload du worker -----------------------------
replace_once(
    "            self.update_sale_stats()\n        else:",
    "            self.update_sale_stats(payload['stats'])\n        else:",
    "stats sale payload",
)

# 7) update_sale_stats : paramètre stats optionnel ---------------------------
MARK_V = "    def update_sale_stats(self):"
i0 = src.index(MARK_V)
assert src.count(MARK_V) == 1
i1 = src.index(STATS_SUCCESS, i0) + len(STATS_SUCCESS)
new_v = '''    def update_sale_stats(self, stats=None):
        """Mettre à jour les statistiques des ventes.

        `stats` est collecté par le worker ; `None` → requête directe.
        """
        if stats is None:
            stats = self.sale_log_manager.get_sale_statistics()
        if stats['success']:'''
src = src[:i0] + new_v + src[i1:]
print("OK  update_sale_stats(stats=None)")

# Validation syntaxique avant écriture --------------------------------------
ast.parse(src)
assert src != initial
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Écrit:", PATH, "- syntaxe OK")

i0 = src.index(MARK_U)
assert src.count(MARK_U) == 1
i1 = src.index(STATS_SUCCESS, i0) + len(STATS_SUCCESS)
new_u = '''    def update_logs_statistics(self, stats=None):
        """Mettre à jour les statistiques des logs système.

        `stats` est collecté par le worker ; `None` → requête directe.
        """
        if stats is None:
            stats = self.log_manager.get_statistics()
        if stats['success']:'''
src = src[:i0] + new_u + src[i1:]
print("OK  update_logs_statistics(stats=None)")
