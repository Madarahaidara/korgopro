import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload

from core.models.stock_models import Product, Supplier
from core.models.sale_models import Sale, SaleItem, Customer, Payment
from core.sale_log_manager import SaleLogManager

logger = logging.getLogger(__name__)


class SaleService:
    """Service pour la gestion des ventes avec journalisation"""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.log_manager = SaleLogManager()

    def create_sale(self, sale_data: Dict[str, Any], currency: str = "FCFA", user_info: Dict = None) -> Tuple[bool, Optional[Sale], str]:
        try:
            for item in sale_data.get("items", []):
                product = self.db_session.query(Product).get(item["product_id"])
                if not product or item["quantity"] > product.quantity:
                    return False, None, f"Stock insuffisant pour {item.get('product_name', 'produit')}"

            sale = Sale(
                sale_number=sale_data["sale_number"],
                customer_id=sale_data.get("customer_id"),
                cashier_id=sale_data["cashier_id"],
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

            if sale_data["payment_method"] == "CRÉDIT" and sale_data.get("customer_id"):
                customer = self.db_session.query(Customer).get(sale_data["customer_id"])
                if customer:
                    customer.balance += sale_data["total_amount"]

            payment = Payment(
                sale_id=sale.id,
                amount=sale_data["amount_paid"],
                payment_method=sale_data["payment_method"],
                collected_by=sale_data["cashier_id"]
            )
            self.db_session.add(payment)

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

            if sale.payment_method == "CRÉDIT" and sale.customer:
                sale.customer.balance -= sale.total_amount

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

    def generate_sale_number(self) -> str:
        today = datetime.now().date()
        count = self.db_session.query(Sale).filter(Sale.sale_date >= today).count()
        return f"S{datetime.now().strftime('%Y%m%d')}{count + 1:04d}"


class ProductService:
    """Service pour la gestion des produits"""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_paginated_products(self, page: int = 1, filters: Optional[Dict] = None) -> Tuple[List[Product], int]:
        try:
            query = self.db_session.query(Product).options(joinedload(Product.supplier)).filter(Product.active == True)

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
            categories = self.db_session.query(Product.category).filter(Product.active == True).distinct().order_by(Product.category).all()
            return [cat[0] for cat in categories if cat[0]]
        except Exception as e:
            logger.error(f"Erreur récupération catégories: {e}")
            return []

    def get_suppliers(self) -> List[str]:
        try:
            suppliers = self.db_session.query(Supplier.name).join(Product, Product.supplier_id == Supplier.id).filter(Product.active == True).distinct().order_by(Supplier.name).all()
            return [sup[0] for sup in suppliers if sup[0]]
        except Exception as e:
            logger.error(f"Erreur récupération fournisseurs: {e}")
            return []

    def get_all_product_names(self) -> List[str]:
        try:
            products = self.db_session.query(Product.code, Product.name).filter(Product.active == True).order_by(Product.name).all()
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
