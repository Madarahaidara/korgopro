#!/usr/bin/env python3
"""
Script spécifique pour tester le graphique du dashboard
"""

import sys
from pathlib import Path

# Ajouter la racine du projet aux imports pour les scripts utilitaires
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Imports dépendants du projet (après insertion du project root)
from core.database import SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import func
from core.models.sale_models import Sale


def test_chart_data():
    print("="*60)
    print("TEST DES DONNÉES POUR LE GRAPHIQUE")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        # Période des 30 derniers jours
        end_date = datetime.now()
        start_date = end_date - timedelta(days=29)
        
        print(f"Période analysée: {start_date.date()} au {end_date.date()}")
        print()
        
        # Vérifier s'il y a des ventes dans cette période
        total_sales_count = db.query(func.count(Sale.id)).filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= end_date,
            Sale.sale_status == "COMPLETED"
        ).scalar() or 0
        
        print(f"Nombre total de ventes (30 jours): {total_sales_count}")
        
        if total_sales_count == 0:
            print("⚠️  AUCUNE VENTE trouvée dans les 30 derniers jours!")
            print("   Le graphique sera vide.")
            print()
            print("SOLUTION: Exécutez 'python recreate_db.py' pour créer des données de test")
            return False
        
        # Récupérer les données par jour
        sales_by_day = db.query(
            func.date(Sale.sale_date).label('date'),
            func.sum(Sale.total_amount).label('total'),
            func.count(Sale.id).label('count')
        ).filter(
            Sale.sale_date >= start_date,
            Sale.sale_date <= end_date,
            Sale.sale_status == "COMPLETED"
        ).group_by(func.date(Sale.sale_date)).order_by(func.date(Sale.sale_date)).all()
        
        print(f"Jours avec des ventes: {len(sales_by_day)} sur 30")
        print()
        
        if len(sales_by_day) > 0:
            print("Exemple de données (5 premiers jours):")
            print("-"*40)
            for i, sale in enumerate(sales_by_day[:5]):
                print(f"{sale.date}: {sale.count} ventes, {sale.total:,.0f} FCFA")
            print()
            
            # Calculer les statistiques
            total_revenue = sum(sale.total for sale in sales_by_day)
            avg_per_day = total_revenue / len(sales_by_day) if len(sales_by_day) > 0 else 0
            
            print("STATISTIQUES:")
            print(f"  Revenu total: {total_revenue:,.0f} FCFA")
            print(f"  Moyenne par jour: {avg_per_day:,.0f} FCFA")
            print(f"  Jour avec plus de ventes: {max(sales_by_day, key=lambda x: x.total).date}")
            print(f"  Montant max: {max(sales_by_day, key=lambda x: x.total).total:,.0f} FCFA")
            print(f"  Montant min: {min(sales_by_day, key=lambda x: x.total).total:,.0f} FCFA")
            print()
            
            print("✅ Données disponibles pour le graphique!")
            return True
        else:
            print("⚠️  Données insuffisantes pour le graphique")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_chart_creation():
    print("="*60)
    print("TEST DE CRÉATION DU GRAPHIQUE")
    print("="*60)
    
    try:
        # Essayer d'importer les composants du graphique
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCharts import QChart, QLineSeries, QDateTimeAxis, QValueAxis
        from PySide6.QtCore import QDateTime, Qt
        from PySide6.QtGui import QPen, QColor
        
        print("✅ Composants graphiques importés")
        
        # Créer une application Qt (nécessaire pour les tests)
        app = QApplication.instance() or QApplication([])
        
        # Créer un graphique de test
        chart = QChart()
        chart.setTitle("Test du graphique")
        
        # Créer une série de données de test
        series = QLineSeries()
        series.setName("Données de test")
        
        # Ajouter des points de test
        now = datetime.now()
        for i in range(10):
            date = now - timedelta(days=i)
            value = 1000 * (i + 1)
            series.append(QDateTime(date).toMSecsSinceEpoch(), value)
        
        # Ajouter la série au graphique
        chart.addSeries(series)
        
        # Créer les axes
        axisX = QDateTimeAxis()
        axisX.setFormat("dd MMM")
        axisX.setTitleText("Date")
        
        axisY = QValueAxis()
        axisY.setTitleText("Valeur")
        axisY.setLabelFormat("%d")
        
        chart.addAxis(axisX, Qt.AlignBottom)
        chart.addAxis(axisY, Qt.AlignLeft)
        
        series.attachAxis(axisX)
        series.attachAxis(axisY)
        
        print("✅ Graphique créé avec succès")
        print(f"   Nombre de points: {series.count()}")
        print(f"   Échelle X: {axisX.min().toString('dd/MM/yyyy')} à {axisX.max().toString('dd/MM/yyyy')}")
        print(f"   Échelle Y: {axisY.min():,.0f} à {axisY.max():,.0f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création du graphique: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("DIAGNOSTIC DU GRAPHIQUE DU DASHBOARD")
    print("="*60)
    
    # Tester les données
    data_ok = test_chart_data()
    
    print()
    
    # Tester la création du graphique
    chart_ok = test_chart_creation()
    
    print()
    print("="*60)
    print("CONCLUSION:")
    
    if data_ok and chart_ok:
        print("✅ Tous les tests ont réussi!")
        print("   Le problème vient peut-être de l'affichage dans l'interface.")
    elif not data_ok:
        print("❌ Problème avec les données.")
        print("   Vérifiez que la base de données contient des ventes.")
    elif not chart_ok:
        print("❌ Problème avec la création du graphique.")
        print("   Vérifiez l'installation de PySide6 et QtCharts.")