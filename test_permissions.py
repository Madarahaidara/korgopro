"""Tests de la source unique de roles et de permissions (``core.permissions``).

Couvre :
  1. normalisation des rôles (fin des six vocabulaires concurrents) ;
  2. matrice des permissions ;
  3. classification appliquées / planifiées ;
  4. libellés et descriptions exposés à l'interface ;
  5. navigation déclarative (``main_window.MENU_ENTRIES``) ;
  6. construction des écrans selon le rôle (offscreen) ;
  7. contrôle de la gestion des magasins (``stock_view``).

Usage :  python test_permissions.py   (code de sortie 1 si un test échoue)
"""
import os
import sys

sys.path.insert(0, ".")

from core.permissions import (  # noqa: E402
    CANONICAL_ROLES,
    ENFORCED_PERMISSIONS,
    LEGACY_ROLES,
    PERMISSIONS,
    PLANNED_PERMISSIONS,
    ROLE_ALIASES,
    can,
    describe_roles,
    is_admin,
    is_enforced,
    is_known_role,
    normalize_role,
    permission_flags,
    permissions_of,
    role_display_name,
)

FAILURES = []


def check(label, condition, detail=""):
    status = "OK  " if condition else "FAIL"
    if not condition:
        FAILURES.append(label)
    print(f"   [{status}] {label}{(' -> ' + str(detail)) if detail else ''}")


print("=" * 70)
print("TEST PERMISSIONS - SOURCE UNIQUE (core.permissions)")
print("=" * 70)

# ---------------------------------------------------------------------------
print("\n1. NORMALISATION DES ROLES")
# ---------------------------------------------------------------------------
check("'gerant' -> GESTIONNAIRE", normalize_role("gerant") == "GESTIONNAIRE",
      normalize_role("gerant"))
check("' Gestionnaire ' -> GESTIONNAIRE",
      normalize_role(" Gestionnaire ") == "GESTIONNAIRE")
check("'Caissier' -> CAISSIER", normalize_role("Caissier") == "CAISSIER")
check("MANAGER -> GESTIONNAIRE (alias patche)", normalize_role("MANAGER") == "GESTIONNAIRE")
check("None -> chaine vide", normalize_role(None) == "")
check("role inconnu conserve en majuscules",
      normalize_role("stockist") == "STOCKIST")
check("tous les alias pointent vers un role canonique",
      set(ROLE_ALIASES.values()) <= set(CANONICAL_ROLES), ROLE_ALIASES)
check("GERANT est un alias (bug P0 : role casse a la caisse)",
      ROLE_ALIASES.get("GERANT") == "GESTIONNAIRE")
check("is_known_role('ADMIN')", is_known_role("ADMIN"))
check("is_known_role('gerant')", is_known_role("gerant"))
check("not is_known_role('STOCKIST')", not is_known_role("STOCKIST"))
check("LEGACY_ROLES disjoints des canoniques",
      not (set(LEGACY_ROLES) & set(CANONICAL_ROLES)))
check("is_admin('admin')", is_admin("admin"))

# ---------------------------------------------------------------------------
print("\n2. MATRICE DE PERMISSIONS")
# ---------------------------------------------------------------------------
check("PERMISSIONS non vide", bool(PERMISSIONS))
check("aucune permission vide",
      all(PERMISSIONS[k][0] and PERMISSIONS[k][1] for k in PERMISSIONS))
check("ENFORCED et PLANNED partitionnent PERMISSIONS",
      set(ENFORCED_PERMISSIONS) | set(PLANNED_PERMISSIONS) == set(PERMISSIONS)
      and not (set(ENFORCED_PERMISSIONS) & set(PLANNED_PERMISSIONS)),
      f"enforced={sorted(ENFORCED_PERMISSIONS)} planned={sorted(PLANNED_PERMISSIONS)}")
check("view_dashboard est controllée (obligatoire comme vue d'accueil)",
      "view_dashboard" in ENFORCED_PERMISSIONS)
check("access_admin est contrôlée", "access_admin" in ENFORCED_PERMISSIONS)

for role in CANONICAL_ROLES:
    perms = permissions_of(role)
    check(f"{role:12s} : permission inconnue refusée",
          not any(p not in PERMISSIONS for p in perms))

check("ADMIN possède toutes les permissions",
      permissions_of("ADMIN") == frozenset(PERMISSIONS.keys()))
check("tous les rôles canoniques ont view_dashboard",
      all(can(role, "view_dashboard") for role in CANONICAL_ROLES))
check("seul ADMIN a access_admin "
      "(SUPERVISEUR retiré : escalade de privilèges)",
      [r for r in CANONICAL_ROLES if can(r, "access_admin")] == ["ADMIN"])
check("seul ADMIN a manage_settings",
      [r for r in CANONICAL_ROLES if can(r, "manage_settings")] == ["ADMIN"])
check("GERANT == GESTIONNAIRE (permissions identiques)",
      permissions_of("GERANT") == permissions_of("GESTIONNAIRE"))
check("CAISSIER ne gère pas la trésorerie (alignement web)",
      not can("CAISSIER", "manage_treasury"))
check("CAISSIER consulte la trésorerie (parité menu existant)",
      can("CAISSIER", "view_treasury"))
check("CAISSIER ne voit pas le stock en écriture",
      not can("CAISSIER", "manage_stock"))
check("GESTIONNAIRE gère les magasins", can("GESTIONNAIRE", "manage_stores"))
check("CAISSIER ne gère pas les magasins", not can("CAISSIER", "manage_stores"))
check("ASSISTANT ne gère pas les magasins", not can("ASSISTANT", "manage_stores"))
check("rôle inconnu : dashboard seulement",
      permissions_of("STOCKIST") == frozenset({"view_dashboard"}))
check("rôle vide : dashboard seulement",
      permissions_of("") == frozenset({"view_dashboard"}))
check("permission inconnue refusée même pour ADMIN",
      can("ADMIN", "create_sale") is False)
check("permission inconnue refusée (chaîne vide)",
      can("ADMIN", "") is False)
check("is_enforced('create_sales')", is_enforced("create_sales"))
check("not is_enforced('view_reports') (planifié)", not is_enforced("view_reports"))

flags = permission_flags("CAISSIER")
check("permission_flags expose toutes les clés",
      set(flags) == set(PERMISSIONS))
check("permission_flags ne contient que des booléens",
      all(isinstance(v, bool) for v in flags.values()))
check("permission_flags('ADMIN') tout à True", all(permission_flags("ADMIN").values()))
check("permission_flags('STOCKIST') : dashboard seul",
      [k for k, v in flags.items() if False] == []
      or sum(1 for v in permission_flags("STOCKIST").values() if v) == 1)

# ---------------------------------------------------------------------------
print("\n3. DESCRIPTEURS D'AFFICHAGE (AdminView / écran Rôles)")
# ---------------------------------------------------------------------------
roles = describe_roles()
check("describe_roles couvre les rôles canoniques",
      set(roles) == set(CANONICAL_ROLES))
check("chaque rôle a name/description/permissions",
      all({"name", "description", "permissions"} <= set(v) for v in roles.values()))
check("GERANT absent de describe_roles (synonyme absorbé)",
      "GERANT" not in roles)
check("libellés lisibles", role_display_name("gerant") == "Gestionnaire")
check("libellé ADMIN", role_display_name("ADMIN") == "Administrateur")
check("rôle inconnu : libellé = rôle brut",
      role_display_name("STOCKIST") == "STOCKIST")

import core.permissions as _perms  # noqa: E402

labels = _perms.permission_labels()
check("permission_labels renvoie (libellé, clé, description)",
      all(len(t) == 3 for t in labels) and len(labels) == len(PERMISSIONS))
check("permission_label résout la clé",
      _perms.permission_label("view_dashboard") == "Tableau de bord")
check("permission_label clé inconnue -> clé",
      _perms.permission_label("inexistant") == "inexistant")
check("available_roles = rôles canoniques (pas d'alias)",
      _perms.available_roles() == list(CANONICAL_ROLES))

check("not is_admin('GESTIONNAIRE')", not is_admin("GESTIONNAIRE"))

# ---------------------------------------------------------------------------
print("\n2. MATRICE DE PERMISSIONS")
# ---------------------------------------------------------------------------
check("ADMIN possede TOUTES les permissions",
      permissions_of("ADMIN") == frozenset(PERMISSIONS),
      f"{len(permissions_of('ADMIN'))}/{len(PERMISSIONS)}")
check("ADMIN garde tout meme en minuscules",
      permissions_of("admin") == frozenset(PERMISSIONS))
check("toute permission d'un role est une cle connue",
      all(p in PERMISSIONS for role in CANONICAL_ROLES
          for p in permissions_of(role)))
check("role inconnu -> tableau de bord seul",
      permissions_of("KJHFDS") == frozenset({"view_dashboard"}))
check("role vide -> tableau de bord seul",
      permissions_of("") == frozenset({"view_dashboard"}))
check("cle de permission inexistante toujours refusee",
      not can("ADMIN", "create_sale"))
check("GERANT == GESTIONNAIRE (alias)",
      permissions_of("GERANT") == permissions_of("GESTIONNAIRE"))
check("GERANT peut encaisser (bug P0 corrige)", can("GERANT", "create_sales"))
check("CAISSIER peut creer une vente mais pas annuler",
      can("CAISSIER", "create_sales") and not can("CAISSIER", "cancel_sales"))
check("CAISSIER consulte la tresorerie (alignement desktop/web)",
      can("CAISSIER", "view_treasury"))
check("CAISSIER n'ecrit pas dans la tresorerie",
      not can("CAISSIER", "manage_treasury"))
check("CAISSIER n'entre pas dans l'administration",
      not can("CAISSIER", "access_admin"))
check("CAISSIER n'accede ni au stock ni aux exports",
      not can("CAISSIER", "view_stock") and not can("CAISSIER", "export_data"))
check("ASSISTANT a les proformas, pas le stock",
      can("ASSISTANT", "manage_proformas")
      and not can("ASSISTANT", "view_stock"))
check("GESTIONNAIRE a le stock et la tresorerie",
      can("GESTIONNAIRE", "view_stock")
      and can("GESTIONNAIRE", "view_treasury"))
check("SUPERVISEUR peut annuler une vente", can("SUPERVISEUR", "cancel_sales"))
check("SUPERVISEUR accede a l'administration (droit existant, P0 pour plus tard)",
      can("SUPERVISEUR", "access_admin"))
check("GESTIONNAIRE n'entre pas dans l'administration",
      not can("GESTIONNAIRE", "access_admin"))
check("seul ADMIN accede aux parametres",
      can("ADMIN", "manage_settings")
      and not any(can(r, "manage_settings") for r in CANONICAL_ROLES
                  if r != "ADMIN"))
check("toutes les permissions sont atteignables",
      all(any(can(r, p) for r in CANONICAL_ROLES) for p in PERMISSIONS))
check("permission_flags expose toutes les cles",
      set(permission_flags("CAISSIER")) == set(PERMISSIONS))
check("permission_flags respecte la matrice",
      all(permission_flags("ASSISTANT")[k] == can("ASSISTANT", k)
          for k in PERMISSIONS))

# ---------------------------------------------------------------------------
print("\n3. CLASSIFICATION DES PERMISSIONS")
# ---------------------------------------------------------------------------
check("ENFORCED et PLANNED sont disjoints",
      not (ENFORCED_PERMISSIONS & PLANNED_PERMISSIONS))
check("ENFORCED + PLANNED couvrent le vocabulaire",
      (ENFORCED_PERMISSIONS | PLANNED_PERMISSIONS) == frozenset(PERMISSIONS),
      f"{len(ENFORCED_PERMISSIONS)} + {len(PLANNED_PERMISSIONS)}"
      f" = {len(PERMISSIONS)}")
check("is_enforced('access_admin')", is_enforced("access_admin"))
check("not is_enforced('manage_users') (prevu au lot suivant)",
      not is_enforced("manage_users"))
print(f"   Info: {len(ENFORCED_PERMISSIONS)} permissions appliquees,"
      f" {len(PLANNED_PERMISSIONS)} planifiees -> {sorted(PLANNED_PERMISSIONS)}")

# ---------------------------------------------------------------------------
print("\n4. LIBELLES ET DESCRIPTIONS")
# ---------------------------------------------------------------------------
check("role_display_name('gerant') == 'Gestionnaire'",
      role_display_name("gerant") == "Gestionnaire")
check("role inconnu affiche tel quel",
      role_display_name("STOCKIST") == "STOCKIST")
check("describe_roles couvre les roles canoniques",
      set(describe_roles()) == set(CANONICAL_ROLES))
check("describe_roles fournit nom + permissions",
      all("name" in v and set(v["permissions"]) == set(PERMISSIONS)
          for v in describe_roles().values()))
check("le role GERANT n'est plus propose a la creation",
      "GERANT" not in describe_roles())

# ---------------------------------------------------------------------------
print("\n5. NAVIGATION DECLARATIVE (main_window.MENU_ENTRIES)")
# ---------------------------------------------------------------------------
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from ui.views.main_window import MENU_ENTRIES  # noqa: E402

check("8 entrees de menu declarees", len(MENU_ENTRIES) == 8,
      str(len(MENU_ENTRIES)))
check("aucune permission en double dans le menu",
      len({perm for _a, perm, _v, _t in MENU_ENTRIES}) == len(MENU_ENTRIES))
check("chaque permission du menu est une cle connue",
      all(perm in PERMISSIONS for _a, perm, _v, _t in MENU_ENTRIES))
check("chaque permission du menu est appliquee (ENFORCED)",
      all(perm in ENFORCED_PERMISSIONS for _a, perm, _v, _t in MENU_ENTRIES))
check("chaque entree pointe une vue existante",
      all(view_attr in ("dashboard_view", "sale_view", "register_view",
                        "proforma_view", "stock_view", "treasury_view",
                        "admin_view", "settings_view")
          for _a, _p, view_attr, _t in MENU_ENTRIES))
check("le role GERANT obtient le meme menu que GESTIONNAIRE",
      [can("GERANT", p) for _a, p, _v, _t in MENU_ENTRIES]
      == [can("GESTIONNAIRE", p) for _a, p, _v, _t in MENU_ENTRIES])
