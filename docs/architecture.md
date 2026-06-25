## Architecture du projet

Diagramme Mermaid représentant les composants principaux et le flux de données.

```mermaid
flowchart LR
  subgraph UI
    A[LoginView] --> B[MainWindow]
    B --> DashboardView
    B --> SaleView
    B --> StockView
    B --> DocumentsView
    B --> AdminView
    B --> SettingsView
    UIThemes[Theme Manager] --> B
    Icons[Icon Manager] --> B
  end

  subgraph Controllers
    C[AuthController] -->|auth| B
    C -->|user_data| LoginView
  end

  subgraph Core
    DB[SQLAlchemy Engine / Session] --> Models[core/models]
    Managers[Business Managers] --> DB
    Managers --> Models
    Startup[Startup Manager] --> Managers
  end

  subgraph Utils
    Settings[SettingsManager] --> B
    Print[Print Service] --> SaleView
    Resource[Resource Path] --> UI
  end

  A --> C
  LoginView -->|on success| B
  B -->|calls| Managers
  Managers --> DB
  Alembic[Alembic migrations] --> DB

  style UI fill:#f9f,stroke:#333,stroke-width:1px
  style Core fill:#ff9,stroke:#333,stroke-width:1px
  style Controllers fill:#9f9,stroke:#333,stroke-width:1px
  style Utils fill:#9cf,stroke:#333,stroke-width:1px
```

Notes:
- Le point d'entrée est `main.py` qui initialise la DB, le thème et la fenêtre de connexion.
- `MainWindow` orchestre les vues via un `QStackedWidget` et applique les permissions par rôle.
- La persistance utilise SQLAlchemy avec une base SQLite (migrations via Alembic).

Vous pouvez rendre ce diagramme visible dans un viewer markdown qui supporte Mermaid, ou l'exporter en PNG/SVG via un outil externe.
