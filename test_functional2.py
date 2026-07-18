print("=" * 60)
print("TEST FONCTIONNEL - PARTIE 2")
print("=" * 60)

import sys, os
sys.path.insert(0, ".")
from core.database import SessionLocal
from sqlalchemy import text

print("\n2b. TEST DONNEES DB...")
try:
    with SessionLocal() as session:
        result = session.execute(text("SELECT COUNT(*) as c FROM users"))
        count = result.scalar()
        print(f"   Utilisateurs: {count}")
        
        result = session.execute(text("SELECT id, username, role, active FROM users"))
        for row in result:
            print(f"      - {row.username} (role={row.role}, actif={row.active})")
except Exception as e:
    print(f"   FAIL: {e}")
    import traceback
    traceback.print_exc()

print("\n3. TEST SECURITE...")
from core.security import hash_password, verify_password, _is_bcrypt_hash

try:
    pwd = "test_password_123"
    hashed = hash_password(pwd)
    assert _is_bcrypt_hash(hashed), "Le hash doit etre bcrypt"
    assert verify_password(pwd, hashed), "Verification doit reussir"
    assert not verify_password("wrong", hashed), "Mauvais mdp doit echouer"
    print(f"   OK hash/verify password (hash: {hashed[:30]}...)")
except Exception as e:
    print(f"   FAIL security: {e}")
    import traceback
    traceback.print_exc()

print("\n4. TEST MODELS...")
from core.models.stock_models import Product, Supplier
from core.models.sale_models import Sale, SaleItem, Customer, Payment

try:
    with SessionLocal() as session:
        products_count = session.query(Product).count()
        sales_count = session.query(Sale).count()
        customers_count = session.query(Customer).count()
        suppliers_count = session.query(Supplier).count()
        
        print(f"   Produits: {products_count}")
        print(f"   Ventes: {sales_count}")
        print(f"   Clients: {customers_count}")
        print(f"   Fournisseurs: {suppliers_count}")
        
        if products_count > 0:
            p = session.query(Product).first()
            print(f"   1er produit: {p.code} - {p.name}")
            print(f"     Stock: {p.quantity}, Prix: {p.sale_price}")
            if p.supplier:
                print(f"     Fournisseur: {p.supplier.name}")
        
        if sales_count > 0:
            s = session.query(Sale).first()
            print(f"   1ere vente: #{s.sale_number}")
            print(f"     Montant: {s.total_amount} {s.currency}")
            print(f"     Items: {len(s.items)}")
except Exception as e:
    print(f"   FAIL models: {e}")
    import traceback
    traceback.print_exc()
