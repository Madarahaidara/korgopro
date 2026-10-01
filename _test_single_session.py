"""Test LIVE du verrou « UNE SEULE SESSION PAR UTILISATEUR ».

Simule les trois clients contre la vraie base :

  * WEB / MOBILE : la session vient du JETON (`session_id` simule avec
    `set_config('request.jwt.claims', ...)` + `SET LOCAL ROLE authenticated`,
    exactement comme le fait PostgREST — cf. _test_mobile_rpc_live.py) ;
  * DESKTOP     : appel direct des RPC `app_desktop_session_*`.

Scenarios verifies :
  1. 1re session ouverte OK, 2e session REFUSEE (code SESSION_ACTIVE) ;
  2. la reprise explicite (`p_force`) ferme l'autre session ;
  3. l'appareil repris s'aperçoit au battement de coeur et doit se fermer ;
  4. la fermeture explicite libere le verrou ;
  5. garde d'ecriture : `app_stock_movement` refuse une session reprise ;
  6. les RPC du desktop ne sont PAS accessibles au role `authenticated` ;
  7. compatibilite : un jeton SANS `session_id` passe (fail-open) ;
  8. compte desactive / email inconnu : refus explicite.

Tout se joue dans UNE transaction annulee (aucune donnee conservee), sauf la
creation des comptes de test, supprimee en toute fin.

Usage : python _test_single_session.py
"""
import json
import os
import uuid

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROBLEMS = 0
TIMEOUT_MIN = 15

ADMIN_EMAIL = f"session-test-admin-{uuid.uuid4().hex[:6]}@korgo-pro.test"
CAISSIER_EMAIL = f"session-test-cashier-{uuid.uuid4().hex[:6]}@korgo-pro.test"


def check(label, ok, detail=""):
    global PROBLEMS
    if not ok:
        PROBLEMS += 1
    print(f"{'OK  ' if ok else 'ECHEC'} {label}" + (f"  ({detail})" if detail else ""))


def fail(detail):
    global PROBLEMS
    PROBLEMS += 1
    print(f"ECHEC {detail}")


def connect():
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    return create_engine(url, connect_args={"sslmode": "require"})


def create_user(conn, email, role):
    """Compte Supabase Auth jetable (le trigger cree le profil public.users)."""
    conn.execute(text("""
        INSERT INTO auth.users (
            instance_id, id, aud, "role", email, encrypted_password,
            email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
            created_at, updated_at, confirmation_token, recovery_token,
            email_change_token_new, email_change, email_change_token_current,
            phone_change_token, phone_change, email_change_confirm_status)
        VALUES ('00000000-0000-0000-0000-000000000000'::uuid, gen_random_uuid(),
                'authenticated', 'authenticated', :email,
                crypt(:pwd, gen_salt('bf')), now(),
                '{"provider":"email","providers":["email"]}'::jsonb,
                jsonb_build_object('username', :uname, 'role', :role,
                                   'active', true, 'must_change_password', false),
                now(), now(), '', '', '', '', '', '', '', 0)"""),
        {"email": email, "pwd": uuid.uuid4().hex + "Aa1!",
         "uname": email.split("@")[0], "role": role})


def auth_id(conn, email):
    return conn.execute(text(
        "SELECT id FROM auth.users WHERE lower(email) = lower(:e)"),
        {"e": email}).scalar()


def as_client(conn, email, session_id=None):
    """Simule la session PostgREST d'un client (JWT + role `authenticated`).

    Le role est d'abord remis a `postgres` : la resolution de l'identifiant
    `auth.users` n'est pas autorisee au role applicatif.
    """
    back_to_owner(conn)
    claims = {"sub": str(auth_id(conn, email)), "email": email,
              "role": "authenticated", "aud": "authenticated"}
    if session_id is not None:
        claims["session_id"] = str(session_id)
    conn.execute(text("SELECT set_config('request.jwt.claims', :c, true)"),
                 {"c": json.dumps(claims)})
    conn.execute(text("SET LOCAL ROLE authenticated"))


def back_to_owner(conn):
    conn.execute(text("RESET ROLE"))
    conn.execute(text("SELECT set_config('request.jwt.claims', '', true)"))


def rpc(conn, name, *args):
    """Appelle une RPC `public.*` sans parametre (les autres ont un defaut)."""
    conn.execute(text("RESET ROLE"))
    return conn.execute(text(f"SELECT public.{name}()")).scalar()


def open_rows(conn, email):
    """Sessions ouvertes du compte (lecture proprietaire)."""
    back_to_owner(conn)
    return conn.execute(text("""
        SELECT s.session_id::text, s.platform, s.device, s.ended_reason
        FROM public.user_sessions s
        JOIN auth.users a ON a.id = s.user_id
        WHERE lower(a.email) = lower(:e) AND s.ended_at IS NULL"""),
        {"e": email}).all()


def reset_sessions(conn, email):
    """Supprime toutes les sessions du compte (etat de depart des scenarios)."""
    back_to_owner(conn)
    conn.execute(text("""
        DELETE FROM public.user_sessions s
        USING auth.users a
        WHERE a.id = s.user_id AND lower(a.email) = lower(:e)"""), {"e": email})


def scenario_lock(conn):
    """Web puis mobile sur le meme compte : le 2e acces doit etre refuse."""
    sid_web, sid_mobile = uuid.uuid4(), uuid.uuid4()
    reset_sessions(conn, ADMIN_EMAIL)

    as_client(conn, ADMIN_EMAIL, sid_web)
    r1 = conn.execute(text(
        "SELECT public.app_register_session('web', 'Chrome - Windows 10', false)"
    )).scalar()
    check("1. le web ouvre la session", (r1 or {}).get("ok") is True,
          json.dumps(r1, default=str)[:110])

    as_client(conn, ADMIN_EMAIL, sid_mobile)
    r2 = conn.execute(text(
        "SELECT public.app_register_session('mobile', 'Android 13', false)"
    )).scalar()
    check("2. le mobile est refuse (SESSION_ACTIVE)",
          (r2 or {}).get("code") == "SESSION_ACTIVE",
          json.dumps(r2, default=str)[:110])
    other = (r2 or {}).get("other") or {}
    check("3. le refus nomme l'autre appareil",
          other.get("platform") == "web" and "Chrome" in (other.get("device") or ""),
          f"{other.get('platform')} / {other.get('device')}")
    check("4. le refus propose la reprise", (r2 or {}).get("can_force") is True)
    print("   message :", (r2 or {}).get("message"))

    r3 = conn.execute(text(
        "SELECT public.app_register_session('mobile', 'Android 13', true)"
    )).scalar()
    check("5. reprise explicite du mobile",
          (r3 or {}).get("ok") is True and (r3 or {}).get("taking_over") is True,
          json.dumps(r3, default=str)[:110])
    rows = open_rows(conn, ADMIN_EMAIL)
    check("6. une seule session ouverte apres reprise", len(rows) == 1,
          f"{len(rows)} ouverte(s)")
    reason = conn.execute(text(
        "SELECT ended_reason FROM public.user_sessions WHERE session_id = :s"),
        {"s": sid_web}).scalar()
    check("7. l'ancien appareil est journalise", reason == "REPRISE_PAR_MOBILE",
          str(reason))

    as_client(conn, ADMIN_EMAIL, sid_web)
    r4 = conn.execute(text(
        "SELECT public.app_session_heartbeat('web', 'Chrome - Windows 10')")).scalar()
    check("8. le web detecte la reprise et doit se fermer",
          (r4 or {}).get("active") is False,
          json.dumps(r4, default=str)[:110])
    print("   message :", (r4 or {}).get("message"))

    as_client(conn, ADMIN_EMAIL, sid_mobile)
    r5 = conn.execute(text("SELECT public.app_end_session()")).scalar()
    check("9. deconnexion explicite du mobile", (r5 or {}).get("closed") is True,
          json.dumps(r5, default=str)[:110])

    as_client(conn, ADMIN_EMAIL, sid_web)
    r6 = conn.execute(text(
        "SELECT public.app_session_heartbeat('web', 'Chrome - Windows 10')")).scalar()
    check("10. le web reprend la place au battement suivant",
          (r6 or {}).get("active") is True and (r6 or {}).get("revived") is True,
          json.dumps(r6, default=str)[:110])

    r7 = conn.execute(text("SELECT public.app_session_status()")).scalar()
    check("11. le statut indique une session suivie et active",
          (r7 or {}).get("active") is True and (r7 or {}).get("tracked") is True,
          json.dumps(r7, default=str)[:110])


def scenario_write_guard(conn):
    """Une ecriture venue d'une session reprise ailleurs doit etre refusee."""
    sid = uuid.uuid4()
    reset_sessions(conn, ADMIN_EMAIL)
    produit = conn.execute(text(
        "SELECT id FROM public.products ORDER BY id LIMIT 1")).scalar()
    if produit is None:
        check("12. garde d'ecriture (aucun produit de test)", False, "base vide")
        return

    as_client(conn, ADMIN_EMAIL, sid)
    conn.execute(text(
        "SELECT public.app_register_session('web', 'Chrome - Windows 10', false)"))
    avant = conn.execute(text(
        "SELECT public.app_stock_movement(:p, 'IN', 1, 'test-session', 1, NULL, NULL, NULL)"
    ), {"p": produit}).scalar()
    check("12. ecriture acceptee tant que la session est ouverte",
          (avant or {}).get("ok") is True, json.dumps(avant, default=str)[:110])

    # La session est fermee « par un autre appareil » (cote base).
    back_to_owner(conn)
    conn.execute(text(
        "UPDATE public.user_sessions SET ended_at = now(), "
        "ended_reason = 'REPRISE_PAR_MOBILE' WHERE session_id = :s"), {"s": sid})

    as_client(conn, ADMIN_EMAIL, sid)
    apres = conn.execute(text(
        "SELECT public.app_stock_movement(:p, 'IN', 1, 'test-session', 1, NULL, NULL, NULL)"
    ), {"p": produit}).scalar()
    check("13. ecriture REFUSEE apres reprise de la session",
          (apres or {}).get("code") == "SESSION_CLOSED",
          json.dumps(apres, default=str)[:110])
    print("   message :", (apres or {}).get("message"))


def scenario_legacy_client(conn):
    """Compatibilite : un jeton SANS claim `session_id` passe (fail-open)."""
    reset_sessions(conn, ADMIN_EMAIL)
    as_client(conn, ADMIN_EMAIL, None)
    r1 = conn.execute(text(
        "SELECT public.app_register_session('web', 'Ancien client', false)")).scalar()
    check("14. jeton sans session_id : acces accepte (fail-open)",
          (r1 or {}).get("ok") is True and (r1 or {}).get("tracked") is False,
          json.dumps(r1, default=str)[:110])
    r2 = conn.execute(text("SELECT public.app_session_heartbeat()")).scalar()
    check("15. battement sans session_id : session consideree active",
          (r2 or {}).get("active") is True, json.dumps(r2, default=str)[:110])
    back_to_owner(conn)
    actif = conn.execute(text("SELECT app_security.session_is_active()")).scalar()
    print(f"   (info) session_is_active sans claim, cote proprietaire : {actif}")


def scenario_desktop(conn):
    """Le logiciel de bureau passe par les RPC `app_desktop_session_*`."""
    sid_web, sid_desktop = uuid.uuid4(), uuid.uuid4()
    reset_sessions(conn, ADMIN_EMAIL)

    as_client(conn, ADMIN_EMAIL, sid_web)
    conn.execute(text(
        "SELECT public.app_register_session('web', 'Chrome - Windows 10', false)"))
    back_to_owner(conn)

    r1 = conn.execute(text(
        "SELECT public.app_desktop_session_open(:e, :s, 'Poste CAISSE-01', false)"),
        {"e": ADMIN_EMAIL, "s": sid_desktop}).scalar()
    check("16. le desktop est refuse si le web est ouvert",
          (r1 or {}).get("code") == "SESSION_ACTIVE", json.dumps(r1, default=str)[:110])
    print("   message :", (r1 or {}).get("message"))

    r2 = conn.execute(text(
        "SELECT public.app_desktop_session_open(:e, :s, 'Poste CAISSE-01', true)"),
        {"e": ADMIN_EMAIL, "s": sid_desktop}).scalar()
    check("17. le desktop reprend la main",
          (r2 or {}).get("ok") is True and (r2 or {}).get("taking_over") is True,
          json.dumps(r2, default=str)[:110])

    r3 = conn.execute(text(
        "SELECT public.app_desktop_session_touch(:s, :e, 'Poste CAISSE-01')"),
        {"s": sid_desktop, "e": ADMIN_EMAIL}).scalar()
    check("18. battement de coeur du desktop", (r3 or {}).get("active") is True,
          json.dumps(r3, default=str)[:110])

    as_client(conn, ADMIN_EMAIL, sid_web)
    r4 = conn.execute(text("SELECT public.app_session_heartbeat()")).scalar()
    check("19. le web voit sa session fermee par le desktop",
          (r4 or {}).get("active") is False, json.dumps(r4, default=str)[:110])

    back_to_owner(conn)
    r5 = conn.execute(text(
        "SELECT public.app_desktop_session_close(:s, 'DECONNEXION')"),
        {"s": sid_desktop}).scalar()
    check("20. fermeture du desktop", (r5 or {}).get("closed") is True,
          json.dumps(r5, default=str)[:110])


def scenario_privileges(conn):
    """Les RPC du desktop ne doivent pas etre joignables par un utilisateur."""
    as_client(conn, ADMIN_EMAIL, uuid.uuid4())
    conn.execute(text("SAVEPOINT privileges"))
    try:
        conn.execute(text(
            "SELECT public.app_desktop_session_open(:e, :s, NULL, false)"),
            {"e": ADMIN_EMAIL, "s": uuid.uuid4()})
        check("21. RPC desktop INTERDITES a un utilisateur connecte", False,
              "l'appel a reussi")
    except Exception as exc:                                    # noqa: BLE001
        check("21. RPC desktop INTERDITES a un utilisateur connecte",
              "permission" in str(exc).lower() or "42501" in str(exc),
              f"{type(exc).__name__}: {str(exc)[:60]}")
    finally:
        conn.execute(text("ROLLBACK TO SAVEPOINT privileges"))


def scenario_admin(conn):
    """Liberation administrative + comptes non utilisables."""
    sid = uuid.uuid4()
    reset_sessions(conn, ADMIN_EMAIL)
    as_client(conn, ADMIN_EMAIL, sid)
    conn.execute(text(
        "SELECT public.app_register_session('mobile', 'Android 13', false)"))

    as_client(conn, CAISSIER_EMAIL, uuid.uuid4())
    r1 = conn.execute(text("SELECT public.admin_revoke_sessions(:e)"),
                      {"e": ADMIN_EMAIL}).scalar()
    check("22. un caissier ne peut pas liberer une session",
          (r1 or {}).get("ok") is False, json.dumps(r1, default=str)[:110])

    as_client(conn, ADMIN_EMAIL, sid)
    r2 = conn.execute(text("SELECT public.admin_revoke_sessions(:e)"),
                      {"e": ADMIN_EMAIL}).scalar()
    check("23. un administrateur libere la session",
          (r2 or {}).get("revoked") == 1, json.dumps(r2, default=str)[:110])

    back_to_owner(conn)
    conn.execute(text("UPDATE public.users SET active = false "
                      "WHERE lower(email) = lower(:e)"), {"e": CAISSIER_EMAIL})
    r3 = conn.execute(text(
        "SELECT public.app_desktop_session_open(:e, :s, NULL, false)"),
        {"e": CAISSIER_EMAIL, "s": uuid.uuid4()}).scalar()
    check("24. profil desactive : acces refuse",
          (r3 or {}).get("code") == "INACTIVE_PROFILE", json.dumps(r3, default=str)[:110])

    r4 = conn.execute(text(
        "SELECT public.app_desktop_session_open('inconnu@korgo-pro.test', :s, NULL, false)"),
        {"s": uuid.uuid4()}).scalar()
    check("25. email inconnu : acces refuse",
          (r4 or {}).get("code") == "UNKNOWN_USER", json.dumps(r4, default=str)[:110])


def scenario_unique_index(conn):
    """Defense en profondeur : l'index unique refuse un doublon, meme en SQL."""
    reset_sessions(conn, ADMIN_EMAIL)
    as_client(conn, ADMIN_EMAIL, uuid.uuid4())
    conn.execute(text(
        "SELECT public.app_register_session('web', 'Session A', false)"))
    back_to_owner(conn)

    conn.execute(text("SAVEPOINT index_unique"))
    try:
        conn.execute(text("""
            INSERT INTO public.user_sessions (session_id, user_id, platform)
            VALUES (:s, :u, 'web')"""),
            {"s": uuid.uuid4(), "u": auth_id(conn, ADMIN_EMAIL)})
        check("26. index unique : une 2e session ouverte est impossible", False,
              "l'INSERT a reussi")
    except Exception as exc:                                    # noqa: BLE001
        check("26. index unique : une 2e session ouverte est impossible",
              "duplicate key" in str(exc).lower() or "unique" in str(exc).lower(),
              str(exc)[:70])
    finally:
        conn.execute(text("ROLLBACK TO SAVEPOINT index_unique"))


def scenario_desktop_python(conn, engine):
    """Le VRAI code Python du desktop (core.single_session + AuthController).

    ATTENTION : `core.single_session` ouvre SES PROPRES sessions SQLAlchemy et
    committe. Le setup doit donc etre committed (engine.begin) : sinon la ligne
    « web » resterait invisible a cette autre connexion et l'index unique
    bloquerait l'INSERT du desktop.
    """
    from controllers.auth_controller import AuthController
    from core import single_session

    def compter_ouvertes(email):
        with engine.connect() as c:
            return c.execute(text("""
                SELECT count(*) FROM public.user_sessions s
                JOIN auth.users a ON a.id = s.user_id
                WHERE lower(a.email) = lower(:e) AND s.ended_at IS NULL"""),
                {"e": email}).scalar()

    with engine.begin() as c:                       # committe : visible partout
        c.execute(text("""
            DELETE FROM public.user_sessions s USING auth.users a
            WHERE a.id = s.user_id AND lower(a.email) = lower(:e)"""),
            {"e": ADMIN_EMAIL})
        c.execute(text(
            "SELECT public.app_desktop_session_open(:e, :s, 'Chrome - Windows 10', false)"),
            {"e": ADMIN_EMAIL, "s": str(uuid.uuid4())})

    check("27. une session concurrente est bien ouverte",
          compter_ouvertes(ADMIN_EMAIL) == 1,
          f"{compter_ouvertes(ADMIN_EMAIL)} ouverte(s)")

    controller = AuthController()
    single_session.session.reset()
    result = controller._open_single_session(ADMIN_EMAIL)
    check("28. le desktop Python REFUSE la connexion (message metier)",
          bool(result) and "Deja connecte" in result, str(result)[:130])
    check("29. aucune session n'est ouverte par le poste refuse",
          single_session.session.email is None,
          str(single_session.session.email))

    # Reprise explicite : le poste ferme l'autre session et prend la main.
    # Via le CONTROLEUR (chemin exact du bouton « Deconnecter l'autre
    # appareil et se connecter » de LoginView).
    result = controller._open_single_session(ADMIN_EMAIL, force=True)
    check("30. le desktop Python peut reprendre la main (force)",
          result is None and single_session.session.email == ADMIN_EMAIL,
          f"message={result}")
    check("31. une seule session ouverte apres reprise",
          compter_ouvertes(ADMIN_EMAIL) == 1,
          f"{compter_ouvertes(ADMIN_EMAIL)} ouverte(s)")

    # Ecran verrouille : re-authentification sur LE MEME poste. Sans la
    # garde « session.email == email », le poste genererait un nouvel UUID
    # et le serveur le traiterait comme UN AUTRE appareil (refus a tort).
    reauth = controller._open_single_session(ADMIN_EMAIL)
    check("31b. re-auth sur le meme poste acceptee (ecran verrouille)",
          reauth is None and single_session.session.email == ADMIN_EMAIL,
          str(reauth))
    check("31c. toujours une seule session ouverte apres re-auth",
          compter_ouvertes(ADMIN_EMAIL) == 1,
          f"{compter_ouvertes(ADMIN_EMAIL)} ouverte(s)")

    battement = single_session.session.touch()
    check("32. battement Python du desktop",
          bool(battement) and battement.get("active") is True,
          json.dumps(battement, default=str)[:110])

    # Fermeture explicite : le verrou redevient disponible.
    single_session.session.close("DECONNEXION")
    check("33. la fermeture libere le verrou",
          compter_ouvertes(ADMIN_EMAIL) == 0,
          f"{compter_ouvertes(ADMIN_EMAIL)} ouverte(s)")
    conn.rollback()

SCENARIOS = (
    scenario_lock,
    scenario_write_guard,
    scenario_legacy_client,
    scenario_desktop_python,
    scenario_desktop,
    scenario_privileges,
    scenario_admin,
    scenario_unique_index,
)



def main() -> int:
    engine = connect()
    conn = engine.connect()
    try:
        table = conn.execute(text(
            "SELECT to_regclass('public.user_sessions')")).scalar()
        if not table:
            check("table public.user_sessions installee", False,
                  "appliquez python _apply_single_session.py")
            return 1
        check("table public.user_sessions installee", True)

        # Comptes jetables (commites : visibles par les autres connexions).
        with engine.begin() as c:
            create_user(c, ADMIN_EMAIL, "ADMIN")
            create_user(c, CAISSIER_EMAIL, "CAISSIER")
        print(f"   comptes de test : {ADMIN_EMAIL} / {CAISSIER_EMAIL}")

        for scenario in SCENARIOS:
            print(f"\n-- {scenario.__name__} --")
            try:
                if scenario is scenario_desktop_python:
                    # Cette variante utilise ses propres connexions committees.
                    scenario(conn, engine)
                else:
                    scenario(conn)
            except Exception as exc:                            # noqa: BLE001
                fail(f"{scenario.__name__} : {type(exc).__name__}: {exc}")
            finally:
                conn.rollback()                                # aucune ecriture gardee
    finally:
        with engine.begin() as c:                                # nettoyage des comptes
            c.execute(text("DELETE FROM auth.users WHERE email = :a OR email = :b"),
                      {"a": ADMIN_EMAIL, "b": CAISSIER_EMAIL})
        conn.rollback()
        restants = conn.execute(text(
            "SELECT count(*) FROM public.user_sessions")).scalar()
        print(f"\nLignes restantes dans public.user_sessions : {restants}")
        conn.close()

    print("Transaction ANNULEE : aucune donnee metier conservee.")
    print("Resultat :", "TOUT OK" if PROBLEMS == 0 else f"{PROBLEMS} probleme(s)")
    return 0 if PROBLEMS == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


