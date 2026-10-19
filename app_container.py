from dataclasses import dataclass, field

from controllers.auth_controller import AuthController
from utils.settings_manager import SettingsManager


@dataclass
class AppContainer:
    """Conteneur de dépendances de l'application.

    Centralise les services de base et permet leur injection dans les vues
    sans création directe dans les widgets.
    """

    auth_controller: AuthController = field(default_factory=AuthController)
    settings_manager: SettingsManager = field(default_factory=SettingsManager)

    @classmethod
    def default(cls) -> "AppContainer":
        return cls()
