# test_treasury.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.treasury_manager import TreasuryManager


def _make_manager():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return TreasuryManager(session=session), session


def test_create_account():
    m, _ = _make_manager()
    r = m.create_account("Caisse principale", "CASH", 1000)
    assert r["success"] is True
    assert r["account"].current_balance == 1000


def test_get_accounts():
    m, _ = _make_manager()
    m.create_account("Banque", "BANK", 500)
    m.create_account("Caisse", "CASH", 0)
    r = m.get_accounts()
    assert r["success"] is True
    assert len(r["accounts"]) == 2


def test_add_movement_updates_balance():
    m, _ = _make_manager()
    a = m.create_account("Caisse", "CASH", 1000)["account"]
    m.add_movement(a.id, "IN", 500, description="Vente")
    m.add_movement(a.id, "OUT", 200, description="Dépense")
    r = m.get_account(a.id)
    assert r["account"].current_balance == 1300


def test_get_movements():
    m, _ = _make_manager()
    a = m.create_account("Caisse", "CASH", 0)["account"]
    m.add_movement(a.id, "IN", 100)
    m.add_movement(a.id, "IN", 200)
    r = m.get_movements(account_id=a.id)
    assert r["success"] is True
    assert r["total"] == 2


def test_transfer():
    m, _ = _make_manager()
    a = m.create_account("Caisse", "CASH", 1000)["account"]
    b = m.create_account("Banque", "BANK", 0)["account"]
    r = m.transfer(a.id, b.id, 400)
    assert r["success"] is True
    assert m.get_account(a.id)["account"].current_balance == 600
    assert m.get_account(b.id)["account"].current_balance == 400


def test_total_balance():
    m, _ = _make_manager()
    m.create_account("Caisse", "CASH", 1000)
    m.create_account("Banque", "BANK", 500)
    r = m.get_total_balance()
    assert r["total"] == 1500


def test_cash_session_flow():
    m, _ = _make_manager()
    a = m.create_account("Caisse", "CASH", 1000)["account"]
    s = m.open_cash_session(a.id, 1, 1000)
    assert s["success"] is True
    m.add_movement(a.id, "IN", 500, description="Vente")
    c = m.close_cash_session(s["session"].id, 1500)
    assert c["success"] is True
    assert c["session"].status == "CLOSED"
    assert c["session"].total_in == 500


def test_treasury_summary():
    m, _ = _make_manager()
    a = m.create_account("Caisse", "CASH", 1000)["account"]
    m.add_movement(a.id, "IN", 500, description="Vente")
    r = m.get_treasury_summary()
    assert r["success"] is True
    assert r["total_in"] == 500
    assert r["current_balance"] == 1500