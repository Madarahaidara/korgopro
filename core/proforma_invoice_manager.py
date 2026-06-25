# core/proforma_invoice_manager.py
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.models.sale_models import ProformaInvoice, ProformaInvoiceItem, Sale, SaleItem
from core.models.customer import Customer
from core.models.stock_models import Product
from core.models.user import User
from core.sale_log_manager import SaleLogManager
import logging

logger = logging.getLogger(__name__)


class ProformaInvoiceManager:
    """Gestionnaire pour les factures proforma"""
    
    def __init__(self, session: Session):
        self.session = session
        self.sale_log_manager = SaleLogManager(session)
    
    def generate_proforma_number(self) -> str:
        """Génère un numéro de facture proforma unique"""
        prefix = "PROF"
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Compter le nombre de proformas créées aujourd'hui
        count = self.session.query(func.count(ProformaInvoice.id)).filter(
            func.date(ProformaInvoice.created_date) == datetime.now().date()
        ).scalar() or 0
        
        return f"{prefix}-{date_str}-{str(count + 1).zfill(4)}"
    
    def create_proforma(
        self,
        customer_id: Optional[int],
        created_by_id: int,
        items: List[Dict[str, Any]],
        discount_percent: float = 0,
        tax_percent: float = 0,
        notes: str = "",
        terms_and_conditions: str = "",
        valid_days: int = 30,
        valid_until: Optional[datetime] = None,
        currency: str = "FCFA"
    ) -> ProformaInvoice:
        """
        Crée une nouvelle facture proforma
        
        Args:
            customer_id: ID du client (optionnel)
            created_by_id: ID de l'utilisateur créant la proforma
            items: Liste des articles avec {'product_id', 'description', 'quantity', 'unit_price', 'discount_percent'}
            discount_percent: Remise globale en pourcentage
            tax_percent: TVA en pourcentage
            notes: Notes supplémentaires
            terms_and_conditions: Conditions générales
            valid_days: Jours de validité
            currency: Devise
        
        Returns:
            ProformaInvoice créée
        """
        try:
            # Déterminer la date de validité: utiliser `valid_until` si fourni,
            # sinon calculer à partir de `valid_days`.
            validity_date = valid_until if valid_until is not None else (datetime.now() + timedelta(days=valid_days))

            proforma = ProformaInvoice(
                proforma_number=self.generate_proforma_number(),
                customer_id=customer_id,
                created_by=created_by_id,
                created_date=datetime.now(),
                valid_until=validity_date,
                discount_percent=discount_percent,
                tax_percent=tax_percent,
                notes=notes,
                terms_and_conditions=terms_and_conditions,
                currency=currency,
                status="DRAFT"
            )
            
            subtotal = 0
            
            # Ajouter les articles
            for item_data in items:
                item = ProformaInvoiceItem(
                    product_id=item_data.get("product_id"),
                    description=item_data.get("description", ""),
                    quantity=item_data.get("quantity", 1),
                    unit_price=item_data.get("unit_price", 0),
                    discount_percent=item_data.get("discount_percent", 0)
                )
                
                # Calculer les montants de l'article
                item_subtotal = item.quantity * item.unit_price
                item.discount_amount = item_subtotal * (item.discount_percent / 100)
                item.line_total = item_subtotal - item.discount_amount
                
                proforma.items.append(item)
                subtotal += item.line_total
            
            proforma.subtotal = subtotal
            proforma.discount_amount = subtotal * (discount_percent / 100)
            
            # Calculer la TVA et le total
            amount_after_discount = subtotal - proforma.discount_amount
            proforma.tax_amount = amount_after_discount * (tax_percent / 100)
            proforma.total_amount = amount_after_discount + proforma.tax_amount
            
            self.session.add(proforma)
            self.session.commit()
            
            logger.info(f"Facture proforma {proforma.proforma_number} créée")
            
            return proforma
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Erreur création proforma: {str(e)}")
            raise
    
    def update_proforma(
        self,
        proforma_id: int,
        customer_id: Optional[int] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        discount_percent: Optional[float] = None,
        tax_percent: Optional[float] = None,
        notes: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
        valid_until: Optional[datetime] = None
    ) -> ProformaInvoice:
        """Met à jour une facture proforma"""
        try:
            proforma = self.session.query(ProformaInvoice).filter(
                ProformaInvoice.id == proforma_id
            ).first()
            
            if not proforma:
                raise ValueError(f"Proforma {proforma_id} introuvable")
            
            if proforma.status != "DRAFT":
                raise ValueError("Seules les proformas en brouillon peuvent être modifiées")
            
            if customer_id is not None:
                proforma.customer_id = customer_id
            
            if discount_percent is not None:
                proforma.discount_percent = discount_percent
            
            if tax_percent is not None:
                proforma.tax_percent = tax_percent
            
            if notes is not None:
                proforma.notes = notes
            
            if terms_and_conditions is not None:
                proforma.terms_and_conditions = terms_and_conditions
            
            if valid_until is not None:
                proforma.valid_until = valid_until
            
            # Mettre à jour les articles si fournis
            if items is not None:
                proforma.items.clear()
                subtotal = 0
                
                for item_data in items:
                    item = ProformaInvoiceItem(
                        product_id=item_data.get("product_id"),
                        description=item_data.get("description", ""),
                        quantity=item_data.get("quantity", 1),
                        unit_price=item_data.get("unit_price", 0),
                        discount_percent=item_data.get("discount_percent", 0)
                    )
                    
                    item_subtotal = item.quantity * item.unit_price
                    item.discount_amount = item_subtotal * (item.discount_percent / 100)
                    item.line_total = item_subtotal - item.discount_amount
                    
                    proforma.items.append(item)
                    subtotal += item.line_total
                
                proforma.subtotal = subtotal
                proforma.discount_amount = subtotal * (proforma.discount_percent / 100)
                amount_after_discount = subtotal - proforma.discount_amount
                proforma.tax_amount = amount_after_discount * (proforma.tax_percent / 100)
                proforma.total_amount = amount_after_discount + proforma.tax_amount
            
            self.session.commit()
            logger.info(f"Facture proforma {proforma.proforma_number} mise à jour")
            
            return proforma
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Erreur mise à jour proforma: {str(e)}")
            raise
    
    def change_proforma_status(self, proforma_id: int, new_status: str) -> ProformaInvoice:
        """Change le statut d'une proforma"""
        try:
            proforma = self.session.query(ProformaInvoice).filter(
                ProformaInvoice.id == proforma_id
            ).first()
            
            if not proforma:
                raise ValueError(f"Proforma {proforma_id} introuvable")
            
            valid_statuses = ["DRAFT", "SENT", "ACCEPTED", "REJECTED", "EXPIRED", "CONVERTED"]
            if new_status not in valid_statuses:
                raise ValueError(f"Statut invalide: {new_status}")
            
            old_status = proforma.status
            proforma.status = new_status
            
            self.session.commit()
            logger.info(f"Proforma {proforma.proforma_number}: {old_status} -> {new_status}")
            
            return proforma
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Erreur changement statut proforma: {str(e)}")
            raise
    
    def convert_to_sale(self, proforma_id: int, created_by_id: int) -> Sale:
        """Convertit une facture proforma en vente"""
        try:
            proforma = self.session.query(ProformaInvoice).filter(
                ProformaInvoice.id == proforma_id
            ).first()
            
            if not proforma:
                raise ValueError(f"Proforma {proforma_id} introuvable")
            
            if proforma.status == "CONVERTED":
                raise ValueError("Cette proforma a déjà été convertie en vente")
            
            # Générer le numéro de vente
            sale_number = self._generate_sale_number()
            
            # Créer la vente
            sale = Sale(
                sale_number=sale_number,
                customer_id=proforma.customer_id,
                cashier_id=created_by_id,
                sale_date=datetime.now(),
                subtotal=proforma.subtotal,
                discount_amount=proforma.discount_amount,
                tax_amount=proforma.tax_amount,
                total_amount=proforma.total_amount,
                payment_status="PENDING",
                sale_status="COMPLETED",
                notes=proforma.notes,
                currency=proforma.currency
            )
            
            # Ajouter les articles à la vente
            for proforma_item in proforma.items:
                sale_item = SaleItem(
                    product_id=proforma_item.product_id,
                    quantity=proforma_item.quantity,
                    unit_price=proforma_item.unit_price,
                    discount_percent=proforma_item.discount_percent,
                    discount_amount=proforma_item.discount_amount,
                    line_total=proforma_item.line_total,
                    notes=proforma_item.notes
                )
                sale.items.append(sale_item)
            
            self.session.add(sale)
            
            # Mettre à jour la proforma
            proforma.status = "CONVERTED"
            proforma.converted_to_sale_id = sale.id
            
            self.session.commit()
            logger.info(f"Proforma {proforma.proforma_number} convertie en vente {sale_number}")
            
            return sale
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Erreur conversion proforma: {str(e)}")
            raise
    
    def get_proforma(self, proforma_id: int) -> Optional[ProformaInvoice]:
        """Récupère une proforma par ID"""
        return self.session.query(ProformaInvoice).filter(
            ProformaInvoice.id == proforma_id
        ).first()
    
    def get_proforma_by_number(self, proforma_number: str) -> Optional[ProformaInvoice]:
        """Récupère une proforma par numéro"""
        return self.session.query(ProformaInvoice).filter(
            ProformaInvoice.proforma_number == proforma_number
        ).first()
    
    def list_proformas(
        self,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProformaInvoice]:
        """Liste les factures proforma"""
        query = self.session.query(ProformaInvoice)
        
        if customer_id:
            query = query.filter(ProformaInvoice.customer_id == customer_id)
        
        if status:
            query = query.filter(ProformaInvoice.status == status)
        
        return query.order_by(ProformaInvoice.created_date.desc()).offset(skip).limit(limit).all()
    
    def delete_proforma(self, proforma_id: int) -> bool:
        """Supprime une facture proforma (uniquement si en brouillon)"""
        try:
            proforma = self.session.query(ProformaInvoice).filter(
                ProformaInvoice.id == proforma_id
            ).first()
            
            if not proforma:
                raise ValueError(f"Proforma {proforma_id} introuvable")
            
            if proforma.status != "DRAFT":
                raise ValueError("Seules les proformas en brouillon peuvent être supprimées")
            
            self.session.delete(proforma)
            self.session.commit()
            logger.info(f"Proforma {proforma.proforma_number} supprimée")
            
            return True
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Erreur suppression proforma: {str(e)}")
            raise
    
    def _generate_sale_number(self) -> str:
        """Génère un numéro de vente unique"""
        prefix = "SALE"
        date_str = datetime.now().strftime("%Y%m%d")
        
        count = self.session.query(func.count(Sale.id)).filter(
            func.date(Sale.sale_date) == datetime.now().date()
        ).scalar() or 0
        
        return f"{prefix}-{date_str}-{str(count + 1).zfill(4)}"
