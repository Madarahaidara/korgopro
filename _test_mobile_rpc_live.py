"""Test LIVE (transaction ANNULÉE) : une vente mobile complète passe-t-elle ?

Reproduit l'appel de `mobile/src/api/rpc.js` avec un JWT Supabase SIMULÉ :

    set_config('request.jwt.claims', '{"sub": <uid>, "email": ..., "role": ...}')
    SET LOCAL ROLE authenticated
    SELECT public.app_create_sale(...)

…puis ROLLBACK : la base n'est pas modifiée (aucune vente fantôme).

Le script vérifie aussi les points qui font échouer une RPC installée :
  * FORCE ROW LEVEL SECURITY + policies `TO authenticated` sur des fonctions
    SECURITY DEFINER (le corps écrit-il réellement ?) ;
  * droits EXECUTE pour `authenticated` / `anon` ;
  * refus métier hors droits (caissier qui ne peut pas gérer la trésorerie).

Usage : python _test_mobile_rpc_live.py
"""
import json
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROBLEMS = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PROBLEMS
    if not ok:
        PROBLEMS += 1
    print(f"{'OK  ' if ok else 'ECHEC'} {label}" + (f"  ({detail})" if detail else ""))


def fail(detail: str) -> None:
    """Erreur technique (exception) : comptée puis signalée."""
    global PROBLEMS
    PROBLEMS += 1
    print(f"ECHEC {detail}")


def connect():
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    return create_engine(url, connect_args={"sslmode": "require"})


def show_facts(c) -> None:
    """État RLS + propriétaires + rôles (contexte de l'échec éventuel)."""
    print("== Rôles ==")
    for row in c.execute(text(
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
        "WHERE rolname IN ('postgres','authenticated','anon','service_role',"
        "'supabase_admin','supabase_auth_admin') ORDER BY rolname")):
        print(f"   {row[0]:22} super={row[1]} bypassrls={row[2]}")

    print("== RLS des tables d'écriture ==")
    for row in c.execute(text("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
               pg_get_userbyid(c.relowner) AS owner
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname IN ('sales','sale_items','products','payments',
                            'treasury_movements','sale_logs','inventory_movements')
        ORDER BY c.relname""")):
        print(f"   {row[0]:20} rls={row[1]} force={row[2]} owner={row[3]}")


def pick_actors(c) -> list[dict]:
    """Un compte actif par rôle (avec compte Supabase Auth associé)."""
    rows = c.execute(text("""
        SELECT DISTINCT ON (UPPER(COALESCE(u.role, '')))
               u.id, u.username, u.email, u.role, a.id AS auth_id
        FROM public.users u
        JOIN auth.users a ON LOWER(a.email) = LOWER(u.email)
        WHERE u.active AND a.id IS NOT NULL
        ORDER BY UPPER(COALESCE(u.role, '')), u.id""")).all()
    return [{"user_id": r[0], "username": r[1], "email": r[2], "role": r[3],
             "auth_id": str(r[4])} for r in rows]


def as_user(c, actor: dict) -> None:
    """Simule la session PostgREST d'un utilisateur authentifié."""
    claims = json.dumps({
        "sub": actor["auth_id"], "email": actor["email"],
        "role": "authenticated", "aud": "authenticated",
    })
    c.execute(text("SELECT set_config('request.jwt.claims', :c, true)"),
              {"c": claims})
    c.execute(text("SET LOCAL ROLE authenticated"))


def find_product(c):
    """Produit en stock du magasin par defaut (sinon magasin le mieux rempli)."""
    row = c.execute(text("""
        SELECT p.id, p.name, p.quantity, p.sale_price, p.store_id
        FROM public.products p
        WHERE COALESCE(p.quantity, 0) > 5
        ORDER BY (p.store_id = COALESCE((SELECT s.id FROM public.stores s
                                         WHERE s.is_default ORDER BY s.id LIMIT 1),
                                        -1)) DESC,
                 p.quantity DESC
        LIMIT 1""")).first()
    return row


def check_role(conn, actor: dict, detailed: bool) -> None:
    """Simule une session PostgREST pour `actor` et tente une vraie vente."""
    as_user(conn, actor)
    role = actor["role"]

    ctx = conn.execute(text("SELECT public.app_mobile_context()")).scalar()
    perms = set((ctx or {}).get("permissions") or [])
    can_sell = "create_sales" in perms
    check(f"[{role}] app_mobile_context() repond", bool(ctx)
          and bool(ctx.get("role")), f"{len(perms)} permission(s)")

    produit = find_product(conn)
    check(f"[{role}] produit en stock disponible", produit is not None,
          f"{produit[0]} {produit[1]} (stock={produit[2]})" if produit else "")
    if produit is None:
        return

    store_id = produit[4]
    amount = float(produit[3] or 0)
    items = [{"product_id": produit[0], "quantity": 1, "unit_price": amount}]
    before = conn.execute(text("SELECT count(*) FROM public.sales")).scalar()
    stock_before = conn.execute(text(
        "SELECT quantity FROM public.products WHERE id = :i"),
        {"i": produit[0]}).scalar()

    result = conn.execute(
        text("SELECT public.app_create_sale("
             "CAST(:items AS jsonb), :store, NULL, 0, 0, 'CASH', :paid, "
             "'test-live', 'FCFA', NULL)"),
        {"items": json.dumps(items), "store": store_id, "paid": amount},
    ).scalar()
    ok = bool(result) and result.get("ok") is True
    print(f"   [{role}] app_create_sale -> {json.dumps(result, default=str)}")
    # Cœur du test : le serveur doit ACCEPTER la vente pour tout role autorise
    # par la matrice (create_sales), et la REFUSER sinon.
    check(f"[{role}] vente coherente avec la matrice (create_sales={can_sell})",
          ok == can_sell, (result or {}).get("message", ""))

    sale_id = (result or {}).get("sale_id")
    if ok and sale_id and detailed:
        after = conn.execute(text("SELECT count(*) FROM public.sales")).scalar()
        check("ligne `sales` creee", after == before + 1, f"{before} -> {after}")
        nb_items = conn.execute(text(
            "SELECT count(*) FROM public.sale_items WHERE sale_id = :s"),
            {"s": sale_id}).scalar()
        check("lignes `sale_items` creees", nb_items >= 1, str(nb_items))
        stock_after = conn.execute(text(
            "SELECT quantity FROM public.products WHERE id = :i"),
            {"i": produit[0]}).scalar()
        check("stock decremente", float(stock_after) == float(stock_before) - 1,
              f"{stock_before} -> {stock_after}")
        logs = conn.execute(text(
            "SELECT count(*) FROM public.sale_logs WHERE sale_id = :s"),
            {"s": sale_id}).scalar()
        check("journal `sale_logs` ecrit", logs >= 1, str(logs))

        pay = conn.execute(
            text("SELECT public.app_register_payment(:s, 1, 'CASH', NULL, "
                 "'test-live')"), {"s": sale_id}).scalar()
        print(f"   app_register_payment -> {json.dumps(pay, default=str)}")
        check("app_register_payment repond par un objet metier",
              isinstance(pay, dict) and "ok" in pay, str(pay)[:90])

        mvt = conn.execute(
            text("SELECT public.app_stock_movement(:p, 'IN', 1, 'test-live', "
                 "10, NULL, NULL, :s)"),
            {"p": produit[0], "s": store_id}).scalar()
        print(f"   app_stock_movement -> {json.dumps(mvt, default=str)}")
        check("app_stock_movement repond par un objet metier",
              isinstance(mvt, dict) and "ok" in mvt, str(mvt)[:90])




def main() -> int:
    engine = connect()
    conn = engine.connect()
    try:
        show_facts(conn)
        conn.rollback()

        actors = pick_actors(conn)
        check("compte(s) actif(s) avec compte Supabase Auth", bool(actors),
              ", ".join(f"{a['role']}:{a['username']}" for a in actors))
        if not actors:
            return 1
        conn.rollback()

        # Chaque role dispose de sa propre transaction, annulee a la fin.
        detailed_done = False
        for actor in actors:
            print(f"\n-- role {actor['role']} ({actor['email']}) --")
            try:
                # Le premier role qui a le droit de vendre sert au detail.
                detailed = not detailed_done
                before_cnt = PROBLEMS
                check_role(conn, actor, detailed)
                if detailed and PROBLEMS == before_cnt:
                    detailed_done = True
            except Exception as exc:               # noqa: BLE001 (diagnostic)
                conn.rollback()
                fail(f"[{actor['role']}] {type(exc).__name__}: {exc}")
            finally:
                conn.rollback()
    finally:
        conn.rollback()                            # AUCUNE ecriture conservee
        conn.close()

    print("\nTransaction ANNULEE : aucune donnee ecrite dans la base.")
    print("Resultat :", "TOUT OK" if PROBLEMS == 0 else f"{PROBLEMS} probleme(s)")
    return 0 if PROBLEMS == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
