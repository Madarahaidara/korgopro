"""Source unique de vérité des rôles et des permissions (desktop).

POURQUOI CE MODULE
------------------
Cinq vocabulaires de rôles/permissions coexistaient sans autorité commune :

* ``ui/views/main_window.py`` : chaîne ``if/elif`` sur le rôle (visibilité du menu) ;
* ``ui/views/sale_view.py``   : dictionnaire ``ROLES`` (``view_sales``, ``create_sales``…) ;
* ``ui/views/admin_view.py``  : ``roles_dict`` (``dashboard``, ``sales``, ``inventory``…) ;
* ``ui/views/stock_view.py``  : tuple en dur ``("ADMIN", "GERANT", "GESTIONNAIRE")`` ;
* ``web/src/context/AuthContext.jsx`` : ``ROLE_PERMISSIONS`` (côté web).

Conséquences constatées avant ce module :

* le rôle ``GERANT`` proposé par l'écran de création d'utilisateur
  (``ui/views/admin_view.py``) n'existait pas dans ``sale_view.ROLES`` : la vue
  de caisse refusait l'accès, restait à moitié construite et affichait un
  dialogue modal pendant la construction de la fenêtre principale ;
* la comparaison des rôles était sensible à la casse
  (``main_window`` appliquait ``.upper()``, ``sale_view`` comparait le rôle brut) :
  un rôle ``gestionnaire`` ouvrait le bouton « Vente » mais pas la vue ;
* un rôle inconnu était silencieusement privé de tous ses boutons.

VOCABULAIRE UNIQUE
------------------
Une seule liste de clés : :data:`PERMISSIONS`. Correspondance avec les anciens
vocabulaires :

===========================  ==============================
Ancien vocabulaire           Clé de ce module
===========================  ==============================
``all`` (ADMIN, sale_view)   toutes les clés de :data:`PERMISSIONS`
``view_products``            ``view_stock``
``dashboard``                ``view_dashboard``
``sales``                    ``view_sales`` / ``create_sales``
``inventory``                ``view_stock`` / ``manage_stock``
``reports``                  ``view_reports``
``users``                    ``manage_users``
``settings``                 ``manage_settings``
``export``                   ``export_data``
``audit``                    ``view_audit_logs``
Boutons du menu              ``view_dashboard``, ``create_sales``,
                             ``view_invoice_register``, ``manage_proformas``,
                             ``view_stock``, ``view_treasury``,
                             ``access_admin``, ``manage_settings``
===========================  ==============================

PÉRIMÈTRE DE VÉRIFICATION
-------------------------
Les clés listées dans :data:`ENFORCED_PERMISSIONS` sont **réellement vérifiées**
par l'interface. Les clés listées dans :data:`PLANNED_PERMISSIONS` expriment la
**cible** : elles ne sont pas encore contrôlées (aucune vue ne les consulte) et
seront branchées lors du lot « gardes de vues + step-up ». Utiliser
:func:`is_enforced` pour savoir dans quel cas on se trouve.

USAGE
-----
::

    from core.permissions import can, normalize_role, permissions_of

    normalize_role("gerant")        # -> "GESTIONNAIRE"
    can(user_role, "create_sales")  # -> True / False
    permissions_of(user_role)       # -> frozenset de clés accordées
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Rôles
# ---------------------------------------------------------------------------
#: Les seuls rôles reconnus par l'application desktop.
CANONICAL_ROLES: tuple[str, ...] = (
    "ADMIN",
    "GESTIONNAIRE",
    "SUPERVISEUR",
    "ASSISTANT",
    "CAISSIER",
)

#: Synonymes historiques ramenés vers un rôle canonique.
#: ``GERANT`` est proposé par l'écran de création d'utilisateur et présent dans
#: certaines bases : il désigne exactement le rôle ``GESTIONNAIRE``.
ROLE_ALIASES: dict[str, str] = {
    "GERANT": "GESTIONNAIRE",
}

#: Rôles hérités (imports web / anciens comptes) qui ne sont PAS des synonymes.
#: Ils restent reconnus pour éviter un verrouillage silencieux (aucun message,
#: aucun bouton) mais leur périmètre doit être arbitré explicitement.
LEGACY_ROLES: tuple[str, ...] = ("MANAGER", "STOCKIST", "ACCOUNTANT")

#: Libellés affichés dans l'interface.
ROLE_LABELS: dict[str, str] = {
    "ADMIN": "Administrateur",
    "GESTIONNAIRE": "Gestionnaire",
    "SUPERVISEUR": "Superviseur",
    "ASSISTANT": "Assistant",
    "CAISSIER": "Caissier",
}

# ---------------------------------------------------------------------------
# Permissions (vocabulaire unique)
# ---------------------------------------------------------------------------
#: ``clé -> (libellé affiché, description)``. L'ordre est celui d'affichage dans
#: l'écran Administration (onglet « Rôles & Permissions »).
PERMISSIONS: dict[str, tuple[str, str]] = {
    "view_dashboard": (
        "Tableau de bord",
        "Accès au tableau de bord principal",
    ),
    "view_sales": (
        "Consulter les ventes",
        "Consulter l'historique et le détail des ventes",
    ),
    "create_sales": (
        "Encaisser (caisse)",
        "Créer une vente et encaisser depuis la vue Caisse",
    ),
    "cancel_sales": (
        "Annuler une vente",
        "Annuler ou supprimer une vente existante",
    ),
    "view_invoice_register": (
        "Registre des factures",
        "Consulter le registre des factures clients",
    ),
    "manage_proformas": (
        "Devis / proformas",
        "Créer, imprimer et convertir les factures pro forma",
    ),
    "view_stock": (
        "Consulter le stock",
        "Consulter les produits, les quantités et les alertes de stock",
    ),
    "manage_stock": (
        "Gérer le stock",
        "Créer/modifier les produits, les entrées et les sorties de stock",
    ),
    "manage_stores": (
        "Gérer les magasins",
        "Créer, modifier et affecter les magasins (multi-magasins)",
    ),
    "view_treasury": (
        "Consulter la trésorerie",
        "Consulter les comptes et les mouvements de trésorerie",
    ),
    "manage_treasury": (
        "Gérer la trésorerie",
        "Créer des comptes, saisir des mouvements, ouvrir/clôturer une caisse",
    ),
    "manage_customers": (
        "Gérer les clients",
        "Créer et modifier la base de données clients",
    ),
    "view_reports": (
        "Rapports et statistiques",
        "Consulter et générer les rapports et statistiques",
    ),
    "access_admin": (
        "Administration",
        "Ouvrir le panneau d'administration",
    ),
    "manage_users": (
        "Gérer les utilisateurs",
        "Créer, modifier, désactiver et supprimer les comptes utilisateurs",
    ),
    "manage_database": (
        "Base de données",
        "Sauvegarde, restauration, optimisation et requêtes SQL",
    ),
    "manage_settings": (
        "Paramètres",
        "Modifier les paramètres société, TVA, devise et thèmes",
    ),
    "export_data": (
        "Export de données",
        "Exporter les données (Excel, PDF, JSON, impression)",
    ),
    "view_audit_logs": (
        "Journaux d'audit",
        "Consulter le journal d'activité et les journaux système",
    ),
}

#: Descriptions du périmètre, affichées à côté du sélecteur de rôle.
ROLE_DESCRIPTIONS: dict[str, str] = {
    "ADMIN": "Accès complet à toutes les fonctionnalités",
    "GESTIONNAIRE": "Gestion des ventes, du stock, des clients et de la trésorerie",
    "SUPERVISEUR": "Comme le gestionnaire, plus l'administration et les journaux",
    "ASSISTANT": "Caisse, registre des factures et devis pro forma",
    "CAISSIER": "Encaissement, clients et consultation de la trésorerie",
}

#: Périmètre minimal appliqué à un rôle inconnu ou hérité : accès au seul
#: tableau de bord, plus un avertissement journalisé par l'appelant.
UNKNOWN_ROLE_PERMISSIONS: frozenset[str] = frozenset({"view_dashboard"})

# ---------------------------------------------------------------------------
# Périmètre réellement vérifié (Lot 1)
# ---------------------------------------------------------------------------
#: Permissions contrôlées aujourd'hui par l'interface :
#:
#: * navigation, dans ``ui/views/main_window.py`` :
#:   ``view_dashboard`` (Tableau de bord), ``create_sales`` (Vente),
#:   ``view_invoice_register`` (Registre factures), ``manage_proformas``
#:   (Document), ``view_stock`` (Stock), ``view_treasury`` (Trésorerie),
#:   ``access_admin`` (Admin), ``manage_settings`` (Paramètres) ;
#: * ``create_sales`` garde aussi l'entrée de ``ui/views/sale_view.py`` ;
#: * ``manage_stores`` dans ``ui/views/stock_view.py``.
#:
#: Le bouton « Vente » est rattaché à ``create_sales`` et non à ``view_sales`` :
#: les caissiers et assistants créent des ventes mais ne consultent pas
#: l'historique complet.
ENFORCED_PERMISSIONS: frozenset[str] = frozenset({
    "view_dashboard",
    "create_sales",
    "view_invoice_register",
    "manage_proformas",
    "view_stock",
    "view_treasury",
    "access_admin",
    "manage_settings",
    "manage_stores",
})

#: Permissions déclarées mais pas encore contrôlées : elles documentent la
#: cible du lot « gardes de vues + step-up ». Pour ces clés, la matrice indique
#: ce que l'application DEVRA appliquer, pas ce qu'elle applique aujourd'hui.
PLANNED_PERMISSIONS: frozenset[str] = frozenset(
    set(PERMISSIONS) - ENFORCED_PERMISSIONS
)

# ---------------------------------------------------------------------------
# Matrice de référence
# ---------------------------------------------------------------------------
# ``manage_stores`` suit le comportement historique de ``stock_view`` :
# ADMIN et GESTIONNAIRE (donc GERANT) ; SUPERVISEUR exclu.
_GESTIONNAIRE_PERMISSIONS = frozenset({
    "view_dashboard",
    "view_sales",
    "create_sales",
    "cancel_sales",
    "view_invoice_register",
    "manage_proformas",
    "view_stock",
    "manage_stock",
    "manage_stores",
    "view_treasury",
    "manage_treasury",
    "manage_customers",
    "view_reports",
    "export_data",
})

_MATRIX: dict[str, frozenset[str]] = {
    # ADMIN : toutes les clés du vocabulaire (calculé — jamais de « all »
    # magique : une clé inconnue reste refusée, même pour un administrateur).
    "ADMIN": frozenset(PERMISSIONS),
    "GESTIONNAIRE": _GESTIONNAIRE_PERMISSIONS,
    # SUPERVISEUR : identique au gestionnaire + ouverture du panneau
    # d'administration et consultation des journaux (comportement historique du
    # menu). ``manage_users`` / ``manage_database`` restent à False : c'est la
    # cible ; la garde de l'AdminView arrive au lot suivant.
    "SUPERVISEUR": _GESTIONNAIRE_PERMISSIONS | {"access_admin", "view_audit_logs"},
    # ASSISTANT : caisse, registre et proformas (pas de stock, ni trésorerie,
    # ni administration, ni paramètres).
    "ASSISTANT": frozenset({
        "view_dashboard",
        "create_sales",
        "view_invoice_register",
        "manage_proformas",
        "manage_customers",
    }),
    # CAISSIER : caisse, registre, proformas et consultation de la trésorerie.
    # ``manage_treasury=False`` est la CIBLE (consultation seule) : la garde
    # sera branchée au lot suivant — voir PLANNED_PERMISSIONS.
    "CAISSIER": frozenset({
        "view_dashboard",
        "create_sales",
        "view_invoice_register",
        "manage_proformas",
        "view_treasury",
        "manage_customers",
    }),
}

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def normalize_role(role) -> str:
    """Retourne le rôle canonique correspondant à *role*.

    Applique ``str`` + ``strip`` + ``upper`` puis résout les synonymes
    (:data:`ROLE_ALIASES`). Un rôle inconnu est retourné normalisé (majuscules)
    pour rester lisible dans les journaux et l'interface.
    """
    if role is None:
        return ""
    normalized = str(role).strip().upper()
    return ROLE_ALIASES.get(normalized, normalized)


def is_known_role(role) -> bool:
    """``True`` si *role* (normalisé) fait partie des rôles canoniques."""
    return normalize_role(role) in CANONICAL_ROLES


def is_legacy_role(role) -> bool:
    """``True`` si *role* (normalisé) est un rôle hérité non arbitré."""
    return normalize_role(role) in LEGACY_ROLES


def is_admin(role) -> bool:
    """``True`` si *role* est administrateur."""
    return normalize_role(role) == "ADMIN"


def permissions_of(role) -> frozenset[str]:
    """Retourne l'ensemble des permissions accordées à *role*.

    Un rôle hérité ou inconnu reçoit :data:`UNKNOWN_ROLE_PERMISSIONS`
    (tableau de bord uniquement) : jamais d'accès implicite, jamais de
    périmètre « vide » ambigu.
    """
    exact = _MATRIX.get(normalize_role(role))
    if exact is not None:
        return exact
    return UNKNOWN_ROLE_PERMISSIONS


def permission_flags(role) -> dict[str, bool]:
    """Comme :func:`permissions_of`, mais sous forme ``{clé: booléen}``.

    Toutes les clés sont présentes (y compris les refus) : c'est la forme
    attendue par l'onglet « Rôles & Permissions » et par le dialogue des
    permissions d'un utilisateur.
    """
    granted = permissions_of(role)
    return {key: (key in granted) for key in PERMISSIONS}


def can(role, permission: str) -> bool:
    """``True`` si *role* possède *permission*.

    Une clé inconnue est toujours refusée (même pour ADMIN) : une faute de
    frappe dans un appel ne peut donc jamais accorder un accès.
    """
    if permission not in PERMISSIONS:
        return False
    return permission in permissions_of(role)


def is_enforced(permission: str) -> bool:
    """``True`` si *permission* est déjà contrôlée par l'interface."""
    return permission in ENFORCED_PERMISSIONS


def role_display_name(role) -> str:
    """Libellé lisible d'un rôle (``GERANT`` -> ``Gestionnaire``)."""
    normalized = normalize_role(role)
    if normalized in ROLE_LABELS:
        return ROLE_LABELS[normalized]
    return "" if role is None else str(role)


def role_description(role) -> str:
    """Description du périmètre d'un rôle."""
    normalized = normalize_role(role)
    if normalized in ROLE_DESCRIPTIONS:
        return ROLE_DESCRIPTIONS[normalized]
    if normalized in LEGACY_ROLES:
        return (
            "Rôle hérité : accès réduit au tableau de bord dans l'attente d'un "
            "arbitrage explicite du périmètre."
        )
    return "Rôle inconnu : accès réduit au tableau de bord."


def describe_roles() -> dict[str, dict]:
    """Décrit tous les rôles canoniques (format attendu par l'AdminView)."""
    return {
        role: {
            "name": ROLE_LABELS[role],
            "description": ROLE_DESCRIPTIONS[role],
            "permissions": permission_flags(role),
        }
        for role in CANONICAL_ROLES
    }


def available_roles() -> list[str]:
    """Rôles proposés à la création d'un utilisateur (canoniques uniquement)."""
    return list(CANONICAL_ROLES)


def permission_labels() -> list[tuple[str, str, str]]:
    """Liste ``(libellé, clé, description)`` dans l'ordre d'affichage."""
    return [
        (label, key, description)
        for key, (label, description) in PERMISSIONS.items()
    ]


def permission_label(key: str) -> str:
    """Libellé d'une permission (``key`` si la clé est inconnue)."""
    entry = PERMISSIONS.get(key)
    return entry[0] if entry else key
