"""Patch : branche la gestion des utilisateurs de admin_view.py sur Supabase Auth.

Remplace les blocs de code par leurs equivalents "Supabase uniquement" :
  - show_create_user_dialog : creation via auth.users (plus de bcrypt local)
  - edit_user               : mise a jour via les metadonnees Supabase Auth
  - toggle_user_status      : bannissement Supabase Auth (plus de suppression)
  - reset_password          : mot de passe ecrit dans Supabase Auth
  - _save_new_password      : idem
  - delete_user             : suppression du compte Supabase Auth
  - hash_password           : supprime (aucun hash local n'est plus produit)

Idempotent : refuse de s'appliquer une seconde fois.
Usage : python _patch_admin_view_supabase.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(ROOT, "ui", "views", "admin_view.py")

BLOCK_A = '''    def show_create_user_dialog(self):
        """Créer un utilisateur — EXCLUSIVEMENT via Supabase Auth.

        Le compte est créé dans auth.users (Supabase), puis son profil
        public.users est généré automatiquement par le trigger PostgreSQL.
        Si Supabase refuse l'opération, AUCUN utilisateur n'est créé : il ne
        peut donc jamais exister de compte local sans accès Supabase.
        """
        from ui.views.admin_view import UserDialog
        dialog = UserDialog(self, mode="create", style=self.style,
                           available_roles=self.available_roles,
                           roles_dict=self.roles_dict)
        if not dialog.exec():
            return

        user_data = dialog.get_user_data()
        email = (user_data.get("email") or "").strip().lower()

        # Supabase Auth utilise l'email comme identifiant de connexion :
        # il n'est donc plus optionnel.
        if not email:
            QMessageBox.warning(
                self, "Email obligatoire",
                "Un email est obligatoire : Supabase Auth l'utilise comme\\n"
                "identifiant de connexion (applications desktop et web).")
            return

        from core.supabase_auth import provision_auth_user, supabase_available

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "La création d'utilisateur est rattachée exclusivement à\\n"
                "Supabase Auth et la base active ne permet pas de le joindre.\\n\\n"
                "Vérifiez la variable DATABASE_URL (projet Supabase).")
            return

        try:
            # 1) Compte Supabase Auth : source de vérité (email + mot de passe).
            ok, message = provision_auth_user(
                self.db_session, email, user_data["temp_password"],
                username=user_data["username"], role=user_data["role"],
                active=True, must_change_password=True)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(
                    self, "Création refusée par Supabase Auth",
                    f"Aucun utilisateur n'a été créé.\\n\\n{message}")
                return

            # 2) Le trigger Supabase a créé le profil : on le recharge pour
            #    appliquer exactement le username et le rôle demandés.
            self.db_session.flush()
            new_user = (self.db_session.query(User)
                        .filter(User.email == email).first())
            if new_user is None:
                self.db_session.rollback()
                QMessageBox.critical(
                    self, "Synchronisation incomplète",
                    "Le compte Supabase Auth a été créé mais le profil\\n"
                    "public.users n'a pas été généré (trigger absent ?).\\n"
                    "Exécutez _apply_users_supabase_only.py puis réessayez.")
                return

            new_user.username = user_data["username"]
            new_user.role = user_data["role"]
            new_user.active = True
            new_user.must_change_password = True
            self.db_session.commit()

            self.load_users_from_db()

            self.user_created.emit({
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role
            })

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Création utilisateur",
                details=f"Création de {new_user.username} (Rôle: {new_user.role})"
            )

            self.filter_users()

            QMessageBox.information(
                self,
                "Succès",
                f"Utilisateur {new_user.username} créé avec succès!\\n"
                f"Mot de passe temporaire: {user_data['temp_password']}\\n\\n"
                f"Compte Supabase Auth provisionné ({email}).\\n"
                "Connexion valable sur l'application desktop ET web.")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la création: {str(e)}")
'''
BLOCK_B = '''    def edit_user(self, user):
        """Modifier un utilisateur (profil propagé depuis Supabase Auth)."""
        from ui.views.admin_view import UserDialog
        dialog = UserDialog(self, mode="edit", user=user, style=self.style,
                           available_roles=self.available_roles,
                           roles_dict=self.roles_dict)
        if not dialog.exec():
            return

        user_data = dialog.get_user_data()
        new_email = (user_data.get("email") or "").strip().lower()

        if not new_email:
            QMessageBox.warning(
                self, "Email obligatoire",
                "L'email est obligatoire : c'est l'identifiant Supabase Auth.")
            return

        from core.supabase_auth import supabase_available, update_auth_profile

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "La modification des utilisateurs est rattachée exclusivement\\n"
                "à Supabase Auth.")
            return

        old_role = user.role
        old_email = user.email

        try:
            # Une seule écriture (Supabase Auth) : le trigger propage ensuite
            # username / rôle / email vers le profil public.users.
            ok, message = update_auth_profile(
                self.db_session, old_email,
                username=user_data["username"], role=user_data["role"],
                new_email=new_email if new_email != old_email else None)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Modification annulée.\\n\\n{message}")
                return
            self.db_session.commit()

            self.db_session.expire_all()
            self.load_users_from_db()

            self.user_updated.emit({
                "id": user.id,
                "username": user_data["username"],
                "email": new_email,
                "role": user_data["role"]
            })

            role_change = (f" (Rôle: {old_role} → {user_data['role']})"
                           if old_role != user_data["role"] else "")
            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Modification utilisateur",
                details=f"Modification de {user_data['username']}{role_change}"
            )

            self.filter_users()

            QMessageBox.information(
                self, "Succès",
                "Utilisateur modifié avec succès!\\n"
                "Profil synchronisé depuis Supabase Auth.")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la modification: {str(e)}")
'''

BLOCK_C = '''    def toggle_user_status(self, user):
        """Activer/désactiver un utilisateur (statut porté par Supabase Auth)."""
        action = "désactiver" if user.active else "activer"
        target_active = not bool(user.active)

        reply = QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir {action} l'utilisateur '{user.username}' ?\\n\\n"
            "Le statut est appliqué dans Supabase Auth : la connexion sera\\n"
            "refusée sur l'application desktop ET web (le mot de passe est conservé).",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        from core.supabase_auth import set_auth_active, supabase_available

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "Le statut des comptes est rattaché exclusivement à Supabase Auth.")
            return

        try:
            ok, message = set_auth_active(self.db_session, user.email, target_active)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Statut inchangé.\\n\\n{message}")
                return

            # Le trigger synchronise public.users.active : rien à écrire ici.
            self.db_session.commit()
            self.db_session.expire_all()
            self.load_users_from_db()

            status = "activé" if target_active else "désactivé"

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Changement statut utilisateur",
                details=f"{'Activation' if target_active else 'Désactivation'} de {user.username}"
            )

            self.filter_users()

            QMessageBox.information(self, "Succès", f"Utilisateur {status} avec succès!")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors du changement de statut: {str(e)}")
'''
BLOCK_D = '''    def reset_password(self, user):
        """Réinitialiser le mot de passe (Supabase Auth = source de vérité)."""
        reply = QMessageBox.question(
            self, "Réinitialisation du mot de passe",
            f"Générer un nouveau mot de passe temporaire pour '{user.username}' ?\\n"
            "L'utilisateur devra le changer à sa prochaine connexion.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        temp_password = self.generate_temp_password()

        from core.supabase_auth import supabase_available, update_auth_password

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "Les mots de passe sont gérés exclusivement par Supabase Auth.")
            return

        try:
            ok, message = update_auth_password(
                self.db_session, user.email, temp_password,
                must_change_password=True)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Mot de passe inchangé.\\n\\n{message}")
                return

            user.must_change_password = True
            self.db_session.commit()

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Réinitialisation mot de passe",
                details=f"Réinitialisation du mot de passe de {user.username}"
            )

            QMessageBox.information(
                self,
                "Mot de passe temporaire",
                f"Mot de passe temporaire pour {user.username}:\\n\\n"
                f"{temp_password}\\n\\n"
                "Copiez ce mot de passe et donnez-le à l'utilisateur.\\n"
                "Il devra le changer à sa prochaine connexion.\\n\\n"
                "Ce mot de passe est valable sur l'application desktop ET web."
            )

            self.password_reset.emit({
                "user_id": user.id,
                "username": user.username
            })

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la réinitialisation: {str(e)}")
'''

BLOCK_E = '''    def _save_new_password(self, dialog, user, new_password, confirm_password):
        """Sauvegarde le nouveau mot de passe dans Supabase Auth."""
        if not new_password or not confirm_password:
            QMessageBox.warning(dialog, "Erreur", "Veuillez remplir tous les champs.")
            return

        if new_password != confirm_password:
            QMessageBox.warning(dialog, "Erreur", "Les mots de passe ne correspondent pas.")
            return

        if len(new_password) < 6:
            QMessageBox.warning(dialog, "Erreur", "Le mot de passe doit contenir au moins 6 caractères.")
            return

        from core.supabase_auth import supabase_available, update_auth_password

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                dialog, "Supabase requis",
                "Les mots de passe sont gérés exclusivement par Supabase Auth.")
            return

        try:
            ok, message = update_auth_password(
                self.db_session, user.email, new_password,
                must_change_password=False)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(dialog, "Échec Supabase Auth",
                                     f"Mot de passe inchangé.\\n\\n{message}")
                return

            user.must_change_password = False
            self.db_session.commit()

            self.log_activity(
                user_id=self.get_current_user_id(),
                username=self.get_current_username(),
                action="Modification mot de passe",
                details=f"Modification du mot de passe de {user.username} par l'administrateur"
            )

            QMessageBox.information(
                dialog,
                "Succès",
                f"Mot de passe de {user.username} modifié avec succès!\\n"
                "Le nouveau mot de passe est actif sur l'application desktop ET web.")

            dialog.accept()

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(dialog, "Erreur", f"Erreur lors de la modification: {str(e)}")
'''
BLOCK_F = '''    def delete_user(self, user):
        """Supprimer un utilisateur (compte Supabase Auth, puis profil)."""
        current_username = self.get_current_username()
        current_user_id = self.get_current_user_id()

        if user.username == current_username:
            QMessageBox.warning(self, "Impossible", "Vous ne pouvez pas supprimer votre propre compte.")
            return

        if user.role == "ADMIN":
            admin_count = self.db_session.query(User).filter(User.role == "ADMIN").count()
            if admin_count <= 1:
                QMessageBox.warning(
                    self,
                    "Impossible",
                    "Impossible de supprimer le dernier administrateur.\\n"
                    "Créez un autre administrateur avant de supprimer celui-ci."
                )
                return

        reply = QMessageBox.question(
            self, "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer définitivement l'utilisateur '{user.username}' ?\\n"
            f"Rôle: {user.role}\\n"
            "Le compte Supabase Auth et son profil seront supprimés.\\n"
            "Cette action est irréversible.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        from core.supabase_auth import delete_auth_user, supabase_available

        if not supabase_available(self.db_session):
            QMessageBox.warning(
                self, "Supabase requis",
                "La suppression des utilisateurs est rattachée exclusivement\\n"
                "à Supabase Auth.")
            return

        user_id = user.id
        username = user.username
        user_role = user.role
        user_email = user.email

        try:
            self.log_activity(
                user_id=current_user_id,
                username=current_username,
                action="Suppression utilisateur",
                details=f"Suppression de {username} (ID: {user_id}, Rôle: {user_role})"
            )

            # 1) Supabase Auth : le trigger `on_auth_user_deleted` supprime le profil.
            ok, message = delete_auth_user(self.db_session, user_email)
            if not ok:
                self.db_session.rollback()
                QMessageBox.critical(self, "Échec Supabase Auth",
                                     f"Suppression annulée.\\n\\n{message}")
                return
            self.db_session.commit()

            # 2) Base sans trigger (déploiement non migré) : profil restant.
            self.db_session.expire_all()
            leftover = (self.db_session.query(User)
                        .filter(User.id == user_id).first())
            if leftover is not None:
                self.db_session.delete(leftover)
                self.db_session.commit()

            self.load_users_from_db()

            self.user_deleted.emit(user_id)

            self.filter_users()

            QMessageBox.information(
                self, "Succès",
                f"Utilisateur {username} ({user_role}) supprimé avec succès!\\n"
                "Compte Supabase Auth retiré (accès web et desktop supprimés).")

        except Exception as e:
            self.db_session.rollback()
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")
'''


def main():
    with io.open(TARGET, encoding="utf-8") as handle:
        content = handle.read()
    lines = content.split("\n")

    if "EXCLUSIVEMENT via Supabase Auth" in content:
        print("[INFO] admin_view.py est deja patché. Rien a faire.")
        return 0

    # (debut, fin) 1-based inclusifs -> bloc de remplacement.
    # Appliques du BAS vers le HAUT pour ne pas decaler les numeros de ligne.
    replacements = [
        (2167, 2168, None),   # hash_password : supprime
        (1979, 2042, BLOCK_F),
        (1923, 1968, BLOCK_E),
        (1823, 1877, BLOCK_D),
        (1777, 1821, BLOCK_C),
        (1726, 1775, BLOCK_B),
        (1663, 1724, BLOCK_A),
    ]

    for start, end, block in replacements:
        before = lines[start - 1][:70]
        lines[start - 1:end] = block.split("\n") if block else []
        print(f"  remplace lignes {start}-{end}  ({before!r})")

    with io.open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))

    print(f"[OK] {TARGET} mis a jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())