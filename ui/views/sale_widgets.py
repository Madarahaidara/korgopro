from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QGraphicsOpacityEffect
)
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QDoubleValidator
from PySide6.QtSvg import QSvgRenderer

from core.models.stock_models import Product


def get_icon(icon_name: str, color: str = "#6b7280", size: int = 20) -> QIcon:
    svg_templates = {
        "search": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>''',
        "cart": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path></svg>''',
        "user": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>''',
        "settings": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>''',
        "check": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>''',
        "x": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>''',
        "plus": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>''',
        "minus": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>''',
        "trash": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>''',
        "clock": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>''',
        "alert": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>''',
        "receipt": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="9" y1="10" x2="15" y2="10"></line><line x1="9" y1="14" x2="15" y2="14"></line><line x1="9" y1="18" x2="15" y2="18"></line></svg>''',
        "credit": f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>''',
    }

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    svg_data = svg_templates.get(icon_name, "")
    if not svg_data:
        return QIcon(pixmap)

    renderer = QSvgRenderer(svg_data.encode())
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def get_stock_icon(stock_status: str) -> str:
    icons = {
        "out": "●",
        "low": "●",
        "ok": "●"
    }
    return icons.get(stock_status, "●")


class ToastNotification(QFrame):
    COLORS = {
        "success": ("#10b981", "#d1fae5", "✓"),
        "error": ("#ef4444", "#fee2e2", "✕"),
        "warning": ("#f59e0b", "#fef3c7", "⚠"),
        "info": ("#3b82f6", "#dbeafe", "ℹ")
    }

    def __init__(self, message: str, toast_type: str = "info", duration: int = 3000, parent=None):
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setFixedHeight(45)
        self.setMinimumWidth(300)

        color, bg_color, icon = self.COLORS.get(toast_type, self.COLORS["info"])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(10)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")
        icon_label.setFixedWidth(25)

        message_label = QLabel(message)
        message_label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 500;")
        message_label.setWordWrap(True)

        layout.addWidget(icon_label)
        layout.addWidget(message_label, 1)

        self.setStyleSheet(f"""
            #toastNotification {{
                background-color: {bg_color};
                border: 1px solid {color};
                border-radius: 8px;
            }}
        """)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        self.fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)

        self.fade_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(400)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InCubic)
        self.fade_out.finished.connect(self.deleteLater)

        self.fade_in.start()
        QTimer.singleShot(duration, self.fade_out.start)


class ToastManager:
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.active_toasts = []

    def show(self, message: str, toast_type: str = "info", duration: int = 3000):
        toast = ToastNotification(message, toast_type, duration, self.parent)
        toast_width = min(400, self.parent.width() - 40)
        x = self.parent.width() - toast_width - 20
        y = 80 + (len(self.active_toasts) * 55)
        toast.setGeometry(x, y, toast_width, 45)
        toast.show()
        toast.destroyed.connect(lambda t=toast: self._remove_toast(t))
        self.active_toasts.append(toast)

    def _remove_toast(self, toast):
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)


class ProductLoaderThread(QThread):
    products_loaded = Signal(list, int)
    error_occurred = Signal(str)

    def __init__(self, product_service, page: int = 1, filters: Optional[Dict] = None):
        super().__init__()
        self.product_service = product_service
        self.page = page
        self.filters = filters or {}

    def run(self):
        try:
            products, total = self.product_service.get_paginated_products(self.page, self.filters)
            self.products_loaded.emit(products, total)
        except Exception as e:
            self.error_occurred.emit(f"Erreur chargement produits: {str(e)}")

    def stop(self):
        self.quit()
        self.wait(1000)


class OptimizedCartTableWidget(QTableWidget):
    quantity_changed = Signal(int, float)
    discount_changed = Signal(int, float)
    item_removed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._row_widgets_cache = {}
        self._update_lock = False
        self._debounce_timers = {}
        self.setup_ui()

    def setup_ui(self):
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(["#", "Produit", "Qté", "P.U.", "Remise %", "Total", ""])

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Fixed)

        self.setColumnWidth(2, 90)
        self.setColumnWidth(4, 90)
        self.setColumnWidth(6, 45)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def display_cart_items(self, items: List[Dict], currency: str = "FCFA"):
        if self._update_lock:
            return

        self._update_lock = True
        try:
            current_count = self.rowCount()
            new_count = len(items)

            if new_count > current_count:
                self.setRowCount(new_count)
                for row in range(current_count, new_count):
                    self._create_row_widgets(row, items[row], currency)
            elif new_count < current_count:
                for row in range(new_count, current_count):
                    if row in self._row_widgets_cache:
                        if row in self._debounce_timers:
                            self._debounce_timers[row].stop()
                            del self._debounce_timers[row]
                        del self._row_widgets_cache[row]
                self.setRowCount(new_count)

            for row, item in enumerate(items):
                if row < current_count:
                    self._update_row_widgets(row, item, currency)
                else:
                    self._create_row_widgets(row, item, currency)

            self._update_row_numbers()
        finally:
            self._update_lock = False

    def _create_row_widgets(self, row: int, item: Dict, currency: str):
        num_item = QTableWidgetItem(str(row + 1))
        num_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 0, num_item)

        name_item = QTableWidgetItem(item["product_name"])
        name_item.setToolTip(item["product_name"])
        self.setItem(row, 1, name_item)

        qty_edit = QLineEdit()
        qty_edit.setText(f"{item['quantity']:.2f}")
        qty_edit.setAlignment(Qt.AlignCenter)
        qty_edit.setValidator(QDoubleValidator(0.1, 9999, 2))
        qty_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                outline: none;
            }
        """)
        qty_edit.editingFinished.connect(lambda r=row, edit=qty_edit: self._on_quantity_edited(r, edit))
        self.setCellWidget(row, 2, qty_edit)

        price_item = QTableWidgetItem(f"{item['unit_price']:,.0f}")
        price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 3, price_item)

        discount_edit = QLineEdit()
        discount_edit.setText(f"{item.get('discount_percent', 0):.2f}")
        discount_edit.setAlignment(Qt.AlignCenter)
        discount_edit.setValidator(QDoubleValidator(0, 100, 2))
        discount_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                outline: none;
            }
        """)
        discount_edit.editingFinished.connect(lambda r=row, edit=discount_edit: self._on_discount_edited(r, edit))
        self.setCellWidget(row, 4, discount_edit)

        line_total = item['quantity'] * item['unit_price'] * (1 - item.get('discount_percent', 0) / 100)
        total_item = QTableWidgetItem(f"{line_total:,.0f} {currency}")
        total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_item.setForeground(QColor("#3b82f6"))
        self.setItem(row, 5, total_item)

        delete_btn = QPushButton()
        delete_btn.setIcon(get_icon("trash", "#ef4444", 16))
        delete_btn.setToolTip("Supprimer l'article")
        delete_btn.setMaximumWidth(35)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 3px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
            }
        """)
        delete_btn.clicked.connect(lambda _, r=row: self._on_remove_item(r))
        self.setCellWidget(row, 6, delete_btn)

        self._row_widgets_cache[row] = {
            'qty_edit': qty_edit,
            'discount_edit': discount_edit
        }

    def _update_row_widgets(self, row: int, item: Dict, currency: str):
        cached = self._row_widgets_cache.get(row)
        if not cached:
            self._create_row_widgets(row, item, currency)
            return

        name_item = self.item(row, 1)
        if name_item and name_item.text() != item["product_name"]:
            name_item.setText(item["product_name"])

        qty_edit = cached['qty_edit']
        if qty_edit:
            new_qty = f"{item['quantity']:.2f}"
            if qty_edit.text() != new_qty:
                qty_edit.setText(new_qty)

        price_item = self.item(row, 3)
        if price_item:
            new_price = f"{item['unit_price']:,.0f}"
            if price_item.text() != new_price:
                price_item.setText(new_price)

        discount_edit = cached['discount_edit']
        if discount_edit:
            new_discount = f"{item.get('discount_percent', 0):.2f}"
            if discount_edit.text() != new_discount:
                discount_edit.setText(new_discount)

        total_item = self.item(row, 5)
        if total_item:
            line_total = item["quantity"] * item["unit_price"] * (1 - item.get("discount_percent", 0) / 100)
            new_total = f"{line_total:,.0f} {currency}"
            if total_item.text() != new_total:
                total_item.setText(new_total)

    def _update_row_numbers(self):
        for row in range(self.rowCount()):
            num_item = self.item(row, 0)
            if num_item and num_item.text() != str(row + 1):
                num_item.setText(str(row + 1))

    def _on_quantity_edited(self, row: int, edit: QLineEdit):
        try:
            value = float(edit.text())
            if value < 0.1:
                value = 0.1
                edit.setText(f"{value:.2f}")
            self.quantity_changed.emit(row, value)
        except ValueError:
            edit.setText("1.00")

    def _on_discount_edited(self, row: int, edit: QLineEdit):
        try:
            value = float(edit.text())
            if value < 0:
                value = 0
                edit.setText("0.00")
            if value > 100:
                value = 100
                edit.setText("100.00")
            self.discount_changed.emit(row, value)
        except ValueError:
            edit.setText("0.00")

    def _on_remove_item(self, row: int):
        if row in self._row_widgets_cache:
            if row in self._debounce_timers:
                self._debounce_timers[row].stop()
                del self._debounce_timers[row]
            del self._row_widgets_cache[row]

        self.removeRow(row)
        self.item_removed.emit(row)
        self._update_row_numbers()

        new_cache = {}
        for r in range(row, self.rowCount()):
            if r + 1 in self._row_widgets_cache:
                new_cache[r] = self._row_widgets_cache[r + 1]
        for r in range(row):
            if r in self._row_widgets_cache:
                new_cache[r] = self._row_widgets_cache[r]
        self._row_widgets_cache = new_cache

    def update_line_total(self, row: int, line_total: float, currency: str):
        total_item = self.item(row, 5)
        if total_item:
            new_text = f"{line_total:,.0f} {currency}"
            if total_item.text() != new_text:
                total_item.setText(new_text)


class ProductTableWidget(QTableWidget):
    product_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "Code", "Nom", "Prix Vente", "Stock", "Catégorie"
        ])

        header = self.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        self.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            product_id = self.item(row, 0).data(Qt.UserRole)
            if product_id:
                self.product_selected.emit(product_id)

    def display_products(self, products: List[Product], currency: str = "FCFA"):
        self.setRowCount(len(products))

        for row, product in enumerate(products):
            code_item = QTableWidgetItem(product.code or "")
            code_item.setData(Qt.UserRole, product.id)
            self.setItem(row, 0, code_item)

            name_item = QTableWidgetItem(product.name)
            self.setItem(row, 1, name_item)

            price_item = QTableWidgetItem(f"{product.sale_price:,.0f} {currency}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 2, price_item)

            if product.is_out_of_stock:
                stock_text = "● 0"
                stock_color = QColor("#ef4444")
                stock_tooltip = "Rupture de stock!"
            elif product.is_low_stock:
                stock_text = f"● {product.quantity}"
                stock_color = QColor("#f59e0b")
                stock_tooltip = f"Stock faible! Minimum: {product.min_stock}"
            else:
                stock_text = f"● {product.quantity}"
                stock_color = QColor("#10b981")
                stock_tooltip = "Stock OK"

            stock_item = QTableWidgetItem(stock_text)
            stock_item.setTextAlignment(Qt.AlignCenter)
            stock_item.setForeground(stock_color)
            stock_item.setToolTip(stock_tooltip)
            self.setItem(row, 3, stock_item)

            category_item = QTableWidgetItem(product.category or "")
            self.setItem(row, 4, category_item)
