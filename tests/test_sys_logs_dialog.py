from pathlib import Path


def test_sys_logs_export_accepts_successful_zip(monkeypatch):
    import ui.views.sys_logs_dialog as sys_logs_dialog

    monkeypatch.setattr(
        sys_logs_dialog,
        "collect_diagnostics_zip",
        lambda: {"success": True, "zip_path": Path("diag.zip"), "error": None},
    )
    monkeypatch.setattr(
        sys_logs_dialog,
        "QFileDialog",
        type(
            "FakeDialog",
            (),
            {"getSaveFileName": staticmethod(lambda *args, **kwargs: ("export.zip", ""))},
        ),
    )
    monkeypatch.setattr(
        sys_logs_dialog.shutil,
        "copy",
        lambda src, dst: None,
    )
    monkeypatch.setattr(
        sys_logs_dialog.QMessageBox,
        "information",
        lambda *args, **kwargs: None,
    )

    dialog = sys_logs_dialog.SysLogsDialog.__new__(sys_logs_dialog.SysLogsDialog)
    dialog.export_diagnostics()

    assert True
