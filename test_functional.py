print("=" * 60)
print("TEST FONCTIONNEL - KORGO PRO")
print("=" * 60)

import sys, os
sys.path.insert(0, ".")

print("\n1. IMPORT DES MODULES...")

modules = [
    "core.database",
    "core.models.user",
    "core.models.customer",
    "core.models.sale_models",
    "core.models.stock_models",
    "core.models.activity_log",
    "core.models.sale_log",
    "core.security",
    "core.log_manager",
    "core.sale_log_manager",
    "core.database_manager",
    "core.bruteforce_protection",
    "utils.settings_manager",
    "utils.helpers",
    "utils.resource_path",
    "controllers.auth_controller",
]

for mod_name in modules:
    try:
        __import__(mod_name.replace("/", "."))
        print(f"   OK {mod_name}")
    except Exception as e:
        print(f"   FAIL {mod_name}: {e}")

print("\n2. TEST BASE DE DONNEES...")
from core.database import engine, Base, SessionLocal
from sqlalchemy import inspect, text

try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"   Tables trouvees: {len(tables)}")
    for t in sorted(tables):
        cols = [c["name"] for c in inspector.get_columns(t)]
        pk_info = inspector.get_pk_constraint(t)
        pk = pk_info.get("constrained_columns", []) if isinstance(pk_info, dict) else []
        print(f"      - {t} ({len(cols)} cols, PK: {pk})")
except Exception as e:
    print(f"   FAIL DB inspect: {e}")
