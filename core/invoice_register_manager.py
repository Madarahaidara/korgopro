# core/invoice_register_manager.py
from core.database import SessionLocal
from core.models.sale_models import Sale
from core.models.customer import Customer
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from core.treasury_manager import TreasuryManager


class InvoiceRegisterManager:
    """Registre des factures définitives (ventes) par client avec suivi du solde dû."""

    def __init__(self, session=None, treasury=None):
        self._session = session
        self._treasury = treasury or TreasuryManager(session=session)

    def _get_db(self):
        return self._session if self._session else SessionLocal()

    def list_invoices(self, customer_id=None, status=None, search=None,
                      date_from=None, date_to=None, limit=1000):
        db = self._get_db()
        try:
            query = db.query(Sale).options(joinedload(Sale.customer)).outerjoin(Customer)
            if customer_id:
                query = query.filter(Sale.customer_id == customer_id)
            if status and status != "ALL":
                if status == "PAID":
                    query = query.filter(Sale.payment_status == "PAID")
                elif status == "PARTIAL":
                    query = query.filter(Sale.payment_status == "PARTIAL")
                else:
                    query = query.filter(Sale.payment_status == "PENDING")
            if search:
                like = f"%{search}%"
                query = query.filter(
                    (Sale.sale_number.ilike(like)) |
                    (Customer.first_name.ilike(like)) |
                    (Customer.last_name.ilike(like)) |
                    (Customer.company.ilike(like))
                )
            if date_from:
                query = query.filter(Sale.sale_date >= date_from)
            if date_to:
                query = query.filter(Sale.sale_date <= date_to)
            invoices = query.order_by(Sale.sale_date.desc()).limit(limit).all()
            return {"success": True, "invoices": invoices}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_invoice_details(self, sale_id):
        """Détail complet d'une facture : entête, lignes, client, paiements."""
        db = self._get_db()
        try:
            sale = db.query(Sale).filter(Sale.id == sale_id).first()
            if not sale:
                return {"success": False, "error": "Facture introuvable"}
            items = [
                {
                    "product": it.product.name if it.product else "?",
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "total": it.quantity * it.unit_price,
                }
                for it in sale.items
            ]
            due = (sale.total_amount or 0) - (sale.amount_paid or 0)
            return {
                "success": True,
                "invoice": sale,
                "customer": sale.customer,
                "items": items,
                "total": sale.total_amount or 0,
                "paid": sale.amount_paid or 0,
                "due": max(due, 0),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_register_summary(self, date_from=None, date_to=None):
        """Totaux du registre : nombre de factures, montant total, encaissé, reste dû."""
        db = self._get_db()
        try:
            query = db.query(
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.total_amount), 0.0),
                func.coalesce(func.sum(Sale.amount_paid), 0.0),
            ).filter(Sale.sale_status == "COMPLETED")
            if date_from:
                query = query.filter(Sale.sale_date >= date_from)
            if date_to:
                query = query.filter(Sale.sale_date <= date_to)
            count, total, paid = query.one()
            by_status = db.query(
                Sale.payment_status, func.count(Sale.id)
            ).filter(Sale.sale_status == "COMPLETED")
            if date_from:
                by_status = by_status.filter(Sale.sale_date >= date_from)
            if date_to:
                by_status = by_status.filter(Sale.sale_date <= date_to)
            by_status = dict(by_status.group_by(Sale.payment_status).all())
            return {
                "success": True,
                "count": count or 0,
                "total": total or 0.0,
                "paid": paid or 0.0,
                "due": (total or 0.0) - (paid or 0.0),
                "by_status": by_status,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def receive_payment(self, sale_id, amount, account_id=None,
                        payment_method="CASH", user_id=None, notes=None):
        """Encaisser un paiement sur une facture et alimenter la trésorerie."""
        if amount <= 0:
            return {"success": False, "error": "Le montant doit être positif"}
        db = self._get_db()
        own = not self._session
        try:
            sale = db.query(Sale).filter(Sale.id == sale_id).first()
            if not sale:
                return {"success": False, "error": "Facture introuvable"}
            due = (sale.total_amount or 0) - (sale.amount_paid or 0)
            if amount > due + 0.001:
                return {"success": False,
                        "error": "Montant supérieur au reste dû (%.2f)" % due}
            sale.amount_paid = (sale.amount_paid or 0) + amount
            if sale.amount_paid >= (sale.total_amount or 0) - 0.001:
                sale.payment_status = "PAID"
                sale.statut = "PAYEE"
            else:
                sale.payment_status = "PARTIAL"
                sale.statut = "PARTIELLEMENT_PAYEE"
            # Le client doit moins : on diminue son solde dû du montant encaissé
            # (même convention que les RPC `app_register_payment` du mobile et
            # de `receivePayment` du web ; sans cela la dette restait à vie).
            if sale.customer_id:
                customer = db.query(Customer).filter(
                    Customer.id == sale.customer_id).first()
                if customer:
                    customer.balance = max(
                        (customer.balance or 0) - amount, 0)
            treasury_result = None
            if account_id:
                treasury_result = self._treasury.add_movement(
                    account_id=account_id, movement_type="IN", amount=amount,
                    reference=sale.sale_number,
                    description="Encaissement facture " + str(sale.sale_number)
                                + ((" — " + notes) if notes else ""),
                    category="Ventes", reference_type="SALE",
                    reference_id=sale.id, user_id=user_id,
                )
                if not treasury_result.get("success"):
                    db.rollback()
                    return {"success": False,
                            "error": "Erreur trésorerie : "
                                     + str(treasury_result.get("error"))}
            db.commit()
            db.refresh(sale)
            return {"success": True, "sale": sale, "treasury": treasury_result}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if own:
                db.close()

    def get_customer_balance(self, customer_id):
        """Solde dû total d'un client (toutes ses factures)."""
        db = self._get_db()
        try:
            row = db.query(
                func.coalesce(func.sum(Sale.total_amount), 0.0),
                func.coalesce(func.sum(Sale.amount_paid), 0.0),
                func.count(Sale.id),
            ).filter(
                Sale.customer_id == customer_id,
                Sale.sale_status == "COMPLETED",
            ).one()
            total, paid, count = row
            return {
                "success": True,
                "customer_id": customer_id,
                "invoices": count or 0,
                "total": total or 0.0,
                "paid": paid or 0.0,
                "due": (total or 0.0) - (paid or 0.0),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

    def get_unpaid_invoices(self, customer_id=None):
        """Liste des factures impayées ou partiellement payées."""
        db = self._get_db()
        try:
            query = db.query(Sale).options(joinedload(Sale.customer)).filter(
                Sale.sale_status == "COMPLETED",
                Sale.payment_status.in_(["PENDING", "PARTIAL"]),
            )
            if customer_id:
                query = query.filter(Sale.customer_id == customer_id)
            invoices = query.order_by(Sale.sale_date.desc()).all()
            return {"success": True, "invoices": invoices}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not self._session:
                db.close()

