#!/usr/bin/env python3
"""
Script pour recréer la base de données stock avec 100 éléments par table
"""

import os
import random
from datetime import datetime, timedelta
import bcrypt
from decimal import Decimal, ROUND_HALF_UP

from core.database import Base, engine, SessionLocal
from core.models.user import User
from core.models.stock_models import (
    Product, Supplier, InventoryMovement, 
    ExpenseCategory, Expense, PurchaseOrder, 
    PurchaseOrderItem, StockAlert
)
from core.models.sale_models import (
    Sale, SaleItem, Customer, Payment, SaleReturn, SaleReturnItem
)

def recreate_database():
    """Recréer la base de données"""
    print("🗑️  Suppression de l'ancienne base de données...")
    
    # Supprimer le fichier de base de données
    db_file = "korgo_pro.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Fichier {db_file} supprimé")
    
    print("🔧 Création des nouvelles tables...")
    
    try:
        # Créer toutes les tables
        Base.metadata.create_all(bind=engine)
        print("✅ Tables créées avec succès!")
        
        # Créer des données minimales
        create_test_data_100()
        
        print("🎉 Base de données recréée avec succès!")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

def create_test_data_100():
    """Créer des données de test avec 100 éléments par table"""
    db = SessionLocal()
    
    try:
        print("Création de données de test avec 100 éléments par table...")
        
        # ========== CRÉATION DES UTILISATEURS (100) ==========
        print("Création de 100 utilisateurs...")
        users = []
        roles = ["ADMIN", "CAISSIER", "GESTIONNAIRE", "ASSISTANT", "SUPERVISEUR"]
        
        # Créer d'abord l'utilisateur admin spécifique
        print("  → Création de l'utilisateur admin...")
        admin_user = User(
            username="admin",
            password_hash=bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
            email="admin@korgo.com",
            role="ADMIN",
            active=True,
            last_login=datetime.now() - timedelta(days=1)
        )
        db.add(admin_user)
        db.flush()
        users.append(admin_user)
        print(f"  ✅ Admin créé: username=admin, password=admin123")
        
        # Créer un utilisateur caissier pour les tests
        print("  → Création de l'utilisateur caissier...")
        cashier_user = User(
            username="caissier",
            password_hash=bcrypt.hashpw("caissier123".encode(), bcrypt.gensalt()).decode(),
            email="caissier@korgo.com",
            role="CAISSIER",
            active=True,
            last_login=datetime.now() - timedelta(days=2)
        )
        db.add(cashier_user)
        db.flush()
        users.append(cashier_user)
        print(f"  ✅ Caissier créé: username=caissier, password=caissier123")
        
        # Créer un utilisateur gestionnaire pour les tests
        print("  → Création de l'utilisateur manager...")
        manager_user = User(
            username="manager",
            password_hash=bcrypt.hashpw("manager123".encode(), bcrypt.gensalt()).decode(),
            email="manager@korgo.com",
            role="GESTIONNAIRE",
            active=True,
            last_login=datetime.now() - timedelta(days=3)
        )
        db.add(manager_user)
        db.flush()
        users.append(manager_user)
        print(f"  ✅ Manager créé: username=manager, password=manager123")
        
        # Créer 97 utilisateurs supplémentaires pour atteindre 100
        for i in range(1, 98):
            username = f"user{i:03d}"
            role = roles[i % len(roles)]
            
            user = User(
                username=username,
                password_hash=bcrypt.hashpw(f"pass{username}".encode(), bcrypt.gensalt()).decode(),
                email=f"{username}@korgo.com",
                role=role,
                active=random.choice([True, False]) if i > 20 else True,
                last_login=datetime.now() - timedelta(days=random.randint(0, 30)) if random.choice([True, False]) else None
            )
            db.add(user)
            db.flush()
            users.append(user)
        
        print(f"✅ {len(users)} utilisateurs créés (dont admin, caissier, manager)")
        
        # ========== CRÉATION DES FOURNISSEURS (100) ==========
        print("Création de 100 fournisseurs...")
        suppliers = []
        cities = ["Abidjan", "Bouaké", "Daloa", "Yamoussoukro", "San-Pédro", "Korhogo", "Man", "Divo", "Gagnoa", "Abengourou"]
        countries = ["Côte d'Ivoire", "France", "Chine", "USA", "Ghana", "Nigeria", "Mali", "Burkina Faso"]
        
        for i in range(1, 101):
            supplier = Supplier(
                code=f"SUP{i:04d}",
                name=f"Fournisseur {random.choice(['Global', 'Tech', 'Pro', 'Elite', 'Premium'])} {i}",
                contact_person=f"Contact {random.choice(['A', 'B', 'C', 'D'])}",
                email=f"contact{i:04d}@fournisseur.com",
                phone=f"+225 0{random.randint(1,9)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}",
                address=f"{random.randint(1,999)} Rue {random.choice(['du Commerce', 'des Affaires', 'Centrale', 'Principale'])}",
                city=random.choice(cities),
                country=random.choice(countries),
                payment_terms=random.choice(["30 jours", "60 jours", "Comptant", "50% à la commande"]),
                active=random.choice([True, False]) if i > 30 else True
            )
            db.add(supplier)
            db.flush()
            suppliers.append(supplier)
        
        print(f"✅ {len(suppliers)} fournisseurs créés")
        
        # ========== CRÉATION DES PRODUITS (100) ==========
        print("Création de 100 produits...")
        products = []
        categories = [
            "Électronique", "Informatique", "Bureau", "Mobilier", "Papeterie",
            "Logiciels", "Périphériques", "Réseau", "Téléphonie", "Accessoires",
            "Consommables", "Électroménager", "Textile", "Alimentation", "Bricolage",
            "Jardinage", "Sport", "Loisirs", "Santé", "Beauté"
        ]
        
        for i in range(1, 101):
            category = random.choice(categories)
            
            # Prix d'achat entre 1 et 5000
            purchase_price = round(random.uniform(1, 5000), 2)
            
            # Prix de vente avec marge de 15-150%
            sale_price = round(purchase_price * random.uniform(1.15, 2.5), 2)
            
            # Quantité aléatoire
            quantity = random.randint(0, 500)
            
            product = Product(
                code=f"PROD{i:04d}",
                name=f"Produit {category} {random.choice(['Pro', 'Premium', 'Elite', 'Plus', 'Max', 'Standard'])} {i}",
                description=f"Description détaillée du produit {i} dans la catégorie {category}. Caractéristiques et spécifications techniques complètes.",
                category=category,
                purchase_price=purchase_price,
                sale_price=sale_price,
                quantity=quantity,
                min_stock=random.randint(5, 50),
                max_stock=random.randint(100, 1000),
                supplier_id=random.choice(suppliers).id,
                location=random.choice(["Entrepôt A", "Entrepôt B", "Rayon 1", "Rayon 2", "Stock Principal", "Réserve"]),
                barcode=f"8{random.randint(10000000, 99999999)}" if i % 2 == 0 else None,
                active=random.choice([True, False]) if i > 80 else True
            )
            db.add(product)
            db.flush()
            products.append(product)
        
        print(f"✅ {len(products)} produits créés")
        
        # ========== CRÉATION DE CATÉGORIES DE DÉPENSES (20) ==========
        print("Création de 20 catégories de dépenses...")
        expense_categories = []
        expense_category_names = [
            "Transport", "Emballage", "Loyer", "Salaires", "Fournitures",
            "Électricité", "Eau", "Internet", "Maintenance", "Nettoyage",
            "Marketing", "Formation", "Assurance", "Frais bancaires", "Impôts",
            "Licences", "Logiciels", "Publicité", "Voyage", "Représentation"
        ]
        
        for i, cat_name in enumerate(expense_category_names, 1):
            category = ExpenseCategory(
                name=cat_name,
                description=f"Catégorie pour les dépenses de type {cat_name}",
                active=True
            )
            db.add(category)
            db.flush()
            expense_categories.append(category)
        
        print(f"✅ {len(expense_categories)} catégories de dépenses créées")
        
        # ========== CRÉATION DE 100 CLIENTS ==========
        print("Création de 100 clients...")
        customers = []
        first_names = ["Jean", "Marie", "Paul", "Sophie", "Marc", "Julie", "Pierre", "Alice", "Luc", "Claire",
                      "David", "Sarah", "Thomas", "Laura", "Kevin", "Emma", "Nicolas", "Chloé", "Alexandre", "Manon"]
        last_names = ["Dupont", "Martin", "Bernard", "Petit", "Durand", "Moreau", "Laurent", "Simon", "Michel", "Lefebvre",
                     "Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor"]
        
        for i in range(1, 101):
            customer_type = random.choice(["RETAIL", "CORPORATE", "WHOLESALE"])
            
            if customer_type == "RETAIL":
                credit_limit = random.uniform(100, 5000)
                company = None
            elif customer_type == "WHOLESALE":
                credit_limit = random.uniform(5000, 20000)
                company = f"Grossiste {random.choice(['Express', 'Pro', 'Global', 'Premium'])}"
            else:  # CORPORATE
                credit_limit = random.uniform(10000, 50000)
                company = f"Entreprise {random.choice(['Tech', 'Solutions', 'Innovations', 'Group'])}"
            
            customer = Customer(
                code=f"CUST{i:04d}",
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                company=company,
                email=f"client{i:04d}@email.com",
                phone=f"+225 07 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
                mobile=f"+225 05 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
                address=f"{random.randint(1, 999)} {random.choice(['Avenue', 'Rue', 'Boulevard'])} {random.choice(['de la République', 'du Commerce', 'Centrale', 'des Fleurs'])}",
                city=random.choice(['Abidjan', 'Bouaké', 'Daloa', 'Yamoussoukro', 'San-Pédro']),
                country="Côte d'Ivoire",
                customer_type=customer_type,
                credit_limit=credit_limit,
                balance=round(random.uniform(-5000, 5000), 2) if i > 30 else 0,
                loyalty_points=random.randint(0, 10000) if i % 3 == 0 else 0,
                active=random.choice([True, False]) if i > 70 else True
            )
            db.add(customer)
            db.flush()
            customers.append(customer)
        
        print(f"✅ {len(customers)} clients créés")
        
        # ========== CRÉATION DE 100 VENTES ==========
        print("Création de 100 ventes...")
        sales = []
        payment_methods = ["CASH", "CARD", "MOBILE_MONEY", "CHECK"]
        payment_statuses = ["PAID", "PARTIAL", "PENDING", "CANCELLED"]
        sale_statuses = ["COMPLETED", "CANCELLED", "REFUNDED"]
        
        for i in range(1, 101):
            sale_date = datetime.now() - timedelta(days=random.randint(0, 365))
            customer = random.choice(customers) if random.choice([True, False]) else None
            cashier = random.choice([cashier_user, manager_user] + users[3:20])  # Privilégier les vrais caissiers
            
            # Calculer les totaux
            discount_amount = round(random.uniform(0, 200), 2) if random.choice([True, False]) else 0
            tax_rate = random.uniform(0, 20)  # Taux de taxe entre 0% et 20%
            
            sale = Sale(
                sale_number=f"SALE{i:05d}",
                sale_date=sale_date,
                customer_id=customer.id if customer else None,
                cashier_id=cashier.id,
                subtotal=0,  # Sera calculé après
                discount_amount=discount_amount,
                tax_amount=0,  # Sera calculé après
                total_amount=0,  # Sera calculé après
                amount_paid=0,  # Sera calculé après
                change_amount=0,
                payment_method=random.choice(payment_methods),
                payment_status=random.choice(payment_statuses),
                sale_status=random.choice(sale_statuses),
                notes=f"Vente {i} - {random.choice(['Client régulier', 'Nouveau client', 'Commande spéciale', 'Promotion'])}"
            )
            db.add(sale)
            db.flush()
            sales.append(sale)
            
            # Créer 1-8 items par vente
            num_items = random.randint(1, 8)
            sale_subtotal = 0
            
            for item_num in range(1, num_items + 1):
                product = random.choice(products)
                quantity = random.randint(1, 10)
                unit_price = product.sale_price
                discount_percent = round(random.uniform(0, 30), 2) if random.choice([True, False]) else 0
                discount_amount_item = round(unit_price * quantity * discount_percent / 100, 2)
                line_total = round(unit_price * quantity - discount_amount_item, 2)
                sale_subtotal += line_total
                
                # Mettre à jour la quantité du produit (simuler la vente)
                product.quantity = max(0, product.quantity - quantity)
                
                # Créer l'item de vente
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount_percent=discount_percent,
                    discount_amount=discount_amount_item,
                    line_total=line_total,
                    notes=f"Item {item_num} - {random.choice(['Standard', 'Promo', 'Série limitée'])}"
                )
                db.add(sale_item)
            
            # Mettre à jour les totaux de la vente
            sale.subtotal = round(sale_subtotal, 2)
            sale.tax_amount = round(sale_subtotal * tax_rate / 100, 2)
            sale.total_amount = round(sale_subtotal - sale.discount_amount + sale.tax_amount, 2)
            
            # Définir le montant payé selon le statut de paiement
            if sale.payment_status == "PAID":
                sale.amount_paid = sale.total_amount
                sale.change_amount = round(random.uniform(0, 50), 2) if sale.payment_method == "CASH" else 0
            elif sale.payment_status == "PARTIAL":
                sale.amount_paid = round(sale.total_amount * random.uniform(0.3, 0.9), 2)
                sale.change_amount = 0
            elif sale.payment_status == "CANCELLED":
                sale.amount_paid = 0
                sale.change_amount = 0
            else:  # PENDING
                sale.amount_paid = round(sale.total_amount * random.uniform(0, 0.5), 2) if random.choice([True, False]) else 0
                sale.change_amount = 0
        
        print(f"✅ {len(sales)} ventes créées")
        
        # ========== CRÉATION DE 100 PAIEMENTS ==========
        print("Création de 100 paiements...")
        for i in range(1, 101):
            sale = random.choice(sales)
            payment_date = sale.sale_date + timedelta(hours=random.randint(0, 72))
            
            # Si la vente est déjà payée, créer un paiement complet
            if sale.payment_status == "PAID":
                amount = sale.total_amount
            elif sale.payment_status == "PARTIAL":
                # Créer un paiement partiel complémentaire
                remaining = sale.total_amount - sale.amount_paid
                amount = round(remaining * random.uniform(0.5, 1.0), 2) if remaining > 0 else 0
            else:
                amount = round(sale.total_amount * random.uniform(0.3, 1.0), 2)
            
            if amount > 0:  # Ne créer un paiement que si le montant est positif
                payment = Payment(
                    sale_id=sale.id,
                    amount=amount,
                    payment_method=sale.payment_method,
                    transaction_id=f"TRX{random.randint(100000, 999999)}" if sale.payment_method in ["CARD", "MOBILE_MONEY"] else None,
                    reference=f"PAY{i:05d}",
                    notes=f"Paiement {i} pour vente {sale.sale_number}",
                    payment_date=payment_date,
                    collected_by=sale.cashier_id
                )
                db.add(payment)
        
        print(f"✅ 100 paiements créés")
        
        # ========== CRÉATION DE 100 MOUVEMENTS DE STOCK ==========
        print("Création de 100 mouvements de stock...")
        movement_types = ["IN", "OUT", "ADJUST", "LOSS", "RETURN"]
        
        for i in range(1, 101):
            movement_date = datetime.now() - timedelta(days=random.randint(0, 180))
            movement_type = random.choice(movement_types)
            product = random.choice(products)
            user = random.choice(users)
            
            if movement_type == "IN":
                quantity = random.randint(10, 200)
                unit_price = product.purchase_price * random.uniform(0.9, 1.1)
            elif movement_type == "OUT":
                quantity = -random.randint(1, 50)
                unit_price = product.sale_price
            elif movement_type == "LOSS":
                quantity = -random.randint(1, 20)
                unit_price = product.purchase_price
            elif movement_type == "RETURN":
                quantity = random.randint(1, 30)
                unit_price = product.sale_price
            else:  # ADJUST
                quantity = random.randint(-20, 20)
                unit_price = product.purchase_price
            
            total_value = abs(quantity) * unit_price
            
            movement = InventoryMovement(
                product_id=product.id,
                movement_type=movement_type,
                quantity=quantity,
                unit_price=round(unit_price, 2),
                total_value=round(total_value, 2),
                reference=f"MVT{i:05d}",
                reason=random.choice([
                    "Réapprovisionnement", "Vente client", "Ajustement inventaire", 
                    "Perte constatée", "Retour client", "Inventaire physique",
                    "Transfert entre dépôts", "Don", "Échantillon"
                ]),
                notes=f"Movement {i}: {movement_type} - {random.choice(['Routine', 'Urgent', 'Planifié'])}",
                user_id=user.id,
                date=movement_date
            )
            db.add(movement)
            
            # Mettre à jour la quantité du produit
            product.quantity = max(0, product.quantity + quantity)
        
        print(f"✅ 100 mouvements de stock créés")
        
        # ========== CRÉATION DE 100 DÉPENSES ==========
        print("Création de 100 dépenses...")
        for i in range(1, 101):
            expense_date = datetime.now() - timedelta(days=random.randint(0, 365))
            amount = round(random.uniform(5, 5000), 2)
            user = random.choice(users)
            
            expense = Expense(
                category_id=random.choice(expense_categories).id,
                amount=amount,
                description=f"Dépense {i}: {random.choice(['Transport marchandises', 'Achat fournitures', 'Maintenance équipement', 'Frais de représentation', 'Publicité locale', 'Formation personnel', 'Licence logiciel', 'Assurance locale'])}",
                payment_method=random.choice(["CASH", "BANK", "MOBILE_MONEY"]),
                reference=f"EXP{i:05d}",
                supplier_id=random.choice(suppliers).id if random.choice([True, False]) else None,
                user_id=user.id,
                date=expense_date
            )
            db.add(expense)
        
        print(f"✅ 100 dépenses créées")
        
        # ========== CRÉATION DE 100 ALERTES DE STOCK ==========
        print("Création de 100 alertes de stock...")
        for i in range(1, 101):
            product = random.choice(products)
            
            # Déterminer le type d'alerte basé sur la quantité
            alert_type_choice = random.random()
            
            if alert_type_choice < 0.3:  # 30% OUT_OF_STOCK
                alert_type = "OUT_OF_STOCK"
                threshold = 0
                message = f"⚠️ RUPTURE: {product.name} est en rupture de stock"
            elif alert_type_choice < 0.7:  # 40% LOW_STOCK
                alert_type = "LOW_STOCK"
                threshold = product.min_stock
                message = f"📉 STOCK BAS: {product.name} - Quantité: {product.quantity}, Seuil: {threshold}"
            else:  # 30% EXPIRING
                alert_type = "EXPIRING"
                threshold = product.max_stock
                message = f"📈 STOCK ÉLEVÉ: {product.name} - Quantité: {product.quantity}, Maximum: {threshold}"
            
            alert = StockAlert(
                product_id=product.id,
                alert_type=alert_type,
                threshold=threshold,
                message=message,
                is_read=random.choice([True, False]) and i > 30  # Les premières alertes sont lues
            )
            db.add(alert)
        
        print(f"✅ 100 alertes de stock créées")
        
        # ========== CRÉATION DE 100 COMMANDES D'ACHAT ==========
        print("Création de 100 commandes d'achat...")
        order_statuses = ["PENDING", "ORDERED", "RECEIVED", "CANCELLED"]
        
        for i in range(1, 101):
            order_date = datetime.now() - timedelta(days=random.randint(0, 180))
            expected_delivery = order_date + timedelta(days=random.randint(3, 30))
            
            # Déterminer la date de réception basée sur le statut
            status = random.choice(order_statuses)
            if status == "RECEIVED":
                received_date = expected_delivery - timedelta(days=random.randint(0, 5))
            elif status == "CANCELLED":
                received_date = None
            else:
                received_date = None
            
            order = PurchaseOrder(
                order_number=f"PO{i:05d}",
                supplier_id=random.choice(suppliers).id,
                status=status,
                total_amount=0,
                notes=f"Commande {i}: {random.choice(['Urgent', 'Standard', 'Contrat annuel', 'Promotion'])}",
                expected_delivery=expected_delivery,
                received_date=received_date,
                user_id=random.choice(users).id
            )
            db.add(order)
            db.flush()
            
            # Créer 2-6 items par commande
            num_items = random.randint(2, 6)
            order_total = 0
            
            for item_num in range(1, num_items + 1):
                product = random.choice(products)
                quantity = random.randint(10, 200)
                unit_price = product.purchase_price * random.uniform(0.8, 1.2)
                total_price = quantity * unit_price
                order_total += total_price
                
                # Quantité reçue selon le statut
                if status == "RECEIVED":
                    received_quantity = quantity - random.randint(0, int(quantity * 0.1))  # Moins 0-10%
                elif status == "ORDERED":
                    received_quantity = random.randint(0, int(quantity * 0.3))  # 0-30% reçu
                else:
                    received_quantity = 0
                
                order_item = PurchaseOrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=round(unit_price, 2),
                    total_price=round(total_price, 2),
                    received_quantity=received_quantity,
                    notes=f"Item {item_num}: {random.choice(['Standard', 'Promo prix', 'Série spéciale'])}"
                )
                db.add(order_item)
            
            # Mettre à jour le total de la commande
            order.total_amount = round(order_total, 2)
        
        print(f"✅ 100 commandes d'achat créées")
        
        # ========== CRÉATION DE 50 RETOURS DE VENTE ==========
        print("Création de 50 retours de vente...")
        for i in range(1, 51):
            # Choisir une vente complétée pour le retour
            completed_sales = [s for s in sales if s.sale_status == "COMPLETED"]
            if not completed_sales:
                continue
                
            sale = random.choice(completed_sales)
            return_date = sale.sale_date + timedelta(days=random.randint(1, 30))
            processor = random.choice(users)
            
            sale_return = SaleReturn(
                return_number=f"RET{i:05d}",
                sale_id=sale.id,
                customer_id=sale.customer_id,
                return_date=return_date,
                total_amount=0,
                reason=random.choice(["Produit défectueux", "Mauvaise taille", "Client insatisfait", "Erreur de commande", "Retard livraison"]),
                notes=f"Retour {i}: {random.choice(['Standard', 'Urgent', 'Garantie'])}",
                processed_by=processor.id,
                status=random.choice(["PENDING", "APPROVED", "COMPLETED", "REJECTED"])
            )
            db.add(sale_return)
            db.flush()
            
            # Créer 1-3 items retournés
            num_items = random.randint(1, 3)
            return_total = 0
            
            # Obtenir les items de la vente
            sale_items = db.query(SaleItem).filter(SaleItem.sale_id == sale.id).limit(num_items).all()
            
            for sale_item in sale_items:
                quantity_returned = random.randint(1, min(3, int(sale_item.quantity)))
                refund_amount = round(sale_item.unit_price * quantity_returned * 0.8, 2)  # 80% du prix
                return_total += refund_amount
                
                return_item = SaleReturnItem(
                    return_id=sale_return.id,
                    sale_item_id=sale_item.id,
                    product_id=sale_item.product_id,
                    quantity=quantity_returned,
                    unit_price=sale_item.unit_price,
                    refund_amount=refund_amount,
                    reason=random.choice(["Défaut fabrication", "Non conforme", "Changé d'avis"]),
                    notes=f"Retour partiel: {quantity_returned} sur {sale_item.quantity}"
                )
                db.add(return_item)
            
            # Mettre à jour le total du retour
            sale_return.total_amount = round(return_total, 2)
        
        print(f"✅ 50 retours de vente créés")
        
        db.commit()
        
        # ========== AFFICHAGE DES INFORMATIONS DE CONNEXION ==========
        print("\n" + "="*60)
        print("🔐 INFORMATIONS DE CONNEXION PRINCIPALES:")
        print("="*60)
        print("👑 ADMINISTRATEUR:")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        print(f"   Email: admin@korgo.com")
        print(f"   Role: ADMIN")
        print()
        print("💰 CAISSIER:")
        print(f"   Username: caissier")
        print(f"   Password: caissier123")
        print(f"   Email: caissier@korgo.com")
        print(f"   Role: CAISSIER")
        print()
        print("📊 GESTIONNAIRE:")
        print(f"   Username: manager")
        print(f"   Password: manager123")
        print(f"   Email: manager@korgo.com")
        print(f"   Role: GESTIONNAIRE")
        print("="*60)
        
        # ========== AFFICHAGE DES STATISTIQUES ==========
        print("\n" + "="*60)
        print("📊 STATISTIQUES DE LA BASE DE DONNÉES (100 par table):")
        print("="*60)
        print(f"👥  Utilisateurs créés: {len(users)}")
        print(f"🏭  Fournisseurs créés: {len(suppliers)}")
        print(f"📦  Produits créés: {len(products)}")
        print(f"💰  Catégories de dépenses: {len(expense_categories)}")
        print(f"👤  Clients créés: {len(customers)}")
        print(f"🛒  Ventes créées: {len(sales)}")
        print(f"💳  Paiements créés: 100")
        print(f"📊  Mouvements de stock: 100")
        print(f"💸  Dépenses créées: 100")
        print(f"⚠️   Alertes de stock: 100")
        print(f"📋  Commandes d'achat: 100")
        print(f"↩️   Retours de vente: 50")
        print("="*60)
        
        # Calculer quelques statistiques financières
        total_sales = sum(s.total_amount for s in sales)
        total_expenses = sum(e.amount for e in db.query(Expense).all())
        total_inventory_value = sum(p.quantity * p.purchase_price for p in products)
        
        print(f"💰  Chiffre d'affaires total: {total_sales:,.2f} FCFA")
        print(f"💸  Dépenses totales: {total_expenses:,.2f} FCFA")
        print(f"📦  Valeur du stock: {total_inventory_value:,.2f} FCFA")
        print("="*60)
        print("✅ Données de test créées avec succès!")
        print("💡 Conseil: Utilisez 'admin' / 'admin123' pour accéder à toutes les fonctionnalités")
        
    except Exception as e:
        print(f"⚠️  Erreur lors de la création des données de test: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    recreate_database()