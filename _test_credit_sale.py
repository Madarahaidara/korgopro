"""Diagnostic (transaction ANNULee) : la vente a credit via `app_create_sale`
echoue-t-elle cote serveur ?

Reproduit fidelement l'appel de mobile/src/api/rpc.js -> createSale :
  * payment_method = 'CREDIT' (accentue) puis 'CREDIT' simple ;
  * amount_paid = 0 (vente a terme) ; customer_id renseigne ;
puis ROLLBACK : rien n'est conserve en base.

Usage : python _test_credit_sale.py
"""
import json
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

METHODS = ["CR\u00c9DIT", "CREDIT"]
PROBLEMS = 0


def check(label, ok, detail=""):
    global PROBLEMS
    if not ok:
        PROBLEMS += 1
    print(f"{'OK  ' if ok else 'ECHEC'} {label}" + (f"  -> {detail}" if detail else ""))


def constraints(conn):
    print("--- contraintes des tables touchees ---")
    for table in ("sales", "payments", "customers"):
        for name, defn in conn.execute(text(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = CAST(:t AS regclass) ORDER BY conname"
        ), {"t": f"public.{table}"}):
            print(f"   {table:9} {name:36} {defn}")


def main() -> int:
    load_dotenv(".env")
    engine = create_engine(
        os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://"),
        connect_args={"sslmode": "require"},
    )
    conn = engine.connect()
    constraints(conn)
    conn.rollback()

    actor = conn.execute(text(
        "SELECT u.id, u.username, u.email, u.role, a.id AS auth_id "
        "FROM public.users u "
        "JOIN auth.users a ON LOWER(a.email) = LOWER(u.email) "
        "WHERE u.active AND UPPER(u.role) IN ('ADMIN','GESTIONNAIRE') "
        "ORDER BY u.id LIMIT 1"
    )).first()
    if actor is None:
        print("AUCUN compte actif lie a auth.users : test impossible.")
        return 1
    claims = json.dumps({"sub": str(actor[4]), "email": actor[2],
                         "role": "authenticated", "aud": "authenticated"})
    print(f"\ncompte utilise : {actor[1]} ({actor[3]})")

    produit = conn.execute(text(
        "SELECT id, name, quantity, sale_price FROM public.products "
        "WHERE active AND quantity > 5 ORDER BY id LIMIT 1"
    )).first()
    client = conn.execute(text(
        "SELECT id, first_name, last_name, balance FROM public.customers "
        "WHERE active ORDER BY id LIMIT 1"
    )).first()
    magasin = conn.execute(text(
        "SELECT id FROM public.stores WHERE active ORDER BY id LIMIT 1"
    )).first()
    conn.rollback()
    if not produit or not client or not magasin:
        print(f"donnees de test manquantes (produit={bool(produit)}, "
              f"client={bool(client)}, magasin={bool(magasin)})")
        return 1
    return run_cases(conn, claims, produit, client, magasin)


def run_cases(conn, claims, produit, client, magasin):
    for method in METHODS:
        print(f"\n===== payment_method = {method!r} =====")
        try:
            conn.execute(text("SELECT set_config('request.jwt.claims', :c, true)"),
                         {"c": claims})
            conn.execute(text("SET LOCAL ROLE authenticated"))

            bal0 = conn.execute(text(
                "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
                {"i": client[0]}).scalar()
            stock0 = conn.execute(text(
                "SELECT quantity FROM public.products WHERE id = :i"),
                {"i": produit[0]}).scalar()

            res = conn.execute(text(
                "SELECT public.app_create_sale("
                "CAST(:items AS jsonb), :store, :customer, 0, 0, :method, "
                "0, 'test credit', 'FCFA', NULL)"),
                {"items": json.dumps([{
                    "product_id": produit[0], "quantity": 1,
                    "unit_price": float(produit[3])}]),
                 "store": magasin[0], "customer": client[0],
                 "method": method}).scalar()
            print("   app_create_sale -> "
                  + json.dumps(res, ensure_ascii=False, default=str))
            ok = isinstance(res, dict) and res.get("ok") is True
            check(f"[{method}] vente a credit acceptee par le serveur", ok,
                  (res or {}).get("message", "") if isinstance(res, dict)
                  else str(res)[:200])
            if not ok:
                continue

            sid = res["sale_id"]
            ligne = conn.execute(text(
                "SELECT payment_method, payment_status, amount_paid, total_amount, "
                "       change_amount FROM public.sales WHERE id = :s"),
                {"s": sid}).first()
            print(f"   sales -> {tuple(ligne)}")
            check(f"[{method}] payment_status = PENDING", ligne[1] == "PENDING",
                  str(ligne[1]))
            check(f"[{method}] amount_paid = 0", float(ligne[2] or 0) == 0.0,
                  str(ligne[2]))

            pay = conn.execute(text(
                "SELECT count(*), COALESCE(sum(amount), 0) FROM public.payments "
                "WHERE sale_id = :s"), {"s": sid}).first()
            print(f"   payments -> nb={pay[0]} total={pay[1]}")
            check(f"[{method}] payments : aucune ligne (rien n'a ete recu)",
                  pay[0] == 0 and float(pay[1] or 0) == 0.0,
                  f"nb={pay[0]} sum={pay[1]}")
            check(f"[{method}] RPC renvoie le reste du",
                  float(res.get("due") or 0) == float(ligne[3]),
                  f"due={res.get('due')} total={ligne[3]}")

            mvt = conn.execute(text(
                "SELECT count(*) FROM public.treasury_movements "
                "WHERE reference_type = 'SALE' AND reference_id = :s"),
                {"s": sid}).scalar()
            check(f"[{method}] aucun mouvement de tresorerie", mvt == 0,
                  f"{mvt} mouvement(s)")

            bal1 = conn.execute(text(
                "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
                {"i": client[0]}).scalar()
            check(f"[{method}] solde client += total",
                  float(bal1) == float(bal0) + float(ligne[3]),
                  f"{bal0} -> {bal1} (total {ligne[3]})")

            stock1 = conn.execute(text(
                "SELECT quantity FROM public.products WHERE id = :i"),
                {"i": produit[0]}).scalar()
            check(f"[{method}] stock decremente",
                  float(stock1) == float(stock0) - 1, f"{stock0} -> {stock1}")

            reste = float(ligne[3])
            regle = conn.execute(text(
                "SELECT public.app_register_payment(:s, :m, 'CASH', NULL, "
                "'test credit')"), {"s": sid, "m": reste}).scalar()
            print("   app_register_payment -> "
                  + json.dumps(regle, ensure_ascii=False, default=str))
            check(f"[{method}] encaissement du reste du",
                  isinstance(regle, dict) and regle.get("ok") is True,
                  str(regle)[:200])

            ligne2 = conn.execute(text(
                "SELECT payment_status, amount_paid FROM public.sales WHERE id = :s"),
                {"s": sid}).first()
            check(f"[{method}] vente soldee (payment_status = PAID)",
                  ligne2[0] == "PAID", str(ligne2[0]))

            bal2 = conn.execute(text(
                "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
                {"i": client[0]}).scalar()
            check(f"[{method}] solde client revenu a sa valeur initiale",
                  float(bal2) == float(bal0), f"{bal0} -> ... -> {bal2}")
        except Exception as exc:  # noqa: BLE001 (diagnostic)
            check(f"[{method}] appel sans exception", False,
                  f"{type(exc).__name__}: {exc}")
        finally:
            conn.rollback()

    case_acompte(conn, claims, produit, client, magasin)

    conn.rollback()
    conn.close()
    print("\nTransaction ANNULEE : aucune donnee conservee.")
    print("Resultat :", "TOUT OK" if not PROBLEMS else f"{PROBLEMS} probleme(s)")
    return 0 if not PROBLEMS else 1


def case_acompte(conn, claims, produit, client, magasin):
    """Vente a credit avec acompte : le client ne doit que le reste du."""
    print("\n===== credit avec acompte de 30 % =====")
    try:
        conn.execute(text("SELECT set_config('request.jwt.claims', :c, true)"),
                     {"c": claims})
        conn.execute(text("SET LOCAL ROLE authenticated"))

        bal0 = conn.execute(text(
            "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
            {"i": client[0]}).scalar()
        total = float(produit[3])
        acompte = round(total * 0.3)
        res = conn.execute(text(
            "SELECT public.app_create_sale("
            " CAST(:items AS jsonb), :store, :customer, 0, 0, :method, :paid, "
            "'test acompte', 'FCFA', NULL)"),
            {"items": json.dumps([{
                "product_id": produit[0], "quantity": 1, "unit_price": total}]),
             "store": magasin[0], "customer": client[0],
             "method": "CR\u00c9DIT", "paid": acompte}).scalar()
        print("   app_create_sale -> "
              + json.dumps(res, ensure_ascii=False, default=str))
        ok = isinstance(res, dict) and res.get("ok") is True
        check("[acompte] vente a credit acceptee", ok,
              (res or {}).get("message", "") if isinstance(res, dict) else str(res)[:200])
        if not ok:
            return

        expected = max(total - acompte, 0)
        check("[acompte] statut PARTIAL", res.get("payment_status") == "PARTIAL",
              str(res.get("payment_status")))
        check("[acompte] reste du = total - acompte",
              abs(float(res.get("due") or 0) - expected) < 0.01,
              f"due={res.get('due')} attendu={expected}")

        sid = res["sale_id"]
        pay = conn.execute(text(
            "SELECT count(*), COALESCE(sum(amount), 0) FROM public.payments "
            "WHERE sale_id = :s"), {"s": sid}).first()
        check("[acompte] 1 paiement du montant recu uniquement",
              pay[0] == 1 and abs(float(pay[1] or 0) - acompte) < 0.01,
              f"nb={pay[0]} sum={pay[1]} (acompte {acompte})")

        mvt = conn.execute(text(
            "SELECT count(*), COALESCE(sum(amount), 0) FROM public.treasury_movements "
            "WHERE reference_type = 'SALE' AND reference_id = :s"), {"s": sid}).first()
        check("[acompte] tresorerie = acompte encaisse",
              mvt[0] == 1 and abs(float(mvt[1] or 0) - acompte) < 0.01,
              f"nb={mvt[0]} sum={mvt[1]}")

        bal1 = conn.execute(text(
            "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
            {"i": client[0]}).scalar()
        check("[acompte] solde client += reste du (pas le total)",
              abs(float(bal1) - (float(bal0) + expected)) < 0.01,
              f"{bal0} -> {bal1} (attendu {float(bal0) + expected})")

        solde = conn.execute(text(
            "SELECT public.app_register_payment(:s, :m, 'MOBILE_MONEY', NULL, "
            "'solde du credit')"), {"s": sid, "m": expected}).scalar()
        check("[acompte] solde du credit encaisse",
              isinstance(solde, dict) and solde.get("ok") is True, str(solde)[:200])

        bal2 = conn.execute(text(
            "SELECT COALESCE(balance, 0) FROM public.customers WHERE id = :i"),
            {"i": client[0]}).scalar()
        check("[acompte] dette du client remise a zero",
              abs(float(bal2) - float(bal0)) < 0.01, f"{bal0} -> ... -> {bal2}")
    except Exception as exc:  # noqa: BLE001 (diagnostic)
        check("[acompte] appel sans exception", False,
              f"{type(exc).__name__}: {exc}")
    finally:
        conn.rollback()


if __name__ == "__main__":
    sys.exit(main())
