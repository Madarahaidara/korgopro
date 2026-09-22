-- ============================================================================
-- supabase_users_supabase_only.sql
--
-- REFONTE : la creation des utilisateurs est rattachee EXCLUSIVEMENT a Supabase.
--
-- AVANT (double verite, source de bugs) :
--   - le desktop ecrivait le mot de passe en bcrypt dans public.users.password_hash ;
--   - Supabase Auth (auth.users) etait un simple MIROIR "best effort" ;
--   - resultat : 2 mots de passe a maintenir, comptes desynchronises (l'admin
--     principal n'avait AUCUN compte auth.users -> connexion web impossible).
--
-- APRES (verite unique) :
--   - auth.users (Supabase Auth) detient email + mot de passe + statut ;
--   - public.users devient un simple PROFIL (username, role, active,
--     must_change_password) relie par email, alimente par TRIGGER ;
--   - creation / mot de passe / email / activation / suppression passent
--     uniquement par Supabase Auth.
--
-- Contenu :
--   1) public.users devient une table de profil (plus de credentials)
--   2) Triggers auth.users -> public.users (INSERT / UPDATE / DELETE)
--   3) Backfill bidirectionnel des comptes existants
--   4) RPC administrateur (pour l'app web, sans cle service_role)
--
-- Idempotent. Application : python _apply_users_supabase_only.py
--   (ou Dashboard Supabase -> SQL Editor)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) public.users = PROFIL (aucun credential)
--
--    password_hash : conserve pour compatibilite ascendante (les anciens hashs
--    bcrypt sont recopies dans auth.users par le backfill) mais n'est PLUS
--    ecrit par l'application -> devient nullable avec valeur vide par defaut.
--
--    email : cle de liaison vers auth.users -> obligatoire et unique.
-- ----------------------------------------------------------------------------
ALTER TABLE public.users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE public.users ALTER COLUMN password_hash SET DEFAULT '';

-- Profils sans email : on en fabrique un deterministe depuis le username, sinon
-- la liaison avec Supabase Auth est impossible.
UPDATE public.users
   SET email = lower(username) || '@korgo.local'
 WHERE email IS NULL OR btrim(email) = '';

-- Doublons d'email : on ne garde que le plus ancien (id le plus faible).
DELETE FROM public.users a
 USING public.users b
 WHERE a.id > b.id
   AND lower(a.email) = lower(b.email);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique_idx
    ON public.users (lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS users_username_unique_idx
    ON public.users (lower(username));

ALTER TABLE public.users ALTER COLUMN email SET NOT NULL;

COMMENT ON COLUMN public.users.password_hash IS
    'DEPRECIE : les credentials vivent dans auth.users (Supabase Auth). '
    'Colonne conservee vide pour compatibilite.';
COMMENT ON COLUMN public.users.email IS
    'Cle de liaison vers auth.users.email (Supabase Auth = source de verite).';
-- ----------------------------------------------------------------------------
-- 2) Triggers : tout compte Supabase Auth possede son profil public.users
--
--    SECURITY DEFINER : l'ecriture fonctionne malgre FORCE ROW LEVEL SECURITY
--    sur public.users (le role `postgres` dispose de BYPASSRLS).
--    Metadonnees attendues dans auth.users.raw_user_meta_data :
--      username, role, active, must_change_password
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.sync_user_profile_from_auth()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
DECLARE
    v_email    text := lower(btrim(coalesce(NEW.email, '')));
    v_username text;
    v_role     text;
    v_active   boolean;
BEGIN
    -- Comptes sans email (telephone / anonymes) : pas de profil applicatif.
    IF v_email = '' THEN
        RETURN NEW;
    END IF;

    -- Renommage d'email : on deplace le profil AVANT la synchronisation,
    -- sinon la recherche par email ne retrouverait pas la ligne existante.
    IF TG_OP = 'UPDATE'
       AND lower(coalesce(OLD.email, '')) <> v_email THEN
        UPDATE public.users SET email = v_email
         WHERE lower(email) = lower(OLD.email);
    END IF;

    v_username := nullif(btrim(coalesce(NEW.raw_user_meta_data ->> 'username', '')), '');
    IF v_username IS NULL THEN
        v_username := split_part(v_email, '@', 1);
    END IF;

    v_role := coalesce(
        upper(nullif(btrim(coalesce(NEW.raw_user_meta_data ->> 'role', '')), '')),
        'CAISSIER');

    -- Un compte banni / supprime cote Supabase Auth n'est jamais "actif",
    -- meme si la metadonnee dit le contraire.
    v_active := coalesce((NEW.raw_user_meta_data ->> 'active')::boolean, true)
                AND NEW.deleted_at IS NULL
                AND (NEW.banned_until IS NULL OR NEW.banned_until < now());

    -- username unique : suffixe numerique tant qu'il appartient a un AUTRE email.
    WHILE EXISTS (
        SELECT 1 FROM public.users u
         WHERE lower(u.username) = lower(v_username)
           AND lower(u.email) IS DISTINCT FROM v_email
    ) LOOP
        v_username := v_username || floor(random() * 1000)::int::text;
    END LOOP;

    UPDATE public.users
       SET username = v_username,
           role     = v_role,
           active   = v_active
     WHERE lower(email) = v_email;

    IF NOT FOUND THEN
        INSERT INTO public.users
            (username, email, role, active, password_hash,
             must_change_password, created_at)
        VALUES
            (v_username, v_email, v_role, v_active, '',
             coalesce((NEW.raw_user_meta_data ->> 'must_change_password')::boolean, true),
             coalesce(NEW.created_at, now()));
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.delete_user_profile_from_auth()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
BEGIN
    IF coalesce(btrim(OLD.email), '') <> '' THEN
        DELETE FROM public.users WHERE lower(email) = lower(OLD.email);
    END IF;
    RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_changed ON auth.users;
CREATE TRIGGER on_auth_user_changed
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.sync_user_profile_from_auth();

DROP TRIGGER IF EXISTS on_auth_user_deleted ON auth.users;
CREATE TRIGGER on_auth_user_deleted
    AFTER DELETE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.delete_user_profile_from_auth();
-- ----------------------------------------------------------------------------
-- 3) Backfill : plus aucun compte orphelin d'un cote ou de l'autre
-- ----------------------------------------------------------------------------

-- 3a) Comptes Supabase Auth SANS profil applicatif -> creation du profil.
--     Le username vient des metadonnees, sinon de la partie locale de l'email.
INSERT INTO auth.users (
    instance_id, id, aud, "role", email, encrypted_password,
    email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
    created_at, updated_at, confirmation_token, recovery_token,
    email_change_token_new, email_change, email_change_token_current,
    phone_change_token, phone_change, email_change_confirm_status
)
SELECT
    '00000000-0000-0000-0000-000000000000'::uuid,
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    lower(btrim(u.email)),
    u.password_hash,                        -- deja un hash bcrypt valide
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    jsonb_build_object(
        'username', u.username,
        'role',     u.role,
        'active',   coalesce(u.active, true),
        'must_change_password', coalesce(u.must_change_password, true)
    ),
    coalesce(u.created_at, now()),
    now(),
    '', '', '', '', '', '', '', 0
FROM public.users u
LEFT JOIN auth.users a ON lower(a.email) = lower(u.email)
WHERE a.id IS NULL
  AND lower(btrim(u.email)) <> ''
  AND u.password_hash LIKE '$2%'            -- hash bcrypt exploitable tel quel
ON CONFLICT DO NOTHING;

-- 3b) Profils dont le hash n'est PAS du bcrypt (anciens SHA256) : le mot de
--     passe ne peut pas etre transcode, on cree le compte avec un secret
--     aleatoire et on IMPOSE un changement a la premiere connexion.
INSERT INTO auth.users (
    instance_id, id, aud, "role", email, encrypted_password,
    email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
    created_at, updated_at, confirmation_token, recovery_token,
    email_change_token_new, email_change, email_change_token_current,
    phone_change_token, phone_change, email_change_confirm_status
)
SELECT
    '00000000-0000-0000-0000-000000000000'::uuid,
    gen_random_uuid(),
    'authenticated',
    'authenticated',
    lower(btrim(u.email)),
    extensions.crypt(gen_random_uuid()::text, extensions.gen_salt('bf', 10)),
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    jsonb_build_object(
        'username', u.username,
        'role',     u.role,
        'active',   coalesce(u.active, true),
        'must_change_password', true
    ),
    coalesce(u.created_at, now()),
    now(),
    '', '', '', '', '', '', '', 0
FROM public.users u
LEFT JOIN auth.users a ON lower(a.email) = lower(u.email)
WHERE a.id IS NULL
  AND lower(btrim(u.email)) <> ''
  AND u.password_hash NOT LIKE '$2%'
ON CONFLICT DO NOTHING;

-- 3c) Comptes Supabase Auth SANS profil (ceux passes a travers 3a/3b, ou crees
--     directement dans le dashboard) : le trigger ne s'applique pas aux lignes
--     deja presentes, on force donc la synchronisation.
UPDATE auth.users SET updated_at = updated_at
 WHERE lower(email) IN (
        SELECT lower(a.email) FROM auth.users a
        LEFT JOIN public.users u ON lower(u.email) = lower(a.email)
        WHERE u.id IS NULL AND coalesce(btrim(a.email), '') <> '');
-- 3d) Sequence de public.users.id : indispensables aux INSERT du trigger.
--
--     Apres une migration SQLite -> PostgreSQL, la sequence n'est pas avancee :
--     elle reste a une valeur deja utilisee, donc le prochain INSERT (ici celui
--     du trigger de creation d'utilisateur) echoue en "duplicate key value
--     violates unique constraint users_pkey". On la resynchronise sur max(id).
DO $$
DECLARE
    v_seq  text := pg_get_serial_sequence('public.users', 'id');
    v_max  bigint;
BEGIN
    IF v_seq IS NULL THEN
        RAISE NOTICE 'public.users.id : aucune sequence (colonne non serial)';
        RETURN;
    END IF;
    SELECT coalesce(max(id), 0) INTO v_max FROM public.users;
    -- setval(..., true) => le prochain nextval renverra v_max + 1.
    PERFORM setval(v_seq, greatest(v_max, 1), true);
    RAISE NOTICE 'Sequence % resynchronisee sur %', v_seq, greatest(v_max, 1);
END;
$$;

-- ----------------------------------------------------------------------------
-- 4) RPC administrateur
--
--    L'app web ne dispose que de la cle publique (anon) : elle ne peut pas
--    appeler l'API Admin de Supabase Auth (qui exige service_role). Ces
--    fonctions SECURITY DEFINER, reservees aux ADMIN actifs, permettent de
--    creer/modifier/supprimer un compte SANS exposer de cle secrete dans le
--    navigateur. La creation reste ainsi rattachee a Supabase Auth.
--
--    Retour uniforme : { ok: bool, message: text, ... }
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_create_user(
    p_email                text,
    p_password             text,
    p_username             text    DEFAULT NULL,
    p_role                 text    DEFAULT 'CAISSIER',
    p_active               boolean DEFAULT true,
    p_must_change_password boolean DEFAULT true
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
DECLARE
    v_email    text := lower(btrim(coalesce(p_email, '')));
    v_username text := nullif(btrim(coalesce(p_username, '')), '');
    v_role     text := upper(coalesce(nullif(btrim(coalesce(p_role, '')), ''), 'CAISSIER'));
    v_uid      uuid;
BEGIN
    IF NOT app_security.is_admin() THEN
        RAISE EXCEPTION 'Reserve aux administrateurs' USING ERRCODE = '42501';
    END IF;

    IF v_email = '' OR position('@' IN v_email) = 0 THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Email invalide');
    END IF;
    IF length(coalesce(p_password, '')) < 6 THEN
        RETURN jsonb_build_object(
            'ok', false, 'message', 'Mot de passe trop court (6 caracteres minimum)');
    END IF;
    IF v_username IS NULL THEN
        v_username := split_part(v_email, '@', 1);
    END IF;

    -- Compte deja present : on reinitialise (idempotent, pas de doublon).
    UPDATE auth.users
       SET encrypted_password   = extensions.crypt(p_password, extensions.gen_salt('bf', 10)),
           email_confirmed_at   = coalesce(email_confirmed_at, now()),
           banned_until         = CASE WHEN p_active THEN NULL ELSE now() + interval '100 years' END,
           updated_at           = now(),
           raw_user_meta_data   = coalesce(raw_user_meta_data, '{}'::jsonb)
               || jsonb_build_object(
                      'username', v_username,
                      'role', v_role,
                      'active', p_active,
                      'must_change_password', p_must_change_password)
     WHERE lower(email) = v_email
     RETURNING id INTO v_uid;

    IF v_uid IS NULL THEN
        INSERT INTO auth.users (
            instance_id, id, aud, "role", email, encrypted_password,
            email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
            created_at, updated_at, confirmation_token, recovery_token,
            email_change_token_new, email_change, email_change_token_current,
            phone_change_token, phone_change, email_change_confirm_status
        ) VALUES (
            '00000000-0000-0000-0000-000000000000'::uuid,
            gen_random_uuid(),
            'authenticated',
            'authenticated',
            v_email,
            extensions.crypt(p_password, extensions.gen_salt('bf', 10)),
            now(),
            '{"provider":"email","providers":["email"]}'::jsonb,
            jsonb_build_object(
                'username', v_username,
                'role', v_role,
                'active', p_active,
                'must_change_password', p_must_change_password),
            now(), now(), '', '', '', '', '', '', '', 0
        )
        RETURNING id INTO v_uid;
    END IF;

    RETURN jsonb_build_object(
        'ok', true,
        'message', 'Compte Supabase Auth enregistre',
        'user_id', v_uid,
        'email', v_email,
        'username', v_username,
        'role', v_role);
END;
$$;

REVOKE ALL ON FUNCTION public.admin_create_user(text, text, text, text, boolean, boolean)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_create_user(text, text, text, text, boolean, boolean)
    TO authenticated;
-- ----------------------------------------------------------------------------
-- 4b) Reinitialiser le mot de passe d'un compte Supabase Auth
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_set_user_password(
    p_email                text,
    p_password             text,
    p_must_change_password boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
BEGIN
    IF NOT app_security.is_admin() THEN
        RAISE EXCEPTION 'Reserve aux administrateurs' USING ERRCODE = '42501';
    END IF;
    IF length(coalesce(p_password, '')) < 6 THEN
        RETURN jsonb_build_object(
            'ok', false, 'message', 'Mot de passe trop court (6 caracteres minimum)');
    END IF;

    UPDATE auth.users
       SET encrypted_password = extensions.crypt(p_password, extensions.gen_salt('bf', 10)),
           email_confirmed_at = coalesce(email_confirmed_at, now()),
           updated_at         = now(),
           raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
               || jsonb_build_object('must_change_password', p_must_change_password)
     WHERE lower(email) = lower(btrim(coalesce(p_email, '')));

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'ok', false, 'message', 'Aucun compte Supabase Auth pour cet email');
    END IF;
    RETURN jsonb_build_object('ok', true, 'message', 'Mot de passe Supabase Auth mis a jour');
END;
$$;

REVOKE ALL ON FUNCTION public.admin_set_user_password(text, text, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_set_user_password(text, text, boolean) TO authenticated;

-- ----------------------------------------------------------------------------
-- 4c) Activer / desactiver un compte (bannissement cote Supabase Auth)
--
--     On ne SUPPRIME plus le compte pour retirer l'acces : les identifiants
--     sont conserves, la connexion web ET desktop est refusee.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_set_user_active(
    p_email  text,
    p_active boolean
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
BEGIN
    IF NOT app_security.is_admin() THEN
        RAISE EXCEPTION 'Reserve aux administrateurs' USING ERRCODE = '42501';
    END IF;

    UPDATE auth.users
       SET banned_until       = CASE WHEN p_active THEN NULL
                                     ELSE now() + interval '100 years' END,
           updated_at         = now(),
           raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
               || jsonb_build_object('active', p_active)
     WHERE lower(email) = lower(btrim(coalesce(p_email, '')));

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'ok', false, 'message', 'Aucun compte Supabase Auth pour cet email');
    END IF;
    RETURN jsonb_build_object(
        'ok', true, 'message',
        CASE WHEN p_active THEN 'Compte active' ELSE 'Compte desactive' END);
END;
$$;

REVOKE ALL ON FUNCTION public.admin_set_user_active(text, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_set_user_active(text, boolean) TO authenticated;
-- ----------------------------------------------------------------------------
-- 4d) Modifier le profil (username / role / statut / email) d'un compte
--     Le trigger propage vers public.users et gere le renommage d'email.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_update_user_profile(
    p_email     text,
    p_username  text    DEFAULT NULL,
    p_role      text    DEFAULT NULL,
    p_active    boolean DEFAULT NULL,
    p_new_email text    DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
DECLARE
    v_email     text := lower(btrim(coalesce(p_email, '')));
    v_new_email text := nullif(lower(btrim(coalesce(p_new_email, ''))), '');
BEGIN
    IF NOT app_security.is_admin() THEN
        RAISE EXCEPTION 'Reserve aux administrateurs' USING ERRCODE = '42501';
    END IF;

    UPDATE auth.users
       SET email      = coalesce(v_new_email, email),
           updated_at = now(),
           raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
               || jsonb_strip_nulls(jsonb_build_object(
                      'username', nullif(btrim(coalesce(p_username, '')), ''),
                      'role',     nullif(upper(btrim(coalesce(p_role, ''))), ''),
                      'active',   p_active))
     WHERE lower(email) = v_email;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'ok', false, 'message', 'Aucun compte Supabase Auth pour cet email');
    END IF;
    RETURN jsonb_build_object('ok', true, 'message', 'Profil synchronise');
END;
$$;

REVOKE ALL ON FUNCTION public.admin_update_user_profile(text, text, text, boolean, text)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_update_user_profile(text, text, text, boolean, text)
    TO authenticated;

-- ----------------------------------------------------------------------------
-- 4e) Supprimer un compte Supabase Auth (le trigger supprime le profil)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.admin_delete_user(p_email text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, extensions
AS $$
BEGIN
    IF NOT app_security.is_admin() THEN
        RAISE EXCEPTION 'Reserve aux administrateurs' USING ERRCODE = '42501';
    END IF;

    DELETE FROM auth.users WHERE lower(email) = lower(btrim(coalesce(p_email, '')));

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'ok', false, 'message', 'Aucun compte Supabase Auth pour cet email');
    END IF;
    RETURN jsonb_build_object('ok', true, 'message', 'Compte Supabase Auth supprime');
END;
$$;

REVOKE ALL ON FUNCTION public.admin_delete_user(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_delete_user(text) TO authenticated;

-- ----------------------------------------------------------------------------
-- 5) Verification finale : plus aucun compte orphelin
-- ----------------------------------------------------------------------------
-- SELECT u.id, u.username, u.email, u.role, u.active, a.id AS auth_id
--   FROM public.users u LEFT JOIN auth.users a ON lower(a.email) = lower(u.email)
--  ORDER BY u.id;
