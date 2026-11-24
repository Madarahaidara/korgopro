import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Input, Card, Text, Spinner } from '../components/ui';
import BrandLogo from '../components/BrandLogo';
import { isSupabaseConfigured } from '../api/supabase';

export default function Login() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login: doLogin, authError } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await doLogin(identifier, password);
      if (res.ok) {
        navigate('/dashboard', { replace: true });
      } else {
        setError(res.message || 'Connexion refusée');
      }
    } catch (err) {
      setError(err.message || 'Erreur de connexion');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <Card className="login-card">
        <div className="login-logo">
          <BrandLogo className="logo-icon" alt="Logo Korgo Pro" />
          <h1>Korgo Pro</h1>
          <span className="tagline">Gestion commerciale · Tauri</span>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="identifier">Email ou nom d’utilisateur</label>
            <Input
              id="identifier"
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="Email ou nom d’utilisateur"
              autoComplete="username"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Mot de passe</label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>

          {(error || authError) && <div className="alert alert-error">{error || authError}</div>}

          <Button
            type="submit"
            className="btn-primary"
            loading={loading}
            disabled={loading}
          >
            {loading ? <Spinner /> : 'Se connecter'}
          </Button>
        </form>

        <p className="text-muted mt-6 text-center">
          {isSupabaseConfigured
            ? 'Connexion sécurisée via Supabase Auth et accès métier limité à votre entreprise.'
            : 'Supabase non configuré. Renseignez les paramètres publics dans web/.env.'}
        </p>
      </Card>
    </div>
  );
}
