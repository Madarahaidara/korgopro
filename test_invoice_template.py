#!/usr/bin/env python3
"""
Script de test pour générer une facture d'exemple avec le nouveau template
"""
from pathlib import Path
import sys
from datetime import datetime

# Détecter dynamiquement la racine du projet (pyproject.toml ou main.py)
def find_repo_root(start: Path = Path(__file__).resolve()) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / 'pyproject.toml').exists() or (parent / 'main.py').exists():
            return parent
    return start.parent

PROJECT_ROOT = find_repo_root()
sys.path.insert(0, str(PROJECT_ROOT))

from core.database import SessionLocal
from core.models.sale_models import Sale, SaleItem
from core.models.customer import Customer
from core.models.stock_models import Product
from core.models.user import User
from utils.print_service import InvoicePrinter
import json


def test_generate_invoice():
    """Teste la génération d'une facture HTML"""
    
    try:
        # Créer une session DB
        db = SessionLocal()
        
        # Créer une instance du service d'impression
        printer = InvoicePrinter(db)
        
        print("✅ Service d'impression créé avec succès")
        
        # Récupérer une vente existante
        sale = db.query(Sale).first()
        
        if not sale:
            print("❌ Aucune vente trouvée dans la base de données")
            print("   Créez d'abord une vente dans l'application")
            return False
        
        print(f"✅ Vente trouvée: {sale.sale_number}")
        print(f"   Montant total: {sale.total_amount}")
        print(f"   Nombre articles: {len(sale.items)}")
        
        # Générer le HTML
        html_content = printer._create_html_template(sale)
        
        if not html_content:
            print("❌ Erreur: Template HTML vide")
            return False
        
        print("✅ Template HTML généré avec succès")
        
        # Sauvegarder dans un fichier de test
        output_file = Path(__file__).parent / "facture_test.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Fichier généré: {output_file}")
        print(f"   Ouvrez ce fichier dans votre navigateur pour voir le rendu")
        
        # Afficher un aperçu du template (premiers 500 caractères)
        print("\n--- Aperçu du template ---")
        print(html_content[:500])
        print("...\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Test de génération de facture")
    print("=" * 50)
    
    success = test_generate_invoice()
    
    print("=" * 50)
    if success:
        print("✅ Test réussi!")
    else:
        print("❌ Test échoué")
    
    sys.exit(0 if success else 1)
