# ui/components/responsive_menu.py
"""
Responsive Navigation Menu Component

Supports desktop (fixed sidebar) and mobile (drawer/hamburger menu).
Tokens from variables.json control colors and spacing.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QFrame, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QColor


class ResponsiveMenu(QWidget):
    """
    Responsive menu component that adapts to screen size.
    
    Features:
    - Desktop (>768px): Fixed sidebar with expanded/collapsed states
    - Mobile (<768px): Drawer overlay with hamburger toggle
    - Animations for smooth transitions
    - Token-based styling via theme system
    """
    
    menu_item_clicked = Signal(str, str)  # Signal: (menu_id, menu_label)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ResponsiveMenu")
        
        self.menu_expanded_width = 220
        self.menu_collapsed_width = 60
        self.menu_is_expanded = True
        self.is_mobile = False
        
        self.menu_items = []
        self._build_ui()
        self._setup_responsive()
        
    def _build_ui(self):
        """Build the menu structure"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with toggle button
        header = QWidget()
        header.setObjectName("MenuHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(8)
        
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setObjectName("MenuToggle")
        self.toggle_btn.setFixedSize(36, 36)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setAccessibleName("Basculer menu")
        self.toggle_btn.setAccessibleDescription("Affiche ou masque le menu latéral")
        self.toggle_btn.clicked.connect(self._toggle_menu)
        
        self.menu_title = QLabel("Menu")
        self.menu_title.setObjectName("MenuTitle")
        self.menu_title.setAlignment(Qt.AlignCenter)
        
        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(self.menu_title)
        header_layout.addStretch()
        
        layout.addWidget(header)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("MenuSeparator")
        layout.addWidget(separator)
        
        # Menu items container
        self.menu_container = QWidget()
        self.menu_container.setObjectName("MenuItemsContainer")
        self.menu_layout = QVBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 8, 0, 8)
        self.menu_layout.setSpacing(4)
        self.menu_layout.setAlignment(Qt.AlignTop)
        
        layout.addWidget(self.menu_container)
        layout.addStretch()
        
    def add_menu_item(self, menu_id, label, icon=None, submenu_items=None):
        """
        Add a menu item to the responsive menu.
        
        Args:
            menu_id (str): Unique identifier for the menu item
            label (str): Display label
            icon: Optional QIcon or path to icon
            submenu_items (list): Optional list of (sub_id, sub_label) tuples for submenu
        """
        item_btn = QPushButton(label)
        item_btn.setObjectName(f"MenuItem_{menu_id}")
        item_btn.setMinimumHeight(40)
        item_btn.setCursor(Qt.PointingHandCursor)
        item_btn.setAccessibleName(label)
        item_btn.setAccessibleDescription(f"Menu item: {label}")
        
        if icon:
            if isinstance(icon, str):
                icon = QIcon(icon)
            item_btn.setIcon(icon)
            item_btn.setIconSize(QSize(20, 20))
        
        item_btn.clicked.connect(
            lambda checked, mid=menu_id: self._on_menu_item_clicked(mid, label)
        )
        
        self.menu_layout.addWidget(item_btn)
        self.menu_items.append((menu_id, label, item_btn))
        
        return item_btn
    
    def _on_menu_item_clicked(self, menu_id, label):
        """Emit signal when menu item is clicked"""
        self.menu_item_clicked.emit(menu_id, label)
        
        # Auto-collapse on mobile when item selected
        if self.is_mobile and self.menu_is_expanded:
            self._toggle_menu()
    
    def _toggle_menu(self):
        """Toggle menu expanded/collapsed state"""
        self.menu_is_expanded = not self.menu_is_expanded
        
        if self.is_mobile:
            # On mobile: animate drawer in/out
            self._animate_mobile_drawer()
        else:
            # On desktop: animate width
            self._animate_sidebar_width()
    
    def _animate_sidebar_width(self):
        """Animate sidebar width change (desktop)"""
        target_width = (
            self.menu_expanded_width if self.menu_is_expanded 
            else self.menu_collapsed_width
        )
        
        anim = QPropertyAnimation(self, b"minimumWidth")
        anim.setDuration(300)
        anim.setStartValue(self.width())
        anim.setEndValue(target_width)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.start()
        self._current_anim = anim
    
    def _animate_mobile_drawer(self):
        """Animate drawer slide in/out (mobile)"""
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        current_geom = self.geometry()
        if self.menu_is_expanded:
            # Slide in
            anim.setStartValue(current_geom.adjusted(-self.width(), 0, 0, 0))
            anim.setEndValue(current_geom)
        else:
            # Slide out
            anim.setStartValue(current_geom)
            anim.setEndValue(current_geom.adjusted(-self.width(), 0, 0, 0))
        
        anim.start()
        self._current_anim = anim
    
    def _setup_responsive(self):
        """Setup responsive behavior"""
        self._check_screen_size()
    
    def _check_screen_size(self):
        """Check screen size and adapt menu layout"""
        screen = QApplication.primaryScreen()
        screen_width = screen.geometry().width()
        
        was_mobile = self.is_mobile
        self.is_mobile = screen_width < 768
        
        if was_mobile != self.is_mobile:
            self._update_layout_for_screen_size()
    
    def _update_layout_for_screen_size(self):
        """Update layout based on screen size"""
        if self.is_mobile:
            # Mobile: drawer mode
            self.setMinimumWidth(0)
            self.setMaximumWidth(250)
            self.menu_title.show()
            self.setStyleSheet("""
                #ResponsiveMenu {
                    background-color: #f5f5f5;
                    position: absolute;
                    left: 0;
                    top: 0;
                    height: 100%;
                    box-shadow: 2px 0 8px rgba(0,0,0,0.1);
                    z-index: 1000;
                }
            """)
        else:
            # Desktop: sidebar mode
            self.setMinimumWidth(self.menu_expanded_width if self.menu_is_expanded else self.menu_collapsed_width)
            self.setMaximumWidth(None)
            self.menu_title.hide()
            self.setStyleSheet("""
                #ResponsiveMenu {
                    background-color: #f5f5f5;
                }
            """)
    
    def set_menu_title(self, title):
        """Update menu title"""
        self.menu_title.setText(title)
    
    def get_menu_state(self):
        """Get current menu state"""
        return {
            'is_mobile': self.is_mobile,
            'is_expanded': self.menu_is_expanded,
            'width': self.width(),
        }
