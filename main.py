# main.py (version optimisée — démarrage rapide)
import sys
from PySide6.QtWidgets import QApplication
from ui.views.login_view import LoginView
from ui.views.main_window import MainWindow
from ui.themes.theme_manager import load_theme
from core.database import Base, engine
from ui.icons import icon_manager
from ui.views.splash_screen import ModernSplashScreen

# Initialisation rapide de la base (ne crée les tables que si elles n'existent pas)
Base.metadata.create_all(bind=engine)

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
    main_window = MainWindow(user_data, theme)
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