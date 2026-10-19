-- ============================================================================
-- Korgo Pro — Paramètres applicatifs centralisés (app_settings)
--
-- Les paramètres de l'entreprise vivaient jusqu'ici dans un fichier local
-- (company_settings.json côté desktop, localStorage côté web) : jamais
-- partagés, et le web ne les synchronisait pas du tout. Cette table les
-- centralise sur Supabase pour que desktop, web (et mobile) lisent/écrivent
-- la MÊME source de vérité.
--
-- MODÈLE : table « singleton » (une seule ligne, id = 1) + colonne JSONB
-- `data`. Un dictionnaire libre plutôt qu'une colonne par réglage, car les
-- schémas desktop (company_name, company_address…) et web (company_name,
-- address…) diffèrent : chaque plateforme ne lit/écrit que ses propres clés.
-- La fusion se fait par un merge « shallow » (jsonb || patch) qui n'écrase
-- que les clés fournies.
--
-- À exécuter une fois dans : Dashboard Supabase -> SQL Editor (ou psql).
-- Idempotent : peut être rejoué sans risque.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) Table singleton
-- ----------------------------------------------------------------------------
create table if not exists public.app_settings (
    id          integer primary key,
    data        jsonb   not null default '{}'::jsonb,
    updated_at  timestamptz not null default now(),
    -- Garantit qu'il n'existe qu'une seule ligne de paramètres.
    constraint  ck_app_settings_singleton check (id = 1)
);

-- Ligne unique par défaut (vide : remplie à la première sauvegarde).
insert into public.app_settings (id, data)
values (1, '{}'::jsonb)
on conflict (id) do nothing;

-- ----------------------------------------------------------------------------
-- 2) Sécurité (RLS) — même modèle que les autres tables métier :
--    lecture pour tout utilisateur authentifié, écriture réservée aux admins.
-- ----------------------------------------------------------------------------
alter table public.app_settings enable row level security;
alter table public.app_settings force row level security;
revoke all on public.app_settings from anon;

drop policy if exists "as_select_all" on public.app_settings;
create policy "as_select_all" on public.app_settings
    for select to authenticated
    using (true);

drop policy if exists "as_write_admin" on public.app_settings;
create policy "as_write_admin" on public.app_settings
    for all to authenticated
    using (app_security.is_admin())
    with check (app_security.is_admin());

-- ----------------------------------------------------------------------------
-- 3) RPC de fusion — utilisée par le web (et réutilisable partout).
--    Fusionne `p_patch` (jsonb) dans la ligne singleton sans écraser les clés
--    absentes du patch : `data = data || p_patch`. Met à jour updated_at.
--    SECURITY INVOKER (défaut) : la policy RLS admin_write_admin s'applique,
--    un non-admin reçoit donc une erreur 42501 s'il tente d'écrire.
-- ----------------------------------------------------------------------------
create or replace function public.app_merge_settings(p_patch jsonb)
returns jsonb
language plpgsql
as $$
declare
    v_data jsonb;
begin
    insert into public.app_settings (id, data)
    values (1, coalesce(p_patch, '{}'::jsonb))
    on conflict (id) do update
        set data = public.app_settings.data || excluded.data,
            updated_at = now()
    returning data into v_data;
    return v_data;
end;
$$;

-- Exécution réservée aux utilisateurs authentifiés (RLS filtre ensuite le rôle).
revoke all on function public.app_merge_settings(jsonb) from public;
revoke all on function public.app_merge_settings(jsonb) from anon;
grant execute on function public.app_merge_settings(jsonb) to authenticated;
