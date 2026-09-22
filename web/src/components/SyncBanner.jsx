// ============================================================================
// Bandeau d'état de la synchronisation Supabase
//
// Affiche en haut du contenu :
//   - le mode actif (Supabase / local) ;
//   - l'état de la dernière écriture (en cours, erreur, succès) ;
//   - un guide de configuration si la clé publique est absente.
//
// En mode Supabase, l'état se met à jour automatiquement grâce à
// `onSyncStatus()` (voir api/db.js) : aucun rafraîchissement manuel.
// ============================================================================
import { useEffect, useState } from 'react';
import { onSyncStatus, syncState, flush } from '../api/db';
import { supabaseProjectRef } from '../api/supabase';
import Icon from './Icon';

/** Formate une heure ISO en HH:MM:SS. */
function timeOf(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('fr-FR');
}

export default function SyncBanner() {
  const [state, setState] = useState({ ...syncState });
  const [hidden, setHidden] = useState(false);

  useEffect(() => onSyncStatus(setState), []);

  // En mode local sans configuration : rappel de configuration discret mais
  // permanent (l'utilisateur doit savoir que ses données restent locales).
  const local = state.mode !== 'supabase';

  if (hidden) return null;

  if (local) {
    return (
      <div className="sync-banner warn">
        <Icon name="alert" size={16} />
        <span>
          <b>Mode local</b> — Supabase n'est pas configuré : les données sont
          stockées dans ce navigateur uniquement.
        </span>
        <span className="spacer" />
        <span style={{ fontSize: 12 }}>
          Renseignez <code>web/.env</code> (<code>VITE_SUPABASE_URL</code> +{' '}
          <code>VITE_SUPABASE_ANON_KEY</code>) puis redémarrez{' '}
          <code>npm run dev</code>.
        </span>
        <button className="btn btn-sm" onClick={() => setHidden(true)}>Masquer</button>
      </div>
    );
  }

  const error = state.lastError;
  const pending = state.pending > 0;
  const cls = error ? 'err' : pending ? 'warn' : 'ok';

  return (
    <div className={`sync-banner ${cls}`}>
      <Icon name={error ? 'alert' : 'globe'} size={16} />
      <span>
        <b>Supabase</b>
        {supabaseProjectRef() ? ` · ${supabaseProjectRef()}` : ''} —{' '}
        {error
          ? `synchronisation en échec : ${error}`
          : pending
            ? `écriture en cours (${state.pending} collection(s))…`
            : 'données synchronisées'}
      </span>
      <span className="spacer" />
      <span style={{ fontSize: 12 }}>Dernière synchro : {timeOf(state.lastSyncAt)}</span>
      <button
        className="btn btn-sm"
        onClick={() => flush()}
        disabled={!pending && !error}
        title="Réessayer immédiatement l'écriture des données en attente"
      >
        <Icon name="refresh" size={14} style={{ verticalAlign: '-2px' }} /> Synchroniser
      </button>
      {error && (
        <button className="btn btn-sm" onClick={() => setHidden(true)}>Masquer</button>
      )}
    </div>
  );
}