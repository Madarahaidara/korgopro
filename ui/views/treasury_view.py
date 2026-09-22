# ui/views/treasury_view.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit,
    QDoubleSpinBox, QMessageBox, QTabWidget, QGroupBox,
    QFormLayout, QAbstractItemView, QInputDialog
)
from PySide6.QtGui import QFont
from core.treasury_manager import TreasuryManager


class TreasuryView(QWidget):
    """Vue de trésorerie : gestion des comptes, mouvements et sessions de caisse."""

    def __init__(self, user=None, parent=None):
        super().__init__(parent)
        self.user = user
        self.manager = TreasuryManager()
        self.current_session = None
        self._init_ui()
        self._load_accounts()
        self._refresh_dashboard()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("💰 Trésorerie")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_dashboard_tab(), "Tableau de bord")
        self.tabs.addTab(self._create_accounts_tab(), "Comptes")
        self.tabs.addTab(self._create_movements_tab(), "Mouvements")
        self.tabs.addTab(self._create_cash_session_tab(), "Session de caisse")
        layout.addWidget(self.tabs)

    def _create_dashboard_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        summary_group = QGroupBox("Résumé du mois")
        summary_layout = QHBoxLayout(summary_group)
        self.lbl_total_in = QLabel("Entrées: 0 FCFA")
        self.lbl_total_in.setStyleSheet("color: green; font-size: 14px; font-weight: bold;")
        self.lbl_total_out = QLabel("Sorties: 0 FCFA")
        self.lbl_total_out.setStyleSheet("color: red; font-size: 14px; font-weight: bold;")
        self.lbl_net = QLabel("Net: 0 FCFA")
        self.lbl_net.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_balance = QLabel("Solde total: 0 FCFA")
        self.lbl_balance.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a73e8;")
        summary_layout.addWidget(self.lbl_total_in)
        summary_layout.addWidget(self.lbl_total_out)
        summary_layout.addWidget(self.lbl_net)
        summary_layout.addWidget(self.lbl_balance)
        layout.addWidget(summary_group)
        accounts_group = QGroupBox("Solde par compte")
        accounts_layout = QVBoxLayout(accounts_group)
        self.accounts_table = QTableWidget(0, 3)
        self.accounts_table.setHorizontalHeaderLabels(["Compte", "Type", "Solde"])
        self.accounts_table.horizontalHeader().setStretchLastSection(True)
        self.accounts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        accounts_layout.addWidget(self.accounts_table)
        layout.addWidget(accounts_group)
        btn_refresh = QPushButton("🔄 Rafraîchir")
        btn_refresh.clicked.connect(self._refresh_dashboard)
        layout.addWidget(btn_refresh)
        return widget

    def _refresh_dashboard(self):
        result = self.manager.get_treasury_summary()
        if result.get("success"):
            data = result
            self.lbl_total_in.setText(f"Entrées: {data['total_in']:,.0f} FCFA")
            self.lbl_total_out.setText(f"Sorties: {data['total_out']:,.0f} FCFA")
            self.lbl_net.setText(f"Net: {data['net']:,.0f} FCFA")
            self.lbl_balance.setText(f"Solde total: {data['current_balance']:,.0f} FCFA")
            accounts = data.get("accounts", [])
            self.accounts_table.setRowCount(len(accounts))
            for i, acc in enumerate(accounts):
                self.accounts_table.setItem(i, 0, QTableWidgetItem(acc["name"]))
                self.accounts_table.setItem(i, 1, QTableWidgetItem(acc["type"]))
                self.accounts_table.setItem(i, 2, QTableWidgetItem(f"{acc['balance']:,.0f}"))


    def _create_accounts_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form_group = QGroupBox("Nouveau compte")
        form_layout = QFormLayout(form_group)
        self.acc_name = QLineEdit()
        self.acc_type = QComboBox()
        self.acc_type.addItems(["CASH", "BANK", "MOBILE_MONEY"])
        self.acc_initial_balance = QDoubleSpinBox()
        self.acc_initial_balance.setRange(0, 999999999)
        self.acc_initial_balance.setSuffix(" FCFA")
        self.acc_bank_name = QLineEdit()
        self.acc_account_number = QLineEdit()
        self.acc_phone_number = QLineEdit()
        self.acc_is_default = QComboBox()
        self.acc_is_default.addItems(["Non", "Oui"])
        form_layout.addRow("Nom:", self.acc_name)
        form_layout.addRow("Type:", self.acc_type)
        form_layout.addRow("Solde initial:", self.acc_initial_balance)
        form_layout.addRow("Banque:", self.acc_bank_name)
        form_layout.addRow("N° compte:", self.acc_account_number)
        form_layout.addRow("Téléphone:", self.acc_phone_number)
        form_layout.addRow("Par défaut:", self.acc_is_default)
        btn_create = QPushButton("➕ Créer le compte")
        btn_create.clicked.connect(self._create_account)
        form_layout.addRow(btn_create)
        layout.addWidget(form_group)
        self.all_accounts_table = QTableWidget(0, 5)
        self.all_accounts_table.setHorizontalHeaderLabels(
            ["ID", "Nom", "Type", "Solde", "Statut"])
        self.all_accounts_table.horizontalHeader().setStretchLastSection(True)
        self.all_accounts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.all_accounts_table)
        return widget

    def _create_account(self):
        name = self.acc_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du compte est obligatoire.")
            return
        result = self.manager.create_account(
            name=name,
            account_type=self.acc_type.currentText(),
            initial_balance=self.acc_initial_balance.value(),
            bank_name=self.acc_bank_name.text().strip() or None,
            account_number=self.acc_account_number.text().strip() or None,
            phone_number=self.acc_phone_number.text().strip() or None,
            is_default=(self.acc_is_default.currentText() == "Oui"),
        )
        if result.get("success"):
            QMessageBox.information(self, "Succès", f"Compte '{name}' créé avec succès.")
            self._load_accounts()
            self._refresh_dashboard()
        else:
            QMessageBox.critical(self, "Erreur", result.get("error", "Erreur inconnue."))

    def _load_accounts(self):
        result = self.manager.get_accounts()
        if result.get("success"):
            accounts = result["accounts"]
            self.all_accounts_table.setRowCount(len(accounts))
            for i, acc in enumerate(accounts):
                self.all_accounts_table.setItem(i, 0, QTableWidgetItem(str(acc.id)))
                self.all_accounts_table.setItem(i, 1, QTableWidgetItem(acc.name))
                self.all_accounts_table.setItem(i, 2, QTableWidgetItem(acc.account_type))
                self.all_accounts_table.setItem(i, 3, QTableWidgetItem(f"{acc.current_balance:,.0f}"))
                self.all_accounts_table.setItem(i, 4, QTableWidgetItem("Actif" if acc.is_active else "Inactif"))
            self._populate_account_combos([a for a in accounts if a.is_active])

    def _populate_account_combos(self, accounts):
        """Remplit les combobox de comptes (mouvements + session de caisse)."""
        for combo in (getattr(self, "mv_account", None),
                      getattr(self, "session_account", None)):
            if combo is None:
                continue
            previous = combo.currentData()
            combo.clear()
            for acc in accounts:
                label = f"{acc.name} ({acc.account_type}) — {acc.current_balance:,.0f} FCFA"
                combo.addItem(label, acc.id)
            if previous is not None:
                idx = combo.findData(previous)
                if idx >= 0:
                    combo.setCurrentIndex(idx)


    def _create_movements_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form_group = QGroupBox("Nouveau mouvement")
        form_layout = QFormLayout(form_group)
        self.mv_account = QComboBox()
        self.mv_type = QComboBox()
        self.mv_type.addItems(["IN", "OUT"])
        self.mv_amount = QDoubleSpinBox()
        self.mv_amount.setRange(1, 999999999)
        self.mv_amount.setSuffix(" FCFA")
        self.mv_category = QLineEdit()
        self.mv_description = QLineEdit()
        self.mv_reference = QLineEdit()
        form_layout.addRow("Compte:", self.mv_account)
        form_layout.addRow("Type:", self.mv_type)
        form_layout.addRow("Montant:", self.mv_amount)
        form_layout.addRow("Catégorie:", self.mv_category)
        form_layout.addRow("Description:", self.mv_description)
        form_layout.addRow("Référence:", self.mv_reference)
        btn_add = QPushButton("➕ Ajouter le mouvement")
        btn_add.clicked.connect(self._add_movement)
        form_layout.addRow(btn_add)
        layout.addWidget(form_group)
        self.movements_table = QTableWidget(0, 6)
        self.movements_table.setHorizontalHeaderLabels(
            ["Date", "Type", "Montant", "Catégorie", "Description", "Réf."])
        self.movements_table.horizontalHeader().setStretchLastSection(True)
        self.movements_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.movements_table)
        btn_load_mv = QPushButton("🔄 Charger les mouvements")
        btn_load_mv.clicked.connect(self._load_movements)
        layout.addWidget(btn_load_mv)
        return widget

    def _add_movement(self):
        if self.mv_account.currentIndex() < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un compte.")
            return
        account_id = self.mv_account.currentData()
        result = self.manager.add_movement(
            account_id=account_id,
            movement_type=self.mv_type.currentText(),
            amount=self.mv_amount.value(),
            category=self.mv_category.text().strip() or None,
            description=self.mv_description.text().strip() or None,
            reference=self.mv_reference.text().strip() or None,
            user_id=self.user.get("id") if isinstance(self.user, dict) else (
                self.user.id if self.user else None),
        )
        if result.get("success"):
            QMessageBox.information(self, "Succès", "Mouvement ajouté.")
            self._load_movements()
            self._refresh_dashboard()
            self._load_accounts()
        else:
            QMessageBox.critical(self, "Erreur", result.get("error", "Erreur inconnue."))

    def _load_movements(self):
        result = self.manager.get_movements(limit=100)
        if result.get("success"):
            movements = result["movements"]
            self.movements_table.setRowCount(len(movements))
            for i, mv in enumerate(movements):
                self.movements_table.setItem(i, 0, QTableWidgetItem(str(mv.date)[:16]))
                self.movements_table.setItem(i, 1, QTableWidgetItem(mv.movement_type))
                self.movements_table.setItem(i, 2, QTableWidgetItem(f"{mv.amount:,.0f}"))
                self.movements_table.setItem(i, 3, QTableWidgetItem(mv.category or ""))
                self.movements_table.setItem(i, 4, QTableWidgetItem(mv.description or ""))
                self.movements_table.setItem(i, 5, QTableWidgetItem(mv.reference or ""))

    def _create_cash_session_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.session_group = QGroupBox("Session de caisse")
        session_layout = QFormLayout(self.session_group)
        self.session_account = QComboBox()
        self.session_opening_amount = QDoubleSpinBox()
        self.session_opening_amount.setRange(0, 999999999)
        self.session_opening_amount.setSuffix(" FCFA")
        self.lbl_session_status = QLabel("Aucune session ouverte")
        self.lbl_session_status.setStyleSheet("color: gray; font-weight: bold;")
        session_layout.addRow("Compte:", self.session_account)
        session_layout.addRow("Montant d'ouverture:", self.session_opening_amount)
        session_layout.addRow("Statut:", self.lbl_session_status)
        btn_layout = QHBoxLayout()
        self.btn_open_session = QPushButton("🔓 Ouvrir la session")
        self.btn_open_session.clicked.connect(self._open_session)
        self.btn_close_session = QPushButton("🔒 Fermer la session")
        self.btn_close_session.clicked.connect(self._close_session)
        self.btn_close_session.setEnabled(False)
        btn_layout.addWidget(self.btn_open_session)
        btn_layout.addWidget(self.btn_close_session)
        session_layout.addRow(btn_layout)
        layout.addWidget(self.session_group)
        self.sessions_table = QTableWidget(0, 6)
        self.sessions_table.setHorizontalHeaderLabels(
            ["Ouverture", "Fermeture", "Initial", "Entrées", "Sorties", "Écart"])
        self.sessions_table.horizontalHeader().setStretchLastSection(True)
        self.sessions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.sessions_table)
        btn_load_sessions = QPushButton("🔄 Charger l'historique")
        btn_load_sessions.clicked.connect(self._load_sessions)
        layout.addWidget(btn_load_sessions)
        return widget

    def _open_session(self):
        if self.session_account.currentIndex() < 0:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un compte.")
            return
        account_id = self.session_account.currentData()
        result = self.manager.open_cash_session(
            account_id=account_id,
            user_id=self.user.get("id") if isinstance(self.user, dict) else (
                self.user.id if self.user else None),
            opening_amount=self.session_opening_amount.value(),
        )
        if result.get("success"):
            self.current_session = result["session"]
            self.lbl_session_status.setText("Session ouverte")
            self.lbl_session_status.setStyleSheet("color: green; font-weight: bold;")
            self.btn_open_session.setEnabled(False)
            self.btn_close_session.setEnabled(True)
            QMessageBox.information(self, "Succès", "Session de caisse ouverte.")
        else:
            QMessageBox.critical(self, "Erreur", result.get("error", "Erreur inconnue."))

    def _close_session(self):
        if not self.current_session:
            return
        amount, ok = QInputDialog.getDouble(
            self, "Fermeture de caisse",
            "Montant réel compté en caisse:", 0, 0, 999999999, 2)
        if not ok:
            return
        result = self.manager.close_cash_session(
            session_id=self.current_session.id,
            closing_amount=amount,
        )
        if result.get("success"):
            session = result["session"]
            self.lbl_session_status.setText("Session fermée")
            self.lbl_session_status.setStyleSheet("color: gray; font-weight: bold;")
            self.btn_open_session.setEnabled(True)
            self.btn_close_session.setEnabled(False)
            self.current_session = None
            msg = f"Session fermée.\nÉcart: {session.difference:,.0f} FCFA"
            QMessageBox.information(self, "Succès", msg)
            self._load_sessions()
            self._refresh_dashboard()
            self._load_accounts()
        else:
            QMessageBox.critical(self, "Erreur", result.get("error", "Erreur inconnue."))

    def _load_sessions(self):
        result = self.manager.get_sessions(limit=50)
        if result.get("success"):
            sessions = result["sessions"]
            self.sessions_table.setRowCount(len(sessions))
            for i, s in enumerate(sessions):
                self.sessions_table.setItem(i, 0, QTableWidgetItem(str(s.opened_at)[:16]))
                self.sessions_table.setItem(i, 1, QTableWidgetItem(str(s.closed_at)[:16] if s.closed_at else ""))
                self.sessions_table.setItem(i, 2, QTableWidgetItem(f"{s.opening_amount:,.0f}"))
                self.sessions_table.setItem(i, 3, QTableWidgetItem(f"{s.total_in:,.0f}"))
                self.sessions_table.setItem(i, 4, QTableWidgetItem(f"{s.total_out:,.0f}"))
                self.sessions_table.setItem(i, 5, QTableWidgetItem(f"{s.difference:,.0f}" if s.difference is not None else ""))