# core/treasury_manager.py
from core.database import SessionLocal
from core.models.treasury_models import (
    TreasuryAccount, TreasuryMovement, CashRegisterSession, MonthlyClosure,
)
from sqlalchemy import func
from datetime import datetime


class TreasuryManager:
    """Gestionnaire de tresorerie : comptes, mouvements, sessions de caisse."""

    def __init__(self, session=None):
        self._session = session

    def _get_db(self):
        return self._session if self._session else SessionLocal()

    def create_account(self, name, account_type="CASH", initial_balance=0.0,
                       currency="FCFA", bank_name=None, account_number=None,
                       phone_number=None, is_default=False, notes=None):
        db = self._get_db()
        try:
            account = TreasuryAccount(
                name=name, account_type=account_type, currency=currency,
                initial_balance=initial_balance, current_balance=initial_balance,
                bank_name=bank_name, account_number=account_number,
                phone_number=phone_number, is_default=is_default, notes=notes,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            return {"success": True, "account": account}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_accounts(self, active_only=True):
        db = self._get_db()
        try:
            query = db.query(TreasuryAccount)
            if active_only:
                query = query.filter(TreasuryAccount.is_active == True)
            accounts = query.order_by(
                TreasuryAccount.is_default.desc(), TreasuryAccount.name).all()
            return {"success": True, "accounts": accounts}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_account(self, account_id):
        db = self._get_db()
        try:
            account = db.query(TreasuryAccount).filter(
                TreasuryAccount.id == account_id).first()
            if not account:
                return {"success": False, "error": "Compte introuvable"}
            return {"success": True, "account": account}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def update_account(self, account_id, **kwargs):
        db = self._get_db()
        try:
            account = db.query(TreasuryAccount).filter(
                TreasuryAccount.id == account_id).first()
            if not account:
                return {"success": False, "error": "Compte introuvable"}
            for key, value in kwargs.items():
                if hasattr(account, key):
                    setattr(account, key, value)
            db.commit()
            return {"success": True, "account": account}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def delete_account(self, account_id):
        db = self._get_db()
        try:
            account = db.query(TreasuryAccount).filter(
                TreasuryAccount.id == account_id).first()
            if not account:
                return {"success": False, "error": "Compte introuvable"}
            account.is_active = False
            db.commit()
            return {"success": True}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def add_movement(self, account_id, movement_type, amount, date=None,
                     reference=None, description=None, category=None,
                     reference_type="MANUAL", reference_id=None, user_id=None):
        db = self._get_db()
        try:
            account = db.query(TreasuryAccount).filter(
                TreasuryAccount.id == account_id).first()
            if not account:
                return {"success": False, "error": "Compte introuvable"}
            if amount <= 0:
                return {"success": False, "error": "Le montant doit etre positif"}
            movement = TreasuryMovement(
                account_id=account_id, movement_type=movement_type, amount=amount,
                date=date or datetime.now(), reference=reference,
                description=description, category=category,
                reference_type=reference_type, reference_id=reference_id,
                user_id=user_id,
            )
            db.add(movement)
            if movement_type == "IN":
                account.current_balance += amount
            else:
                account.current_balance -= amount
            db.commit()
            db.refresh(movement)
            return {"success": True, "movement": movement}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_movements(self, account_id=None, movement_type=None,
                      start_date=None, end_date=None, limit=100, offset=0):
        db = self._get_db()
        try:
            query = db.query(TreasuryMovement)
            if account_id:
                query = query.filter(TreasuryMovement.account_id == account_id)
            if movement_type:
                query = query.filter(TreasuryMovement.movement_type == movement_type)
            if start_date:
                query = query.filter(TreasuryMovement.date >= start_date)
            if end_date:
                query = query.filter(TreasuryMovement.date <= end_date)
            total = query.count()
            movements = (query.order_by(TreasuryMovement.date.desc())
                         .offset(offset).limit(limit).all())
            return {"success": True, "movements": movements, "total": total}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_total_balance(self):
        db = self._get_db()
        try:
            result = db.query(func.sum(TreasuryAccount.current_balance)).filter(
                TreasuryAccount.is_active == True).scalar()
            return {"success": True, "total": result or 0.0}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def transfer(self, from_account_id, to_account_id, amount,
                 user_id=None, description=None):
        db = self._get_db()
        try:
            from_acc = db.query(TreasuryAccount).filter(
                TreasuryAccount.id == from_account_id).first()
            to_acc = db.query(TreasuryAccount).filter(
                TreasuryAccount.id == to_account_id).first()
            if not from_acc or not to_acc:
                return {"success": False, "error": "Compte introuvable"}
            if amount <= 0:
                return {"success": False, "error": "Montant invalide"}
            db.add(TreasuryMovement(
                account_id=from_account_id, movement_type="OUT", amount=amount,
                description="Transfert vers " + to_acc.name,
                category="Transfert", reference_type="TRANSFER", user_id=user_id,
            ))
            from_acc.current_balance -= amount
            db.add(TreasuryMovement(
                account_id=to_account_id, movement_type="IN", amount=amount,
                description="Transfert depuis " + from_acc.name,
                category="Transfert", reference_type="TRANSFER", user_id=user_id,
            ))
            to_acc.current_balance += amount
            db.commit()
            return {"success": True}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def open_cash_session(self, account_id, user_id, opening_amount=0.0, notes=None):
        db = self._get_db()
        try:
            existing = db.query(CashRegisterSession).filter(
                CashRegisterSession.account_id == account_id,
                CashRegisterSession.status == "OPEN").first()
            if existing:
                return {"success": False, "error": "Une session est deja ouverte sur ce compte"}
            session = CashRegisterSession(
                account_id=account_id, user_id=user_id,
                opening_amount=opening_amount, expected_amount=opening_amount,
                status="OPEN", notes=notes,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return {"success": True, "session": session}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def close_cash_session(self, session_id, closing_amount, notes=None):
        db = self._get_db()
        try:
            session = db.query(CashRegisterSession).filter(
                CashRegisterSession.id == session_id).first()
            if not session:
                return {"success": False, "error": "Session introuvable"}
            if session.status == "CLOSED":
                return {"success": False, "error": "Session deja fermee"}
            totals = db.query(
                TreasuryMovement.movement_type,
                func.sum(TreasuryMovement.amount)
            ).filter(
                TreasuryMovement.account_id == session.account_id,
                TreasuryMovement.date >= session.opened_at
            ).group_by(TreasuryMovement.movement_type).all()
            total_in = sum(amt for t, amt in totals if t == "IN")
            total_out = sum(amt for t, amt in totals if t == "OUT")
            expected = session.opening_amount + total_in - total_out
            difference = closing_amount - expected
            session.closing_amount = closing_amount
            session.expected_amount = expected
            session.total_in = total_in
            session.total_out = total_out
            session.difference = difference
            session.closed_at = datetime.now()
            session.status = "CLOSED"
            if notes:
                session.notes = (session.notes or "") + "\n" + notes
            db.commit()
            db.refresh(session)
            return {"success": True, "session": session}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_open_session(self, account_id):
        db = self._get_db()
        try:
            session = db.query(CashRegisterSession).filter(
                CashRegisterSession.account_id == account_id,
                CashRegisterSession.status == "OPEN").first()
            return {"success": True, "session": session}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_sessions(self, account_id=None, status=None, limit=50):
        db = self._get_db()
        try:
            query = db.query(CashRegisterSession)
            if account_id:
                query = query.filter(CashRegisterSession.account_id == account_id)
            if status:
                query = query.filter(CashRegisterSession.status == status)
            sessions = query.order_by(
                CashRegisterSession.opened_at.desc()).limit(limit).all()
            return {"success": True, "sessions": sessions}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    # ------------------------------------------------------------------
    # Clôtures mensuelles des ventes (même logique que web/src/api/treasuryApi.js)
    # ------------------------------------------------------------------

    def compute_month_summary(self, year, month):
        """Totaux du mois 'YYYY-MM' : ventes, encaissé, crédit, dépenses, net."""
        from core.models.sale_models import Sale
        db = self._get_db()
        try:
            start = datetime(year, month, 1)
            end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
            sales = db.query(Sale).filter(
                Sale.sale_date >= start, Sale.sale_date < end,
                Sale.sale_status != "CANCELLED",
                Sale.type_document != "AVOIR",
            ).all()
            total_sales = sum(s.total_amount or 0 for s in sales)
            collected = sum(max(0.0, (s.amount_paid or 0) - (s.change_amount or 0)) for s in sales)
            out = db.query(func.coalesce(func.sum(TreasuryMovement.amount), 0.0)).filter(
                TreasuryMovement.movement_type == "OUT",
                TreasuryMovement.reference_type != "SALE",
                TreasuryMovement.date >= start,
                TreasuryMovement.date < end,
            ).scalar() or 0.0
            return {
                "success": True, "period": f"{year:04d}-{month:02d}",
                "sales_count": len(sales), "total_sales": total_sales,
                "total_collected": collected, "total_credit": total_sales - collected,
                "total_out": float(out), "net": collected - float(out),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def close_month(self, year, month, user_id=None, notes=None):
        """Clôture une période : fige les totaux (refus si déjà clôturée)."""
        db = self._get_db()
        try:
            period = f"{year:04d}-{month:02d}"
            existing = db.query(MonthlyClosure).filter(
                MonthlyClosure.period == period).first()
            if existing and existing.status == "CLOSED":
                return {"success": False, "error": "Ce mois est déjà clôturé."}
            summary = self.compute_month_summary(year, month)
            if not summary.get("success"):
                return summary
            accounts = db.query(TreasuryAccount).filter(
                TreasuryAccount.is_active == True).all()
            balances = [
                {"id": a.id, "name": a.name, "account_type": a.account_type,
                 "balance": a.current_balance or 0}
                for a in accounts]
            import json as _json
            if not existing:
                existing = MonthlyClosure(period=period)
                db.add(existing)
            # Affectation via setattr (même pattern que update_account) :
            # évite le diagnostic Pylance sur les colonnes SQLAlchemy.
            for key, value in {
                "sales_count": summary["sales_count"],
                "total_sales": summary["total_sales"],
                "total_collected": summary["total_collected"],
                "total_credit": summary["total_credit"],
                "total_out": summary["total_out"],
                "net": summary["net"],
                "balances": _json.dumps(balances, ensure_ascii=False),
                "status": "CLOSED",
                "closed_by": user_id,
                "closed_at": datetime.now(),
                "notes": notes,
            }.items():
                setattr(existing, key, value)
            db.commit()
            db.refresh(existing)
            return {"success": True, "closure": existing}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_closures(self, limit=60):
        db = self._get_db()
        try:
            rows = db.query(MonthlyClosure).order_by(
                MonthlyClosure.period.desc()).limit(limit).all()
            return {"success": True, "closures": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_treasury_summary(self, start_date=None, end_date=None):
                db.close()

    def get_treasury_summary(self, start_date=None, end_date=None):
        db = self._get_db()
        try:
            if not start_date:
                start_date = datetime.now().replace(
                    day=1, hour=0, minute=0, second=0)
            if not end_date:
                end_date = datetime.now()
            totals = db.query(
                TreasuryMovement.movement_type,
                func.sum(TreasuryMovement.amount)
            ).filter(
                TreasuryMovement.date >= start_date,
                TreasuryMovement.date <= end_date
            ).group_by(TreasuryMovement.movement_type).all()
            total_in = sum(amt for t, amt in totals if t == "IN")
            total_out = sum(amt for t, amt in totals if t == "OUT")
            balance = db.query(func.sum(TreasuryAccount.current_balance)).filter(
                TreasuryAccount.is_active == True).scalar() or 0.0
            accounts = db.query(TreasuryAccount).filter(
                TreasuryAccount.is_active == True).all()
            account_balances = [
                {"name": a.name, "type": a.account_type, "balance": a.current_balance}
                for a in accounts]
            return {
                "success": True, "total_in": total_in, "total_out": total_out,
                "net": total_in - total_out, "current_balance": balance,
                "accounts": account_balances,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()
