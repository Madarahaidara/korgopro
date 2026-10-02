# main.py
import sys


def initialize_runtime():
    """Initialise la base, les modèles et les réglages applicatifs."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from core.database import Base, SessionLocal, engine
    from core.store_manager import ensure_default_store
    from core.system_logger import setup_logging

    # Initialiser le journal système (capture les logs et crashs, même sans console)
    setup_logging()

    # Importer tous les modèles pour que Base.metadata soit complet avant create_all.
    import core.models.activity_log  # noqa: F401
    import core.models.customer  # noqa: F401
    import core.models.sale_log  # noqa: F401
    import core.models.store  # noqa: F401
    import core.models.stock_models  # noqa: F401
    import core.models.sale_models  # noqa: F401
    import core.models.treasury_models  # noqa: F401

    # Initialisation rapide de la base (ne crée les tables que si elles n'existent pas)
    Base.metadata.create_all(bind=engine)

    # Multi-magasins : garantir un magasin par défaut et rattacher les données
    # historiques (produits, mouvements, ventes sans store_id). Non bloquant : si la
    # base n'a pas encore été migrée, l'application démarre sans cloisement.
    try:
        with SessionLocal() as _session:
            _store = ensure_default_store(_session)
            if _store is not None:
                print(f"Magasin par défaut : {_store.name} ({_store.code})")
    except Exception as _exc:
        print(f"Initialisation des magasins ignorée : {_exc}")

    # Activer le High DPI scaling pour les écrans 4K/Retina
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def run_application(argv=None):
    """Crée et exécute l'application Qt."""
    if argv is None:
        argv = sys.argv

    from PySide6.QtWidgets import QApplication, QMessageBox

    initialize_runtime()
    app = QApplication(argv)

    from ui.icons import icon_manager
    from ui.themes.theme_manager import load_theme
    from ui.views.login_view import LoginView
    from ui.views.main_window import MainWindow
    from ui.views.splash_screen import ModernSplashScreen

    splash = ModernSplashScreen(app)
    splash.show()
    app.processEvents()

    def close_splash():
        splash.close()

    splash.update_status("Chargement des modules...", 30)
    app.processEvents()

    splash.update_status("Chargement du thème...", 60)
    app.processEvents()
    load_theme(app, theme="light")

    splash.update_status("Finalisation...", 90)
    app.processEvents()
    icon_manager.set_app_icon(app)

    login_window = LoginView()

    def on_login_success(user_data, theme):
        try:
            main_window = MainWindow(user_data, theme)
        except Exception as exc:
            import logging

            logging.getLogger("korgo_pro").critical(
                "Échec de la création de la fenêtre principale", exc_info=True
            )
            QMessageBox.critical(
                None,
                "Erreur au démarrage",
                f"Impossible d'ouvrir l'interface principale :\n{exc}\n\n"
                "L'application va se fermer.",
            )
            app.quit()
            return

        main_window.show()
        login_window.hide()

    login_window.login_successful.connect(on_login_success)
    login_window.show()

    splash.update_status("Prêt !", 100)
    app.processEvents()
    splash.fade_out(close_splash)

    return app.exec()


def main():
    """Point d'entrée public de l'application."""
    raise SystemExit(run_application())


if __name__ == "__main__":
    main()