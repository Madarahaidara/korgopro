import sys, os, subprocess, json

print("=" * 50)
print("KORGO PRO - AUDIT DE TEST")
print("=" * 50)

print("\n1. Python: {}".format(sys.version))

print("\n2. Dependances:")
deps = ["PySide6", "sqlalchemy", "bcrypt", "reportlab", "pandas", "openpyxl", "alembic"]
for dep in deps:
    try:
        mod = __import__(dep)
        v = getattr(mod, "__version__", getattr(mod, "Version", "inconnu"))
        print("   OK {} == {}".format(dep, v))
    except ImportError:
        print("   MISSING {} - NON INSTALLE".format(dep))

print("\n3. Base de donnees:")
db = "korgo_pro.db"
if os.path.exists(db):
    kb = os.path.getsize(db) / 1024
    print("   OK {} ({:.1f} Ko)".format(db, kb))
else:
    print("   MISSING {} introuvable".format(db))

print("\n4. Fichiers .qss:")
qss = []
for r, d, f in os.walk("ui"):
    for fn in f:
        if fn.endswith(".qss"):
            qss.append(os.path.join(r, fn))
if qss:
    for q in qss:
        print("   OK {}".format(q))
else:
    print("   MISSING Aucun fichier .qss trouve")

print("\n5. Fichiers de test:")
tests = []
for r, d, f in os.walk("."):
    for fn in f:
        if fn.startswith("test_") and fn.endswith(".py"):
            tests.append(os.path.join(r, fn))
if tests:
    for t in tests:
        print("   OK {}".format(t))
else:
    print("   MISSING AUCUN TEST TROUVE")

print("\n6. Structure du projet:")
print("   controllers/")
for f in os.listdir("controllers"):
    if f.endswith(".py"):
        print("      {}".format(f))
print("   core/")
for f in os.listdir("core"):
    p = os.path.join("core", f)
    if os.path.isfile(p) and f.endswith(".py"):
        print("      {}".format(f))
print("   core/models/")
for f in os.listdir("core/models"):
    if f.endswith(".py"):
        print("      {}".format(f))
print("   ui/views/")
for f in os.listdir("ui/views"):
    if f.endswith(".py"):
        print("      {}".format(f))
print("   utils/")
for f in os.listdir("utils"):
    if f.endswith(".py"):
        print("      {}".format(f))

print("\n7. Parametres entreprise:")
if os.path.exists("company_settings.json"):
    with open("company_settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
        print("   Nom: {}".format(settings.get('company_name', 'N/A')))
        print("   Devise: {}".format(settings.get('currency', 'N/A')))
        print("   TVA: {}".format(settings.get('tax_rate', 'N/A')))
else:
    print("   company_settings.json introuvable")

print("\n8. Verification DB interne:")
try:
    from core.database import SessionLocal, engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("   Tables ({}): {}".format(len(tables), tables))
    for t in tables:
        cols = [c["name"] for c in inspector.get_columns(t)]
        print("      - {}: {}".format(t, cols))
except Exception as e:
    print("   Erreur DB: {}".format(e))

print("\n" + "=" * 50)
print("AUDIT TERMINE")
print("=" * 50)

"""Script pour vérifier les dépendances et l'état du projet"""
import sys
import os

print(f"Python: {sys.version}")

# Dépendances
deps = {
    "PySide6": None,
    "sqlalchemy": None, 
    "bcrypt": None,
    "reportlab": None,
    "pandas": None,
    "openpyxl": None,
    "alembic": None,
}

for dep in deps:
    try:
        mod = __import__(dep)
        version = getattr(mod, "__version__", getattr(mod, "Version", "inconnu"))
        deps[dep] = version
        print(f"✅ {dep}: {version}")
    except ImportError as e:
        print(f"❌ {dep}: NON INSTALLÉ ({e})")

# Base de données
db_path = "korgo_pro.db"
if os.path.exists(db_path):
    size_kb = os.path.getsize(db_path) / 1024
    print(f"\n📦 Base de données: {db_path} ({size_kb:.1f} Ko)")
else:
    print(f"\n❌ Base de données: {db_path} introuvable")

# Fichiers QSS
qss_files = []
for root, dirs, files in os.walk("ui"):
    for f in files:
        if f.endswith(".qss"):
            qss_files.append(os.path.join(root, f))
print(f"\n📄 Fichiers QSS trouvés: {len(qss_files)}")
for qss in qss_files:
    print(f"   - {qss}")

# Fichiers de test
test_files = []
for root, dirs, files in os.walk("."):
    for f in files:
        if f.startswith("test_") and f.endswith(".py"):
            test_files.append(os.path.join(root, f))
print(f"\n🧪 Fichiers de test trouvés: {len(test_files)}")
for tf in test_files:
    print(f"   - {tf}")

if not test_files:
    print("   ⚠️ AUCUN TEST TROUVÉ — risque de régression")

# company_settings
if os.path.exists("company_settings.json"):
    import json
    with open("company_settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
    print(f"\n⚙️ Paramètres entreprise: {json.dumps(settings, indent=2, ensure_ascii=False)[:200]}...")
