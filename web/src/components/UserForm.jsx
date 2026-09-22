// ============================================================================
// Formulaire de création / édition d'un utilisateur.
//
// ARCHITECTURE : Supabase Auth est la source de vérité. La sauvegarde passe
// exclusivement par les RPC `admin_*` (voir web/src/api/authApi.js) :
//   - le compte (email + mot de passe) vit dans auth.users ;
//   - le profil public.users est alimenté par le trigger PostgreSQL ;
//   - le navigateur n'écrit JAMAIS la table users directement.
//
// Conséquences :
//   - l'email est OBLIGATOIRE (identifiant de connexion Supabase Auth) ;
//   - le mot de passe est requis à la création (6 caractères minimum,
//     contrôlé aussi par la RPC `admin_create_user`) ;
//   - en édition, un mot de passe laissé vide conserve l'actuel.
// ============================================================================
import { useState } from 'react';
import { saveUser } from '../api/authApi';
import { Modal } from './ui';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function UserForm({ user, roles, onSave, onClose }) {
  const editing = Boolean(user);
  const [form, setForm] = useState({
    username: user?.username || '',
    email: user?.email || '',
    password: '',
    role: user?.role || 'CAISSIER',
    active: user?.active !== false,
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const set = (k) => (e) =>
    setForm({
      ...form,
      [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value,
    });

  const save = async (e) => {
    e.preventDefault();
    setError('');

    const email = form.email.trim().toLowerCase();
    if (!email || !EMAIL_RE.test(email)) {
      setError("L'email est obligatoire : Supabase Auth l'utilise comme identifiant de connexion.");
      return;
    }
    if (!editing && form.password.length < 6) {
      setError('Mot de passe requis (6 caractères minimum).');
      return;
    }
    if (editing && form.password && form.password.length < 6) {
      setError('Nouveau mot de passe trop court (6 caractères minimum).');
      return;
    }

    setSaving(true);
    try {
      await saveUser({
        id: user?.id,
        username: form.username.trim(),
        email,
        password: form.password,
        role: form.role,
        active: form.active,
      });
      onSave();
    } catch (err) {
      setError(err?.message || 'Enregistrement impossible.');
      setSaving(false);
    }
  };

  return (
    <Modal
      title={editing ? 'Modifier l’utilisateur' : 'Nouvel utilisateur'}
      onClose={onClose}
      width={520}
    >
      <form onSubmit={save}>
        {error && <div className="login-error" style={{ marginBottom: 12 }}>{error}</div>}

        <div className="form-grid">
          <div className="field">
            <label>Nom d'utilisateur</label>
            <input
              className="input"
              value={form.username}
              onChange={set('username')}
              placeholder="Ex : jdupont"
            />
          </div>
          <div className="field">
            <label>Rôle</label>
            <select className="select" value={form.role} onChange={set('role')}>
              {(roles || ['CAISSIER']).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="field">
          <label>Email *</label>
          <input
            className="input"
            type="email"
            value={form.email}
            onChange={set('email')}
            placeholder="utilisateur@exemple.com"
            autoComplete="off"
          />
        </div>

        <div className="field">
          <label>{editing ? 'Nouveau mot de passe (laisser vide pour conserver)' : 'Mot de passe *'}</label>
          <input
            className="input"
            type="password"
            value={form.password}
            onChange={set('password')}
            placeholder={editing ? '••••••' : '6 caractères minimum'}
            autoComplete="new-password"
          />
        </div>

        <div className="field">
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.active} onChange={set('active')} />
            Compte actif (l'utilisateur peut se connecter)
          </label>
        </div>

        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>Annuler</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Enregistrement…' : editing ? 'Enregistrer' : 'Créer le compte'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
