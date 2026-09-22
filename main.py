# main.py (version optimisée — démarrage rapide)
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ui.views.login_view import LoginView
from ui.views.main_window import MainWindow
from ui.themes.theme_manager import load_theme
from core.database import Base, engine
from ui.icons import icon_manager
from ui.views.splash_screen import ModernSplashScreen
from core.system_logger import setup_logging

# Initialiser le journal système (capture les logs et crashs, même sans console)
setup_logging()

# Importer tous les modèles pour que Base.metadata soit complet avant create_all
# (notamment Store, indispensable au multi-magasins).
import core.models.activity_log  # noqa: E402,F401
import core.models.customer  # noqa: E402,F401
import core.models.sale_log  # noqa: E402,F401
import core.models.store  # noqa: E402,F401
import core.models.stock_models  # noqa: E402,F401
import core.models.sale_models  # noqa: E402,F401
import core.models.treasury_models  # noqa: E402,F401
from core.database import SessionLocal  # noqa: E402
from core.store_manager import ensure_default_store  # noqa: E402

# Initialisation rapide de la base (ne crée les tables que si elles n'existent pas)
Base.metadata.create_all(bind=engine)

# Multi-magasins : garantir un magasin par défaut et rattacher les données
# historiques (produits, mouvements, ventes sans store_id). Non bloquant : si la
# base n'a pas encore été migrée, l'application démarre sans cloisement.
try:
    with SessionLocal() as _session:
        _store = ensure_default_store(_session)
        # Message affiché dans le bloc : l'instance est détachée après fermeture.
        if _store is not None:
            print(f"Magasin par défaut : {_store.name} ({_store.code})")
except Exception as _exc:
    print(f"Initialisation des magasins ignorée : {_exc}")

# Activer le High DPI scaling pour les écrans 4K/Retina
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

# Créer l'application
app = QApplication(sys.argv)

# Créer et afficher le splash screen
splash = ModernSplashScreen(app)
splash.show()
app.processEvents()

# Fonction pour fermer le splash
def close_splash():
    splash.close()

# Initialisation directe — PAS de délais artificiels
splash.update_status("Chargement des modules...", 30)
app.processEvents()

splash.update_status("Chargement du thème...", 60)
app.processEvents()
load_theme(app, theme="light")

splash.update_status("Finalisation...", 90)
app.processEvents()
icon_manager.set_app_icon(app)

# Créer la fenêtre de connexion immédiatement
login_window = LoginView()

def on_login_success(user_data, theme):
    try:
        main_window = MainWindow(user_data, theme)
    except Exception as e:
        import logging
        logging.getLogger("korgo_pro").critical(
            "Échec de la création de la fenêtre principale", exc_info=True)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "Erreur au démarrage",
            f"Impossible d'ouvrir l'interface principale :\n{e}\n\n"
            "L'application va se fermer.")
        app.quit()
        return
    main_window.show()
    login_window.hide()

login_window.login_successful.connect(on_login_success)
login_window.show()

splash.update_status("Prêt !", 100)
app.processEvents()
# Animation de fondu uniquement — PAS de délai fixe
splash.fade_out(close_splash)

# Exécuter l'application
sys.exit(app.exec())