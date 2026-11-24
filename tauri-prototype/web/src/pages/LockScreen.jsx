import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ActionButton, InlineMessage } from '../components/erp';
import BrandLogo from '../components/BrandLogo';
import Icon from '../components/Icon';

export default function LockScreen() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const unlock = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await login(user?.email || '', password);
      if (!result.ok) {
        setError(result.message || 'Déverrouillage refusé.');
        return;
      }
      navigate('/dashboard', { replace: true });
    } catch (reason) {
      setError(reason.message || 'Le service Supabase est indisponible.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="erp-standalone">
      <div className="erp-lock-card">
        <BrandLogo className="erp-brand-mark" alt="Logo Korgo Pro" />
        <span className="erp-lock-symbol"><Icon name="lock" size={28} /></span>
        <h1>Session verrouillée</h1>
        <p>Confirmez votre mot de passe Supabase pour reprendre votre session.</p>
        <InlineMessage tone="danger">{error}</InlineMessage>
        <form className="erp-login-form" onSubmit={unlock}>
          <label className="erp-field"><span>Compte</span><input value={user?.email || 'Non connecté'} readOnly /></label>
          <label className="erp-field"><span>Mot de passe Supabase</span><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <ActionButton type="submit" disabled={loading}>{loading ? 'Vérification…' : 'Déverrouiller la session'}</ActionButton>
        </form>
        <Link to="/login" className="erp-text-link">Changer de compte</Link>
      </div>
    </div>
  );
}
