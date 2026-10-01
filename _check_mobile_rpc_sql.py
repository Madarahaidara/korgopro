"""Pré-vol SQL (statique + schéma réel) — supabase_mobile_rpc.sql.

Pourquoi ce script ?
--------------------
PostgreSQL ne compile PAS le corps PL/pgSQL à la création : `CREATE FUNCTION`
réussit même si une variable locale n'existe pas. L'erreur n'apparaît qu'à
l'exécution, dans le téléphone :

    column "v_currency" does not exist   (constaté en production)

Ce script détecte AVANT déploiement :
  1. toute variable `v_*` utilisée mais non déclarée dans le bloc DECLARE ;
  2. toute colonne citée dans un INSERT / UPDATE / SELECT ... INTO qui
     n'existe pas réellement dans la base (croisement information_schema).

Usage : python _check_mobile_rpc_sql.py
"""
import re
from pathlib import Path

from sqlalchemy import text

from _test_mobile_rpc_live import connect

SQL_FILE = Path(__file__).with_name("supabase_mobile_rpc.sql")

FUNCTION_RE = re.compile(
    r"CREATE OR REPLACE FUNCTION (?:public|app_security)\.(\w+)\s*\(.*?AS \$\$(.*?)\$\$;",
    re.S)
DECL_RE = re.compile(
    r"^\s{4}(\w+)\s+(?:text|numeric|integer|bigint|jsonb|boolean|record|date|"
    r"timestamptz|uuid|double precision)", re.M)
VAR_RE = re.compile(r"\bv_[a-z0-9_]+")
INSERT_RE = re.compile(r"INSERT INTO public\.(\w+)\s*\(([^)]*)\)")
UPDATE_RE = re.compile(r"UPDATE public\.(\w+)\s+SET\s+(.*?)\s+WHERE", re.S)


def functions(sql: str):
    """(nom, corps) de chaque fonction PL/pgSQL du fichier."""
    return FUNCTION_RE.findall(sql)


def static_vars(sql: str):
    """Variables v_* non declarees, par fonction."""
    problems = []
    for name, body in functions(sql):
        # Le bloc DECLARE s'arrete au BEGIN de premier niveau.
        head, _, tail = body.partition("\nBEGIN")
        declared = set(DECL_RE.findall(head))
        used = set(VAR_RE.findall(tail))
        missing = sorted(used - declared)
        if missing:
            problems.append((name, missing, sorted(declared)))
    return problems


def db_columns(c, table: str) -> set[str]:
    rows = c.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t"), {"t": table})
    return {r[0] for r in rows}


def schema_refs(sql: str):
    """(table, colonne, contexte) citees par les INSERT/UPDATE du fichier."""
    refs = []
    for table, cols in INSERT_RE.findall(sql):
        for col in cols.split(","):
            col = col.strip()
            if col:
                refs.append((table, col, "INSERT"))
    for table, set_clause in UPDATE_RE.findall(sql):
        for assign in set_clause.split(","):
            col = assign.split("=")[0].strip()
            if re.fullmatch(r"\w+", col):
                refs.append((table, col, "UPDATE"))
    return refs


def main() -> int:
    sql = SQL_FILE.read_text(encoding="utf-8")
    print(f"Fichier : {SQL_FILE.name}")
    print(f"Fonctions PL/pgSQL trouvees : "
          f"{', '.join(n for n, _ in functions(sql)) or '(aucune)'}")

    problems = 0
    print("\n== 1. Variables locales declarees ==")
    findings = static_vars(sql)
    for name, missing, declared in findings:
        problems += len(missing)
        print(f"KO    {name} : utilisee(s) mais non declaree(s) -> "
              f"{', '.join(missing)}")
        print(f"      declarees : {', '.join(declared)}")
    if not findings:
        print("OK    aucune variable v_* utilisee sans declaration")

    print("\n== 2. Colonnes citees vs schema reel ==")
    refs = schema_refs(sql)
    unknown = 0
    engine = connect()
    with engine.connect() as c:
        cache: dict[str, set[str]] = {}
        for table, col, kind in refs:
            if table not in cache:
                cache[table] = db_columns(c, table)
            if not cache[table]:
                unknown += 1
                print(f"KO    table public.{table} inexistante ({kind})")
            elif col not in cache[table]:
                unknown += 1
                print(f"KO    public.{table}.{col} inexistante ({kind})")
    problems += unknown
    print(f"{'OK   ' if unknown == 0 else '     '} "
          f"{len(refs)} reference(s) de colonne verifiee(s) "
          f"sur {len(cache)} table(s)")
    print("\nResultat :", "AUCUN PROBLEME" if problems == 0
          else f"{problems} probleme(s) a corriger")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
