print("=" * 60)
print("TEST FONCTIONNEL - PARTIE 3")
print("=" * 60)

import sys, os
sys.path.insert(0, ".")

print("\n5. TEST BRUTEFORCE PROTECTION...")
from core.bruteforce_protection import BruteForceProtection

try:
    bfp = BruteForceProtection()
    assert bfp.is_locked_out("test_user") == False
    print("   5 tentatives echouees...")
    for i in range(5):
        locked = bfp.record_failed_attempt("test_user")
    bfp2 = BruteForceProtection()
    assert bfp.is_locked_out("test_user") == True
    print("   OK: utilisateur bloque apres 5 tentatives")
    bfp.record_successful_attempt("test_user")
    assert bfp.is_locked_out("test_user") == False
    print("   OK: debloque apres reussite")
    print(f"   Config: max={bfp.max_attempts}, duree={bfp.lockout_duration}")
except Exception as e:
    print(f"   FAIL: {e}")

print("\n6. TEST SETTINGS MANAGER...")
from utils.settings_manager import SettingsManager

try:
    sm = SettingsManager()
    settings = sm.get_all_settings()
    print(f"   Entreprise: {settings.get('company_name')}")
    print(f"   Devise: {settings.get('currency')}")
    print(f"   TVA: {settings.get('tax_rate')}%")
    print(f"   Nb parametres: {len(settings)}")
    print(f"   Theme: {settings.get('theme')}")
except Exception as e:
    print(f"   FAIL: {e}")

print("\n7. TEST LOG MANAGER...")
from core.log_manager import LogManager

try:
    lm = LogManager()
    result = lm.get_logs(limit=5)
    if result.get("success"):
        print(f"   Total logs: {result.get('total', 0)}")
        for log in result.get("logs", [])[:3]:
            print(f"      [{log.created_at}] {log.username}: {log.action}")
    else:
        print(f"   Erreur: {result.get('error')}")
except Exception as e:
    print(f"   FAIL: {e}")

print("\n8. TEST DATABASE MANAGER...")
from core.database_manager import DatabaseManager

try:
    dbm = DatabaseManager()
    info = dbm.get_database_info()
    print(f"   Moteur: {info.get('engine')}")
    print(f"   Base: {info.get('database')}")
    print(f"   Tables: {len(info.get('tables', {}))}")
    for t_name, t_info in info.get("tables", {}).items():
        print(f"      - {t_name}: {t_info['row_count']} lignes")
except Exception as e:
    print(f"   FAIL: {e}")

print("\n9. TEST CHEMIN RESSOURCES...")
from utils.resource_path import resource_path

try:
    for name in ["ui/themes/light.qss", "ui/themes/dark.qss", "ui/themes/main.qss"]:
        p = resource_path(name)
        existe = os.path.exists(p)
        taille = os.path.getsize(p) if existe else 0
        print(f"   {name}: {p} ({taille} octets)")
except Exception as e:
    print(f"   FAIL: {e}")

print("\n10. TEST CONTROLLER AUTH...")
from controllers.auth_controller import AuthController
from core.database import SessionLocal
from core.models.user import User

try:
    auth = AuthController()
    with SessionLocal() as session:
        user = session.query(User).first()
        if user:
            result = auth.get_user_by_id(user.id)
            if result:
                print(f"   Utilisateur #{user.id}: {result['username']} ({result['role']})")
            else:
                print(f"   ERREUR: get_user_by_id a retourne None pour l'utilisateur #{user.id}")
        else:
            print("   Aucun utilisateur trouve dans la DB")
except Exception as e:
    print(f"   FAIL: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TESTS TERMINES")
print("=" * 60)
