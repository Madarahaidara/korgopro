# Guide : lancer Korgo Pro Web (Windows)

## Etat actuel (01/10/2026)

- **Node.js v22.17.0** installe dans `C:\tools\nodejs` (ajoute au PATH utilisateur).
- Dependances deja installees (`web/node_modules`).
- Le serveur Vite **tourne** sur http://localhost:5173

## Lancer l'application

Option A — double-clic (recommande) :
- `web/LANCER-WEB.bat` pour demarrer.
- `web/ARRETER-WEB.bat` pour arreter.

Option B — terminal :
```powershell
cd c:\Users\COMTECH-DESKONE\korgopro\web
npm run dev
```

Puis ouvrez http://localhost:5173

## Se connecter

- Utilisez un compte **Supabase Auth existant** (meme email que dans
  `public.users`, `active = true`).
- `web/.env` est deja configure (URL + cle publique du projet
  `tvvvgrqzcjtzdqxhnxtc`).

## Probleme : ERR_CONNECTION_REFUSED

= le serveur Vite ne tourne pas. Relancez `LANCER-WEB.bat` et gardez la
fenetre ouverte (fermer la fenetre = arreter le serveur).

## Probleme : node / npm introuvable

1. Verifiez `C:\tools\nodejs\node.exe`.
2. Si absent : installez Node.js LTS depuis https://nodejs.org/
   (tout par defaut) puis **fermez / rouvrez VS Code**.
3. Verifiez avec `node --version` et `npm --version`.

## Problemes frequents

| Symptome | Cause probable | Solution |
|---|---|---|
| `ERR_CONNECTION_REFUSED` | Serveur Vite non demarre | Relancer `LANCER-WEB.bat` |
| `node` introuvable | PATH non recharge | Rouvrir VS Code / redemarrer Windows |
| `npm install` echoue | Pas d'Internet / proxy | Verifier la connexion, reessayer |
| Port 5173 occupe | Un autre Vite tourne | `ARRETER-WEB.bat` puis relancer |
| Page blanche apres login | Compte sans profil `public.users` actif | Verifier email + `active=true` + RLS |

