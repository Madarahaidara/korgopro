# core/database_manager.py
import re
from sqlalchemy import inspect, text
from core.database import SessionLocal, engine
from core.models.user import User
from core.models.activity_log import ActivityLog
import logging
import json
import sqlite3
import tempfile
import uuid
import urllib.request, urllib.error
from datetime import datetime
import os

# Regex pour valider une requête SELECT uniquement (sécurité)
# Autorise: SELECT, WITH, EXPLAIN, PRAGMA (lecture seule)
_ALLOWED_SQL_PATTERN = re.compile(
    r'^\s*(SELECT|WITH|EXPLAIN\s+QUERY\s+PLAN|PRAGMA)\s',
    re.IGNORECASE
)

# Liste des mots-clés dangereux à bloquer même dans un SELECT
_FORBIDDEN_KEYWORDS = [
    'INTO OUTFILE', 'INTO DUMPFILE',
    'LOAD_FILE', 'INFORMATION_SCHEMA',
    'PRAGMA WRITEABLE_SCHEMA',
      
      'ATTACH DATABASE',
]


def _json_default(o):
    """Sérialise un datetime pour l'export portable JSON (dump/restore multi-dialecte)."""
    if isinstance(o, datetime):
        return {"__dt__": o.isoformat()}
    if hasattr(o, "isoformat"):
        return {"__dt__": o.isoformat()}
    if isinstance(o, bytes):
        return o.hex()
    raise TypeError(f"Objet non sérialisable: {type(o)!r}")


def _json_object_hook(d):
    """Décode un datetime préalablement sérialisé via _json_default."""
    if isinstance(d, dict) and "__dt__" in d:
        try:
            return datetime.fromisoformat(d["__dt__"])
        except ValueError:
            return d["__dt__"]
    return d


class DatabaseManager:
    """Gestionnaire de base de données pour l'administration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._inspector = None  # Cache : évite de re-réfléchir le schéma à chaque appel (coûteux en réseau)

    def get_database_info(self):
        """Obtenir des informations sur la base de données"""
        # Inspecteur mis en cache : la réflexion du schéma coûte plusieurs allers-retours
        # réseau sur PostgreSQL/Supabase — inutile de la refaire à chaque actualisation.
        if self._inspector is None:
            self._inspector = inspect(engine)
        inspector = self._inspector

        info = {
            "tables": {},
            "total_size": 0,
            "engine": str(engine.url.drivername),
            "database": str(engine.url.database)
        }

        # Taille de la base (PostgreSQL uniquement)
        if engine.url.drivername.startswith("postgresql"):
            try:
                with SessionLocal() as session:
                    size = session.execute(text("SELECT pg_database_size(current_database())")).scalar()
                    info["total_size"] = int(size or 0)
            except Exception:
                info["total_size"] = 0
        
        # Noms des tables (1 réflexion, mise en cache via l'inspecteur)
        table_names = inspector.get_table_names()

        # Comptage de TOUTES les tables en UNE SEULE requête : crucial en réseau
        # (Supabase) où 22 COUNT séparés = 22 allers-retours ≈ 20 s de gel.
        counts = {}
        if table_names:
            try:
                with SessionLocal() as session:
                    if engine.url.drivername.startswith("postgresql"):
                        # Exact et en un seul aller-retour : sous-requêtes COUNT(*)
                        select_parts = ", ".join(
                            f'(SELECT COUNT(*) FROM "{name}") AS c_{i}'
                            for i, name in enumerate(table_names)
                        )
                        row = session.execute(text(f"SELECT {select_parts}")).one()
                        counts = {name: int(row[i]) for i, name in enumerate(table_names)}
                    else:
                        for name in table_names:
                            try:
                                counts[name] = session.execute(
                                    text(f'SELECT COUNT(*) FROM "{name}"')
                                ).scalar() or 0
                            except Exception:
                                counts[name] = 0
            except Exception:
                counts = {}

        for table_name in table_names:
            info["tables"][table_name] = {
                "row_count": counts.get(table_name, 0)
            }

        return info

    def _count_table_rows(self, table_name: str, session) -> int:
        """Compte le nombre de lignes d'une table de manière sécurisée"""
        try:
            # Mapping table → modèle connu
            model_map = {
                "users": User,
                "activity_logs": ActivityLog,
                "customers": None,
                "products": None,
                "suppliers": None,
                "sales": None,
                "sale_items": None,
                "payments": None,
                "sale_returns": None,
                "sale_return_items": None,
                "inventory_movements": None,
                "expenses": None,
                "expense_categories": None,
                "purchase_orders": None,
                "purchase_order_items": None,
                "stock_alerts": None,
                "sale_logs": None,
            }
            
            model = model_map.get(table_name)
            if model is not None:
                return session.query(model).count()
            
            # Fallback sécurisé : utiliser text() avec nom de table validé
            # Le nom de table provient de l'inspecteur SQLAlchemy, donc sûr
            result = session.execute(text(f"SELECT COUNT(*) FROM \"{table_name}\""))
            return result.scalar() or 0
        except:
            return 0
    
    def backup_database(self, backup_path):
        """Sauvegarder la base de données"""
        try:
            # Obtenir le chemin de la base SQLite
            db_url = str(engine.url)
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
                
                import shutil
                
                # Créer le dossier de backup si nécessaire
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                
                # Copier le fichier
                shutil.copy2(db_path, backup_path)
                
                return {
                    "success": True,
                    "message": f"Base de données sauvegardée dans {backup_path}",
                    "path": backup_path,
                    "size": os.path.getsize(backup_path)
                }
            else:
                # PostgreSQL / Supabase : export logique portable (JSON)
                self._logical_export(backup_path)
                return {
                    "success": True,
                    "message": f"Base de données sauvegardée dans {backup_path}",
                    "path": backup_path,
                    "size": os.path.getsize(backup_path)
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors du backup: {str(e)}"
            }
    
    @staticmethod
    def _get_db_path():
        """Retourne le chemin du fichier SQLite ou None si ce n'est pas du SQLite."""
        db_url = str(engine.url)
        if db_url.startswith("sqlite:///"):
            return db_url.replace("sqlite:///", "")
        return None

    @staticmethod
    def _is_sqlite():
        """Vrai si le moteur actif est SQLite."""
        return str(engine.url).startswith("sqlite")

    def _logical_export(self, filepath):
        """
        Export portable (JSON) de toutes les tables.
        Compatible SQLite et PostgreSQL : réflète le schéma actif et sérialise
        les lignes. Utilisé pour les backups en base PostgreSQL / Supabase.
        """
        from sqlalchemy import MetaData

        metadata = MetaData()
        metadata.reflect(bind=engine)

        payload = {"tables": {}}
        with engine.connect() as conn:
            for table in metadata.sorted_tables:
                rows = [dict(row._mapping) for row in conn.execute(table.select())]
                payload["tables"][table.name] = rows

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=_json_default, indent=2)
        return filepath

    @staticmethod
    def _is_sqlite_file(path):
        """Vrai si le fichier est une base SQLite (d'après son en-tête magique)."""
        try:
            with open(path, "rb") as f:
                return f.read(16).startswith(b"SQLite format 3\x00")
        except OSError:
            return False

    @staticmethod
    def _payload_from_sqlite(sqlite_path):
        """Construit un payload {"tables": {...}} depuis une base SQLite locale."""
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            payload = {"tables": {}}
            for name in names:
                rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{name}"').fetchall()]
                payload["tables"][name] = rows
            return payload
        finally:
            conn.close()

    def _read_restore_payload(self, filepath):
        """
        Lit un backup et retourne un payload {"tables": {...}}.

        Supporte :
          - une base SQLite (.db) : permet de restaurer/migrer un backup SQLite
            vers PostgreSQL/Supabase (corrige l'ancienne erreur
            « 'utf-8' codec can't decode byte ... ») ;
          - un export JSON portable (cf. _logical_export), avec repli d'encodage
            (utf-8-sig / cp1252 / latin-1) pour les fichiers non UTF-8.
        """
        if self._is_sqlite_file(filepath):
            return self._payload_from_sqlite(filepath)

        with open(filepath, "rb") as f:
            raw = f.read()

        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                data = json.loads(raw.decode(encoding), object_hook=_json_object_hook)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                last_error = e
                continue
            if isinstance(data, dict) and "tables" in data:
                return data
            last_error = ValueError("Format JSON invalide : clé 'tables' absente")

        raise ValueError(
            f"Fichier de backup illisible (ni base SQLite ni JSON valide) : {last_error}"
        )

    def _logical_import(self, filepath):
        """
        Restaure un backup (export JSON portable ou base SQLite .db) dans la base active.

        Purge uniquement les tables présentes dans le backup puis réinsère les
        lignes. Les tables de la base active absentes du backup sont préservées.

        La vérification des FK est désactivée le temps de l'import
        (session_replication_role = replica sur PostgreSQL) car :
          - les contraintes créées par SQLAlchemy ne sont pas DEFERRABLE, donc
            SET CONSTRAINTS ALL DEFERRED n'a aucun effet ;
          - le schéma contient un cycle (proforma_invoices <-> sales) qui empêche
            un tri fiable des tables via SQLAlchemy.
        """
        from sqlalchemy import MetaData

        payload = self._read_restore_payload(filepath)
        backup_tables = payload.get("tables", {})

        metadata = MetaData()
        metadata.reflect(bind=engine)

        is_postgres = engine.dialect.name == "postgresql"

        with engine.begin() as conn:
            replica_disabled = False
            if is_postgres:
                try:
                    conn.execute(text("SET session_replication_role = replica"))
                    replica_disabled = True
                except Exception as e:
                    self.logger.warning(
                        "Désactivation des FK impossible (session_replication_role): %s", e
                    )

            try:
                # 1) Purge ciblée : uniquement les tables du backup (préserve les
                #    tables hors périmètre, ex. treasury_* / stores).
                for table in reversed(metadata.sorted_tables):
                    if table.name not in backup_tables:
                        continue
                    if is_postgres:
                        conn.execute(text(f'DELETE FROM "{table.name}"'))
                    else:
                        conn.execute(table.delete())

                # 2) Insertion des lignes (l'ordre importe peu : FK désactivées)
                for table in metadata.sorted_tables:
                    rows = backup_tables.get(table.name, [])
                    if not rows:
                        continue
                    col_names = {c.name for c in table.columns}
                    clean = [{k: v for k, v in r.items() if k in col_names} for r in rows]
                    if clean:
                        conn.execute(table.insert(), clean)

                # 3) Réalignement des séquences PostgreSQL sur max(id) : évite les
                #    conflits de clé primaire lors du prochain INSERT applicatif.
                if is_postgres:
                    for table in metadata.sorted_tables:
                        if table.name not in backup_tables or "id" not in table.columns:
                            continue
                        try:
                            seq = conn.execute(
                                text("SELECT pg_get_serial_sequence(:t, 'id')"),
                                {"t": table.name},
                            ).scalar()
                            if not seq:
                                continue
                            max_id = conn.execute(
                                text(f'SELECT MAX(id) FROM "{table.name}"')
                            ).scalar()
                            if max_id is not None:
                                conn.execute(
                                    text("SELECT setval(:s, :v)"),
                                    {"s": seq, "v": int(max_id)},
                                )
                        except Exception as e:
                            self.logger.warning(
                                "Réalignement séquence échoué pour %s: %s", table.name, e
                            )
            finally:
                if replica_disabled:
                    conn.execute(text("SET session_replication_role = default"))

        return filepath

    @staticmethod
    def _build_multipart_body(file_path, filename, content=""):
        """
        Construit le corps multipart/form-data pour l'envoi sur un webhook Discord.

        Discord attend :
          - le champ texte "content" (message)
          - le champ fichier "files[0]"
        """
        boundary = uuid.uuid4().hex
        line_break = "\r\n"
        buf = bytearray()

        def add_field(name, value):
            buf.extend(f"--{boundary}{line_break}".encode("utf-8"))
            buf.extend(f'Content-Disposition: form-data; name="{name}"{line_break}{line_break}'.encode("utf-8"))
            buf.extend(str(value).encode("utf-8"))
            buf.extend(line_break.encode("utf-8"))

        def add_file():
            buf.extend(f"--{boundary}{line_break}".encode("utf-8"))
            buf.extend(
                f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"{line_break}'.encode("utf-8")
            )
            buf.extend(b"Content-Type: application/octet-stream" + line_break.encode("utf-8"))
            buf.extend(line_break.encode("utf-8"))
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    buf.extend(chunk)
            buf.extend(line_break.encode("utf-8"))

        if content:
            add_field("content", content)

        add_file()
        buf.extend(f"--{boundary}--{line_break}".encode("utf-8"))
        return bytes(buf), boundary

    def backup_to_discord(self, webhook_url, content=None):
        """
        Créer un backup de la base de données et l'envoyer sur un serveur Discord (webhook).

        Args:
            webhook_url: URL du webhook Discord (https://discord.com/api/webhooks/...)
            content: message texte optionnel envoyé avec le fichier

        Returns:
            dict: {"success": bool, "message": str, "size": int, "filename": str}
        """
        if not webhook_url or not str(webhook_url).strip().lower().startswith("http"):
            return {"success": False, "message": "URL de webhook Discord invalide"}

        tmp_path = None
        try:
            if self._is_sqlite():
                db_path = self._get_db_path()
                if db_path is None or not os.path.exists(db_path):
                    return {"success": False, "message": "Fichier de base de données introuvable"}

                # Copie cohérente du fichier SQLite (même s'il est ouvert)
                fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="korgo_backup_")
                os.close(fd)

                src = sqlite3.connect(db_path)
                try:
                    dst = sqlite3.connect(tmp_path)
                    with dst:
                        src.backup(dst)
                finally:
                    src.close()
                suffix = ".db"
            else:
                # PostgreSQL / Supabase : export logique portable (JSON)
                fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="korgo_backup_")
                os.close(fd)
                self._logical_export(tmp_path)
                suffix = ".json"

            size = os.path.getsize(tmp_path)
            filename = f"korgo_pro_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"

            message = content or (
                f"🗄️ **Backup base de données KORGO PRO**\n"
                f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"📁 `{filename}`\n"
                f"⚖️ Taille : {size / 1024:.2f} Ko"
            )

            body, boundary = self._build_multipart_body(tmp_path, filename, message)
            content_type = f"multipart/form-data; boundary={boundary}"

            req = urllib.request.Request(
                webhook_url,
                data=body,
                headers={
                    "Content-Type": content_type,
                    "User-Agent": "KorgoPro-Backup/1.0",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    # Un webhook Discord répond 204 No Content (ou 200) en cas de succès
                    _ = resp.read()
            except urllib.error.HTTPError as e:
                details = e.read().decode("utf-8", errors="replace")
                return {
                    "success": False,
                    "message": f"Erreur Discord (HTTP {e.code}): {details[:200]}",
                }
            except urllib.error.URLError as e:
                return {"success": False, "message": f"Erreur réseau: {str(e.reason)}"}

            return {
                "success": True,
                "message": "Backup envoyé sur Discord avec succès",
                "size": size,
                "filename": filename,
            }
        except Exception as e:
            return {"success": False, "message": f"Erreur lors du backup Discord: {str(e)}"}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def restore_database(self, backup_path):
        """Restaurer la base de données depuis un backup (.db SQLite ou export JSON)"""
        try:
            if not os.path.exists(backup_path):
                return {
                    "success": False,
                    "message": "Fichier de backup introuvable"
                }

            if self._is_sqlite() and self._is_sqlite_file(backup_path):
                db_path = self._get_db_path()

                import shutil

                # Restaurer
                shutil.copy2(backup_path, db_path)
                
                return {
                    "success": True,
                    "message": f"Base de données restaurée depuis {backup_path}"
                }
            else:
                # PostgreSQL / Supabase (ou backup JSON) : import logique.
                # Accepte aussi bien un export JSON qu'un fichier SQLite .db.
                self._logical_import(backup_path)
                return {
                    "success": True,
                    "message": f"Base de données restaurée depuis {backup_path}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de la restauration: {str(e)}"
            }
    
    def vacuum_database(self):
        """Optimiser la base de données"""
        try:
            with SessionLocal() as session:
                session.execute(text("VACUUM"))
                session.commit()
            return {
                "success": True,
                "message": "Base de données optimisée avec succès"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de l'optimisation: {str(e)}"
            }
    
    def get_table_data(self, table_name, limit=100, offset=0):
        """Récupérer les données d'une table (sécurisé)"""
        try:
            with SessionLocal() as session:
                # Validation stricte : seulement les tables connues et autorisées
                allowed_tables = {
                    "users": User,
                    "activity_logs": ActivityLog,
                }
                
                if table_name not in allowed_tables:
                    return {"success": False, "message": "Table non supportée"}
                
                model = allowed_tables[table_name]
                
                # Récupérer les données
                query = session.query(model)
                total = query.count()
                data = query.offset(offset).limit(limit).all()
                
                # Convertir en dictionnaire
                rows = []
                for row in data:
                    row_dict = {}
                    for column in model.__table__.columns:
                        value = getattr(row, column.name)
                        if isinstance(value, datetime):
                            value = value.strftime("%Y-%m-%d %H:%M:%S")
                        row_dict[column.name] = value
                    rows.append(row_dict)
                
                return {
                    "success": True,
                    "data": rows,
                    "total": total,
                    "limit": limit,
                    "offset": offset
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur: {str(e)}"
            }
    
    def execute_sql(self, sql_query):
        """
        Exécuter une requête SQL SELECT en lecture seule (sécurisé).
        Les requêtes non-SELECT sont rejetées. Utilise une whitelist.
        """
        if not sql_query or not sql_query.strip():
            return {
                "success": False,
                "message": "Requête vide"
            }
        
        sql_stripped = sql_query.strip()
        
        # Vérifier que la requête commence par SELECT, WITH, EXPLAIN ou PRAGMA (lecture seule)
        if not _ALLOWED_SQL_PATTERN.match(sql_stripped):
            return {
                "success": False,
                "message": "Seules les requêtes SELECT (lecture seule) sont autorisées."
            }
        
        # Vérifier les mots-clés dangereux même dans un SELECT
        sql_upper = sql_stripped.upper()
        for keyword in _FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                return {
                    "success": False,
                    "message": f"Mot-clé interdit détecté: {keyword}"
                }
        
        try:
            with SessionLocal() as session:
                result = session.execute(text(sql_stripped))
                rows = result.fetchall()
                columns = result.keys()
                
                data = []
                for row in rows:
                    row_dict = {}
                    for col_name, value in zip(columns, row):
                        # Convertir les types non-sérialisables
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        elif isinstance(value, bytes):
                            value = value.hex()
                        row_dict[col_name] = value
                    data.append(row_dict)
                
                return {
                    "success": True,
                    "data": data,
                    "row_count": len(data),
                    "columns": list(columns)
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur SQL: {str(e)}"
            }