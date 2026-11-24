// db.rs — Couche d'accès aux données (mock pour le prototype)
//
// En production, remplacer MockDb par une connexion tokio-postgres vers Supabase.

use serde_json::{Map, Value};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

/// Génère les données de démonstration pour les comptes de trésorerie.
fn treasury_accounts() -> Vec<Map<String, Value>> {
    vec![
        serde_json::from_value(serde_json::json!({
            "id": 1,
            "name": "Caisse principale",
            "account_type": "CASH",
            "currency": "FCFA",
            "initial_balance": 25000.0,
            "current_balance": 25000.0,
            "bank_name": null,
            "account_number": null,
            "phone_number": null,
            "is_active": true,
            "is_default": true,
            "notes": "Caisse de gestion du prototype"
        })).unwrap(),
        serde_json::from_value(serde_json::json!({
            "id": 2,
            "name": "Compte courant Korgo Bank",
            "account_type": "BANK",
            "currency": "FCFA",
            "initial_balance": 150000.0,
            "current_balance": 150000.0,
            "bank_name": "Korgo Bank",
            "account_number": "KG00000012345",
            "phone_number": null,
            "is_active": true,
            "is_default": false,
            "notes": "Compte bancaire d'activité"
        })).unwrap(),
    ]
}

/// Génère les données de démonstration pour les mouvements de trésorerie.
fn treasury_movements() -> Vec<Map<String, Value>> {
    vec![
        serde_json::from_value(serde_json::json!({
            "id": 1,
            "account_id": 1,
            "movement_type": "IN",
            "amount": 20000.0,
            "date": "2026-11-01T08:00:00Z",
            "reference": "Vente-#001",
            "description": "Vente de produits",
            "category": "Vente",
            "reference_type": "SALE",
            "reference_id": 101,
            "user_id": null,
            "created_at": "2026-11-01T08:00:00Z"
        })).unwrap(),
        serde_json::from_value(serde_json::json!({
            "id": 2,
            "account_id": 1,
            "movement_type": "OUT",
            "amount": 5000.0,
            "date": "2026-11-02T10:00:00Z",
            "reference": "Fournisseur-#045",
            "description": "Achat fournisseur",
            "category": "Achat",
            "reference_type": "SUPPLIER",
            "reference_id": 45,
            "user_id": null,
            "created_at": "2026-11-02T10:00:00Z"
        })).unwrap(),
    ]
}

/// Génère les données de démonstration pour les sessions de caisse.
fn cash_register_sessions() -> Vec<Map<String, Value>> {
    vec![]
}

/// Génère les données de démonstration pour les clôtures mensuelles.
fn monthly_closures() -> Vec<Map<String, Value>> {
    vec![]
}

/// Simule une base de données avec des tables en mémoire.
pub struct MockDb {
    pub tables: Arc<RwLock<HashMap<String, Vec<Map<String, Value>>>>>,
}

impl MockDb {
    pub fn new() -> Self {
        let mut tables = HashMap::new();

        // Données de démonstration pour le prototype Korgo Pro
        tables.insert(
            "users".to_string(),
            vec![serde_json::from_value(serde_json::json!({
                "id": "1",
                "username": "admin",
                "email": "admin@korgo.pro",
                "role": "ADMIN",
                "active": true
            })).unwrap()],
        );

        tables.insert(
            "customers".to_string(),
            vec![
                serde_json::from_value(serde_json::json!({
                    "id": "1",
                    "full_name": "Jean Dupont",
                    "code": "C001",
                    "company": "SARL Dupont",
                    "phone": "22 50 00 00",
                    "email": "jean@dupont.bf",
                    "customer_type": "PRO"
                })).unwrap(),
                serde_json::from_value(serde_json::json!({
                    "id": "2",
                    "full_name": "Marie Konaté",
                    "code": "C002",
                    "company": "",
                    "phone": "70 12 34 56",
                    "email": "marie@konate.bf",
                    "customer_type": "PARTICULIER"
                })).unwrap(),
            ],
        );

        tables.insert(
            "products".to_string(),
            vec![
                serde_json::from_value(serde_json::json!({
                    "id": "1",
                    "name": "Riz 5kg",
                    "code": "P001",
                    "category": "Alimentaire",
                    "quantity": 50,
                    "threshold": 10,
                    "purchase_price": 2500,
                    "sale_price": 3000,
                    "active": true
                })).unwrap(),
                serde_json::from_value(serde_json::json!({
                    "id": "2",
                    "name": "Huile 1L",
                    "code": "P002",
                    "category": "Alimentaire",
                    "quantity": 30,
                    "threshold": 5,
                    "purchase_price": 1500,
                    "sale_price": 2000,
                    "active": true
                })).unwrap(),
            ],
        );

        tables.insert("sales".to_string(), vec![]);
        tables.insert("app_settings".to_string(), vec![serde_json::from_value(serde_json::json!({
            "id": "1",
            "data": { "currency": "FCFA", "company_name": "Korgo Pro" },
            "updated_at": "2026-11-10T00:00:00Z"
        })).unwrap()]);

        // === TABLES DE TRÉSORERIE (nouveau) ===
        tables.insert("treasury_accounts".to_string(), treasury_accounts());
        tables.insert("treasury_movements".to_string(), treasury_movements());
        tables.insert("cash_register_sessions".to_string(), cash_register_sessions());
        tables.insert("monthly_closures".to_string(), monthly_closures());

        MockDb {
            tables: Arc::new(RwLock::new(tables)),
        }
    }

    /// Liste les noms de tables disponibles.
    pub fn list_tables(&self) -> Vec<String> {
        self.tables.read().unwrap().keys().cloned().collect()
    }

    /// Requête une table avec un filtre optionnel (JSON { colonne: valeur }).
    pub fn query(&self, table: &str, where_filter: Option<&Value>) -> Vec<Value> {
        let tables = self.tables.read().unwrap();
        let rows = match tables.get(table) {
            Some(r) => r,
            None => return vec![],
        };

        let mut result: Vec<Map<String, Value>> = rows
            .iter()
            .filter(|row| {
                match where_filter {
                    Some(filter) => {
                        if let Value::Object(obj) = filter {
                            obj.iter().all(|(k, v)| {
                                row.get(k).map(|rv| rv == v).unwrap_or(false)
                            })
                        } else {
                            true
                        }
                    }
                    None => true,
                }
            })
            .cloned()
            .collect();

        // Appliquer limit si présent
        if let Some(Value::Object(filter)) = where_filter {
            if let Some(Value::Number(limit)) = filter.get("limit") {
                let limit = limit.as_u64().unwrap_or(200) as usize;
                result.truncate(limit);
            }
        }

        result.into_iter().map(Value::Object).collect()
    }

    /// Insère une ligne dans une table.
    pub fn insert(&self, table: &str, data: &Value) -> Option<Value> {
        let mut tables = self.tables.write().unwrap();
        let rows = match tables.get_mut(table) {
            Some(r) => r,
            None => return None,
        };

        let mut new_row = Map::new();
        if let Value::Object(obj) = data {
            for (k, v) in obj {
                new_row.insert(k.clone(), v.clone());
            }
        }

        // Générer un id si absent
        if new_row.get("id").is_none() {
            let id = (rows.len() + 1).to_string();
            new_row.insert("id".to_string(), Value::String(id));
        }

        rows.push(new_row.clone());
        Some(Value::Object(new_row))
    }
}
