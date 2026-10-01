import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload

from core.models.stock_models import Product, Supplier
from core.models.sale_models import Sale, SaleItem, Customer, Payment
from core.models.treasury_models import TreasuryAccount, TreasuryMovement
from core.treasury_manager import TreasuryManager
from core.sale_log_manager import SaleLogManager
# Multi-magasins : filtrage du catalogue + rattachement des ventes
from core.store_manager import apply_store_scope, current_store_id_for, scope_products_query

logger = logging.getLogger(__name__)


def default_cash_account(db_session):
    """Compte de trésorerie par defaut pour les encaissements de ventes.

    Priorite : premier compte actif de type CASH, sinon premier compte actif.
    """
    acc = (db_session.query(TreasuryAccount)
           .filter(TreasuryAccount.is_active == True,  # noqa: E712
                   TreasuryAccount.account_type == 'CASH')
           .order_by(TreasuryAccount.id).first())
    if not acc:
        acc = (db_session.query(TreasuryAccount)
               .filter(TreasuryAccount.is_active == True)  # noqa: E712
               .order_by(TreasuryAccount.id).first())
    return acc


class SaleService:
    """Service pour la gestion des ventes avec journalisation"""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.log_manager = SaleLogManager(db_session)

    def create_sale(self, sale_data: Dict[str, Any], currency: str = "FCFA", user_info: Dict = None) -> Tuple[bool, Optional[Sale], str]:
        try:
            for item in sale_data.get("items", []):
                product = self.db_session.query(Product).get(item["product_id"])
                if not product or item["quantity"] > product.quantity:
                    return False, None, f"Stock insuffisant pour {item.get('product_name', 'produit')}"

            # Garantir l'unicité du numéro de vente (contre les collisions après
            # suppression/renumérotation). Si le numéro affiché est déjà utilisé,
            # on en régénère un autre avant insertion.
            guard = 0
            while guard < 100 and self._sale_number_exists(sale_data["sale_number"]):
                sale_data["sale_number"] = self.generate_sale_number()
                guard += 1

            sale = Sale(
                sale_number=sale_data["sale_number"],
                customer_id=sale_data.get("customer_id"),
                cashier_id=sale_data["cashier_id"],
                # Multi-magasins : la vente appartient au magasin actif
                store_id=sale_data.get("store_id") or current_store_id_for(self.db_session),
                subtotal=sale_data["subtotal"],
                discount_amount=sale_data["discount_amount"],
                tax_amount=sale_data["tax_amount"],
                total_amount=sale_data["total_amount"],
                amount_paid=sale_data["amount_paid"],
                change_amount=sale_data["change_amount"],
                payment_method=sale_data["payment_method"],
                payment_status=sale_data["payment_status"],
                sale_status="COMPLETED",
                currency=currency
            )

            self.db_session.add(sale)
            self.db_session.flush()

            for item in sale_data["items"]:
                product = self.db_session.query(Product).get(item["product_id"])
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    discount_percent=item.get("discount_percent", 0),
                    discount_amount=item.get("discount_amount", 0),
                    line_total=item.get("line_total", item["quantity"] * item["unit_price"]),
                    notes=item.get("notes", "")
                )
                self.db_session.add(sale_item)
                product.quantity -= item["quantity"]

            if str(sale_data["payment_method"]).upper() in ("CRÉDIT", "CREDIT") \
                    and sale_data.get("customer_id"):
                customer = self.db_session.query(Customer).get(sale_data["customer_id"])
                if customer:
                    # Seule la part non encaissée devient une dette : un acompte
                    # versé à la création ne doit pas rester dans le solde dû.
                    cash_in = float(sale_data.get("amount_paid") or 0) - float(
                        sale_data.get("change_amount") or 0)
                    due = max(float(sale_data["total_amount"] or 0) - cash_in, 0)
                    customer.balance = float(customer.balance or 0) + due

            payment = Payment(
                sale_id=sale.id,
                amount=sale_data["amount_paid"],
                payment_method=sale_data["payment_method"],
                collected_by=sale_data["cashier_id"]
            )
            self.db_session.add(payment)

            # Trésorerie : encaissement automatique de l'argent réellement
            # reçu (amount_paid - change_amount) sur le compte de caisse par
            # defaut. Mêmes conventions que le registre factures
            # (reference_type="SALE", categorie "Ventes"). Une vente à crédit
            # sans acompte ne génère aucun mouvement.
            cash_in = float(sale_data.get("amount_paid") or 0) - float(
                sale_data.get("change_amount") or 0)
            if cash_in > 0.001:
                account = default_cash_account(self.db_session)
                if account is not None:
                    treasury = TreasuryManager(session=self.db_session)
                    result = treasury.add_movement(
                        account_id=account.id, movement_type="IN",
                        amount=cash_in,
                        reference=sale.sale_number,
                        description="Encaissement vente " + str(sale.sale_number),
                        category="Ventes", reference_type="SALE",
                        reference_id=sale.id,
                        user_id=sale_data.get("cashier_id"),
                    )
                    if not result.get("success"):
                        self.db_session.rollback()
                        return False, None, ("Erreur trésorerie : "
                                             + str(result.get("error")))

            self.db_session.commit()

            if user_info:
                customer_name = None
                if sale_data.get("customer_id"):
                    customer = self.db_session.query(Customer).get(sale_data["customer_id"])
                    if customer:
                        customer_name = f"{customer.first_name} {customer.last_name}"

                details = f"Vente créée - {len(sale_data['items'])} articles"
                self.log_manager.add_sale_log(
                    sale_id=sale.id,
                    sale_number=sale.sale_number,
                    action="CREATE",
                    user_id=user_info.get("id"),
                    username=user_info.get("username", "unknown"),
                    user_role=user_info.get("role", "CAISSIER"),
                    customer_id=sale_data.get("customer_id"),
                    customer_name=customer_name,
                    total_amount=sale.total_amount,
                    payment_method=sale.payment_method,
                    details=details
                )

            return True, sale, "Vente créée avec succès"

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Erreur création vente: {e}")
            return False, None, f"Erreur: {str(e)}"

    def cancel_sale(self, sale_id: int, reason: str, user_info: Dict) -> Tuple[bool, str]:
        try:
            sale = self.db_session.query(Sale).get(sale_id)
            if not sale:
                return False, "Vente non trouvée"

            if sale.sale_status == "CANCELLED":
                return False, "Vente déjà annulée"

            for item in sale.items:
                product = self.db_session.query(Product).get(item.product_id)
                if product:
                    product.quantity += item.quantity

            if str(sale.payment_method or "").upper() in ("CRÉDIT", "CREDIT") and sale.customer:
                # On ne reverse que la part encore due (le solde porté à la
                # création de la vente, diminué des encaissements déjà faits).
                due = max(float(sale.total_amount or 0) - float(sale.amount_paid or 0), 0)
                sale.customer.balance = max(float(sale.customer.balance or 0) - due, 0)

            # Trésorerie : reversement des encaissements lies a cette vente
            # (mouvement OUT compense sur les memes comptes).
            linked = (self.db_session.query(TreasuryMovement)
                      .filter(TreasuryMovement.reference_type == "SALE",
                              TreasuryMovement.reference_id == sale.id,
                              TreasuryMovement.movement_type == "IN").all())
            if linked:
                treasury = TreasuryManager(session=self.db_session)
                for mv in linked:
                    result = treasury.add_movement(
                        account_id=mv.account_id, movement_type="OUT",
                        amount=mv.amount, reference=sale.sale_number,
                        description=("Annulation vente "
                                     + str(sale.sale_number)),
                        category="Ventes", reference_type="SALE_CANCEL",
                        reference_id=sale.id,
                        user_id=user_info.get("id"),
                    )
                    if not result.get("success"):
                        self.db_session.rollback()
                        return False, ("Erreur trésorerie : "
                                       + str(result.get("error")))

            sale.sale_status = "CANCELLED"
            sale.notes = f"Annulée: {reason}"

            self.db_session.commit()

            customer_name = None
            if sale.customer:
                customer_name = f"{sale.customer.first_name} {sale.customer.last_name}"

            self.log_manager.add_sale_log(
                sale_id=sale.id,
                sale_number=sale.sale_number,
                action="CANCEL",
                user_id=user_info.get("id"),
                username=user_info.get("username", "unknown"),
                user_role=user_info.get("role", "CAISSIER"),
                customer_id=sale.customer_id,
                customer_name=customer_name,
                total_amount=sale.total_amount,
                payment_method=sale.payment_method,
                details=f"Vente annulée - Motif: {reason}"
            )

            return True, "Vente annulée avec succès"

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Erreur annulation vente: {e}")
            return False, f"Erreur: {str(e)}"

    def _sale_number_exists(self, sale_number: str) -> bool:
        """Vérifie si un numéro de vente existe déjà en base."""
        return self.db_session.query(Sale.id).filter(Sale.sale_number == sale_number).first() is not None

    def generate_sale_number(self) -> str:
        """Génère un numéro de vente unique à partir de la séquence déjà utilisée.

        Le numéro dérive du préfixe du jour + 1 du dernier numéro effectivement
        attribué (et non de l'id auto-incrémenté), ce qui reste unique même après
        suppression de ventes ou en cas d'écart entre id et numéro.
        """
        prefix = f"S{datetime.now().strftime('%Y%m%d')}"
        prefix_len = len(prefix)
        # Récupérer tous les numéros du jour pour en déduire la séquence max réelle
        numbers = self.db_session.query(Sale.sale_number).filter(
            Sale.sale_number.like(f"{prefix}%")
        ).all()
        max_seq = 0
        for (num,) in numbers:
            suffix = num[prefix_len:]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
        return f"{prefix}{max_seq + 1:04d}"


class ProductService:
    """Service pour la gestion des produits"""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_paginated_products(self, page: int = 1, filters: Optional[Dict] = None) -> Tuple[List[Product], int]:
        try:
            query = self.db_session.query(Product).options(joinedload(Product.supplier)).filter(Product.active == True)
            # Multi-magasins : uniquement le stock du magasin actif
            query = scope_products_query(query, self.db_session, Product)

            if filters:
                if filters.get("search"):
                    search = f"%{filters['search']}%"
                    query = query.filter(
                        (Product.code.ilike(search)) |
                        (Product.name.ilike(search)) |
                        (Product.category.ilike(search))
                    )

                if filters.get("category") and filters["category"] != "Toutes catégories":
                    query = query.filter(Product.category == filters["category"])

                if filters.get("supplier") and filters["supplier"] != "Tous fournisseurs":
                    query = query.join(Product.supplier).filter(Supplier.name == filters["supplier"])

            total = query.count()
            offset = (page - 1) * 50
            products = query.order_by(Product.name).offset(offset).limit(50).all()

            return products, total

        except Exception as e:
            logger.error(f"Erreur récupération produits: {e}")
            return [], 0

    def get_product_categories(self) -> List[str]:
        try:
            query = self.db_session.query(Product.category).filter(Product.active == True)
            query = scope_products_query(query, self.db_session, Product)
            categories = query.distinct().order_by(Product.category).all()
            return [cat[0] for cat in categories if cat[0]]
        except Exception as e:
            logger.error(f"Erreur récupération catégories: {e}")
            return []

    def get_suppliers(self) -> List[str]:
        try:
            query = self.db_session.query(Supplier.name).join(
                Product, Product.supplier_id == Supplier.id
            ).filter(Product.active == True)
            query = apply_store_scope(query, self.db_session, Product.store_id)
            suppliers = query.distinct().order_by(Supplier.name).all()
            return [sup[0] for sup in suppliers if sup[0]]
        except Exception as e:
            logger.error(f"Erreur récupération fournisseurs: {e}")
            return []

    def get_all_product_names(self) -> List[str]:
        try:
            query = self.db_session.query(Product.code, Product.name).filter(Product.active == True)
            query = scope_products_query(query, self.db_session, Product)
            products = query.order_by(Product.name).all()
            return [f"{p.code} - {p.name}" if p.code else p.name for p in products]
        except Exception as e:
            logger.error(f"Erreur récupération noms: {e}")
            return []


class CustomerService:
    """Service pour la gestion des clients"""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_customers(self, search: str = "") -> List[Customer]:
        try:
            query = self.db_session.query(Customer).filter(Customer.active == True)

            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    (Customer.first_name.ilike(search_term)) |
                    (Customer.last_name.ilike(search_term)) |
                    (Customer.company.ilike(search_term)) |
                    (Customer.phone.ilike(search_term)) |
                    (Customer.email.ilike(search_term))
                )

            return query.order_by(Customer.last_name, Customer.first_name).all()

        except Exception as e:
            logger.error(f"Erreur récupération clients: {e}")
            return []

    def create_customer(self, customer_data: Dict[str, Any]) -> Tuple[bool, Optional[Customer], str]:
        try:
            if customer_data.get("email"):
                existing = self.db_session.query(Customer).filter(Customer.email == customer_data["email"]).first()
                if existing:
                    return False, None, "Un client avec cet email existe déjà"

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            code = f"CUST{timestamp[-6:]}"

            customer = Customer(
                code=code,
                first_name=customer_data["first_name"],
                last_name=customer_data["last_name"],
                company=customer_data.get("company"),
                email=customer_data.get("email"),
                phone=customer_data.get("phone"),
                address=customer_data.get("address"),
                customer_type=customer_data.get("customer_type", "RETAIL"),
                credit_limit=customer_data.get("credit_limit", 0)
            )

            self.db_session.add(customer)
            self.db_session.commit()

            return True, customer, f"Client créé avec succès (Code: {code})"

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Erreur création client: {e}")
            return False, None, f"Erreur: {str(e)}"
