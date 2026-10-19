from __future__ import annotations

import logging
import sys
from typing import Sequence

from app_container import AppContainer


def initialize_runtime() -> None:
    """Initialise le runtime applicatif (base, modèles, DPI, logging)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from core.database import Base, SessionLocal, engine
    from core.store_manager import ensure_default_store
    from core.system_logger import setup_logging

    setup_logging()

    for module_name in (
        "core.models.activity_log",
        "core.models.app_setting",
        "core.models.customer",
        "core.models.sale_log",
        "core.models.store",
        "core.models.stock_models",
        "core.models.sale_models",
        "core.models.treasury_models",
    ):
        __import__(module_name)

    Base.metadata.create_all(bind=engine)

    try:
        with SessionLocal() as session:
            store = ensure_default_store(session)
            if store is not None:
                print(f"Magasin par défaut : {store.name} ({store.code})")
    except Exception as exc:  # pragma: no cover - non bloquant au démarrage
        print(f"Initialisation des magasins ignorée : {exc}")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def build_application(argv: Sequence[str] | None = None):
    """Crée l'application Qt et initialise le runtime avant le bootstrap UI."""
    from PySide6.QtWidgets import QApplication

    initialize_runtime()
    app = QApplication(list(sys.argv if argv is None else argv))
    # Police sans-sérif par défaut pour toute l'application (projet 100 % sans-sérif).
    # Les feuilles QSS redéclarent déjà « Segoe UI », mais cette valeur garantit
    # le sans-sérif aussi avant le chargement du thème et pour les boîtes natives.
    default_font = app.font()
    default_font.setFamilies(["Segoe UI", "Arial", "Helvetica", "sans-serif"])
    app.setFont(default_font)
    return app


class ApplicationFactory:
    """Factory de création de l'application et de ses vues."""

    def __init__(self, theme: str = "light", app=None, container: AppContainer | None = None):
        self.theme = theme
        self.app = app
        self.container = container or AppContainer.default()

    def create_app(self, argv: Sequence[str] | None = None):
        self.app = build_application(argv)
        return self.app

    def create_splash(self):
        from ui.views.splash_screen import ModernSplashScreen

        return ModernSplashScreen(self.app)

    def create_login_window(self):
        from ui.views.login_view import LoginView

        return LoginView(auth_controller=self.container.auth_controller)

    def create_main_window(self, user_data, theme):
        from ui.views.main_window import MainWindow

        return MainWindow(user_data, theme, settings_manager=self.container.settings_manager)

    def bootstrap_ui(self, app=None):
        """Configure le flux UI de connexion et le splash screen."""
        if app is not None:
            self.app = app

        from PySide6.QtWidgets import QMessageBox

        from ui.icons import icon_manager
        from ui.themes.theme_manager import load_theme

        splash = self.create_splash()
        splash.show()
        self.app.processEvents()

        def close_splash() -> None:
            splash.close()

        splash.update_status("Chargement des modules...", 30)
        self.app.processEvents()

        splash.update_status("Chargement du thème...", 60)
        self.app.processEvents()
        load_theme(self.app, theme=self.theme)

        splash.update_status("Finalisation...", 90)
        self.app.processEvents()
        icon_manager.set_app_icon(self.app)

        login_window = self.create_login_window()

        def on_login_success(user_data, theme):
            try:
                main_window = self.create_main_window(user_data, theme)
            except Exception as exc:
                logging.getLogger("korgo_pro").critical(
                    "Échec de la création de la fenêtre principale", exc_info=True
                )
                QMessageBox.critical(
                    None,
                    "Erreur au démarrage",
                    f"Impossible d'ouvrir l'interface principale :\n{exc}\n\n"
                    "L'application va se fermer.",
                )
                self.app.quit()
                return

            main_window.show()
            login_window.hide()

        login_window.login_successful.connect(on_login_success)
        login_window.show()

        splash.update_status("Prêt !", 100)
        self.app.processEvents()
        splash.fade_out(close_splash)
        return self.app

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Exécute la boucle principale de l'application."""
        app = self.create_app(argv)
        self.bootstrap_ui(app)
        return app.exec()


def run_application(argv: Sequence[str] | None = None) -> int:
    """Construit l'application, affiche le splash, puis lance la boucle de Qt."""
    factory = ApplicationFactory(theme="light")
    return factory.run(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Point d'entrée public de l'application."""
    raise SystemExit(run_application(argv))


if __name__ == "__main__":
    main()
