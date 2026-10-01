"""Vérifie que la matrice de permissions mobile est identique partout.

Trois copies de la même matrice existent désormais :
  1. ``core/permissions.py``        (desktop — source de référence) ;
  2. ``supabase_mobile_rpc.sql``    (app_security.can — décide des écritures) ;
  3. ``mobile/src/lib/permissions.js`` (affichage des écrans sur le téléphone).

Une divergence entre (1) et (2) serait un TROU DE SÉCURITÉ : le téléphone
afficherait un écran dont le serveur refuse l'écriture (ou l'inverse).

Usage :
    python _check_mobile_matrix.py
"""
import json
import re
from pathlib import Path

from core.permissions import CANONICAL_ROLES, PERMISSIONS, permissions_of

SQL_FILE = Path(__file__).with_name("supabase_mobile_rpc.sql")
JS_FILE = Path(__file__).with_name("mobile") / "src" / "lib" / "permissions.js"
JSON_REF = Path(__file__).with_name("_mobile_matrix_ref.json")

ROLE_ALIASES = {"GERANT": "GESTIONNAIRE"}


def reference_matrix() -> dict[str, list[str]]:
    """Matrice de référence (core.permissions)."""
    return {role: sorted(permissions_of(role)) for role in CANONICAL_ROLES}


def sql_matrix(text: str) -> dict[str, set[str]]:
    """Extrait les couples ('ROLE', 'permission') de app_security.can()."""
    block = text.split("matrice(role, permission) AS (", 1)
    if len(block) != 2:
        raise SystemExit("ANCRE INTROUVABLE : bloc matrice(...) dans le SQL")
    block = block[1].split("AS t(role, permission)", 1)[0]
    pairs = re.findall(r"\('([A-Z]+)',\s*'([a-z_]+)'\)", block)
    if not pairs:
        raise SystemExit("Aucun couple (role, permission) trouvé dans le SQL.")
    matrix: dict[str, set[str]] = {}
    for role, permission in pairs:
        matrix.setdefault(ROLE_ALIASES.get(role, role), set()).add(permission)
    return matrix


def js_matrix(text: str) -> dict[str, list[str]]:
    """Extrait la matrice déclarée dans mobile/src/lib/permissions.js."""
    return {
        "ADMIN": js_array(text, "PERMISSIONS"),  # ADMIN = PERMISSIONS (toutes les clés)
        "GESTIONNAIRE": js_array(text, "GESTIONNAIRE"),
        "SUPERVISEUR": js_array(text, "SUPERVISEUR", base="GESTIONNAIRE"),
        "ASSISTANT": js_array(text, "ASSISTANT"),
        "CAISSIER": js_array(text, "CAISSIER"),
    }


def js_array(text: str, key: str, base: str | None = None) -> list[str]:
    """Contenu du tableau JS : `const KEY = [...]` ou `KEY: [...]`."""
    patterns = (
        rf"const {key} = \[(.*?)\]",
        rf"\n  {key}:\s*\[(.*?)\]",
    )
    for pattern in patterns:
        found = re.search(pattern, text, re.S)
        if found:
            values = sorted(set(re.findall(r"'([a-z_]+)'", found.group(1))))
            if base:
                # SUPERVISEUR : [...GESTIONNAIRE, 'access_admin', ...]
                values = sorted(set(js_array(text, base)) | set(values))
            return values
    raise SystemExit(f"Tableau {key} introuvable dans {JS_FILE.name}")


def main() -> int:
    reference = reference_matrix()
    sql_source = SQL_FILE.read_text(encoding="utf-8")
    js_source = JS_FILE.read_text(encoding="utf-8")

    sql = sql_matrix(sql_source)
    js = js_matrix(js_source)

    problems = 0
    for role in CANONICAL_ROLES:
        expected = set(reference[role])
        got_sql = set(sql.get(role, set()))
        got_js = set(js.get(role, []))

        missing_sql = sorted(expected - got_sql)
        extra_sql = sorted(got_sql - expected)
        missing_js = sorted(expected - got_js)
        extra_js = sorted(got_js - expected)

        status = "OK" if not (missing_sql or extra_sql or missing_js or extra_js) else "ECART"
        print(f"[{status}] {role:12} {len(expected):2} permission(s)")
        for label, values in (
            ("  SQL manquant", missing_sql),
            ("  SQL en trop ", extra_sql),
            ("  JS manquant ", missing_js),
            ("  JS en trop  ", extra_js),
        ):
            if values:
                problems += len(values)
                print(f"{label} : {', '.join(values)}")

    JSON_REF.write_text(json.dumps(reference, indent=2), encoding="utf-8")
    print(f"\nRéférence écrite : {JSON_REF.name}")
    print("Résultat :", "AUCUN ÉCART" if problems == 0 else f"{problems} écart(s)")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
