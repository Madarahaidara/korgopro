"""Diagnostic (LECTURE SEULE) : les RPC de l'application mobile sont-elles
réellement installées dans la base Supabase ?

Répond à l'erreur PostgREST :
    « Could not find the function public.app_create_sale(...) in the schema
      cache »  (code PGRST202)

Deux causes possibles, ce script les distingue :
  * la fonction n'existe pas en base        -> supabase_mobile_rpc.sql non appliqué ;
  * la fonction existe mais PostgREST ne la voit pas -> cache de schéma à recharger.

Usage :
    python _diag_mobile_rpc.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

RPC = ("app_mobile_context", "app_create_sale", "app_register_payment",
       "app_stock_movement", "app_cancel_sale")

# Signatures attendues par mobile/src/api/rpc.js (noms ET types).
EXPECTED = {
    "app_create_sale": [
        ("p_items", "jsonb"), ("p_store_id", "integer"),
        ("p_customer_id", "integer"), ("p_discount_amount", "numeric"),
        ("p_tax_amount", "numeric"), ("p_payment_method", "text"),
        ("p_amount_paid", "numeric"), ("p_notes", "text"),
        ("p_currency", "text"), ("p_account_id", "integer"),
    ],
    "app_register_payment": [
        ("p_sale_id", "integer"), ("p_amount", "numeric"),
        ("p_payment_method", "text"), ("p_account_id", "integer"),
        ("p_notes", "text"),
    ],
    "app_stock_movement": [
        ("p_product_id", "integer"), ("p_movement_type", "text"),
        ("p_quantity", "numeric"), ("p_reason", "text"),
        ("p_unit_cost", "numeric"), ("p_reference", "text"),
        ("p_notes", "text"), ("p_store_id", "integer"),
    ],
    "app_cancel_sale": [
        ("p_sale_id", "integer"), ("p_reason", "text"),
    ],
    "app_mobile_context": [],
}

FUNCTIONS = text("""
    SELECT n.nspname,
           p.proname,
           pg_get_function_identity_arguments(p.oid)      AS args,
           pg_get_function_arguments(p.oid)               AS args_full,
           has_function_privilege('authenticated', p.oid, 'EXECUTE') AS anon_ok,
           has_function_privilege('anon', p.oid, 'EXECUTE')          AS anon_grant,
           p.prosecdef                                    AS security_definer
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname IN ('public', 'app_security')
      AND p.proname IN ('app_mobile_context', 'app_create_sale',
                        'app_register_payment', 'app_stock_movement',
                        'app_cancel_sale', 'current_role', 'can')
    ORDER BY p.proname
""")


def mobile_ref() -> str:
    """Référence du projet Supabase utilisée par l'application mobile."""
    env = Path(__file__).with_name("mobile") / ".env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("EXPO_PUBLIC_SUPABASE_URL="):
            host = line.split("=", 1)[1].strip()
            return host.replace("https://", "").split(".")[0]
    return "?"


def db_ref(url: str) -> str:
    """Référence du projet Supabase déduite de DATABASE_URL.

    Attention : l'hôte est un pooler (`aws-1-eu-west-1.pooler.supabase.com`),
    qui ne contient PAS la référence du projet. Elle se trouve dans
    l'utilisateur : `postgres.<ref>` (ou dans l'hôte `db.<ref>.supabase.co`).
    """
    user = url.split("://", 1)[-1].split(":", 1)[0]        # postgres.<ref>
    if "." in user:
        return user.split(".", 1)[1]
    host = url.split("@", 1)[-1].split("/", 1)[0].split(":")[0]
    if host.startswith("db."):
        return host.split(".")[1]
    return host


def main() -> int:
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"]
    engine = create_engine(
        url.replace("postgresql://", "postgresql+psycopg2://"),
        connect_args={"sslmode": "require"},
    )

    print(f"Projet Supabase (base)   : {db_ref(url)}")
    print(f"Projet Supabase (mobile) : {mobile_ref()}")
    print("ALERTE : mobile et base pointent deux projets DIFFERENTS !"
          if db_ref(url).upper() != mobile_ref().upper()
          else "OK : mobile et base = meme projet")

    with engine.connect() as c:
        rows = c.execute(FUNCTIONS).fetchall()
    found = {}
    for schema, name, args, args_full, priv, anon_grant, secdef in rows:
        print(f"\n[{schema}.{name}]")
        print(f"   arguments    : {args or '(aucun)'}")
        print(f"   defaults     : {args_full or '(aucun)'}")
        print(f"   SECURITY DEFINER : {secdef}")
        print(f"   EXECUTE authenticated : {priv}   anon : {anon_grant}")
        found.setdefault(name, []).append(args)

    print("\n----- Resultat -----")
    problems = 0
    for name, expected in EXPECTED.items():
        present = name in found
        print(f"{'OK  ' if present else 'KO  '} {name:22} "
              f"{'presente' if present else 'ABSENTE EN BASE'}")
        if not present:
            problems += 1
            continue
        # Comparaison nom par nom (l'ordre SQL compte pour PostgREST aussi).
        got = []
        for chunk in found[name][0].split(","):
            chunk = chunk.strip()
            if chunk:
                got.append(tuple(chunk.split()))
        if [g[0] for g in got] != [e[0] for e in expected]:
            problems += 1
            print(f"     ECART de signature (attendue : "
                  f"{', '.join(e[0] for e in expected)})")
            print(f"     trouvee en base : {', '.join(g[0] for g in got)}")
        else:
            print(f"     signature conforme aux appels mobile/src/api/rpc.js")

    print("\nVerdict :",
          "RPC ABSENTES -> appliquer supabase_mobile_rpc.sql (python _apply_mobile_rpc.py)"
          if problems else "toutes les RPC attendues sont installees")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
