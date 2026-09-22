# ui/views/sys_logs_dialog.py
"""
Boîte de dialogue de consultation et d'export des logs système.

Permet, en cas de bug, de :
    - consulter les logs récents de l'application ;
    - ouvrir le dossier des logs sur le disque ;
    - exporter un rapport de diagnostic complet (ZIP) à envoyer au support.
"""

from __future__ import annotations

import shutil
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QMessageBox,
)

from core.system_logger import (
    get_logs_dir,
    get_log_files,
    read_logs,
    get_system_info,
    collect_diagnostics_zip,
)


def _format_system_info() -> str:
    """Met en forme les informations système pour l'affichage."""
    info = get_system_info()
    lines = [
        f"Rapport de diagnostic — {info.get('app_name')}",
        f"Généré le : {info.get('timestamp')}",
        f"Version : {info.get('app_version')}",
        f"OS : {info.get('os')} {info.get('os_release')} ({info.get('machine')})",
        f"Python : {info.get('python')}",
        f"PySide6 : {info.get('pyside6_version')}",
        f"SQLAlchemy : {info.get('sqlalchemy_version')}",
        f"Pandas : {info.get('pandas_version')}",
    ]
    _db = info.get("db_files") or {}
    if _db:
        db_part = ", ".join(
            f"{name} ({meta.get('size_bytes', 0)} o)" for name, meta in _db.items()
        )
        lines.append(f"Base de données : {db_part}")
    lines.append(f"Dossier des logs : {info.get('logs_dir')}")
    return "\n".join(lines)


class SysLogsDialog(QDialog):
    """Dialogue pour consulter et exporter les logs système."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Journaux système — Korgo Pro")
        self.resize(760, 560)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Résumé système
        self.summary_label = QLabel()
        self.summary_label.setObjectName("LogSummary")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.summary_label)

        # Zone de logs
        self.log_text = QPlainTextEdit(self)
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("LogView")
        self.log_text.setMaximumBlockCount(50000)
        layout.addWidget(self.log_text, 1)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_refresh = QPushButton("Rafraîchir", self)
        self.btn_open_folder = QPushButton("Ouvrir le dossier des logs", self)
        self.btn_export = QPushButton("Exporter un rapport de diagnostic (ZIP)", self)
        self.btn_close = QPushButton("Fermer", self)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_open_folder.clicked.connect(self.open_logs_folder)
        self.btn_export.clicked.connect(self.export_diagnostics)
        self.btn_close.clicked.connect(self.close)

        for btn in (self.btn_refresh, self.btn_open_folder, self.btn_export):
            btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_open_folder)
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.refresh()

    def refresh(self) -> None:
        """Rafraîchit le résumé système et le contenu des logs."""
        status_parts = [
            "<b>Korgo Pro — Journaux système</b>",
            f"<span style='color:#666'>Généré : {datetime.now():%Y-%m-%d %H:%M:%S}</span>",
        ]
        files = get_log_files()
        if files:
            status_parts.append(
                f"<span style='color:#666'>{len(files)} fichier(s) dans "
                f"<code>{get_logs_dir()}</code></span>"
            )
        else:
            status_parts.append("Aucun fichier de log pour le moment.")
        self.summary_label.setText(" • ".join(status_parts))

        content = _format_system_info()
        content += "\n\n" + "="*20 + " LOGS " + "="*20 + "\n"
        content += read_logs()
        self.log_text.setPlainText(content)

    def open_logs_folder(self) -> None:
        """Ouvre le dossier des logs dans l'explorateur."""
        import subprocess
        folder = get_logs_dir()
        try:
            subprocess.Popen(["explorer", str(folder)])
        except Exception as exc:
            QMessageBox.warning(self, "Ouverture", f"Impossible d'ouvrir le dossier : {exc}")

    def export_diagnostics(self) -> None:
        """Exporte un rapport de diagnostic (ZIP) vers un emplacement choisi."""
        default_name = f"korgo_pro_diagnostic_{datetime.now():%Y%m%d_%H%M%S}.zip"
        dest_dir, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le rapport de diagnostic",
            default_name,
            "Archive ZIP (*.zip)",
        )
        if not dest_dir:
            return
        try:
            tmp = collect_diagnostics_zip()
            if not tmp.get("success") or tmp.get("zip_path"):
                raise RuntimeError(tmp.get("error") or "Échec de l'export.")
            shutil.copy(str(tmp["zip_path"]), dest_dir)
            QMessageBox.information(
                self,
                "Export terminé",
                f"Le rapport de diagnostic a été enregistré :\n{dest_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export", f"Erreur : {exc}")