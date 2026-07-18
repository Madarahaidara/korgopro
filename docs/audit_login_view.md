# Audit de Sécurité — Vue Login
**Date:** 26/06/2026  
**Fichier audité:** `ui/views/login_view.py`  
**Fichiers associés:** `controllers/auth_controller.py`, `core/security.py`, `core/models/user.py`

---

## Résumé Exécutif

| Aspect | État | Niveau |
|--------|------|--------|
| Interface utilisateur | ✅ Bien implémentée | - |
| Communication UI → Backend | ✅ Thread async, pas de blocage | - |
| Validation des entrées (UI) | ⚠️ Partielle | Moyen |
| Gestion des erreurs | ✅ Feedback utilisateur clair | - |
| Protection brute force | ❌ Absente | **Critique** |
| Verrouillage de compte | ❌ Absent | **Critique** |
| Journalisation (logging) | ❌ Absente | **Élevé** |
| Tracking IP | ❌ Champ existe mais non utilisé | **Élevé** |
| Hash mot de passe | ✅ bcrypt + migration auto | - |
| Injection SQL | ✅ ORM SQLAlchemy | - |

---

## 1. Analyse de la Vue Login (`ui/views/login_view.py`)

### 1.1 Points Positifs

- **Interface soignée:** Design moderne avec panneaux séparés, ombres, et animations fluides
- **Thread asynchrone:** Authentification dans `LoginWorker(QThread)` → pas de gel de l'interface
- **Feedback utilisateur:**
  - Loader animé pendant l'authentification
  - Animation de "shake" en cas d'erreur
  - Message d'erreur contextuel
  - État de succès visuel (bouton vert "✓ Connecté")
- **Gestion des touches Entrée:** Les champs username/password réagissent à la touche Entrée
- **Empêchement double-clic:** Vérification `if self.worker and self.worker.isRunning(): return`
- **Nettoyage password:** `self.password.clear()` en cas d'échec

### 1.2 Vulnérabilités et Faiblesses

#### 🔴 [CRITIQUE] Absence de Protection contre le Bruteforce
**Ligne concernée:** `controllers/auth_controller.py:8-42`

```python
def authenticate(self, username: str, password: str):
    # Aucune vérification de taux de tentatives
    # Aucun délai progressif
    # Aucun verrouillage temporaire
```

**Risque:**  
Un attaquant peut tester des millions de combinaisons par seconde sans restriction.

**Recommandation:**
```python
# À ajouter dans auth_controller.py
from collections import defaultdict
from datetime import datetime, timedelta

class BruteForceProtection:
    def __init__(self):
        self.failed_attempts = defaultdict(list)  # {username: [timestamps]}
        self.max_attempts = 5
        self.lockout_duration = timedelta(minutes=15)
    
    def is_locked_out(self, username: str) -> bool:
        now = datetime.utcnow()
        attempts = self.failed_attempts[username]
        # Nettoyer les tentatives anciennes
        self.failed_attempts[username] = [
            t for t in attempts if now - t < self.lockout_duration
        ]
        return len(self.failed_attempts[username]) >= self.max_attempts
    
    def record_failed_attempt(self, username: str):
        self.failed_attempts[username].append(datetime.utcnow())
```

---

#### 🔴 [CRITIQUE] Pas de Journalisation des Tentatives de Connexion
**Ligne concernée:** `controllers/auth_controller.py:40-42`

**Risque:**  
Aucune trace des tentatives échouées, réussies, ou des changements de mot de passe. Impossible de détecter une intrusion a posteriori.

**Recommandation:**
```python
# Dans auth_controller.py, avant chaque return
from core.log_manager import LogManager  # Supposé exister

log = LogManager()

# Après authentification réussie:
log.info(f"Connexion réussie: {username} (ID: {user_data['id']})")

# Après échec:
log.warning(f"Tentative échouée: {username} depuis IP {request_ip}")
```

---

#### 🟡 [MOYEN] Champ `last_ip` Non Utilisé
**Ligne concernée:** `core/models/user.py:16`  
**Ligne concernée:** `controllers/auth_controller.py:11-42`

```python
# user.py
last_ip = Column(String(45), nullable=True)  # Dernière adresse IP connue

# auth_controller.py
# Aucune mise à jour de last_ip pendant l'authentification
```

**Risque:**  
Impossible de détecter les connexions depuis des lieux suspects ou de mettre en place une authentification à deux facteurs basée sur la localisation.

**Recommandation:**
```python
# Dans auth_controller.py, après authentification réussie:
user.last_ip = request_ip  # À récupérer depuis la couche UI
user.last_login = datetime.utcnow()
```

---

#### 🟡 [MOYEN] Validation Faible des Entrées (Vue)
**Ligne concernée:** `ui/views/login_view.py:520-533`

```python
username = self.username.text().strip()
password = self.password.text()

# Seule vérification: non-vide
if not username:
    # ...
if not password:
    # ...
```

**Risques:**
- Pas de limite de longueur (DoS avec chaînes de 10 Mo)
- Pas de filtrage des caractères spéciaux
- Pas de normalisation Unicode (homoglyphes)

**Recommandation:**
```python
MAX_USERNAME_LENGTH = 50
MAX_PASSWORD_LENGTH = 128  # bccepte jusqu'à 72 bytes utilement

if len(username) > MAX_USERNAME_LENGTH:
    self._show_error("Nom d'utilisateur trop long")
    return
if len(password) > MAX_PASSWORD_LENGTH:
    self._show_error("Mot de passe trop long")
    return

# Normalisation Unicode pour éviter les homoglyphes
import unicodedata
username = unicodedata.normalize('NFKC', username)
```

---

#### 🟡 [MOYEN] Absence de Durée de Session et de Timeout
**Ligne concernée:** `main.py:41-46`

```python
def on_login_success(user_data, theme):
    main_window = MainWindow(user_data, theme)
    main_window.show()
    login_window.hide()

login_window.login_successful.connect(on_login_success)
```

**Risque:**  
Si l'utilisateur ferme la fenêtre de login sans se déconnecter, la session reste active indéfiniment. Pas de déconnexion automatique après inactivité.

**Recommandation:**
```python
# Implémenter un système de token avec expiration
# Stocker l'heure de dernière activité dans MainWindow
# Déconnecter automatiquement après X minutes d'inactivité
```

---

#### 🟢 [FAIBLE] Pas de Bouton "Afficher/Masquer" le Mot de Passe
**Ligne concernée:** `ui/views/login_view.py:367-388`

**Amélioration possible:**  
Ajouter un icône œil pour permettre à l'utilisateur de vérifier son mot de passe avant soumission.

---

#### 🟢 [FAIBLE] Pas de Message "Mot de passe oublié ?"
**Ligne concernée:** `ui/views/login_view.py:292-440`

**Amélioration possible:**  
Ajouter un lien vers la réinitialisation de mot de passe.

---

## 2. Analyse du Contrôleur d'Authentification

### Points Positifs
- Utilisation de SQLAlchemy ORM → pas d'injection SQL
- Vérification `user.active` avant authentification
- Migration automatique SHA256 → bcrypt
- Mise à jour de `last_login`
- Retour d'un dictionnaire sans `password_hash`

### Points Faibles
1. **Pas de rate limiting** (voir section 1.2)
2. **Pas de logging** (voir section 1.2)
3. **Pas de contexte de requête** (IP, User-Agent)

---

## 3. Analyse de la Couche Sécurité

### Points Positifs
- `bcrypt` utilisé pour le hachage (paramètres par défaut acceptables)
- Migration automatique des anciens hash SHA256
- Fonction `_is_bcrypt_hash()` pour détection propre du format

### Points d'Attention
1. **SHA256 toujours supporté** (fallback):
   - Bien que migré automatiquement, le code conserve la possibilité de vérifier SHA256
   - Risque: Si un attaquant accède à la base et modifie un hash bcrypt en SHA256 invalide, le système acceptera toute entrée

2. **Paramètres bcrypt non configurés:**
   ```python
   # core/security.py:12
   return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
   # Utilise les paramètres par défaut (work factor=4 obsolète)
   ```

**Recommandation:**
```python
# Forcer un work factor élevé (minimum 12 recommandé aujourd'hui)
return bcrypt.hashpw(
    password.encode(), 
    bcrypt.gensalt(rounds=12)
).decode()
```

---

## 4. Analyse du Modèle Utilisateur

### Points Faibles
1. **Pas de compteur de tentatives échouées:**
   ```python
   # Manque dans user.py:
   failed_login_attempts = Column(Integer, default=0)
   locked_until = Column(DateTime, nullable=True)
   ```

2. **Pas de date de dernier changement de mot de passe:**
   ```python
   password_changed_at = Column(DateTime, default=func.now())
   ```

3. **`last_ip` et `must_change_password`** existent mais ne sont **jamais mis à jour** dans le flux d'authentification actuel.

---

## 5. Flux d'Authentification Actuel

```
[UI] LoginView
   │
   ├─► [Thread] LoginWorker.run()
   │       │
   │       ├─► time.sleep(0.3)  ← Délai artificiel (amélioration faible)
   │       │
   │       └─► [Controller] AuthController.authenticate()
   │               │
   │               ├─► Query User (ORM SQLAlchemy)
   │               │
   │               ├─► verify_password(password, hash)
   │               │       │
   │               │       ├─► bcrypt.checkpw() ou SHA256
   │               │       │
   │               │       └─► Retour booléen
   │               │
   │               ├─► migrate_old_hash() si nécessaire
   │               │
   │               └─► Commit + Retour dict user_data
   │
   └─► [UI] on_authentication_finished()
           │
           ├─► État succès → Émet signal login_successful
           └─► État échec → Affiche erreur + shake animation
```

---

## 6. Recommandations Priorisées

### Actions Immédiates (P0 - Critique)
1. **Implémenter un rate limiter** sur les tentatives de connexion (5 échecs → 15 min de blocage)
2. **Ajouter un logging complet** de toutes les tentatives (succès/échecs, IP, timestamp)
3. **Mettre à jour `last_ip`** dans le contrôleur d'authentification
4. **Désactiver le fallback SHA256** après période de grâce (ex: 30 jours)

### Actions à Court Terme (P1 - Élevé)
5. Augmenter le work factor bcrypt à **12 minimum**
6. Ajouter les champs manquants au modèle User (`failed_login_attempts`, `locked_until`, `password_changed_at`)
7. Implémenter une durée de session avec timeout automatique
8. Ajouter une validation forte des entrées côté UI

### Actions à Moyen Terme (P2 - Moyen)
9. Ajouter un bouton "afficher/masquer" le mot de passe
10. Ajouter un lien "mot de passe oublié"
11. Implémenter une authentification à deux facteurs (2FA/TOTP)
12. Ajouter un CAPTCHA après 3 échecs consécutifs

### Améliorations (P3 - Faible)
13. Proposer un indicateur de force du mot de passe lors de la création de compte
14. Ajouter des raccourcis clavier (Ctrl+Q pour quitter, etc.)
15. Proposer le choix "se souvenir de moi" avec token sécurisé

---

## 7. Checklist de Conformité OWASP

| Exigence OWASP | Statut | Notes |
|---------------|--------|-------|
| A01:2021 – Broken Access Control | ⚠️ Partiel | Pas de vérification de rôle dans login (normal), mais pas de verrouillage compte |
| A02:2021 – Cryptographic Failures | ✅ | bcrypt correctement utilisé, SHA256 en cours de migration |
| A03:2021 – Injection | ✅ | ORM SQLAlchemy, pas de concaténation SQL |
| A04:2021 – Insecure Design | ❌ | Pas de rate limiting, pas de verrouillage |
| A05:2021 – Security Misconfiguration | ✅ | Pas de configuration par défaut dangereuse |
| A06:2021 – Vulnerable and Outdated Components | ⚠️ | Dépend de bcrypt version (à vérifier) |
| A07:2021 – Identification and Authentication Failures | ❌ | Bruteforce possible, pas de 2FA |
| A08:2021 – Software and Data Integrity Failures | ✅ | Pas de validation de signature détectée |
| A09:2021 – Security Logging and Monitoring Failures | ❌ | Pas de logging des authentifications |
| A10:2021 – Server-Side Request Forgery | N/A | Pas de SSRF dans login |

---

## 8. Code à Risque Identifié

### A. `controllers/auth_controller.py` — Absence de Protection
```python
def authenticate(self, username: str, password: str):
    # ❌ Pas de vérification préalable (rate limit, lockout)
    # ❌ Pas de log de la tentative
    # ❌ Pas de tracking IP
    try:
        with SessionLocal() as session:
            user = session.query(User).filter(
                User.username == username
            ).first()
            # ...
```

### B. `ui/views/login_view.py` — Délai Artificiel
```python
def run(self):
    try:
        time.sleep(0.3)  # ← Delai cosmétique, pas de protection réelle
        user_data = self.auth_controller.authenticate(
            self.username, 
            self.password
        )
        self.finished.emit(user_data)
    except Exception as e:
        self.error.emit(str(e))
```

**Note:** Ce délai de 0.3s peut aider contre les attaques à très haut débit, mais ne remplace pas un rate limiter proper. À conserver comme défense en profondeur.

---

## 9. Conclusion

La vue Login présente une **interface utilisateur bien réalisée** et des **bases de sécurité correctes** (bcrypt, ORM, thread async). Cependant, elle souffre de **lacunes critiques** en matière de protection contre les attaques par force brute et de journalisation.

**Priorité absolue:** Implémenter un mécanisme de limitation du taux de requêtes et un système de journalisation des authentifications.

**Indicateur de risque global:**  
🔴 **ÉLEVÉ** — L'application est vulnérable aux attaques par credential stuffing et brute force sans détection possible.