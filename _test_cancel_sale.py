"""Diagnostic (transaction ANNULEE) : annulation d'une vente via app_cancel_sale.

Couvre, dans le meme ordre que le desktop (ui/views/sale_services.py) :
  * vente a credit (0 encaisse)  -> stock restaure, dette client a zero,
    facture ANNULEE / CANCELLED, journal sale_logs (action CANCEL) ;
  * vente especes encaissee      -> compensation OUT en tresorerie,
    solde du compte de caisse inchange (remboursement) ;
  * deuxieme annulation          -> ok=false (idempotence) ;
  * caissier (sans cancel_sales) -> exception 42501.

Tout est ROLLBACK : aucune donnee n'est conservee en base.

Usage : python _test_cancel_sale.py
"""
import json
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROBLEMS = 0


def check(label, ok, detail=""):
    global PROBLEMS
    if not ok:
        PROBLEMS += 1
    print(f"{'OK  ' if ok else 'ECHEC'} {label}" + (f"  -> {detail}" if detail else ""))


def create_sale(conn, produit, client, magasin, method, paid):
    """Vente d'une unité du produit de test via app_create_sale."""
    total = float(produit[3])
    return conn.execute(text(
        "SELECT public.app_create_sale("
        " CAST(:items AS jsonb), :store, :customer, 0, 0, :method, :paid, "
        "'test annulation', 'FCFA', NULL)"),
        {"items": json.dumps([{"product_id": produit[0], "quantity": 1,
                               "unit_price": total}]),
         "store": magasin[0], "customer": client[0],
         "method": method, "paid": paid}).scalar()


def run_cancel_cases(conn, admin, produit, client, magasin):
    as_role(conn, admin)

    stock0 = conn.execute(text(
        "SELECT quantity FROM public.products WHERE id = :i"),
        {"i": produit[0]}).scalar()
    bal0 = conn.execute(text(
        "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
        {"i": client[0]}).scalar()
    treso0 = conn.execute(text(
        "SELECT COALESCE(SUM(current_balance), 0) FROM public.treasury_accounts"
    )).scalar()

    # ------------------------------------------------------------------
    print("\n===== A. Vente a credit (0 encaisse) : annulation =====")
    sale_a = create_sale(conn, produit, client, magasin, "CR\u00c9DIT", 0)
    ok_a = isinstance(sale_a, dict) and sale_a.get("ok") is True
    check("vente a credit creee", ok_a, str(sale_a)[:200])
    if not ok_a:
        return
    sid_a, total_a = sale_a["sale_id"], float(sale_a["total_amount"])

    stock_a = conn.execute(text(
        "SELECT quantity FROM public.products WHERE id = :i"),
        {"i": produit[0]}).scalar()
    check("stock debite a la creation", float(stock_a) == float(stock0) - 1,
          f"{stock0} -> {stock_a}")
    bal_a = conn.execute(text(
        "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
        {"i": client[0]}).scalar()
    check("dette inscrite (= total)", float(bal_a) == float(bal0) + total_a,
          f"{bal0} -> {bal_a} (total {total_a})")

    res = conn.execute(text(
        "SELECT public.app_cancel_sale(:i, :r)"),
        {"i": sid_a, "r": "erreur de caisse"}).scalar()
    print("   app_cancel_sale -> " + json.dumps(res, ensure_ascii=False, default=str))
    check("annulation acceptee", res.get("ok") is True, str(res.get("message")))
    check("1 article remis en stock", res.get("items_restored") == 1,
          str(res.get("items_restored")))
    check("due_cancelled = total du credit",
          abs(float(res.get("due_cancelled") or 0) - total_a) < 0.01,
          f"{res.get('due_cancelled')} / {total_a}")
    check("refunded = 0 (aucun encaissement a rembourser)",
          abs(float(res.get("refunded") or 0)) < 0.01, str(res.get("refunded")))

    ligne = conn.execute(text(
        "SELECT sale_status, statut, payment_status, notes "
        "FROM public.sales WHERE id = :s"), {"s": sid_a}).first()
    print(f"   sales -> {tuple(ligne)}")
    check("sale_status = CANCELLED", ligne[0] == "CANCELLED", str(ligne[0]))
    check("statut = ANNULEE", ligne[1] == "ANNULEE", str(ligne[1]))
    check("payment_status = CANCELLED (plus d'encaissement possible)",
          ligne[2] == "CANCELLED", str(ligne[2]))
    check("motif conserve dans les notes", "erreur de caisse" in (ligne[3] or ""),
          str(ligne[3]))

    stock_b = conn.execute(text(
        "SELECT quantity FROM public.products WHERE id = :i"),
        {"i": produit[0]}).scalar()
    check("stock restaure", float(stock_b) == float(stock0),
          f"{stock0} -> {stock_b}")
    bal_b = conn.execute(text(
        "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
        {"i": client[0]}).scalar()
    check("dette du client remise a zero", float(bal_b) == float(bal0),
          f"{bal0} -> {bal_b}")

    logs = conn.execute(text(
        "SELECT count(*) FROM public.sale_logs "
        "WHERE sale_id = :s AND action = 'CANCEL'"), {"s": sid_a}).scalar()
    check("journal sale_logs (action CANCEL)", int(logs) == 1, f"{logs} ligne(s)")

    twice = conn.execute(text(
        "SELECT public.app_cancel_sale(:i, NULL)"), {"i": sid_a}).scalar()
    print("   2e appel -> " + json.dumps(twice, ensure_ascii=False, default=str))
    check("2e annulation refusee (idempotent)",
          twice.get("ok") is False and "annul" in (twice.get("message") or ""),
          str(twice.get("message")))


def as_role(conn, actor):
    """Pose les revendications JWT de `actor` pour la transaction en cours."""
    claims = json.dumps({"sub": str(actor[4]), "email": actor[2],
                         "role": "authenticated", "aud": "authenticated"})
    conn.execute(text("SELECT set_config('request.jwt.claims', :c, true)"),
                 {"c": claims})
    conn.execute(text("SET LOCAL ROLE authenticated"))


def find_actor(conn, roles_sql):
    """Compte actif lie a auth.users dont le role figure dans `roles_sql`."""
    return conn.execute(text(
        "SELECT u.id, u.username, u.email, u.role, a.id AS auth_id "
        "FROM public.users u "
        "JOIN auth.users a ON LOWER(a.email) = LOWER(u.email) "
        f"WHERE u.active AND UPPER(u.role) IN ({roles_sql}) "
        "ORDER BY u.id LIMIT 1"
    )).first()


def run_treasury_case(conn, admin, produit, client, magasin):
    """Vente especes encaissee -> annulation = remboursement en tresorerie."""
    as_role(conn, admin)
    treso0 = conn.execute(text(
        "SELECT COALESCE(SUM(current_balance), 0) FROM public.treasury_accounts"
    )).scalar()
    stock0 = conn.execute(text(
        "SELECT quantity FROM public.products WHERE id = :i"),
        {"i": produit[0]}).scalar()

    print("\n===== B. Vente especes encaissee : annulation = remboursement =====")
    sale = create_sale(conn, produit, client, magasin, "CASH",
                       float(produit[3]))
    ok = isinstance(sale, dict) and sale.get("ok") is True
    check("vente cash creee", ok, str(sale)[:200])
    if not ok:
        return
    sid, total = sale["sale_id"], float(sale["total_amount"])

    entree = conn.execute(text(
        "SELECT COALESCE(SUM(amount), 0) FROM public.treasury_movements "
        "WHERE reference_type = 'SALE' AND reference_id = :s "
        "AND movement_type = 'IN'"), {"s": sid}).scalar()
    check("entree de tresorerie enregistree", abs(float(entree) - total) < 0.01,
          f"{entree} / {total}")

    res = conn.execute(text(
        "SELECT public.app_cancel_sale(:i, 'client reparti')"),
        {"i": sid}).scalar()
    print("   app_cancel_sale -> " + json.dumps(res, ensure_ascii=False, default=str))
    check("annulation acceptee", res.get("ok") is True, str(res.get("message")))
    check("refunded = total encaisse",
          abs(float(res.get("refunded") or 0) - total) < 0.01,
          f"{res.get('refunded')} / {total}")
    check("1 compensation OUT creee", int(res.get("movements") or 0) == 1,
          str(res.get("movements")))

    net = conn.execute(text(
        "SELECT COALESCE(SUM(CASE WHEN movement_type = 'IN' THEN amount "
        "ELSE -amount END), 0) FROM public.treasury_movements "
        "WHERE reference_id = :s AND reference_type IN ('SALE', 'SALE_CANCEL')"),
        {"s": sid}).scalar()
    check("net trésorerie de la vente = 0 (IN compense par OUT)",
          abs(float(net)) < 0.01, f"net={net}")

    treso1 = conn.execute(text(
        "SELECT COALESCE(SUM(current_balance), 0) FROM public.treasury_accounts"
    )).scalar()
    check("caisse revenue au montant initial",
          abs(float(treso1) - float(treso0)) < 0.01,
          f"{treso0} -> {treso1}")

    stock1 = conn.execute(text(
        "SELECT quantity FROM public.products WHERE id = :i"),
        {"i": produit[0]}).scalar()
    check("stock restaure (2e vente)", float(stock1) == float(stock0),
          f"{stock0} -> {stock1}")


def run_permission_case(conn, admin):
    """Sans `cancel_sales`, app_cancel_sale doit lever 42501 AVANT tout effet.

    Aucun compte CAISSIER n'est lie a auth.users dans la base : on fait passer
    provisoirement le compte admin en CAISSIER (le ROLLBACK final restaure le
    role reel) pour verifier la matrice de permissions.
    """
    print("\n===== C. Droits : profil reduit en CAISSIER (sans cancel_sales) =====")
    conn.execute(text("UPDATE public.users SET role = 'CAISSIER' WHERE id = :i"),
                 {"i": admin[0]})
    as_role(conn, admin)
    try:
        conn.execute(text("SELECT public.app_cancel_sale(1, NULL)")).scalar()
        check("annulation refusee sans cancel_sales", False,
              "aucune exception levee")
    except Exception as exc:  # noqa: BLE001 (diagnostic)
        code = getattr(exc, "pgcode", None) or getattr(getattr(exc, "orig", None),
                                                       "pgcode", None)
        check("exception 42501 (permission cancel_sales refusee)", code == "42501",
              f"{type(exc).__name__}: {exc}")


def main() -> int:
    load_dotenv(".env")
    engine = create_engine(
        os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://"),
        connect_args={"sslmode": "require"},
    )
    conn = engine.connect()

    admin = find_actor(conn, "'ADMIN','GESTIONNAIRE','SUPERVISEUR'")
    produit = conn.execute(text(
        "SELECT id, name, quantity, sale_price FROM public.products "
        "WHERE active AND quantity > 5 ORDER BY id LIMIT 1")).first()
    client = conn.execute(text(
        "SELECT id, first_name, last_name, balance FROM public.customers "
        "WHERE active ORDER BY id LIMIT 1")).first()
    magasin = conn.execute(text(
        "SELECT id FROM public.stores WHERE active ORDER BY id LIMIT 1")).first()
    conn.rollback()

    if not admin:
        print("AUCUN compte ADMIN/GESTIONNAIRE/SUPERVISEUR actif : test impossible.")
        return 1
    if not (produit and client and magasin):
        print(f"donnees de test manquantes (produit={bool(produit)}, "
              f"client={bool(client)}, magasin={bool(magasin)})")
        return 1

    print(f"admin utilise : {admin[1]} ({admin[3]})")
    print(f"produit : {produit[0]} {produit[1]} (stock {produit[2]})")

    run_cancel_cases(conn, admin, produit, client, magasin)
    conn.rollback()

    run_treasury_case(conn, admin, produit, client, magasin)
    conn.rollback()

    run_permission_case(conn, admin)
    conn.rollback()

    conn.close()
    print("\nTransaction ANNULEE : aucune donnee conservee.")
    print("Resultat :", "TOUT OK" if not PROBLEMS else f"{PROBLEMS} probleme(s)")
    return 0 if not PROBLEMS else 1


if __name__ == "__main__":
    sys.exit(main())
