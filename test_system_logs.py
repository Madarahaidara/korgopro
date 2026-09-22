# test_system_logs.py
"""Tests du sous-système de récupération des logs système (core/system_logger.py)."""

import sys
import time

from core.system_logger import (
    setup_logging,
    get_logs_dir,
    get_main_log_file,
    get_log_files,
    get_system_info,
    read_logs,
    log_exception,
    collect_diagnostics_zip,
)


def test_logging_configured_and_file_created():
    """La configuration crée un dossier 'logs' et un fichier de log."""
    setup_logging(level=20, console=False)  # INFO
    logs_dir = get_logs_dir()
    assert logs_dir.is_dir(), "Le dossier des logs doit exister."
    # Écrire un message pour forcer la création du fichier
    logger = __import__("logging").getLogger("korgo_pro")
    logger.info("test_system_logs: écriture de vérification")


def test_read_logs_contains_message():
    """Le contenu des logs doit contenir nos messages."""
    setup_logging(level=20)
    logger = __import__("logging").getLogger("korgo_pro")
    marker = f"message_test_{int(time.time())}"
    logger.info(marker)
    content = read_logs()
    assert marker in content, "Le message journalisé doit être relisible."


def test_log_exception_writes_traceback():
    """Une exception journalisée via log_exception doit laisser une trace."""
    setup_logging(level=20)
    try:
        raise ValueError("erreur_de_test_system_log")
    except Exception:
        log_exception()
    content = read_logs()
    assert "ValueError" in content, "La trace de l'exception doit apparaître."
    assert "erreur_de_test_system_log" in content


def test_global_excepthook_installed():
    """Le hook global d'exception doit pointer vers notre handler après setup."""
    setup_logging()
    from core.system_logger import _excepthook
    assert sys.excepthook is _excepthook, "sys.excepthook doit être installé."


def test_get_system_info():
    """Les informations système doivent être collectées."""
    info = get_system_info()
    assert isinstance(info, dict)
    assert info.get("app_name") == "Korgo Pro"
    assert "python" in info
    assert "timestamp" in info


def test_get_log_files():
    """Au moins un fichier de log doit être présent après la configuration."""
    setup_logging()
    files = get_log_files()
    assert files, "Des fichiers de log doivent exister."


def test_collect_diagnostics_zip():
    """L'export du rapport de diagnostic doit créer un ZIP valide."""
    setup_logging()
    result = collect_diagnostics_zip()
    assert result["success"] is True, f"Échec: {result.get('error')}"
    zip_path = result["zip_path"]
    assert zip_path is not None and zip_path.exists()
    import zipfile
    with zipfile.ZipFile(str(zip_path)) as zf:
        names = zf.namelist()
        assert "system_info.json" in names, "Le ZIP doit contenir system_info.json"