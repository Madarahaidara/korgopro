# -*- coding: utf-8 -*-
"""Patch multi-magasins pour les fichiers proforma (fins de ligne CRLF).

Script utilitaire temporaire : chaque remplacement doit être unique, sinon le
script échoue sans rien écrire.
"""
MANAGER = 'core/proforma_invoice_manager.py'
VIEW = 'ui/views/proforma_invoice_view.py'

PATCHES = {
    MANAGER: [
        (
            "from core.sale_log_manager import SaleLogManager\r\n",
            "from core.sale_log_manager import SaleLogManager\r\n"
            "from core.store_manager import current_store_id_for\r\n",
        ),
        (
            "                sale_number=sale_number,\r\n"
            "                customer_id=proforma.customer_id,\r\n"
            "                cashier_id=created_by_id,\r\n",
            "                sale_number=sale_number,\r\n"
            "                customer_id=proforma.customer_id,\r\n"
            "                cashier_id=created_by_id,\r\n"
            "                # Multi-magasins : vente rattachée au magasin actif\r\n"
            "                store_id=current_store_id_for(self.session),\r\n",
        ),
    ],
    VIEW: [
        (
            "from utils.settings_manager import SettingsManager\r\n",
            "from utils.settings_manager import SettingsManager\r\n"
            "from core.store_manager import scope_products_query\r\n",
        ),
        (
            "            query = self.db_session.query(Product).filter(Product.active == True)\r\n"
            "            if search:\r\n",
            "            query = self.db_session.query(Product).filter(Product.active == True)\r\n"
            "            # Multi-magasins : produits du magasin actif uniquement\r\n"
            "            query = scope_products_query(query, self.db_session, Product)\r\n"
            "            if search:\r\n",
        ),
        (
            "            return self.db_session.query(Product).filter(Product.active == True)"
            ".order_by(Product.name).all()\r\n",
            "            query = self.db_session.query(Product).filter(Product.active == True)\r\n"
            "            query = scope_products_query(query, self.db_session, Product)\r\n"
            "            return query.order_by(Product.name).all()\r\n",
        ),
    ],
}


def patch(path, replacements):
    with open(path, encoding='utf-8', newline='') as handle:
        text = handle.read()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            print(f"ECHEC {path}: {count} occurrence(s) pour {old[:70]!r}")
            return False
        text = text.replace(old, new)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)
    print(f"OK {path} ({len(replacements)} remplacement(s))")
    return True


if __name__ == '__main__':
    ok = True
    for path, replacements in PATCHES.items():
        ok = patch(path, replacements) and ok
    raise SystemExit(0 if ok else 1)