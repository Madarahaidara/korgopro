# Maintenance Guide - Korgo Pro

Guide pour l'administration et la maintenance continue de Korgo Pro en production.

## Table des Matières

1. [Surveillance](#surveillance)
2. [Gestion des Performances](#gestion-des-performances)
3. [Gestion des Utilisateurs](#gestion-des-utilisateurs)
4. [Sécurité](#sécurité)
5. [Mises à Jour](#mises-à-jour)
6. [Récupération d'Urgence](#récupération-durgence)
7. [Audit et Conformité](#audit-et-conformité)

---

## Surveillance

### Logs Application

**Fichier Log** : Défini par `LOG_LEVEL` dans `.env`

```bash
# Vérifier les erreurs récentes
tail -50 korgo.log | grep ERROR

# Compter les erreurs par type
grep ERROR korgo.log | cut -d':' -f2 | sort | uniq -c

# Erreurs du dernier jour
find . -name "*.log" -mtime -1 -exec grep ERROR {} \;
```

### Métriques de Santé

**Checks Quotidiens :**

```bash
# 1. App responsive
# Lancer app et vérifier démarrage < 10 secondes

# 2. DB accessible
# Vérifier un SELECT simple exécute
python -c "from core.database import get_db; print(get_db().query('SELECT 1').fetchone())"

# 3. Space disque
df -h | grep -E "korgo|data"  # Vérifier disponibilité

# 4. Processus actif
ps aux | grep "python main.py"

# 5. Dernier backup récent
ls -lt backups/ | head -5
```

### Alertes à Configurer

| Alert | Seuil | Action |
|-------|-------|--------|
| CPU usage | >80% pendant 5 min | Investiguer processes |
| Memory | >90% | Redémarrer app |
| Disk | <10% libre | Nettoyer anciens logs/exports |
| DB latency | >5s par requête | Analyser + optimize |
| Login failures | >10 en 1h | Check security, disable account |

---

## Gestion des Performances

### Identifier Goulots

**PostgreSQL - Queries Lentes :**

```sql
-- Activer query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
SELECT pg_reload_conf();

-- Voir queries lentes
SELECT query, calls, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```

**SQLite - Identifier Problèmes :**

```bash
# Vérifier intégrité DB
sqlite3 korgo_pro.db "PRAGMA integrity_check;"

# Analyser performance
sqlite3 korgo_pro.db "PRAGMA analysis_limit=1000; ANALYZE;"
```

### Optimisation DB

**PostgreSQL :**

```sql
-- Réindex tables volumineux
REINDEX TABLE sales;
REINDEX TABLE stock;

-- Vacuum (défragmente + stats)
VACUUM FULL;
ANALYZE;

-- Vérifier index existants
SELECT * FROM pg_stat_user_indexes 
ORDER BY idx_scan DESC;

-- Créer index manquants
CREATE INDEX idx_sales_date ON sales(created_at);
CREATE INDEX idx_stock_product ON stock(product_id);
```

**SQLite :**

```bash
# Vacuum & optimize
sqlite3 korgo_pro.db "VACUUM;"
sqlite3 korgo_pro.db "PRAGMA optimize;"

# Vérifier fragmentation
sqlite3 korgo_pro.db "PRAGMA freelist_count;"
```

### Nettoyage Périodique

**Hebdomadaire :**

```bash
# Supprimer logs > 30 jours
find logs/ -name "*.log" -mtime +30 -delete

# Archiver exports > 60 jours
find data/exports -name "*.pdf" -mtime +60 | xargs tar -czf backups/exports_$(date +%Y%m).tar.gz
```

**Mensuellement :**

```bash
# Nettoyer rapports anciens
find data/reports -name "*.xlsx" -mtime +90 -delete

# Exécuter cleanup DB
# Pour PostgreSQL
vacuumdb -U korgo -d korgo_pro -f

# Pour SQLite
sqlite3 korgo_pro.db "VACUUM FULL; PRAGMA optimize;"
```

---

## Gestion des Utilisateurs

### Créer Nouvel Utilisateur

```bash
python scripts/create_user.py \
  --username john \
  --email john@company.com \
  --role USER \
  --password-hash $(python -c "import bcrypt; print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode())")
```

### Réinitialiser Mot de Passe

```bash
python scripts/reset_user_password.py --user john --new-password newpass123
```

### Désactiver Compte (Suspension)

```bash
# Mark account as disabled without deleting
python -c "
from core.database import session
from core.models import User
user = session.query(User).filter_by(username='john').first()
user.is_active = False
session.commit()
print('User suspended')
"
```

### Audit Utilisateurs

```sql
-- Derniers login (PostgreSQL)
SELECT username, role, last_login, login_attempts 
FROM users 
ORDER BY last_login DESC;

-- Utilisateurs inactifs > 90 jours
SELECT username, last_login 
FROM users 
WHERE last_login < NOW() - INTERVAL '90 days';

-- Utilisateurs avec permissions élevées
SELECT username, role 
FROM users 
WHERE role IN ('ADMIN', 'MANAGER');
```

---

## Sécurité

### Checklist Mensuelle

- [ ] ✅ Vérifier pas de secrets en logs (grep SECRET, password, token)
- [ ] ✅ Vérifier dépendances outdated: `pip list --outdated`
- [ ] ✅ Audit fichiers `.env` : secrets forts, rotatés
- [ ] ✅ Vérifier accès fichiers DB (permissions 600)
- [ ] ✅ Revoir logs de login pour patterns suspectes
- [ ] ✅ Tester backup restauration

### Sécurisation de l'Accès

**Permissions Fichiers :**

```bash
# DB et .env doivent être accessibles seulement au process
chmod 600 korgo_pro.db
chmod 600 .env

# Logs peuvent être lus par admin
chmod 640 *.log

# Data folder accessible au process
chmod 755 data/
```

**Hardening Network (si serveur distant) :**

```bash
# Firewall : Ouvrir seulement le port de l'app
sudo ufw allow 5000/tcp  # si app écoute sur 5000
sudo ufw allow 22/tcp    # SSH admin only

# SSH : Clés uniquement, pas de passwords
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### Gestion des Tokens/Secrets

**SECRET_KEY Rotation :**

```bash
# Générer nouvelle clé
NEW_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

# Mettre à jour .env
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_SECRET/" .env

# Redémarrer app pour appliquer
pkill -f "python main.py"
python main.py &
```

---

## Mises à Jour

### Checklist Avant Mise à Jour

```bash
# 1. Verifier version actuelle
git describe --tags

# 2. Backup complet
pg_dump -U korgo korgo_pro | gzip > backups/pre-update-$(date +%Y%m%d).sql.gz

# 3. Arrêter l'application
pkill -f "python main.py"

# 4. Stash local changes si any
git stash
```

### Effectuer Mise à Jour

```bash
# 1. Récupérer changements
git fetch origin
git pull origin main

# 2. Mettre à jour dépendances
pip install -r requirements.txt --upgrade

# 3. Vérifier changements .env
# Si nouveau fichier .env.example, vérifier variables
diff .env.example .env

# 4. Lancer
python main.py &
```

### Post-Mise à Jour

```bash
# 1. Vérifier logs
tail -100 debug.log

# 2. Test basique : login + créer vente
python -c "
from controllers.auth_controller import AuthController
auth = AuthController()
result = auth.authenticate('admin', 'password')
assert result is not None, 'Auth failed'
print('✅ Auth working')
"

# 3. Notifier utilisateurs
echo "App updated to $(git describe --tags)" > /tmp/notification.txt
```

---

## Récupération d'Urgence

### Scénario 1 : Corruption DB

**Symptômes :** Erreurs de lecture, queries échouent

```bash
# 1. Arrêter app
pkill -f "python main.py"

# 2. Vérifier intégrité
# PostgreSQL
pg_dump korgo_pro > /dev/null && echo "DB OK" || echo "CORRUPT"

# SQLite
sqlite3 korgo_pro.db "PRAGMA integrity_check;"

# 3. Restaurer depuis backup
# PostgreSQL
psql -U korgo korgo_pro < backups/korgo_pro_YYYYMMDD.sql

# SQLite
cp backups/korgo_pro_YYYYMMDD.db korgo_pro.db

# 4. Redémarrer
python main.py &
```

### Scénario 2 : Perte de Données

**Si commit accidentel de fichiers sensibles :**

```bash
# 1. Identifier le commit
git log --all --full-history -- <file>

# 2. Remove from history (dangerous operation!)
git-filter-repo --invert-paths --path <file>

# 3. Force push (notifier tous les contributeurs!)
git push origin --force-with-lease

# 4. Avertir l'équipe de faire git pull --force
```

### Scénario 3 : App Crashe au Démarrage

**Diagnostic :**

```bash
# 1. Vérifier erreur
python main.py 2>&1 | head -50

# 2. Checker .env
cat .env | grep -E "KORGO_DB|SECRET"

# 3. Vérifier DB connexion
python -c "
import os
from sqlalchemy import create_engine
url = os.environ.get('KORGO_DB_URL', 'sqlite:///korgo_pro.db')
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('DB OK')
"

# 4. Vérifier dépendances
pip check

# 5. Restore der backup si nécessaire
cp backups/korgo_pro_YYYYMMDD.db korgo_pro.db
```

### Scénario 4 : Espace Disque Plein

```bash
# 1. Identifier consumer
du -sh /* | sort -rh | head -5

# 2. Nettoyer
# Logs
find logs/ -name "*.log" -mtime +30 -delete

# Exports anciens
find data/exports -name "*.pdf" -mtime +60 -delete

# Cache Python
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# 3. Vérifier space
df -h
```

---

## Audit et Conformité

### Audit Trail

**Logging Événements Critiques :**

```python
# En core/__init__.py ou main.py
import logging

audit_log = logging.getLogger('audit')
audit_log.info(f"User {username} logged in from {ip}")
audit_log.info(f"Sale created: {sale_id} by {user}")
audit_log.warning(f"Failed login attempt: {username} from {ip}")
audit_log.error(f"DB backup failed: {error}")
```

**Consulter Audit Logs :**

```bash
grep "logged in\|created\|failed" audit.log | tail -100
```

### Conformité RGPD (si applicable)

**Droits d'accès/oubli :**

```sql
-- Voir toutes données d'un utilisateur
SELECT * FROM users WHERE email = 'user@example.com';
SELECT * FROM sales WHERE user_id = 123;
SELECT * FROM audit_log WHERE user_id = 123;

-- Supprimer un utilisateur (anonymiser plutôt que supprimer)
UPDATE users SET 
    email = 'deleted@example.com',
    name = 'Deleted User',
    is_active = false
WHERE id = 123;
```

### Rapports de Conformité

**Mensuel :**

```bash
cat <<EOF > compliance_report_$(date +%Y%m).txt
== CONFORMITÉ MENSUELLE ==
Date: $(date)

1. Backups
   - Nombre: $(ls backups/*.sql.gz 2>/dev/null | wc -l)
   - Plus récent: $(ls -t backups/*.sql.gz 2>/dev/null | head -1)

2. Sécurité
   - Dépendances outdated: $(pip list --outdated | wc -l)
   - Fichiers exposés (secrets): $(grep -r SECRET . 2>/dev/null | wc -l)

3. Performance
   - Taille DB: $(du -sh korgo_pro.db 2>/dev/null)
   - Users actifs (dernière semaine): $(sqlite3 korgo_pro.db "SELECT COUNT(*) FROM users WHERE last_login > datetime('now', '-7 days');")

4. Incidents
   - Erreurs dans logs: $(grep ERROR *.log 2>/dev/null | wc -l)
   - Failed logins: $(grep "failed login" audit.log 2>/dev/null | wc -l)

EOF
cat compliance_report_$(date +%Y%m).txt
```

---

## Contacts & Escalade

- **Admin Support**: [email ou contact]
- **Technical Issues**: GitHub Issues
- **Security**: security@korgo.example.com (confidential)
- **Documentation**: See docs/

---

**Last Updated**: 2026-08-12
