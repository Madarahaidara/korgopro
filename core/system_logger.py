# core/system_logger.py
"""
Sous-système de journalisation centralisé de Korgo Pro.

Objectif : récupérer les logs système (application + système) en cas de bug,
même dans les builds PyInstaller compilés avec ``console=False`` (où les
``print()`` sont perdus).

Il fournit :
    - une configuration ``logging`` écrivant dans un fichier à rotation ;
    - un ``sys.excepthook`` global qui capture toute exception non gérée ;
    - un gestionnaire de messages Qt (``qInstallMessageHandler``) ;
    - une collecte d'informations système (OS, versions, environnement) ;
    - un export de "rapport de diagnostic" (ZIP) prêt à envoyer au support.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import platform
import shutil
import socket
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# Niveau de log par défaut (INFO en mode normal, DEBUG si activé).
DEFAULT_LOG_LEVEL = logging.INFO

# Taille maximale d'un fichier de log avant rotation (2 Mo).
MAX_BYTES = 2 * 1024 * 1024
# Nombre de fichiers de rotation conservés.
BACKUP_COUNT = 5

logger = logging.getLogger("korgo_pro")


# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
def get_base_dir() -> Path:
    """Retourne le dossier de base de l'application.

    En exécutable PyInstaller (frozen), on utilise le dossier de
    l'exécutable ; sinon la racine du projet (dossier parent de ``core``).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_logs_dir() -> Path:
    """Retourne le dossier où sont écrits les fichiers de log (créé au besoin)."""
    logs_dir = get_base_dir() / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Si le dossier n'est pas accessible, repli dans le répertoire temporaire.
        import tempfile
        logs_dir = Path(tempfile.gettempdir()) / "korgo_pro_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_main_log_file() -> Path:
    """Retourne le chemin du fichier de log principal."""
    return get_logs_dir() / "korgo_pro.log"


def get_log_files() -> list:
    """Retourne la liste des fichiers de log disponibles (triés par date)."""
    logs_dir = get_logs_dir()
    patterns = ("korgo_pro.log", "korgo_pro.log.*", "crash_*.log")
    files: list = []
    for pattern in patterns:
        try:
            files.extend(logs_dir.glob(pattern))
        except OSError:
            continue
    files = sorted(set(files), key=lambda p: p.stat().st_mtime, reverse=True)
    return files


# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
def _create_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_logging(level: int = DEFAULT_LOG_LEVEL, console: bool = True) -> logging.Logger:
    """Configure la journalisation fichier + console et installe les hooks.

    Appelée une fois au démarrage de l'application (voir ``main.py``).

    Args:
        level: Niveau de log global.
        console: Si True, ajoute un handler vers la sortie standard (utile
            en développement ; inoffensif en build windowed).

    Returns:
        Le logger racine de Korgo Pro.
    """
    if getattr(setup_logging, "_configured", False):
        return logger
    setup_logging._configured = True

    logger.setLevel(level)

    # Éviter les doublons si le module est réimporté.
    logger.handlers.clear()

    # --- Handler fichier avec rotation ---
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            get_main_log_file(),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(_create_formatter())
        logger.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover - dépend de l'environnement
        print(f"[system_logger] Impossible de créer le fichier de log : {exc}")

    # --- Handler console ---
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(_create_formatter())
        logger.addHandler(console_handler)

    # --- Hooks globaux pour la capture des crashs ---
    try:
        _install_excepthook()
    except Exception as exc:  # pragma: no cover
        logger.warning("Impossible d'installer le hook d'exception : %s", exc)
    try:
        _install_qt_message_handler()
    except Exception as exc:  # pragma: no cover
        logger.warning("Impossible d'installer le gestionnaire Qt : %s", exc)

    logger.info("Journalisation démarrée (niveau=%s).", logging.getLevelName(level))
    return logger


# ---------------------------------------------------------------------------
# Excepthook global (exceptions non gérées)
# ---------------------------------------------------------------------------
_ORIGINAL_EXCEPTHOOK = sys.excepthook


def _exc_info_tuple(exc: Optional[BaseException]):
    """Retourne un tuple (type, value, traceback) exploitable.

    Préfère l'exception en cours de ``sys.exc_info()`` ; sinon celles
    fournies explicitement.
    """
    exc_type, exc_value, exc_tb = sys.exc_info()
    if exc_type is None and exc_value is None and exc_tb is None and exc is not None:
        return type(exc), exc, exc.__traceback__
    return exc_type, exc_value, exc_tb


def log_exception(exc: Optional[BaseException] = None) -> str:
    """Journalise l'exception courante avec sa trace complète et la retourne.

    Utilisable dans les blocs ``except Exception`` en remplacement de
    ``print`` / ``traceback.print_exc()`` pour garantir l'écriture fichier.
    """
    exc_type, exc_value, exc_tb = _exc_info_tuple(exc)
    trace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error("Exception capturée :\n%s", trace)
    return trace


def _write_crash_file(etype, value, tb) -> Optional[Path]:
    """Écrit un rapport de crash dédié dans le dossier des logs."""
    trace = "".join(traceback.format_exception(etype, value, tb))
    try:
        crash_file = get_logs_dir() / f"crash_{datetime.now():%Y%m%d_%H%M%S}.log"
        header = (
            f"Korgo Pro - Rapport de crash\n"
            f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"{'-' * 60}\n"
        )
        crash_file.write_text(header + trace, encoding="utf-8")
        return crash_file
    except OSError:
        return None


def _show_crash_dialog(message: str) -> None:
    """Affiche une boîte de dialogue de crash si un QApplication existe."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is None:
            return
        QMessageBox.critical(
            None,
            "Erreur inattendue",
            "Une erreur inattendue est survenue.\n\n"
            "Les détails ont été enregistrés dans le dossier 'logs' de "
            "l'application. Utilisez le bouton 'Journal' (en-tête) pour "
            "consulter ou exporter ces logs.\n\n"
            f"{message}",
        )
    except Exception:
        # Ne jamais faire échouer le handler d'exception.
        pass


def _excepthook(etype, value, tb) -> None:
    """Hook global : capture toute exception non gérée (thread principal)."""
    trace = "".join(traceback.format_exception(etype, value, tb))
    logger.critical("Exception non gérée :\n%s", trace)
    _write_crash_file(etype, value, tb)
    _show_crash_dialog(f"{etype.__name__}: {value}")
    # Conserver le comportement d'origine (affichage dans la console).
    if _ORIGINAL_EXCEPTHOOK is not None and _ORIGINAL_EXCEPTHOOK is not _excepthook:
        try:
            _ORIGINAL_EXCEPTHOOK(etype, value, tb)
        except Exception:
            pass


def _install_excepthook() -> None:
    """Installe le hook global d'exception (idempotent)."""
    if sys.excepthook is not _excepthook:
        sys.excepthook = _excepthook


# ---------------------------------------------------------------------------
# Gestionnaire de messages Qt (qInstallMessageHandler)
# ---------------------------------------------------------------------------
_QT_LEVEL_MAP = {
    0: logging.DEBUG,     # QtDebugMsg
    1: logging.WARNING,   # QtWarningMsg
    2: logging.ERROR,     # QtCriticalMsg
    3: logging.CRITICAL,  # QtFatalMsg
    4: logging.INFO,      # QtInfoMsg
}

# Messages Qt connus, bénins et hautement répétitifs -> ignorés du journal.
# (ex : l'animation du splash screen déclenche « setting window opacity »
# pendant toute sa durée, ce qui inondait le fichier de log.)
_QT_IGNORED_MSG_MARKERS = {
    "does not support setting window opacity",
    "no longer ships fonts",
    "Cannot find font directory",
}

# Fenêtre de dédoublement des messages répétitifs (en secondes。
_QT_DEDUP_WINDOW_SECONDS = 5.0


def _qt_message_handler(msg_type, context, msg) -> None:
    """Redirige les messages Qt vers le logging, avec dédoublement.

    Les messages identiques répétés sur une courte fenêtre ne sont journalisés
    qu'une seule fois (avec un compteur) pour éviter d'inonder le journal.
"""
    level = _QT_LEVEL_MAP.get(int(msg_type), logging.DEBUG)
    module = getattr(context, "file", None) or ""
    text = msg if isinstance(msg, str) else str(msg)

    # Ignorer les messages connus bénins.

    ignored = any(marker in text for marker in _QT_IGNORED_MSG_MARKERS)
    if ignored:
        return

    # Dédoublement des messages répétitifs (sauf les vrais ERREURS qui
    # doivent toujours être journalisés intégralement).
    if level < logging.ERROR:
        now = _monotonic()
        last = getattr(_qt_message_handler, "_last_qt", None)
        if last is not None and last[0] == text and now - last[1] < _QT_DEDUP_WINDOW_SECONDS:
            _qt_message_handler._repeat_count = getattr(
                _qt_message_handler, "_repeat_count", 0
            ) + 1
            return
        _qt_message_handler._last_qt = (text, now)
        repeat = getattr(_qt_message_handler, "_repeat_count", 0)
        if repeat:
            logger.log(level, "[Qt%s] %s (%dx répétitions ignorées)", f"/{module}" if module else "", text, repeat)
            _qt_message_handler._repeat_count = 0
        else:
            logger.log(level, "[Qt%s] %s", f"/{module}" if module else "", text)
    else:
        logger.log(level, "[Qt%s] %s", f"/{module}" if module else "", text)


def _monotonic() -> float:
    """Petit helper monotone compatible (le module time est chargé paresseusement."""
    import time
    return time.monotonic()


def _install_qt_message_handler() -> None:
    """Installe le handler de messages Qt (idempotent)."""
    from PySide6.QtCore import qInstallMessageHandler
    qInstallMessageHandler(_qt_message_handler)
# ---------------------------------------------------------------------------
# Informations système
# ---------------------------------------------------------------------------
def _get_version() -> str:
    """Retourne la version de l'application depuis version_info.txt si possible."""
    try:
        version_file = get_base_dir() / "version_info.txt"
        if version_file.exists():
            import re
            content = version_file.read_text(encoding="utf-8")
            m = re.search(r"filevers=\(\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)", content)
            if m:
                return ".".join(m.groups())
    except Exception:
        pass
    return "0.1.0"


def get_system_info() -> dict:
    """Collecte les informations système et applicatives (aide au diagnostic.)"""
    info = {
        "timestamp": datetime.now().isoformat(),
        "app_name": "Korgo Pro",
        "app_version": _get_version(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "base_dir": str(get_base_dir()),
        "logs_dir": str(get_logs_dir()),
    }
    # Versions des librairies clés (si disponibles.
    for lib in ("PySide6", "SQLAlchemy", "pandas", "openpyxl"):
        try:
            mod = __import__(lib)
            info[f"{lib.lower()}_version"] = getattr(mod, "__version__", "inconnue")
        except ImportError:
            info[f"{lib.lower()}_version"] = "non installée"
    # Informations sur la base de données (hors données sensibles).
    info["db_files"] = {}
    for name in ("korgo_pro.db", "base.db"):
        db_path = get_base_dir() / name
        if db_path.exists():
            try:
                info["db_files"][name] = {
                    "size_bytes": db_path.stat().st_size,
                    "modified": datetime.fromtimestamp(db_path.stat().st_mtime).isoformat(),
                }
                if name == "korgo_pro.db":
                    import sqlite3
                    con = sqlite3.connect(str(db_path))
                    info["db_files"][name]["sqlite_version"] = sqlite3.sqlite_version
                    con.close()
            except Exception as exc:
                info["db_files"][name] = {"error": str(exc)}
    return info


# ---------------------------------------------------------------------------
# Lecture / export des logs
# ---------------------------------------------------------------------------
def read_logs(max_bytes: int = 200_000) -> str:
    """Lit le contenu récent du fichier de log principal.


    Args:
        max_bytes: Nombre maximal de caractères à lire (depuis la fin).

    Returns:
        Le texte des logs (vide si le fichier n'existe pas).
    """
    log_file = get_main_log_file()
    if not log_file.exists():
        return "Aucun log disponible pour le moment."
    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Impossible de lire les logs : {exc}"
    if len(text) > max_bytes:
        text = "... (début tronqué) ...\n" + text[-max_bytes:]
    return text


def collect_diagnostics_zip(dest_dir: Optional[os.PathLike] = None) -> dict:
    """Crée un rapport de diagnostic (ZIP) destiné au support.


    Contenu :
        - tous les fichiers de log applicatifs ;
        - les informations système (JSON) ;
        - les réglages de l'entreprise (configuration non sensible en lecture.


    Args:
        dest_dir: Dossier où écrire le ZIP (défaut : le dossier ``logs``).

    Returns:
        Un dictionnaire : ``{"success": bool, "zip_path": Path|None, "error": str|None}``.

    """
    try:
        logs_dir = get_logs_dir()
        dest = Path(dest_dir) if dest_dir else logs_dir
        dest.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = dest / f"korgo_pro_diagnostic_{timestamp}.zip"

        import zipfile
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Fichiers de log
            for f in get_log_files():
                try:
                    zf.write(f, arcname=f"logs/{f.name}")
                except OSError:
                    continue
            # Informations système
            info = get_system_info()
            zf.writestr(
                "system_info.json",
                json.dumps(info, ensure_ascii=False, indent=2),
            )
            # Réglages entreprise (si présent)
            settings_file = get_base_dir() / "company_settings.json"
            if settings_file.exists():
                zf.write(settings_file, arcname="config/company_settings.json")

        logger.info("Rapport de diagnostic créé : %s", zip_path)
        return {"success": True, "zip_path": zip_path, "error": None}
    except Exception as exc:
        logger.error("Échec de l'export des diagnostics : %s", exc)
        return {"success": False, "zip_path": None, "error": str(exc)}