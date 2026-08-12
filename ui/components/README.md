# ui/components/README.md

# UI Components Library

Token-based, reusable components for consistent design across the application.

All components use `ui/themes/variables.json` for theming. Colors and styles are substituted at runtime via the theme manager.

## Components

### 1. ResponsiveMenu

Adaptive navigation menu that switches between desktop sidebar and mobile drawer.

**Features:**
- Desktop (>768px): Fixed sidebar with expand/collapse animation
- Mobile (<768px): Drawer overlay with hamburger toggle
- Smooth animations and transitions
- Accessibility labels for screen readers

**Usage:**

```python
from ui.components import ResponsiveMenu

menu = ResponsiveMenu()
menu.add_menu_item("dashboard", "Dashboard", icon=dashboard_icon)
menu.add_menu_item("sales", "Ventes", icon=sales_icon)
menu.add_menu_item("stock", "Stock", icon=stock_icon)

menu.menu_item_clicked.connect(self.on_menu_item_selected)
```

**API:**

- `add_menu_item(menu_id, label, icon=None, submenu_items=None)` - Add menu item
- `set_menu_title(title)` - Update menu title
- `get_menu_state()` - Get current state (mobile, expanded, width)
- Signal: `menu_item_clicked(menu_id, label)`

---

### 2. CustomButton

Versatile button with multiple variants and sizes.

**Variants:**
- `primary` - Main action (blue, filled)
- `secondary` - Alternative (gray, outlined)
- `danger` - Destructive (red, filled)
- `outline` - Border-only style

**Sizes:**
- `small` (32px) - Compact actions
- `medium` (40px) - Default, most common
- `large` (48px) - Prominent actions
- `icon` (36px) - Icon-only buttons

**Usage:**

```python
from ui.components import CustomButton

# Primary button
btn_save = CustomButton("Enregistrer", variant="primary")

# Danger button with icon
btn_delete = CustomButton("Supprimer", variant="danger", icon="icons/trash.png")

# Outline small button
btn_cancel = CustomButton("Annuler", variant="outline", size="small")

# Icon-only button
btn_settings = CustomButton("", variant="secondary", size="icon", icon="icons/settings.png")
btn_settings.setAccessibleName("Paramètres")
```

**API:**

- `set_icon(icon_path)` - Set/update button icon
- `set_variant(variant)` - Change button variant dynamically
- Inherits all QPushButton methods

---

### 3. CustomCard

Container component for grouping related content.

**Features:**
- Optional header with title
- Main content area
- Optional footer
- Elevation/shadow control
- Token-based border and background

**Elevation Levels:**
- `0` - No shadow
- `1` - Subtle shadow (default)
- `2` - Light shadow
- `3` - Medium shadow
- `4` - Heavy shadow

**Usage:**

```python
from ui.components import CustomCard
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Create card with title
card = CustomCard(title="Statistics", elevation=2)

# Set content
content = QWidget()
layout = QVBoxLayout(content)
layout.addWidget(QLabel("Sales: $1,250"))
layout.addWidget(QLabel("Orders: 42"))
card.set_content(content)

# Add footer
footer = QLabel("Last updated: 2 minutes ago")
card.set_footer(footer)

# Dynamically change elevation
card.set_elevation(3)
```

**API:**

- `set_content(widget)` - Set main content
- `set_footer(widget)` - Add footer section
- `set_elevation(level)` - Change shadow depth (0-4)

---

## Token System

All components use tokens from `ui/themes/variables.json`. The theme manager substitutes tokens at runtime.

**Common tokens:**

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `{{PRIMARY}}` | #2F4255 | #60a5fa | Main brand color |
| `{{PRIMARY_DARK}}` | #1B3A7A | #3b82f6 | Hover state |
| `{{PRIMARY_DARKER}}` | #0d2052 | #1d4ed8 | Pressed state |
| `{{DANGER}}` | #dc2626 | #ef4444 | Destructive actions |
| `{{BG}}` | #f8fafc | #0f1724 | Main background |
| `{{BG_SECONDARY}}` | #f1f5f9 | #1a2332 | Secondary background |
| `{{TEXT}}` | #1e293b | #e6eef8 | Main text |
| `{{BORDER}}` | #e2e8f0 | #1f2937 | Borders |

Add more tokens to `variables.json` and reference them in component stylesheets.

---

## Integration with Existing Components

To migrate existing UI to use the component library:

1. **Import components:**
   ```python
   from ui.components import CustomButton, CustomCard, ResponsiveMenu
   ```

2. **Replace hardcoded styles:**
   ```python
   # Before
   btn = QPushButton("Save")
   btn.setStyleSheet("background-color: #2F4255; ...")
   
   # After
   btn = CustomButton("Save", variant="primary")
   ```

3. **Use token variables in custom stylesheets:**
   ```python
   self.setStyleSheet("""
       QLabel {
           color: {{TEXT}};
           font-size: 14px;
       }
   """)
   ```

---

## Future Enhancements

- [ ] Input/TextField component
- [ ] Select/Dropdown component
- [ ] Table component with sorting/filtering
- [ ] Modal/Dialog component
- [ ] Notification/Toast component
- [ ] Tabs component
- [ ] Breadcrumb navigation
- [ ] Form builder utility

---

## Testing

Components support accessibility features:
- `setAccessibleName(name)` - Screen reader label
- `setAccessibleDescription(desc)` - Detailed description

Example:
```python
btn = CustomButton("Delete", variant="danger")
btn.setAccessibleName("Delete item")
btn.setAccessibleDescription("Permanently remove this item (cannot be undone)")
```
