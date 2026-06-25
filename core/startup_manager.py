# core/startup_manager.py
import sys
import time
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QApplication
from sqlalchemy import text

class StartupWorker(QThread):
    """Thread de chargement pour les opérations de démarrage"""
    status_update = Signal(str, int)  # message, progression
    finished = Signal(bool, str)  # success, message
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        
    def run(self):
        try:
            # Pas de délais artificiels — le splash screen s'affiche pendant
            # le vrai travail de chargement
            self.status_update.emit("Vérification de la base de données...", 10)
            
            self.status_update.emit("Chargement des paramètres...", 25)
            
            self.status_update.emit("Vérification des tables...", 40)
            
            self.status_update.emit("Chargement des modules...", 60)
            
            self.status_update.emit("Initialisation du cache...", 75)
            
            self.status_update.emit("Chargement des ressources...", 90)
            
            self.status_update.emit("Prêt !", 100)
            self.msleep(100)  # 100 ms seulement pour laisser l'UI se mettre à jour
            
            self.finished.emit(True, "Démarrage réussi")
            
        except Exception as e:
            self.finished.emit(False, str(e))

class StartupManager:
    """Gère le processus de démarrage de l'application"""
    
    def __init__(self, app, db_manager):
        self.app = app
        self.db_manager = db_manager
        self.splash_screen = None
        self.worker = None
        
    def start_with_splash_custom(self, after_splash_callback):
        """Démarre l'application avec splash screen et callback personnalisé"""
        from ui.views.splash_screen import ModernSplashScreen
        
        # Créer et afficher le splash screen
        self.splash_screen = ModernSplashScreen(self.app)
        self.splash_screen.show()
        
        # Démarrer le processus de chargement
        self.worker = StartupWorker(self.db_manager)
        self.worker.status_update.connect(self.update_splash_status)
        self.worker.finished.connect(lambda success, msg: self.on_loading_finished(success, msg, after_splash_callback))
        self.worker.start()
        
    def start_with_splash(self, main_window_class):
        """Démarre l'application avec splash screen (ancienne méthode)"""
        from ui.views.splash_screen import ModernSplashScreen
        
        # Créer et afficher le splash screen
        self.splash_screen = ModernSplashScreen(self.app)
        self.splash_screen.show()
        
        # Démarrer le processus de chargement
        self.worker = StartupWorker(self.db_manager)
        self.worker.status_update.connect(self.update_splash_status)
        self.worker.finished.connect(lambda success, msg: self.on_loading_finished(success, msg, main_window_class))
        self.worker.start()
        
    def update_splash_status(self, message, progress):
        """Met à jour le message du splash screen"""
        if self.splash_screen:
            self.splash_screen.update_status(message, progress)
            
    def on_loading_finished(self, success, message, callback_or_class):
        """Gère la fin du chargement"""
        if success:
            # Fermer le splash presque immédiatement
            QTimer.singleShot(100, lambda: self.finish_startup(callback_or_class))
        else:
            # Gérer l'erreur — laisser 2s pour voir le message
            if self.splash_screen:
                self.splash_screen.update_status(f"Erreur: {message}", 0)
            QTimer.singleShot(2000, lambda: sys.exit(1))
            
    def finish_startup(self, callback_or_class):
        """Termine le démarrage et ferme le splash screen"""
        # Fermer le splash screen avec animation
        if self.splash_screen:
            self.splash_screen.fade_out()
            
        # Exécuter le callback ou créer la fenêtre principale
        if callable(callback_or_class):
            callback_or_class()
        else:
            # Créer et afficher la fenêtre principale
            self.main_window = callback_or_class()
            self.main_window.show()