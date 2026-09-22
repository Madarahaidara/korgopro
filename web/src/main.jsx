import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { StoreProvider } from './context/StoreContext';
import App from './App';
import './index.css';
import { db } from './api/db';
import { seedDatabase } from './api/seed';

/** Monte l'application React dans le conteneur `#root`. */
function mount() {
  const container = document.getElementById('root');
  container.innerHTML = '';
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <BrowserRouter>
        <AuthProvider>
          <StoreProvider>
            <App />
          </StoreProvider>
        </AuthProvider>
      </BrowserRouter>
    </React.StrictMode>
  );
}

/**
 * Séquence de démarrage.
 *
 * IMPORTANT (mode Supabase) : aucune donnée n'est lisible AVANT la connexion.
 * Le rôle `anon` est volontairement privé de tout droit sur les tables (voir
 * supabase_rls_policies.sql) : hydrater à ce stade échouerait systématiquement
 * avec « permission denied for table … » et l'application repartirait sur le
 * cache localStorage en annonçant à tort une synchronisation réussie.
 *
 * Le téléchargement des données est donc déclenché par AuthContext, juste
 * après le signInWithPassword (rôle `authenticated`).
 *
 * En mode local, on injecte le jeu de démonstration au premier lancement.
 */
function boot() {
  if (db.mode === 'local') {
    try {
      if (!localStorage.getItem('korgo_pro_seeded')) {
        seedDatabase();
        localStorage.setItem('korgo_pro_seeded', '1');
      }
    } catch (e) {
      console.error('Erreur au seed des données.', e);
    }
  }

  mount();
}

boot();