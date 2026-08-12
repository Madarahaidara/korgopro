# ui/components/custom_card.py
"""
Custom Card Component

Versatile card container for displaying content with optional header, footer, and shadow.
Token-based styling for consistency.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt


class CustomCard(QWidget):
    """
    Card component for grouping related content.
    
    Features:
    - Optional header with title/icon
    - Main content area
    - Optional footer
    - Elevation/shadow effect
    - Token-based colors
    
    Examples:
        card = CustomCard(title="Statistics")
        card.set_content(widget)
        card.set_footer(footer_label)
    """
    
    def __init__(self, title="", elevation=1, parent=None):
        super().__init__(parent)
        self.title = title
        self.elevation = elevation  # 0-4, controls shadow depth
        
        self.setObjectName("CustomCard")
        self._build_ui()
        self._apply_elevation()
    
    def _build_ui(self):
        """Build card structure"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header (optional title)
        if self.title:
            self.header = QWidget()
            self.header.setObjectName("CardHeader")
            header_layout = QVBoxLayout(self.header)
            header_layout.setContentsMargins(16, 16, 16, 12)
            header_layout.setSpacing(0)
            
            self.title_label = QLabel(self.title)
            self.title_label.setObjectName("CardTitle")
            self.title_label.setStyleSheet("""
                #CardTitle {
                    color: {{TEXT}};
                    font-size: 16px;
                    font-weight: 600;
                }
            """)
            header_layout.addWidget(self.title_label)
            
            layout.addWidget(self.header)
            
            # Separator line
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setObjectName("CardSeparator")
            separator.setStyleSheet("""
                #CardSeparator {
                    background-color: {{BORDER}};
                    height: 1px;
                }
            """)
            layout.addWidget(separator)
        
        # Content area
        self.content_container = QWidget()
        self.content_container.setObjectName("CardContent")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(16, 12, 16, 12)
        self.content_layout.setSpacing(8)
        
        layout.addWidget(self.content_container)
        
        # Footer (optional)
        self.footer = None
        
        self.main_layout = layout
    
    def set_content(self, widget):
        """Set the main content widget"""
        # Clear existing content
        while self.content_layout.count() > 0:
            self.content_layout.takeAt(0)
        
        # Add new content
        self.content_layout.addWidget(widget)
    
    def set_footer(self, widget):
        """Add a footer widget"""
        if self.footer:
            self.main_layout.removeWidget(self.footer)
            self.footer.deleteLater()
        
        self.footer = QWidget()
        self.footer.setObjectName("CardFooter")
        footer_layout = QVBoxLayout(self.footer)
        footer_layout.setContentsMargins(16, 12, 16, 16)
        footer_layout.setSpacing(0)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("CardSeparator")
        separator.setStyleSheet("""
            #CardSeparator {
                background-color: {{BORDER}};
                height: 1px;
            }
        """)
        
        footer_layout.addWidget(separator)
        footer_layout.addWidget(widget)
        
        self.main_layout.addWidget(self.footer)
    
    def _apply_elevation(self):
        """Apply shadow/elevation style based on level"""
        shadows = {
            0: "box-shadow: none;",
            1: "box-shadow: 0 1px 3px rgba(0,0,0,0.1);",
            2: "box-shadow: 0 4px 6px rgba(0,0,0,0.1);",
            3: "box-shadow: 0 10px 15px rgba(0,0,0,0.1);",
            4: "box-shadow: 0 20px 25px rgba(0,0,0,0.15);",
        }
        
        shadow = shadows.get(self.elevation, shadows[1])
        
        self.setStyleSheet(f"""
            #CustomCard {{
                background-color: white;
                border-radius: 8px;
                border: 1px solid {{BORDER}};
                {shadow}
            }}
            #CardHeader {{
                background-color: {{BG_SECONDARY}};
                border-radius: 8px 8px 0 0;
            }}
            #CardContent {{
                background-color: white;
            }}
        """)
    
    def set_elevation(self, level):
        """Change card elevation/shadow dynamically"""
        if 0 <= level <= 4:
            self.elevation = level
            self._apply_elevation()
