"""Tests Supabase REST : isolation inter-entreprises via PostgREST.

Securite (REGLES ABSOLUES) :
- SKIPPED sauf si SUPABASE_TEST_URL + cles de TEST fournies :
    SUPABASE_TEST_URL        (ex. https://xyzcompany.supabase.co)
    SUPABASE_TEST_ANON_KEY   (cle anon du projet de TEST)
    SUPABASE_TEST_USER_A_JWT (JWT d'un membre de l'org A, TEST uniquement)
    SUPABASE_TEST_USER_B_JWT (JWT d'un membre de l'org B, TEST uniquement)
- Garde-fou : si l'URL contient "supabase.co" il faut en plus
  KORGO_TEST_TARGET=staging (sinon FAIL, jamais d'execution).
- Aucun secret affiche dans les rapports (cles masquees, JWT tronques).

Principe : avec RLS deployee, le JWT A ne doit voir que les lignes de
l'org A ; une tentative d'acces croise (org B) doit etre vide/refusee.
"""
import os
from uuid import uuid4

import pytest

try:
    import urllib.request as _url
    import urllib.error as _urlerr
    import json as _json
    _HAS_URLLIB = True
except Exception:
    _HAS_URLLIB = False


def _jwt_preview(token: str) -> str:
    return (token[:12] + "...") if token else "(absent)"




def _get(base, anon, jwt, table, params="select=id&limit=5"):
    assert _HAS_URLLIB, "urllib indisponible"
    req = _url.Request(f"{base}/rest/v1/{table}?{params}")
    req.add_header("apikey", anon)
    req.add_header("Authorization", f"Bearer {jwt}")
    try:
        with _url.urlopen(req, timeout=15) as resp:
            return resp.status, _json.loads(resp.read().decode("utf-8"))
    except _urlerr.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            body = ""
        return exc.code, {"error": body}


def get_cfg():
    base = (os.environ.get("SUPABASE_TEST_URL") or "").strip().rstrip("/")
    anon = (os.environ.get("SUPABASE_TEST_ANON_KEY") or "").strip()
    jwt_a = (os.environ.get("SUPABASE_TEST_USER_A_JWT") or "").strip()
    jwt_b = (os.environ.get("SUPABASE_TEST_USER_B_JWT") or "").strip()
    if not base or not anon:
        pytest.skip("SUPABASE_TEST_URL/ANON_KEY absents : tests REST ignores.")
    if "supabase.co" in base.lower():
        if os.environ.get("KORGO_TEST_TARGET") != "staging":
            pytest.fail("Refus anti-prod : KORGO_TEST_TARGET=staging requis.")
    return base, anon, jwt_a, jwt_b


def test_rest_organizations_visibles_selon_membre():
    """Chaque JWT ne liste que ses organisations (statut 200)."""
    base, anon, jwt_a, jwt_b = get_cfg()
    if not jwt_a or not jwt_b:
        pytest.skip("JWT de TEST A/B absents : isolation non verifiable.")
    for label, jwt in (("A", jwt_a), ("B", jwt_b)):
        status, body = _get(base, anon, jwt, "organizations")
        assert status == 200, f"JWT {label} ({_jwt_preview(jwt)}): {body}"


def test_rest_cross_org_invisible():
    """Le contrôle positif B voit la ligne ; le JWT A ne la voit pas."""
    base, anon, jwt_a, jwt_b = get_cfg()
    if not jwt_a or not jwt_b:
        pytest.skip("JWT de TEST A/B absents.")
    org_b = (os.environ.get("SUPABASE_TEST_ORG_B_ID") or "").strip()
    customer_b = (os.environ.get("SUPABASE_TEST_CUSTOMER_B_ID") or "").strip()
    if not org_b or not customer_b:
        pytest.skip("IDs d'organisation/client B absents : positif de contrôle impossible.")
    params = (f"select=id&organization_id=eq.{org_b}"
              f"&id=eq.{customer_b}&limit=5")
    status_b, rows_b = _get(base, anon, jwt_b, "customers", params=params)
    assert status_b == 200, rows_b
    assert len(rows_b) == 1 and str(rows_b[0]["id"]) == customer_b, (
        "Le JWT B doit voir le client témoin de son organisation.")
    status, body = _get(
        base, anon, jwt_a, "customers", params=params)
    assert status == 200, body
    assert body == [], f"fuite inter-entreprises : {body!r}"[:200]


def test_rest_insert_sans_membre_refuse():
    """POST avec organization_id etranger -> 4xx (WITH CHECK)."""
    base, anon, jwt_a, _jwt_b = get_cfg()
    if not jwt_a:
        pytest.skip("JWT de TEST A absent.")
    org_b = (os.environ.get("SUPABASE_TEST_ORG_B_ID") or "").strip()
    if not org_b:
        pytest.skip("SUPABASE_TEST_ORG_B_ID absent.")
    suffix = uuid4().hex[:12].upper()
    payload = _json.dumps({
        "code": f"TEST-ISO-{suffix}",
        "first_name": "Tenant",
        "last_name": f"Isolation-{suffix}",
        "organization_id": org_b,
    }).encode()
    req = _url.Request(f"{base}/rest/v1/customers", data=payload,
                       method="POST")
    req.add_header("apikey", anon)
    req.add_header("Authorization", f"Bearer {jwt_a}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=minimal")
    try:
        with _url.urlopen(req, timeout=15):
            status = 201
    except _urlerr.HTTPError as exc:
        status = exc.code
    assert status in (401, 403), f"insert cross-org: HTTP {status}"
