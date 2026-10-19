from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from app_container import AppContainer
from ui.views.dashboard_view import DashboardView
from utils.settings_manager import SettingsManager


def test_app_container_exposes_core_dependencies():
    container = AppContainer.default()

    assert container.auth_controller is not None
    assert container.settings_manager is not None


def test_dashboard_view_accepts_injected_settings_manager():
    app = QApplication.instance() or QApplication([])
    settings_manager = SettingsManager()

    with patch.object(DashboardView, "init_ui"), \
         patch.object(DashboardView, "setup_chart"), \
         patch.object(DashboardView, "apply_light_theme"), \
         patch.object(DashboardView, "load_real_data"):
        view = DashboardView({"username": "alice", "role": "admin"}, settings_manager=settings_manager)

    assert view.settings_manager is settings_manager
    app.deleteLater()
