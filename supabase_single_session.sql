-- ============================================================================
-- supabase_single_session.sql
--
-- REGLE METIER : UN SEUL APPAREIL CONNECTE A LA FOIS PAR UTILISATEUR.
--
-- Pourquoi ?
--   Un meme compte (ex. « caissier ») pouvait etre ouvert simultanement sur le
--   logiciel de bureau, la version web et l'application mobile : ventes en
--   double, caisse incoherente, aucun moyen de savoir qui a fait quoi.
--
-- COMMENT CELA FONCTIONNE
-- ---------------------------------------------------------------------------
--   * chaque session Supabase Auth possede un identifiant unique, present dans
--     l'access token (`session_id`) ET dans `auth.sessions.id` : il sert de cle
--     de session. Il est LU DANS LE JWT cote serveur, donc NON FALSIFIABLE par
--     le client (le desktop, qui n'a pas de JWT, transmet un UUID genere) ;
--   * `public.user_sessions` memorise la session OUVERTE de chaque compte, avec
--     un battement de coeur (`last_seen_at`) envoye par les applications ;
--   * un INDEX UNIQUE PARTIEL (`user_id` ou `ended_at IS NULL`) garantit au
--     niveau de la base qu'une deuxieme session ne peut pas s'ouvrir : la
--     protection ne depend pas du code applicatif ;
--   * une session sans battement depuis `session_timeout()` (15 min) est
--     consideree comme abandonnee (telephone eteint, navigateur ferme, panne) :
--     elle est liberee automatiquement a la connexion suivante ;
--   * les RPC d'ecriture (`app_create_sale`, ...) refusent toute operation
--     issue d'une session reprendue ailleurs (voir supabase_mobile_rpc.sql).
--
-- REPRISE (« l'autre appareil »)
-- ---------------------------------------------------------------------------
--   Une connexion sur un compte deja ouvert est REFUSEE, avec l'heure et le
--   type d'appareil concerne. L'utilisateur peut choisir explicitement de
--   reprendre la main (`p_force = true`) : l'autre session est alors fermée et
--   se deconnecte d'elle-meme au battement suivant (<= 60 s).
--   Un administrateur dispose de `public.admin_revoke_sessions(email)`.
--
-- LIMITES (assumees)
-- ---------------------------------------------------------------------------
--   * l'APPLICATION METIER est bloquee (connexion refusee + ecritures refusees)
--     mais pas la LECTURE PostgREST d'une session deja ouverte qui ignorerait
--     la consigne : son jeton reste valide jusqu'a expiration (1 h). Les
--     clients officiels se deconnectent, eux, en moins d'une minute ;
--   * un client ANCIEN (APK non mis a jour) n'appelle pas les RPC de session :
--     il n'est donc pas suivi et reste autorise (compatibilite ascendante).
--     Tout client a jour est, lui, verrouille.
--
-- APPLICATION
--   python _apply_single_session.py      (puis python _apply_mobile_rpc.py)
--   ou Dashboard Supabase -> SQL Editor. Idempotent.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1) Table des sessions applicatives
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_sessions (
    session_id   uuid PRIMARY KEY,
    user_id      uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    app_user_id  integer,
    username     text,
    role         text,
    platform     text NOT NULL DEFAULT 'inconnu',
    device       text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    ended_at     timestamptz,
    ended_reason text
);

-- Colonnes historiques (base deja migree avec une version precedente).
ALTER TABLE public.user_sessions ADD COLUMN IF NOT EXISTS ended_reason text;

COMMENT ON TABLE public.user_sessions IS
    'Sessions applicatives ouvertes : une seule par utilisateur (verrou '
    'multi-appareils). Alimentee uniquement par les RPC app_* / app_security.*';

-- AU PLUS UNE session ouverte par utilisateur : garantie par la BASE.
CREATE UNIQUE INDEX IF NOT EXISTS user_sessions_open_unique_idx
    ON public.user_sessions (user_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS user_sessions_last_seen_idx
    ON public.user_sessions (last_seen_at) WHERE ended_at IS NULL;

-- Aucun acces direct : tout passe par les fonctions SECURITY DEFINER.
REVOKE ALL ON TABLE public.user_sessions FROM PUBLIC;
REVOKE ALL ON TABLE public.user_sessions FROM anon;
REVOKE ALL ON TABLE public.user_sessions FROM authenticated;
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;


-- ----------------------------------------------------------------------------
-- 2) Helpers `app_security` (schema NON expose par l'API PostgREST)
-- ----------------------------------------------------------------------------

-- Duree sans battement au-dela de laquelle une session est reputee abandonnee.
CREATE OR REPLACE FUNCTION app_security.session_timeout()
RETURNS interval
LANGUAGE sql IMMUTABLE
AS $$ SELECT interval '15 minutes' $$;

REVOKE ALL ON FUNCTION app_security.session_timeout() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_security.session_timeout() TO authenticated;

-- Libelle lisible d'une plateforme (messages utilisateur).
CREATE OR REPLACE FUNCTION app_security.platform_label(p_platform text)
RETURNS text
LANGUAGE sql IMMUTABLE
AS $$
  SELECT CASE LOWER(BTRIM(COALESCE(p_platform, '')))
           WHEN 'mobile'  THEN 'application mobile'
           WHEN 'web'     THEN 'version web'
           WHEN 'desktop' THEN 'logiciel de bureau'
           ELSE 'appareil inconnu'
         END
$$;

REVOKE ALL ON FUNCTION app_security.platform_label(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_security.platform_label(text) TO authenticated;

-- Identifiant de la session DE L'APPELANT : lu dans le JWT (claim
-- `session_id`, identique a auth.sessions.id), donc NON falsifiable.
-- NULL si le jeton ne le porte pas (client ancien) : les appelants tolerent.
CREATE OR REPLACE FUNCTION app_security.current_session_id()
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, auth
AS $$ SELECT NULLIF(auth.jwt() ->> 'session_id', '')::uuid $$;

REVOKE ALL ON FUNCTION app_security.current_session_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_security.current_session_id() TO authenticated;

-- La session de l'appelant est-elle OUVERTE ?
--   true  : ouverte, OU inconnue (client ancien -> on laisse passer) ;
--   false : fermee (reprise par un autre appareil, deconnexion, expiration).
CREATE OR REPLACE FUNCTION app_security.session_is_active()
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT COALESCE(
           (SELECT s.ended_at IS NULL
              FROM public.user_sessions s
             WHERE s.session_id = app_security.current_session_id()),
           true)
$$;

REVOKE ALL ON FUNCTION app_security.session_is_active() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_security.session_is_active() TO authenticated;

-- Identifiant auth.users a partir d'un email (chemin desktop, sans JWT).
CREATE OR REPLACE FUNCTION app_security.auth_user_id(p_email text)
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT a.id FROM auth.users a
   WHERE LOWER(a.email) = LOWER(BTRIM(COALESCE(p_email, '')))
   LIMIT 1
$$;

REVOKE ALL ON FUNCTION app_security.auth_user_id(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.auth_user_id(text) FROM anon;
REVOKE ALL ON FUNCTION app_security.auth_user_id(text) FROM authenticated;

-- Ferme les sessions abandonnees d'un utilisateur (battement trop ancien).
CREATE OR REPLACE FUNCTION app_security.expire_stale_sessions(p_user_id uuid)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_closed integer := 0;
BEGIN
    UPDATE public.user_sessions s
       SET ended_at = NOW(),
           ended_reason = 'EXPIRE'
     WHERE s.user_id = p_user_id
       AND s.ended_at IS NULL
       AND s.last_seen_at < NOW() - app_security.session_timeout();
    GET DIAGNOSTICS v_closed = ROW_COUNT;
    RETURN v_closed;
END;
$$;

REVOKE ALL ON FUNCTION app_security.expire_stale_sessions(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.expire_stale_sessions(uuid) FROM anon;
REVOKE ALL ON FUNCTION app_security.expire_stale_sessions(uuid) FROM authenticated;


-- Description JSON d'une session (messages + ecrans d'administration).
CREATE OR REPLACE FUNCTION app_security.session_json(s public.user_sessions)
RETURNS jsonb
LANGUAGE sql STABLE
AS $$
  SELECT CASE
           WHEN s.session_id IS NULL THEN NULL
           ELSE jsonb_build_object(
             'session_id', s.session_id,
             'platform', s.platform,
             'platform_label', app_security.platform_label(s.platform),
             'device', s.device,
             'username', s.username,
             'role', s.role,
             'started_at', s.created_at,
             'last_seen_at', s.last_seen_at,
             'since_minutes',
               GREATEST(0, (EXTRACT(EPOCH FROM (NOW() - s.created_at)) / 60)::int),
             'idle_minutes',
               GREATEST(0, (EXTRACT(EPOCH FROM (NOW() - s.last_seen_at)) / 60)::int),
             'timeout_minutes',
               (EXTRACT(EPOCH FROM app_security.session_timeout()) / 60)::int,
             'ended_at', s.ended_at,
             'ended_reason', s.ended_reason)
         END
$$;

REVOKE ALL ON FUNCTION app_security.session_json(public.user_sessions) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.session_json(public.user_sessions) FROM anon;
REVOKE ALL ON FUNCTION app_security.session_json(public.user_sessions) FROM authenticated;

-- Refus « compte deja connecte ailleurs » : message + details exploitables
-- par l'interface (bouton « Deconnecter l'autre appareil »).
CREATE OR REPLACE FUNCTION app_security.session_conflict(
    s public.user_sessions,
    p_session_id uuid)
RETURNS jsonb
LANGUAGE sql STABLE
AS $$
  SELECT jsonb_build_object(
    'ok', false,
    'code', 'SESSION_ACTIVE',
    'session_id', p_session_id,
    'can_force', true,
    'other', app_security.session_json(s),
    'message',
      'Ce compte est deja connecte sur ' || app_security.platform_label(s.platform)
      || CASE WHEN COALESCE(BTRIM(s.device), '') <> ''
              THEN ' (' || s.device || ')' ELSE '' END
      || ' depuis '
      || GREATEST(0, (EXTRACT(EPOCH FROM (NOW() - s.created_at)) / 60)::int)::text
      || ' min (derniere activite il y a '
      || GREATEST(0, (EXTRACT(EPOCH FROM (NOW() - s.last_seen_at)) / 60)::int)::text
      || ' min). Choisissez « Deconnecter l''autre appareil » pour continuer '
      || 'ici, ou patientez '
      || ((EXTRACT(EPOCH FROM app_security.session_timeout()) / 60)::int)::text
      || ' min sans activite de l''autre cote.'
  )
$$;

REVOKE ALL ON FUNCTION app_security.session_conflict(public.user_sessions, uuid)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.session_conflict(public.user_sessions, uuid)
    FROM anon;
REVOKE ALL ON FUNCTION app_security.session_conflict(public.user_sessions, uuid)
    FROM authenticated;

-- Refus unitaire (reprise impossible ou compte inconnu).
CREATE OR REPLACE FUNCTION app_security.session_refused(
    p_code text,
    p_message text,
    p_session_id uuid DEFAULT NULL)
RETURNS jsonb
LANGUAGE sql IMMUTABLE
AS $$
  SELECT jsonb_build_object('ok', false, 'code', p_code, 'message', p_message,
                            'session_id', p_session_id)
$$;

REVOKE ALL ON FUNCTION app_security.session_refused(text, text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.session_refused(text, text, uuid) FROM anon;
REVOKE ALL ON FUNCTION app_security.session_refused(text, text, uuid)
    FROM authenticated;


-- ----------------------------------------------------------------------------
-- 3) Coeur du verrou : ouverture / battement / fermeture
--
--    Ces fonctions prennent l'utilisateur en PARAMETRE : elles ne sont donc
--    PAS accessibles a `authenticated` (sinon un compte pourrait verrouiller
--    ou liberer la session d'un autre). Seul le proprietaire (postgres) et
--    `service_role` les executent, via les RPC publiques ci-dessous.
-- ----------------------------------------------------------------------------

-- Ouvre (ou re-ouvre) la session p_session_id pour p_user_id.
--   * p_force = false : refus si un AUTRE appareil detient deja le verrou ;
--   * p_force = true  : l'autre session est fermee au profit de celle-ci.
CREATE OR REPLACE FUNCTION app_security.session_open(
    p_user_id    uuid,
    p_session_id uuid,
    p_platform   text    DEFAULT NULL,
    p_device     text    DEFAULT NULL,
    p_force      boolean DEFAULT false)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_profile      record;
    v_other        public.user_sessions%ROWTYPE;
    v_platform     text;
    v_platform_set boolean;
    v_device       text := NULLIF(BTRIM(COALESCE(p_device, '')), '');
BEGIN
    IF p_user_id IS NULL THEN
        RETURN app_security.session_refused('UNKNOWN_USER',
            'Compte Supabase Auth introuvable pour cet identifiant.', p_session_id);
    END IF;

    -- Aucun identifiant de session (jeton Supabase Auth ancien) : on ne peut
    -- pas verrouiller sans risque de bloquer tout le monde -> tolerer.
    IF p_session_id IS NULL THEN
        RETURN jsonb_build_object('ok', true, 'tracked', false,
            'code', 'NO_SESSION_ID',
            'message', 'Session sans identifiant : verrou multi-appareils ignore.');
    END IF;

    SELECT u.id, u.username, UPPER(BTRIM(COALESCE(u.role, ''))) AS role
      INTO v_profile
      FROM public.users u
      JOIN auth.users a ON LOWER(a.email) = LOWER(u.email)
     WHERE a.id = p_user_id
       AND u.active
     LIMIT 1;

    IF v_profile.id IS NULL THEN
        RETURN app_security.session_refused('INACTIVE_PROFILE',
            'Profil actif introuvable pour ce compte (compte desactive ?).',
            p_session_id);
    END IF;

    -- Liberation des sessions abandonnees (appareil eteint sans deconnexion).
    PERFORM app_security.expire_stale_sessions(p_user_id);

    v_platform_set := COALESCE(BTRIM(COALESCE(p_platform, '')), '') <> '';
    v_platform := CASE WHEN v_platform_set THEN BTRIM(p_platform) ELSE 'inconnu' END;

    BEGIN
        -- Re-ouverture de MA session (redemarrage de l'application, retour au
        -- premier plan, deverrouillage du poste) : la contrainte de cle
        -- primaire absorbe la ligne existante.
        INSERT INTO public.user_sessions
            (session_id, user_id, app_user_id, username, role, platform, device,
             created_at, last_seen_at, ended_at, ended_reason)
        VALUES
            (p_session_id, p_user_id, v_profile.id, v_profile.username,
             v_profile.role, v_platform, v_device,
             NOW(), NOW(), NULL, NULL)
        ON CONFLICT (session_id) DO UPDATE
            SET last_seen_at = NOW(),
                ended_at     = NULL,
                ended_reason = NULL,
                app_user_id  = EXCLUDED.app_user_id,
                username     = EXCLUDED.username,
                role         = EXCLUDED.role,
                platform     = CASE WHEN v_platform_set
                                    THEN EXCLUDED.platform
                                    ELSE user_sessions.platform END,
                device       = COALESCE(EXCLUDED.device, user_sessions.device);
    EXCEPTION WHEN unique_violation THEN
        -- L'index unique partiel revele que le compte est DEJA ouvert ailleurs.
        SELECT s.* INTO v_other
          FROM public.user_sessions s
         WHERE s.user_id = p_user_id
           AND s.ended_at IS NULL
         LIMIT 1;

        IF NOT p_force THEN
            RETURN app_security.session_conflict(v_other, p_session_id);
        END IF;

        UPDATE public.user_sessions
           SET ended_at = NOW(),
               ended_reason = 'REPRISE_PAR_' || UPPER(COALESCE(v_platform, 'INCONNU'))
         WHERE user_id = p_user_id
           AND ended_at IS NULL
           AND session_id <> p_session_id;

        INSERT INTO public.user_sessions
            (session_id, user_id, app_user_id, username, role, platform, device,
             created_at, last_seen_at)
        VALUES
            (p_session_id, p_user_id, v_profile.id, v_profile.username,
             v_profile.role, v_platform, v_device, NOW(), NOW());

        RETURN jsonb_build_object('ok', true, 'taking_over', true,
            'tracked', true, 'session_id', p_session_id, 'platform', v_platform,
            'other', app_security.session_json(v_other));
    END;

    RETURN jsonb_build_object('ok', true, 'tracked', true,
        'session_id', p_session_id, 'platform', v_platform,
        'started_at', NOW());
END;
$$;

REVOKE ALL ON FUNCTION app_security.session_open(uuid, uuid, text, text, boolean)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.session_open(uuid, uuid, text, text, boolean)
    FROM anon;
REVOKE ALL ON FUNCTION app_security.session_open(uuid, uuid, text, text, boolean)
    FROM authenticated;
GRANT EXECUTE ON FUNCTION app_security.session_open(uuid, uuid, text, text, boolean)
    TO service_role;


-- Battement de coeur : prolonge la session si elle est toujours la sienne.
CREATE OR REPLACE FUNCTION app_security.session_touch(
    p_session_id uuid,
    p_user_id    uuid DEFAULT NULL,
    p_platform   text DEFAULT NULL,
    p_device     text DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_row public.user_sessions%ROWTYPE;
    v_res jsonb;
BEGIN
    IF p_session_id IS NULL THEN
        RETURN jsonb_build_object('ok', true, 'active', true, 'tracked', false,
                                  'code', 'NO_SESSION_ID');
    END IF;

    UPDATE public.user_sessions s
       SET last_seen_at = NOW(),
           platform = COALESCE(NULLIF(BTRIM(COALESCE(p_platform, '')), ''), s.platform),
           device   = COALESCE(NULLIF(BTRIM(COALESCE(p_device, '')), ''), s.device)
     WHERE s.session_id = p_session_id
       AND s.ended_at IS NULL;

    IF FOUND THEN
        RETURN jsonb_build_object('ok', true, 'active', true, 'tracked', true,
                                  'session_id', p_session_id);
    END IF;

    SELECT s.* INTO v_row
      FROM public.user_sessions s
     WHERE s.session_id = p_session_id;

    IF v_row.session_id IS NULL AND p_user_id IS NULL THEN
        -- Plus aucune trace de cette session : on ne peut rien conclure.
        RETURN jsonb_build_object('ok', true, 'active', true, 'tracked', false,
                                  'code', 'UNTRACKED');
    END IF;

    IF v_row.session_id IS NOT NULL AND p_user_id IS NULL THEN
        RETURN jsonb_build_object('ok', true, 'active', false, 'tracked', true,
            'code', 'SESSION_CLOSED', 'reason', v_row.ended_reason,
            'session', app_security.session_json(v_row),
            'message', 'Votre session a ete fermee : ce compte est utilise '
                       'ailleurs. Reconnectez-vous pour reprendre la main.');
    END IF;

    -- Session inconnue ou fermee : on retente l'ouverture SANS forcer, pour
    -- reprendre place si le verrou est libre (l'ancien appareil est parti).
    v_res := app_security.session_open(p_user_id, p_session_id, p_platform,
                                       p_device, false);

    IF COALESCE((v_res ->> 'ok')::boolean, false) THEN
        RETURN v_res || jsonb_build_object('active', true, 'revived', true);
    END IF;

    -- Verrou detenu par un AUTRE appareil : le client doit se deconnecter.
    RETURN v_res || jsonb_build_object('active', false);
END;
$$;

REVOKE ALL ON FUNCTION app_security.session_touch(uuid, uuid, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.session_touch(uuid, uuid, text, text) FROM anon;
REVOKE ALL ON FUNCTION app_security.session_touch(uuid, uuid, text, text)
    FROM authenticated;
GRANT EXECUTE ON FUNCTION app_security.session_touch(uuid, uuid, text, text)
    TO service_role;

-- Fermeture explicite (bouton « Deconnexion », fermeture de l'application).
CREATE OR REPLACE FUNCTION app_security.session_close(
    p_session_id uuid,
    p_reason     text DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_closed boolean := false;
BEGIN
    IF p_session_id IS NULL THEN
        RETURN jsonb_build_object('ok', true, 'closed', false, 'tracked', false);
    END IF;

    UPDATE public.user_sessions
       SET ended_at = NOW(),
           ended_reason = COALESCE(NULLIF(BTRIM(COALESCE(p_reason, '')), ''),
                                   'DECONNEXION')
     WHERE session_id = p_session_id
       AND ended_at IS NULL;
    v_closed := FOUND;

    RETURN jsonb_build_object('ok', true, 'closed', v_closed, 'tracked', true,
                              'session_id', p_session_id);
END;
$$;

REVOKE ALL ON FUNCTION app_security.session_close(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.session_close(uuid, text) FROM anon;
REVOKE ALL ON FUNCTION app_security.session_close(uuid, text) FROM authenticated;
GRANT EXECUTE ON FUNCTION app_security.session_close(uuid, text) TO service_role;

-- Fermeture administrative de toutes les sessions d'un utilisateur.
CREATE OR REPLACE FUNCTION app_security.sessions_revoke(
    p_user_id uuid,
    p_reason  text DEFAULT NULL)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_count integer := 0;
BEGIN
    UPDATE public.user_sessions
       SET ended_at = NOW(),
           ended_reason = COALESCE(NULLIF(BTRIM(COALESCE(p_reason, '')), ''), 'ADMIN')
     WHERE user_id = p_user_id
       AND ended_at IS NULL;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

REVOKE ALL ON FUNCTION app_security.sessions_revoke(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION app_security.sessions_revoke(uuid, text) FROM anon;
REVOKE ALL ON FUNCTION app_security.sessions_revoke(uuid, text) FROM authenticated;
GRANT EXECUTE ON FUNCTION app_security.sessions_revoke(uuid, text) TO service_role;


-- ----------------------------------------------------------------------------
-- 4) RPC publiques appelees par le WEB et le MOBILE (JWT Supabase Auth)
--    L'utilisateur et la session sont deduits du JETON : rien a falsifier.
-- ----------------------------------------------------------------------------

-- Ouvre la session de l'appelant (a appeler juste apres la connexion).
--   * {ok:true, tracked, session_id, platform}                     -> ouverte
--   * {ok:false, code:'SESSION_ACTIVE', message, other, can_force}  -> refus
CREATE OR REPLACE FUNCTION public.app_register_session(
    p_platform text    DEFAULT 'inconnu',
    p_device   text    DEFAULT NULL,
    p_force    boolean DEFAULT false)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT app_security.session_open(auth.uid(),
                                   app_security.current_session_id(),
                                   p_platform, p_device, p_force)
$$;

REVOKE ALL ON FUNCTION public.app_register_session(text, text, boolean)
    FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_register_session(text, text, boolean)
    TO authenticated;

-- Battement de coeur (60 s cote client) : prolonge la session et indique si
-- elle est toujours celle de l'appareil.
CREATE OR REPLACE FUNCTION public.app_session_heartbeat(
    p_platform text DEFAULT NULL,
    p_device   text DEFAULT NULL)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT app_security.session_touch(app_security.current_session_id(),
                                    auth.uid(), p_platform, p_device)
$$;

REVOKE ALL ON FUNCTION public.app_session_heartbeat(text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_session_heartbeat(text, text) TO authenticated;

-- Etat de la session courante (au demarrage : la session restauree est-elle
-- toujours celle qui a le droit d'ouvrir l'application ?).
CREATE OR REPLACE FUNCTION public.app_session_status()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_sid uuid := app_security.current_session_id();
    v_row public.user_sessions%ROWTYPE;
BEGIN
    IF v_sid IS NULL THEN
        RETURN jsonb_build_object('ok', true, 'tracked', false, 'active', true,
                                  'code', 'NO_SESSION_ID');
    END IF;

    SELECT s.* INTO v_row
      FROM public.user_sessions s
     WHERE s.session_id = v_sid;

    IF v_row.session_id IS NULL THEN
        -- Aucune trace (base reinitialisee, client ancien) : on laisse ouvrir,
        -- le client s'enregistrera au premier battement.
        RETURN jsonb_build_object('ok', true, 'tracked', false, 'active', true,
                                  'session_id', v_sid);
    END IF;

    RETURN jsonb_build_object('ok', true, 'tracked', true,
                              'active', v_row.ended_at IS NULL,
                              'session', app_security.session_json(v_row));
END;
$$;

REVOKE ALL ON FUNCTION public.app_session_status() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_session_status() TO authenticated;

-- Deconnexion explicite : libere immediatement le verrou.
CREATE OR REPLACE FUNCTION public.app_end_session()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT app_security.session_close(app_security.current_session_id(),
                                    'DECONNEXION')
$$;

REVOKE ALL ON FUNCTION public.app_end_session() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_end_session() TO authenticated;


-- ----------------------------------------------------------------------------
-- 5) RPC administrateur (page Administration du web)
-- ----------------------------------------------------------------------------

-- Sessions actuellement ouvertes (toutes, ou celles d'un email precis).
CREATE OR REPLACE FUNCTION public.admin_list_sessions(p_email text DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_sessions jsonb;
BEGIN
    IF NOT app_security.is_admin() THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Reserve aux administrateurs.');
    END IF;

    SELECT COALESCE(
             jsonb_agg(app_security.session_json(s) ORDER BY s.created_at DESC),
             '[]'::jsonb)
      INTO v_sessions
      FROM public.user_sessions s
      JOIN auth.users a ON a.id = s.user_id
     WHERE s.ended_at IS NULL
       AND (p_email IS NULL OR LOWER(a.email) = LOWER(BTRIM(p_email)));

    RETURN jsonb_build_object('ok', true, 'sessions', v_sessions,
                              'count', jsonb_array_length(v_sessions));
END;
$$;

REVOKE ALL ON FUNCTION public.admin_list_sessions(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_list_sessions(text) TO authenticated;

-- Ferme les sessions d'un compte (depannage : « ce compte est bloque
-- ailleurs »), sans toucher au mot de passe.
CREATE OR REPLACE FUNCTION public.admin_revoke_sessions(p_email text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_uid   uuid;
    v_count integer := 0;
BEGIN
    IF NOT app_security.is_admin() THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Reserve aux administrateurs.');
    END IF;

    v_uid := app_security.auth_user_id(p_email);
    IF v_uid IS NULL THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Compte Supabase Auth introuvable pour cet email.');
    END IF;

    v_count := app_security.sessions_revoke(v_uid, 'ADMIN');

    RETURN jsonb_build_object('ok', true, 'revoked', v_count,
        'message', CASE WHEN v_count = 0
                        THEN 'Aucune session ouverte pour ce compte.'
                        ELSE v_count::text || ' session(s) fermee(s).' END);
END;
$$;

REVOKE ALL ON FUNCTION public.admin_revoke_sessions(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_revoke_sessions(text) TO authenticated;


-- ----------------------------------------------------------------------------
-- 6) RPC du LOGICIEL DE BUREAU (PySide6)
--
--    Le desktop se connecte en direct a PostgreSQL (SQLAlchemy) : il n'a ni
--    JWT ni claim `session_id`. Il transmet donc son email et un UUID local.
--    Ces fonctions prennent l'identite en PARAMETRE : elles sont reservees au
--    role technique de l'application (proprietaire `postgres` / `service_role`)
--    et NE DOIVENT PAS etre accessibles a `authenticated`.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_desktop_session_open(
    p_email      text,
    p_session_id uuid,
    p_device     text    DEFAULT NULL,
    p_force      boolean DEFAULT false)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT app_security.session_open(app_security.auth_user_id(p_email),
                                   p_session_id, 'desktop', p_device, p_force)
$$;

REVOKE ALL ON FUNCTION public.app_desktop_session_open(text, uuid, text, boolean)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_desktop_session_open(text, uuid, text, boolean)
    TO service_role;

CREATE OR REPLACE FUNCTION public.app_desktop_session_touch(
    p_session_id uuid,
    p_email      text DEFAULT NULL,
    p_device     text DEFAULT NULL)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT app_security.session_touch(p_session_id,
                                    app_security.auth_user_id(p_email),
                                    'desktop', p_device)
$$;

REVOKE ALL ON FUNCTION public.app_desktop_session_touch(uuid, text, text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_desktop_session_touch(uuid, text, text)
    TO service_role;

CREATE OR REPLACE FUNCTION public.app_desktop_session_close(
    p_session_id uuid,
    p_reason     text DEFAULT NULL)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, auth
AS $$ SELECT app_security.session_close(p_session_id, p_reason) $$;

REVOKE ALL ON FUNCTION public.app_desktop_session_close(uuid, text)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.app_desktop_session_close(uuid, text)
    TO service_role;


-- ----------------------------------------------------------------------------
-- 7) Verification : table, index unique et RPC installees
-- ----------------------------------------------------------------------------
SELECT c.relname AS table_sql,
       c.relrowsecurity AS rls,
       pg_get_userbyid(c.relowner) AS proprietaire,
       (SELECT count(*) FROM pg_indexes i
         WHERE i.schemaname = 'public'
           AND i.tablename = 'user_sessions') AS index_sql
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = 'user_sessions';

SELECT p.proname AS fonction,
       pg_get_function_identity_arguments(p.oid) AS arguments_,
       pg_get_userbyid(p.proowner) AS proprietaire
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE (n.nspname = 'public' AND p.proname IN (
          'app_register_session', 'app_session_heartbeat',
          'app_session_status', 'app_end_session',
          'admin_list_sessions', 'admin_revoke_sessions',
          'app_desktop_session_open', 'app_desktop_session_touch',
          'app_desktop_session_close'))
   OR (n.nspname = 'app_security' AND p.proname IN (
          'session_open', 'session_touch', 'session_close',
          'sessions_revoke', 'session_is_active', 'session_timeout',
          'expire_stale_sessions'))
ORDER BY n.nspname, p.proname;







