"""Patch Lot 1 : AdminView branchée sur core.permissions (source unique).

Remplace les dictionnaires divergents de `ui/views/admin_view.py`
(roles_dict, available_roles, permissions_list, reset_permissions_to_default,
permissions_list du PermissionsDialog) par les données de core.permissions.
Script ponctuel : supprimable après application.
"""
from pathlib import Path

PATH = Path("ui/views/admin_view.py")
text = PATH.read_text(encoding="utf-8")


def replace_once(source, old, new, label):
    if old not in source:
        raise SystemExit(f"ANCRE INTROUVABLE : {label}")
    if source.count(old) != 1:
        raise SystemExit(f"ANCRE AMBIGUE ({source.count(old)}) : {label}")
    print(f"  OK  {label}")
    return source.replace(old, new)


# --- 1. Imports -------------------------------------------------------------
text = replace_once(
    text,
    "from utils.settings_manager import SettingsManager\nimport os",
    "from utils.settings_manager import SettingsManager\n"
    "# Source unique des rôles et permissions (partagée avec le frontend web).\n"
    "from core.permissions import (\n"
    "    describe_roles,\n"
    "    permission_label,\n"
    "    permission_labels,\n"
    "    role_description,\n"
    "    role_display_name,\n"
    ")\n"
    "import os",
    "imports core.permissions",
)

# --- 2. roles_dict / available_roles / permissions_list --------------------
old_start = text.index("        # Rôles et permissions (dictionnaire structuré)")
old_end = text.index("        # Charger les utilisateurs depuis la base de données", old_start)
text = text[:old_start] + (
    "        # Rôles et permissions : source unique core.permissions (le web s'y\n"
    "        # adosse également). Ne pas redéfinir de matrice ici.\n"
    "        self.roles_dict = describe_roles()\n"
    "\n"
    "        # Rôles proposés à la création d'un utilisateur\n"
    "        self.available_roles = available_roles()\n"
    "\n"
    "        # Permissions disponibles : (libellé, clé, description)\n"
    "        self.permissions_list = permission_labels()\n"
    "\n"
) + text[old_end:]
print("  OK  roles_dict / available_roles / permissions_list")

# --- 3. Libellés / permissions d'un rôle ----------------------------------
text = replace_once(
    text,
    "    def get_role_display_name(self, role_key):\n"
    "        if role_key in self.roles_dict:\n"
    "            return self.roles_dict[role_key][\"name\"]\n"
    "        return role_key\n"
    "    \n"
    "    def get_role_permissions(self, role_key):\n"
    "        if role_key in self.roles_dict:\n"
    "            return self.roles_dict[role_key].get(\"permissions\", {})\n"
    "        return {}\n",
    "    def get_role_display_name(self, role_key):\n"
    "        \"\"\"Libellé lisible d'un rôle (source unique : core.permissions).\"\"\"\n"
    "        return role_display_name(role_key)\n"
    "    \n"
    "    def get_role_permissions(self, role_key):\n"
    "        \"\"\"Permissions d'un rôle, toutes clés présentes (booléens).\"\"\"\n"
    "        role = self.roles_dict.get(role_key)\n"
    "        if role is not None:\n"
    "            return role.get(\"permissions\", {})\n"
    "        from core.permissions import permission_flags\n"
    "        return permission_flags(role_key)\n",
    "get_role_display_name / get_role_permissions",
)

# --- 4. Nom lisible d'une permission --------------------------------------
text = replace_once(
    text,
    "    def get_permission_name(self, perm_key):\n"
    "        for perm_name, key, _ in self.permissions_list:\n"
    "            if key == perm_key:\n"
    "                return perm_name\n"
    "        return perm_key\n",
    "    def get_permission_name(self, perm_key):\n"
    "        \"\"\"Libellé d'une permission (source unique : core.permissions).\"\"\"\n"
    "        return permission_label(perm_key)\n",
    "get_permission_name",
)

# --- 5. Réinitialisation aux valeurs par défaut ---------------------------
old_start = text.index("        if reply == QMessageBox.Yes:\n            self.roles_dict = {")
old_end = text.index("            self.log_activity(", old_start)
text = text[:old_start] + (
    "        if reply == QMessageBox.Yes:\n"
    "            # Retour à la matrice de référence (core.permissions), sans copie\n"
    "            # locale : impossible de diverger de la source unique.\n"
    "            self.roles_dict = describe_roles()\n"
    "            \n"
) + text[old_end:]
print("  OK  reset_permissions_to_default")

# --- 6. PermissionsDialog : liste des permissions -------------------------
old_start = text.index(
    "        permissions_list = [\n"
    "            (\"Tableau de bord\", \"dashboard\", \"Accès au tableau de bord principal\"),"
)
old_end = text.index("        for perm_name, perm_key, perm_desc in permissions_list:", old_start)
text = text[:old_start] + (
    "        permissions_list = permission_labels()\n"
    "        \n"
) + text[old_end:]
print("  OK  PermissionsDialog : liste des permissions")

# --- 7. Description du rôle dans le dialogue utilisateur ------------------
text = replace_once(
    text,
    "        if role_key and role_key in self.roles_dict:\n"
    "            description = self.roles_dict[role_key].get(\"description\", \"\")\n",
    "        if role_key and role_key in self.roles_dict:\n"
    "            description = self.roles_dict[role_key].get(\n"
    "                \"description\", role_description(role_key))\n",
    "description du rôle",
)

# --- 8. Libellé du rôle dans PermissionsDialog ----------------------------
text = replace_once(
    text,
    "        role_label = QLabel(f\"Rôle: {self.roles_dict.get(user.role, {}).get('name', user.role)}\")",
    "        role_label = QLabel(f\"Rôle: {self.roles_dict.get(user.role, {}).get(\n"
    "            'name', role_display_name(user.role))}\")",
    "PermissionsDialog : libellé du rôle",
)

# --- 9. AdminView.__init__ : rôles disponibles via la source unique -------
text = replace_once(
    text,
    "        self.available_roles = available_roles()\n",
    "        self.available_roles = available_roles()\n",
    "appel available_roles()",
)

# --- 10. UserDialog : plus de repli sur l'ancien rôle GERANT -------------
text = replace_once(
    text,
    "        self.available_roles = available_roles or [\"ADMIN\", \"GERANT\", \"CAISSIER\"]",
    "        # Le paramètre prime (AdminView passe la liste canonique) ; le repli\n"
    "        # utilise aussi la source unique pour ne jamais proposer GERANT.\n"
    "        from core.permissions import available_roles as _available_roles\n"
    "        self.available_roles = list(available_roles or _available_roles())",
    "UserDialog : rôles disponibles",
)

PATH.write_text(text, encoding="utf-8")
print("\nadmin_view.py patché.")
