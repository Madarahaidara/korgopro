import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Icon from '../components/Icon';
import { isSupabaseConfigured } from '../api/supabase';
import { SessionConflictError, describeOtherSession } from '../api/sessionApi';

const DEMO_ACCOUNTS = [
  { username: 'admin', role: 'ADMIN' },
  { username: 'gestionnaire', role: 'GESTIONNAIRE' },
  { username: 'caissier', role: 'CAISSIER' },
];

const FEATURES = ['Gestion des ventes', 'Suivi de stock', 'Trésorerie', 'Proformas & devis'];

export default function Login() {
  const { loginUser, settings, user, restoring, sessionNotice, clearSessionNotice } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  // Session unique : un autre appareil est deja connecte a ce compte.
  const [conflict, setConflict] = useState(null);

  // Session déjà active (restaurée au refresh) : retour à l'application.
  useEffect(() => {
    if (user && !restoring) navigate('/', { replace: true });
  }, [user, restoring, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    await connect({ force: false });
  };

  const connect = async (options) => {
    setError('');
    setConflict(null);
    clearSessionNotice();
    setLoading(true);
    try {
      const authenticated = await loginUser(username.trim(), password, options);
      if (authenticated) navigate('/');
      else setError('Identifiants invalides ou compte désactivé.');
    } catch (err) {
      if (err instanceof SessionConflictError || err?.code === 'SESSION_ACTIVE') {
        // Compte deja ouvert ailleurs : on propose de reprendre la main.
        setConflict({ message: err.message, other: err.other });
      } else {
        setError(err.message || 'Connexion impossible.');
      }
    } finally {
      setLoading(false);
    }
  };

  // L'utilisateur assume de fermer la session de l'autre appareil.
  const takeOver = async () => {
    setLoading(true);
    await connect({ force: true });
    setLoading(false);
  };

  const fill = (uname) => {
    setUsername(uname);
    setPassword(uname);
    setError('');
    setConflict(null);
  };

  return (
    <div className="login-page">
      <div className="login-wrap">
        <div className="login-left">
          <div className="login-icon">
            <img src="/icons/apple-touch-icon.png" width="62" height="62" alt="Korgo Pro" />
          </div>
          <div className="login-brand-title">{settings.company_name || 'KORGO PRO'}</div>
          <div className="login-brand-sub">Gestion d'entreprise tout-en-un</div>
          <div style={{ flex: 1, marginTop: 32 }}>
            {FEATURES.map((f) => (
              <div className="login-feature" key={f}>
                <span><Icon name="check" size={14} /></span>{f}
              </div>
            ))}
          </div>
          <div className="login-version" style={{ color: 'rgba(255,255,255,0.6)' }}>Version web 0.1.0</div>
        </div>

        <div className="login-right">
          <div className="form-title">Connexion</div>
          <div className="form-subtitle">Connectez-vous pour accéder à votre espace</div>

          {error && <div className="login-error">{error}</div>}

          {/* Session unique : le compte est déjà ouvert sur un autre appareil. */}
          {!error && !conflict && sessionNotice && (
            <div className="login-error">{sessionNotice}</div>
          )}

          <form onSubmit={submit}>
            <div className="field">
              <label className="login-field-label">{isSupabaseConfigured() ? 'Email Supabase Auth' : "Nom d'utilisateur"}</label>
              <input
                className="login-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
              />
            </div>
            <div className="field">
              <label className="login-field-label">Mot de passe</label>
              <input
                className="login-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? 'Connexion…' : 'Se connecter'}
            </button>
          </form>

          {/* Refus « deja connecte ailleurs » : l'utilisateur tranche. */}
          {conflict && (
            <>
              <div className="login-error">
                {conflict.message}
                <br />
                <strong>Session en cours :</strong> {describeOtherSession(conflict.other)}
              </div>
              <button className="login-btn" type="button" onClick={takeOver} disabled={loading}>
                {loading
                  ? 'Deconnexion de l\u2019autre appareil\u2026'
                  : 'Deconnecter l\u2019autre appareil et se connecter'}
              </button>
            </>
          )}

          <div className="login-divider" />
          {!isSupabaseConfigured() && <>
          <div className="login-demo-title">Comptes de démonstration</div>
          {DEMO_ACCOUNTS.map((a) => (
            <button key={a.username} className="btn btn-sm login-demo-btn" onClick={() => fill(a.username)}>
              {a.username} <span className="badge badge-gray">{a.role}</span>
            </button>
          ))}
          <p className="login-hint">Mot de passe = nom d'utilisateur</p>
          </>}
          {isSupabaseConfigured() && <p className="login-hint">Compte Supabase Auth requis, associé au même email dans le logiciel. Connexion en lecture seule.</p>}
          <div className="login-version">© {new Date().getFullYear()} Korgo Pro</div>
        </div>
      </div>
    </div>
  );
}