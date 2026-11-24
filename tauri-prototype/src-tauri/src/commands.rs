// commands.rs — Commandes Tauri exposées au frontend
//
// - db::list_tables   : liste des tables
// - db::query         : lecture avec filtre optionnel
// - db::insert        : insertion
// - auth_login        : connexion (mock)
// - auth_is_admin     : vérification du rôle ADMIN (mock)

use std::sync::Arc;

use serde_json::{json, Value};
use tauri::State;

use crate::db::MockDb;

/// ➜ `db::list_tables`
#[tauri::command]
pub async fn db_list_tables(
    conn: State<'_, Arc<MockDb>>,
) -> Result<Vec<String>, String> {
    Ok(conn.list_tables())
}

/// ➜ `db::query(table, where)`
#[tauri::command]
pub async fn db_query(
    conn: State<'_, Arc<MockDb>>,
    table: String,
    where_filter: Option<Value>,
) -> Result<Vec<Value>, String> {
    Ok(conn.query(&table, where_filter.as_ref()))
}

/// ➜ `db::insert(table, data)`
#[tauri::command]
pub async fn db_insert(
    conn: State<'_, Arc<MockDb>>,
    table: String,
    data: Value,
) -> Result<Value, String> {
    conn.insert(&table, &data)
        .ok_or_else(|| format!("Table inconnue: {}", table))
}

/// ➜ `auth_login(email, password)`
#[tauri::command]
pub async fn auth_login(
    email: String,
    password: String,
) -> Result<Value, String> {
    let email = email.trim().to_lowercase();

    // Vérification mock : admin@korgo.pro / admin123
    if email == "admin@korgo.pro" && password == "admin123" {
        return Ok(json!({
            "ok": true,
            "message": "connecté",
            "user": {
                "id": "1",
                "email": "admin@korgo.pro",
                "username": "admin",
                "role": "ADMIN",
                "active": true,
                "authenticated": true
            }
        }));
    }

    Ok(json!({
        "ok": false,
        "message": "identifiants invalides"
    }))
}

/// ➜ `auth_is_admin(email)`
#[tauri::command]
pub async fn auth_is_admin(email: String) -> Result<Value, String> {
    let email_lower = email.trim().to_lowercase();
    let is_admin = email_lower == "admin@korgo.pro";
    Ok(json!({ "is_admin": is_admin }))
}

/// ➜ `app_tauri_treasury_move`
#[tauri::command]
pub async fn app_tauri_treasury_move(
    conn: State<'_, Arc<MockDb>>,
    payload: Value,
) -> Result<Value, String> {
    let account_id = payload
        .get("p_account_id")
        .and_then(|v| v.as_i64())
        .ok_or_else(|| "account_id manquant".to_string())? as i64;

    let movement_type = payload
        .get("p_movement_type")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "movement_type manquant".to_string())?;

    let amount = payload
        .get("p_amount")
        .and_then(|v| v.as_f64())
        .ok_or_else(|| "amount manquant".to_string())?;

    let reference = payload
        .get("p_reference")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let description = payload
        .get("p_description")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let category = payload
        .get("p_category")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    if movement_type != "IN" && movement_type != "OUT" {
        return Err("movement_type doit être IN ou OUT".to_string());
    }
    if amount <= 0.0 {
        return Err("Le montant doit être positif".to_string());
    }

    let accounts = conn.query("treasury_accounts", None.as_ref());
    let account = accounts
        .iter()
        .find(|a| a.get("id").and_then(|v| v.as_i64()) == Some(account_id))
        .ok_or_else(|| "Compte introuvable".to_string())?;

    let now = chrono::Utc::now().to_rfc3339();
    let movement_id = account
        .get("id")
        .and_then(|v| v.as_i64())
        .unwrap_or(0)
        .max(0)
        + 1;

    let movement = json!({
        "id": movement_id,
        "account_id": account_id,
        "movement_type": movement_type,
        "amount": amount,
        "date": now,
        "reference": reference,
        "description": description,
        "category": category,
        "reference_type": "MANUAL",
        "reference_id": null,
        "user_id": null,
        "created_at": now,
    });

    conn.insert("treasury_movements", &movement)?;

    let mut account_mut = account.clone();
    let current_balance = account_mut
        .get("current_balance")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let new_balance = if movement_type == "IN" {
        current_balance + amount
    } else {
        current_balance - amount
    };
    account_mut.insert("current_balance".to_string(), json!(new_balance));

    conn.insert("treasury_accounts", &account_mut)?;

    Ok(json!({
        "success": true,
        "movement": movement,
        "new_balance": new_balance
    }))
}

/// ➜ `app_tauri_cash_session`
#[tauri::command]
pub async fn app_tauri_cash_session(
    conn: State<'_, Arc<MockDb>>,
    payload: Value,
) -> Result<Value, String> {
    let action = payload
        .get("p_action")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "action manquante".to_string())?;

    let account_id = payload
        .get("p_account_id")
        .and_then(|v| v.as_i64())
        .ok_or_else(|| "account_id manquant".to_string())? as i64;

    let account = conn.query("treasury_accounts", None.as_ref())
        .iter()
        .find(|a| a.get("id").and_then(|v| v.as_i64()) == Some(account_id))
        .ok_or_else(|| "Compte introuvable".to_string())?;

    if action == "open" {
        // Vérifier qu'il n'y a pas de session ouverte
        let open_sessions: Vec<Value> = conn.query("cash_register_sessions", None.as_ref());
        let has_open = open_sessions
            .iter()
            .any(|s| {
                s.get("account_id").and_then(|v| v.as_i64()) == Some(account_id)
                    && s.get("status").and_then(|v| v.as_str()) == Some("OPEN")
            });
        if has_open {
            return Err("Une session est déjà ouverte sur ce compte".to_string());
        }

        let session_id = 1;
        let now = chrono::Utc::now().to_rfc3339();
        let session = json!({
            "id": session_id,
            "account_id": account_id,
            "user_id": payload.get("p_user_id").and_then(|v| v.as_i64()),
            "opened_at": now,
            "closing_amount": null,
            "expected_amount": payload.get("p_amount").and_then(|v| v.as_f64()),
            "total_in": 0.0,
            "total_out": 0.0,
            "difference": 0.0,
            "status": "OPEN",
            "notes": "",
        });

        conn.insert("cash_register_sessions", &session)?;
        return Ok(json!({ "success": true, "session": session }));
    } else if action == "close" {
        let session_id = payload
            .get("p_session_id")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| "session_id manquant".to_string())? as i64;

        // Trouver la session
        let mut sessions = conn.query("cash_register_sessions", None.as_ref());
        let session_idx = sessions
            .iter()
            .position(|s| s.get("id").and_then(|v| v.as_i64()) == Some(session_id))
            .ok_or_else(|| "Session introuvable".to_string())?;

        let mut session = sessions.remove(session_idx);

        if session.get("status").and_then(|v| v.as_str()) == Some("CLOSED") {
            return Err("Session déjà fermée".to_string());
        }

        let closing_amount = payload
            .get("p_amount")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);

        // Calculer le total IN et OUT de la session
        let movements: Vec<Value> = conn.query("treasury_movements", None.as_ref());
        let (total_in, total_out) = movements.iter().filter(|m| {
            m.get("account_id").and_then(|v| v.as_i64()) == Some(account_id)
        }).fold((0.0, 0.0), |acc, m| {
            let amt = m.get("amount").and_then(|v| v.as_f64()).unwrap_or(0.0);
            if m.get("movement_type").and_then(|v| v.as_str()) == Some("IN") {
                (acc.0 + amt, acc.1)
            } else {
                (acc.0, acc.1 + amt)
            }
        });

        let expected = session
            .get("expected_amount")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let difference = closing_amount - expected;

        session.insert("closing_amount".to_string(), json!(closing_amount));
        session.insert("total_in".to_string(), json!(total_in));
        session.insert("total_out".to_string(), json!(total_out));
        session.insert("difference".to_string(), json!(difference));
        session.insert("closed_at".to_string(), json!(chrono::Utc::now().to_rfc3339()));
        session.insert("status".to_string(), json!("CLOSED"));

        conn.insert("cash_register_sessions", &session)?;

        return Ok(json!({
            "success": true,
            "session": session,
            "total_in": total_in,
            "total_out": total_out,
            "expected": expected,
            "difference": difference
        }));
    }

    Err("action doit être 'open' ou 'close'".to_string())
}

