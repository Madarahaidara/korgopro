import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './context/AuthContext';
import './index.css';

// Les services métier Rust ne sont pas encore migrés. L'authentification
// Supabase utilise le client public et fonctionne aussi en mode navigateur.
const tauriReady = () => typeof window !== 'undefined' && !!window.__TAURI_INTERNALS__;

if (!tauriReady()) {
  console.info('[tpg] Mode navigateur : les services métier Rust ne sont pas disponibles.');
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
);
