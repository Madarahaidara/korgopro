# ui/components/custom_button.py
"""
Custom Button Component

Token-based button with multiple variants (primary, secondary, danger).
Supports icons, sizes, and disabled states.
"""

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon


class CustomButton(QPushButton):
    """
    Customizable button using token-based styling.
    
    Variants:
    - primary: Main action button (blue/accent color)
    - secondary: Alternative action (gray)
    - danger: Destructive action (red)
    - outline: Border-only style
    
    Examples:
        btn = CustomButton("Click me", variant="primary")
        btn = CustomButton("Delete", variant="danger", size="small")
        btn = CustomButton("", icon="path/to/icon.png", size="icon")
    """
    
    def __init__(self, text="", variant="primary", size="medium", icon=None, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.size = size
        
        self.setCursor(Qt.PointingHandCursor)
        self._setup_style()
        
        if icon:
            self.set_icon(icon)
    
    def _setup_style(self):
        """Apply variant and size styles"""
        height_map = {
            "small": 32,
            "medium": 40,
            "large": 48,
            "icon": 36,
        }
        
        min_height = height_map.get(self.size, 40)
        self.setMinimumHeight(min_height)
        
        # Apply variant styles via objectName
        self.setObjectName(f"CustomButton_{self.variant}_{self.size}")
        
        # Base stylesheet (tokens will be substituted)
        styles = {
            "primary": """
                #CustomButton_primary_* {
                    background-color: {{PRIMARY}};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-weight: 600;
                    font-size: 14px;
                }
                #CustomButton_primary_*:hover {
                    background-color: {{PRIMARY_DARK}};
                }
                #CustomButton_primary_*:pressed {
                    background-color: {{PRIMARY_DARKER}};
                }
                #CustomButton_primary_*:disabled {
                    background-color: {{DISABLED}};
                    color: {{TEXT_DISABLED}};
                }
            """,
            "secondary": """
                #CustomButton_secondary_* {
                    background-color: {{BG_SECONDARY}};
                    color: {{TEXT}};
                    border: 1px solid {{BORDER}};
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-weight: 600;
                    font-size: 14px;
                }
                #CustomButton_secondary_*:hover {
                    background-color: {{BG_HOVER}};
                }
                #CustomButton_secondary_*:pressed {
                    background-color: {{BG_PRESSED}};
                }
                #CustomButton_secondary_*:disabled {
                    background-color: {{DISABLED}};
                    color: {{TEXT_DISABLED}};
                }
            """,
            "danger": """
                #CustomButton_danger_* {
                    background-color: {{DANGER}};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-weight: 600;
                    font-size: 14px;
                }
                #CustomButton_danger_*:hover {
                    background-color: {{DANGER_DARK}};
                }
                #CustomButton_danger_*:pressed {
                    background-color: {{DANGER_DARKER}};
                }
                #CustomButton_danger_*:disabled {
                    background-color: {{DISABLED}};
                    color: {{TEXT_DISABLED}};
                }
            """,
            "outline": """
                #CustomButton_outline_* {
                    background-color: transparent;
                    color: {{PRIMARY}};
                    border: 2px solid {{PRIMARY}};
                    border-radius: 8px;
                    padding: 8px 18px;
                    font-weight: 600;
                    font-size: 14px;
                }
                #CustomButton_outline_*:hover {
                    background-color: {{PRIMARY_LIGHT}};
                }
                #CustomButton_outline_*:pressed {
                    background-color: {{PRIMARY}};
                    color: white;
                }
                #CustomButton_outline_*:disabled {
                    color: {{TEXT_DISABLED}};
                    border-color: {{DISABLED}};
                }
            """,
        }
        
        base_style = styles.get(self.variant, "")
        self.setStyleSheet(base_style)
    
    def set_icon(self, icon_path):
        """Set button icon"""
        if isinstance(icon_path, str):
            icon = QIcon(icon_path)
        else:
            icon = icon_path
        
        self.setIcon(icon)
        self.setIconSize(QSize(20, 20))
    
    def set_variant(self, variant):
        """Change button variant dynamically"""
        if variant in ["primary", "secondary", "danger", "outline"]:
            self.variant = variant
            self._setup_style()
