import sys
sys.path.insert(0, '.')

print("=" * 60)
print("TEST DES BUGS IDENTIFIES")
print("=" * 60)

# ===== BUG 1: Singleton BruteForceProtection =====
print("\n1. TEST SINGLETON BRUTEFORCE PROTECTION...")
from core.bruteforce_protection import BruteForceProtection

bfp = BruteForceProtection()
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
bfp.record_failed_attempt('test_user')
locked_after_5 = bfp.is_locked_out('test_user')

# Nouvelle instanciation
bfp2 = BruteForceProtection()
locked_after_reinit = bfp2.is_locked_out('test_user')

print(f"   Apres 5 tentatives - locked: {locked_after_5}")
print(f"   Apres re-instanciation - locked: {locked_after_reinit}")
if locked_after_5 and not locked_after_reinit:
    print("   BUG CONFIRME: Le singleton reinitialise son etat a chaque instanciation!")
elif locked_after_5 and locked_after_reinit:
    print("   OK: Le singleton conserve son etat")
else:
    print("   Etat inattendu")

# ===== BUG 2: Test get_pk_constraint =====
print("\n2. TEST INSPECTION DB...")
from core.database import engine
from sqlalchemy import inspect

try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"   Tables trouvees: {len(tables)}")
    for t in sorted(tables[:3]):
        try:
            pk_info = inspector.get_pk_constraint(t)
            cols = [c["name"] for c in inspector.get_columns(t)]
            if isinstance(pk_info, dict):
                pk = pk_info.get("constrained_columns", [])
                print(f"      - {t} ({len(cols)} cols, PK: {pk})")
            else:
                print(f"      - {t} ({len(cols)} cols)")
                print(f"      BUG: get_pk_constraint retourne {type(pk_info)} au lieu d'un dict")
        except Exception as e:
            print(f"      - {t}: Erreur => {e}")
except Exception as e:
    print(f"   FAIL: {e}")

# ===== BUG 3: Roles incoherents =====
print("\n3. TEST COHERENCE DES ROLES...")
from core.database import SessionLocal
from core.models.user import User
from sqlalchemy import text

managed_roles = {"ADMIN", "CAISSIER", "GERANT"}
with SessionLocal() as session:
    roles = session.execute(text("SELECT DISTINCT role FROM users")).fetchall()
    db_roles = set(r[0] for r in roles)
    print(f"   Roles en DB: {db_roles}")
    print(f"   Roles geres dans main_window: {managed_roles}")
    missing = db_roles - managed_roles
    if missing:
        print(f"   BUG: Les roles {missing} ne sont pas geres dans le code (main_window.py)")
    else:
        print("   OK: Tous les roles sont geres")

    # Verifier les permissions pour le role GESTIONNAIRE
    from ui.views.sale_view import ROLES
    allowed = ROLES.get("GESTIONNAIRE", [])
    print(f"   Permissions pour GESTIONNAIRE: {allowed}")
    if not allowed:
        print("   BUG: Le role GESTIONNAIRE n'a aucune permission dans sale_view.py")

    # Verifier que le user 'manager' existe
    manager = session.query(User).filter(User.username == 'manager').first()
    if manager:
        print(f"   User manager: role={manager.role}")
        if manager.role not in managed_roles:
            print(f"   BUG: L'utilisateur 'manager' a le role '{manager.role}' non gere par le code")

# ===== BUG 4: convert_to_sale id =====
print("\n4. TEST CONVERT_TO_SALE ID...")
try:
    from core.database import SessionLocal
    from core.models.sale_models import ProformaInvoice

    session = SessionLocal()
    try:
        proforma = session.query(ProformaInvoice).first()
        if proforma:
            print(f"   Proforma trouvee: {proforma.proforma_number} (status: {proforma.status})")
            print("   Analyse du code: proforma.converted_to_sale_id = sale.id est appelle AVANT session.flush()")
            print("   BUG POTENTIEL: sale.id sera None si pas de flush avant")
        else:
            print("   Aucune proforma trouvee en DB")
    finally:
        session.close()
except Exception as e:
    print(f"   FAIL: {e}")

# ===== BUG 5: Extrait SQL =====
print("\n5. TEST EXTRACT SQL (compatibilite SQLite)...")
try:
    from core.database import SessionLocal
    from sqlalchemy import text
    with SessionLocal() as session:
        try:
            result = session.execute(text("SELECT EXTRACT(YEAR FROM '2026-01-01')")).fetchone()
            print(f"   Resultat EXTRACT: {result}")
            print("   OK: SQLite supporte EXTRACT")
        except Exception as e:
            print(f"   BUG: SQLite ne supporte pas EXTRACT: {e}")
except Exception as e:
    print(f"   FAIL: {e}")

# ===== BUG 6: SaleService log manager =====
print("\n6. TEST SALE SERVICE LOG MANAGER...")
try:
    from ui.views.sale_services import SaleService
    import inspect
    sig = inspect.getsource(SaleService)
    if "SaleLogManager()" in sig and "SaleLogManager(self.db_session)" not in sig:
        print("   BUG: SaleService cree SaleLogManager sans session, les logs utilisent une session differente")
    else:
        print("   OK ou verifie manuellement")
except Exception as e:
    print(f"   FAIL: {e}")

# ===== BUG 7: UnicodeEncodeError dans icon_manager =====
print("\n7. TEST UNICODE ENCODING...")
try:
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c", "print('✓ test')"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"   BUG: Probleme d'encodage Unicode: {result.stderr}")
    else:
        print("   OK: Encodage Unicode fonctionne")
except Exception as e:
    print(f"   FAIL: {e}")

# ===== BUG 8: Test main.py import =====
print("\n8. TEST IMPORT MAIN.PY...")
try:
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); from ui.icons.icon_manager import IconManager; print('OK')"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"   BUG: Erreur import: {result.stderr}")
    else:
        print("   OK: Import reussi")
except Exception as e:
    print(f"   FAIL: {e}")

print("\n" + "=" * 60)
print("FIN DES TESTS DE BUGS")
print("=" * 60)