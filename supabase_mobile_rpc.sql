-- ============================================================================
-- supabase_mobile_rpc.sql
--
-- API d'écriture pour l'application mobile « Korgo Pro Terrain » (mobile/).
--
-- POURQUOI DES RPC ET NON DES ÉCRITURES DIRECTES (PostgREST)
-- ---------------------------------------------------------------------------
-- supabase_rls_policies.sql active RLS (FORCE) et réserve l'écriture des tables
-- opérationnelles à `app_security.is_admin()` :
--   * `sales`, `sale_items`, `payments`, `inventory_movements`, `sale_logs` :
--     INSERT/UPDATE/DELETE -> admin uniquement ;
--   * `products`, `treasury_accounts`, `treasury_movements` : idem.
-- Un caissier ou un assistant ne peut donc PAS enregistrer une vente
-- directement en PostgREST (erreur 42501). Comme l'application mobile ne peut
-- pas embarquer la clé `service_role` (secret), l'écriture passe par des
-- fonctions SECURITY DEFINER qui :
--   1. vérifient le rôle du compte connecté (matrice alignée sur
--      core/permissions.py — source unique déjà partagée desktop/web) ;
--   2. exécutent l'opération dans UNE transaction (vente + lignes + stock +
--      trésorerie + journal) : plus de demi-vente en cas de coupure réseau ;
--   3. recalculent tous les montants côté serveur (le client n'est jamais cru).
--
-- SÉCURITÉ
-- ---------------------------------------------------------------------------
-- * Aucune clé secrète n'est exposée : seul le JWT de l'utilisateur connecté
--   est utilisé (`auth.uid()` / `app_security.current_email()`).
-- * Le schéma `app_security` n'est pas exposé par PostgREST.
-- * Les fonctions sont `SECURITY DEFINER` : exécutées en éditeur SQL Supabase
--   (rôle `postgres`), elles ne subissent pas les RLS. Elles restent joignables
--   par `/rest/v1/rpc/...` par le rôle `authenticated` uniquement.
--
-- Idempotent. À exécuter dans Dashboard Supabase -> SQL Editor, ou via :
--   python _apply_mobile_rpc.py
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1) Helpers `app_security` : rôle courant + matrice de permissions
-- ----------------------------------------------------------------------------

-- Rôle canonique du compte connecté (NULL si aucun profil actif lié).
--   - résout le synonyme historique GERANT -> GESTIONNAIRE (comme
--     core.permissions.normalize_role) ;
--   - un rôle hérité/inconnu est retourné tel quel : la matrice le privera de
--     tout sauf du tableau de bord (UNKNOWN_ROLE_PERMISSIONS).
CREATE OR REPLACE FUNCTION app_security.current_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT CASE UPPER(BTRIM(COALESCE(u.role, '')))
           WHEN 'GERANT' THEN 'GESTIONNAIRE'
           ELSE UPPER(BTRIM(COALESCE(u.role, '')))
         END
  FROM public.users u
  WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
    AND u.active
  LIMIT 1
$$;

REVOKE ALL ON FUNCTION app_security.current_role() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_security.current_role() TO authenticated;


-- `app_security.can('<permission>')` : réplique de la matrice de
-- core/permissions.py (_MATRIX + UNKNOWN_ROLE_PERMISSIONS).
--
-- ATTENTION : toute évolution de la matrice doit être faite des DEUX côtés
-- (core/permissions.py PUIS ce fichier). `public.app_mobile_context()` permet à
-- l'application mobile de comparer ses droits locaux aux droits serveur.
CREATE OR REPLACE FUNCTION app_security.can(p_permission text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH moi AS (
    SELECT app_security.current_role() AS role
  ),
  -- Un rôle -> une permission accordée.
  matrice(role, permission) AS (
    SELECT * FROM (VALUES
      -- ADMIN : toutes les clés de core.permissions.PERMISSIONS
      ('ADMIN', 'view_dashboard'), ('ADMIN', 'view_sales'),
      ('ADMIN', 'create_sales'), ('ADMIN', 'cancel_sales'),
      ('ADMIN', 'view_invoice_register'), ('ADMIN', 'manage_proformas'),
      ('ADMIN', 'view_stock'), ('ADMIN', 'manage_stock'),
      ('ADMIN', 'manage_stores'), ('ADMIN', 'view_treasury'),
      ('ADMIN', 'manage_treasury'), ('ADMIN', 'manage_customers'),
      ('ADMIN', 'view_reports'), ('ADMIN', 'access_admin'),
      ('ADMIN', 'manage_users'), ('ADMIN', 'manage_database'),
      ('ADMIN', 'manage_settings'), ('ADMIN', 'export_data'),
      ('ADMIN', 'view_audit_logs'),
      -- GESTIONNAIRE (_GESTIONNAIRE_PERMISSIONS)
      ('GESTIONNAIRE', 'view_dashboard'), ('GESTIONNAIRE', 'view_sales'),
      ('GESTIONNAIRE', 'create_sales'), ('GESTIONNAIRE', 'cancel_sales'),
      ('GESTIONNAIRE', 'view_invoice_register'),
      ('GESTIONNAIRE', 'manage_proformas'), ('GESTIONNAIRE', 'view_stock'),
      ('GESTIONNAIRE', 'manage_stock'), ('GESTIONNAIRE', 'manage_stores'),
      ('GESTIONNAIRE', 'view_treasury'), ('GESTIONNAIRE', 'manage_treasury'),
      ('GESTIONNAIRE', 'manage_customers'), ('GESTIONNAIRE', 'view_reports'),
      ('GESTIONNAIRE', 'export_data'),
      -- SUPERVISEUR : gestionnaire + administration + journaux
      ('SUPERVISEUR', 'view_dashboard'), ('SUPERVISEUR', 'view_sales'),
      ('SUPERVISEUR', 'create_sales'), ('SUPERVISEUR', 'cancel_sales'),
      ('SUPERVISEUR', 'view_invoice_register'),
      ('SUPERVISEUR', 'manage_proformas'), ('SUPERVISEUR', 'view_stock'),
      ('SUPERVISEUR', 'manage_stock'), ('SUPERVISEUR', 'manage_stores'),
      ('SUPERVISEUR', 'view_treasury'), ('SUPERVISEUR', 'manage_treasury'),
      ('SUPERVISEUR', 'manage_customers'), ('SUPERVISEUR', 'view_reports'),
      ('SUPERVISEUR', 'export_data'), ('SUPERVISEUR', 'access_admin'),
      ('SUPERVISEUR', 'view_audit_logs'),
      -- ASSISTANT : caisse, registre, proformas, clients
      ('ASSISTANT', 'view_dashboard'), ('ASSISTANT', 'create_sales'),
      ('ASSISTANT', 'view_invoice_register'),
      ('ASSISTANT', 'manage_proformas'), ('ASSISTANT', 'manage_customers'),
      -- CAISSIER : caisse, registre, proformas, clients (+ trésorerie en lecture)
      ('CAISSIER', 'view_dashboard'), ('CAISSIER', 'create_sales'),
      ('CAISSIER', 'view_invoice_register'), ('CAISSIER', 'manage_proformas'),
      ('CAISSIER', 'view_treasury'), ('CAISSIER', 'manage_customers')
    ) AS t(role, permission)
  )
  SELECT
    EXISTS (
      SELECT 1 FROM moi, matrice m
      WHERE m.role = moi.role AND m.permission = p_permission
    )
    -- Rôle hérité / inconnu : UNKNOWN_ROLE_PERMISSIONS = {view_dashboard}.
    OR (
      p_permission = 'view_dashboard'
      AND (SELECT role FROM moi) IS NOT NULL
      AND (SELECT role FROM moi) NOT IN (SELECT DISTINCT role FROM matrice)
    );
$$;

REVOKE ALL ON FUNCTION app_security.can(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_security.can(text) TO authenticated;


-- ----------------------------------------------------------------------------
-- 2) Diagnostic : identité + droits vus PAR LE SERVEUR
--
--    L'application mobile affiche cette liste dans l'écran « Compte » : c'est
--    la référence, car c'est elle qui décide réellement des écritures. Si elle
--    diffère des droits calculés localement (même matrice dans
--    mobile/src/lib/permissions.js), c'est le serveur qui a raison.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_mobile_context()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
  WITH moi AS (
    SELECT u.id, u.username, u.email, u.role
    FROM public.users u
    WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
      AND u.active
    LIMIT 1
  )
  SELECT jsonb_build_object(
    'ok', EXISTS (SELECT 1 FROM moi),
    'role', app_security.current_role(),
    'user_id', (SELECT id FROM moi),
    'username', (SELECT username FROM moi),
    'permissions', (
      SELECT COALESCE(jsonb_agg(k ORDER BY k), '[]'::jsonb)
      FROM unnest(ARRAY[
        'view_dashboard', 'view_sales', 'create_sales', 'cancel_sales',
        'view_invoice_register', 'manage_proformas', 'view_stock',
        'manage_stock', 'manage_stores', 'view_treasury', 'manage_treasury',
        'manage_customers', 'view_reports', 'access_admin', 'manage_users',
        'manage_database', 'manage_settings', 'export_data', 'view_audit_logs'
      ]) AS k
      WHERE app_security.can(k)
    ),
    'server_time', now()
  );
$$;

-- `anon` reçoit, par défaut chez Supabase, un GRANT direct à la création de
-- toute fonction du schéma public : révoquer seulement PUBLIC le laisserait
-- appeler cette RPC. On le retire explicitement (défense en profondeur).
REVOKE ALL ON FUNCTION public.app_mobile_context() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_mobile_context() TO authenticated;


-- ----------------------------------------------------------------------------
-- 3) RPC : créer une vente (caisse mobile) — transaction unique
--
--    Réplique la logique de :
--      * desktop : ui/views/sale_services.py -> SaleService.create_sale
--      * web     : web/src/api/salesApi.js   -> createSale
--      * mobile  : mobile/src/api/rpc.js     -> createSale
--
--    Opérations, dans l'ordre :
--      1. contrôle du stock ligne par ligne (verrou de ligne) ;
--      2. numéro FAC-YYYY-NNNNNN unique (verrou consultatif par année) ;
--      3. INSERT sales + sale_items ;
--      4. décrément products.quantity ;
--      5. INSERT payments (amount = amount_paid, collected_by = utilisateur) ;
--      6. vente à crédit : customers.balance += total_amount ;
--      7. trésorerie : entrée du NET encaissé (amount_paid - change_amount)
--         sur le compte de caisse par défaut — identique au desktop ;
--      8. INSERT sale_logs (action CREATE) pour l'audit.
--
--    Le stock est décrémenté directement sur products.quantity (comme le
--    desktop) : aucune ligne n'est ajoutée à inventory_movements.
--
--    Montants : recalculés ici. Le client envoie des lignes, jamais un total.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_create_sale(
    p_items           jsonb,
    p_store_id        integer DEFAULT NULL,
    p_customer_id     integer DEFAULT NULL,
    p_discount_amount numeric DEFAULT 0,
    p_tax_amount      numeric DEFAULT 0,
    p_payment_method  text    DEFAULT 'CASH',
    p_amount_paid     numeric DEFAULT 0,
    p_notes           text    DEFAULT NULL,
    p_currency        text    DEFAULT 'FCFA',
    p_account_id      integer DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id     integer;
    v_username    text;
    v_role        text;
    v_store_id    integer;
    v_method      text    := UPPER(COALESCE(NULLIF(BTRIM(p_payment_method), ''), 'CASH'));
    -- Devise de la vente : toujours renseignée (colonne `sales.currency`), la
    -- valeur du client n'est utilisée que si elle est non vide.
    v_currency    text    := COALESCE(NULLIF(BTRIM(p_currency), ''), 'FCFA');
    v_item        jsonb;
    v_produit     record;
    v_qty         numeric;
    v_unit        numeric;
    v_disc_pct    numeric;
    v_disc_amt    numeric;
    v_line_total  numeric;
    v_lignes      jsonb   := '[]'::jsonb;
    v_subtotal    numeric := 0;
    v_total       numeric;
    v_paid        numeric;
    v_due         numeric := 0;
    v_change      numeric := 0;
    v_status      text;
    v_number      text;
    v_sale_id     integer := NULL;
    v_year        text    := to_char(now(), 'YYYY');
    v_max_seq     integer := 0;
    v_suffixe     text;
    v_tentative   integer;
    v_cash_in     numeric;
    v_account     integer;
    v_customer    record;
    v_client_nom  text;
BEGIN
    -- --- Contrôle de droit (le serveur décide, pas l'application) -----------
    IF NOT app_security.can('create_sales') THEN
        RAISE EXCEPTION 'Encaissement non autorise pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » -----------------------
    -- (voir supabase_single_session.sql) : refuse une vente provenant d'un
    -- appareil dont la session a ete reprise ailleurs -> pas de double caisse.
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array'
       OR jsonb_array_length(p_items) = 0 THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Aucun article dans la vente.');
    END IF;

    -- --- Identité (le caissier est l'utilisateur connecté) -----------------
    SELECT u.id, u.username, u.role
      INTO v_user_id, v_username, v_role
      FROM public.users u
     WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
       AND u.active
     LIMIT 1;

    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object(
            'ok', false,
            'message', 'Profil utilisateur actif introuvable pour ce compte.');
    END IF;

    -- --- Magasin (celui de l'app, sinon premier magasin actif) -------------
    v_store_id := COALESCE(
        p_store_id,
        (SELECT s.id FROM public.stores s WHERE s.active ORDER BY s.id LIMIT 1));
    IF v_store_id IS NULL
       OR NOT EXISTS (SELECT 1 FROM public.stores s
                       WHERE s.id = v_store_id AND s.active) THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Magasin invalide ou inactif.');
    END IF;

    -- --- Lignes : contrôle du stock, décrément, totaux ---------------------
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_items) LOOP
        SELECT p.id, p.name, p.quantity, p.active, p.sale_price
          INTO v_produit
          FROM public.products p
         WHERE p.id = COALESCE((v_item->>'product_id')::integer, -1)
         FOR UPDATE;                            -- verrou : jamais de survente

        IF v_produit.id IS NULL THEN
            RAISE EXCEPTION 'Produit #% introuvable.',
                COALESCE(v_item->>'product_id', '?');
        END IF;
        IF NOT v_produit.active THEN
            RAISE EXCEPTION 'Produit desactive : %.', v_produit.name;
        END IF;

        v_qty := COALESCE((v_item->>'quantity')::numeric, 0);
        IF v_qty <= 0 THEN
            RAISE EXCEPTION 'Quantite invalide pour %.', v_produit.name;
        END IF;
        IF v_qty > COALESCE(v_produit.quantity, 0) THEN
            RETURN jsonb_build_object('ok', false,
                'message', format(
                    'Stock insuffisant pour « %s » : %s disponible(s), %s demandé(s).',
                    v_produit.name, v_produit.quantity, v_qty));
        END IF;

        v_unit     := COALESCE((v_item->>'unit_price')::numeric, v_produit.sale_price);
        v_disc_pct := COALESCE((v_item->>'discount_percent')::numeric, 0);
        v_disc_amt := COALESCE((v_item->>'discount_amount')::numeric, 0)
                      + (v_unit * v_qty * v_disc_pct / 100);
        IF v_unit < 0 OR v_disc_amt < 0 THEN
            RETURN jsonb_build_object('ok', false,
                'message', format('Montants invalides pour « %s ».', v_produit.name));
        END IF;

        v_line_total := (v_unit * v_qty) - v_disc_amt;
        v_subtotal   := v_subtotal + v_line_total;

        v_lignes := v_lignes || jsonb_build_object(
            'product_id',       v_produit.id,
            'quantity',         v_qty,
            'unit_price',       v_unit,
            'discount_percent', v_disc_pct,
            'discount_amount',  v_disc_amt,
            'line_total',       v_line_total,
            'notes',            COALESCE(v_item->>'notes', '')
        );

        UPDATE public.products
           SET quantity   = COALESCE(quantity, 0) - v_qty,
               updated_at = now()
         WHERE id = v_produit.id;
    END LOOP;

    -- --- Totaux (autorité serveur) -----------------------------------------
    v_total  := v_subtotal
                - GREATEST(COALESCE(p_discount_amount, 0), 0)
                + GREATEST(COALESCE(p_tax_amount, 0), 0);
    IF v_total < 0 THEN
        v_total := 0;
    END IF;

    -- Règle de paiement (identique au web) :
    --   * ESPÈCES : on encaisse exactement ce qui est saisi (monnaie rendue) ;
    --   * CRÉDIT / A_TERME : ce qui est saisi est un acompte (0 = vente à terme),
    --    le reliquat est porté au solde dû du client ;
    --   * autres  : le moyen de paiement est réputé immédiat -> total si 0 saisi.
    IF v_method IN ('CREDIT', 'CRÉDIT', 'A_TERME') THEN
        v_paid := GREATEST(COALESCE(p_amount_paid, 0), 0);
    ELSIF v_method IN ('CASH', 'ESPECES', 'ESPÈCES') THEN
        v_paid := GREATEST(COALESCE(p_amount_paid, 0), 0);
    ELSE
        v_paid := CASE
                    WHEN COALESCE(p_amount_paid, 0) <= 0 THEN v_total
                    ELSE GREATEST(p_amount_paid, 0)
                  END;
    END IF;

    v_change := GREATEST(v_paid - v_total, 0);
    v_due    := GREATEST(v_total - v_paid, 0);
    v_status := CASE
                  WHEN v_paid >= v_total AND v_paid > 0 THEN 'PAID'
                  WHEN v_paid > 0                      THEN 'PARTIAL'
                  ELSE 'PENDING'
                END;

    -- --- Numéro de facture : FAC-YYYY-NNNNNN (format desktop) --------------
    -- Le verrou consultatif sérialise deux encaissements simultanés ; la
    -- boucle absorbe en dernier recours une collision avec l'app desktop
    -- (qui, elle, ne prend pas ce verrou).
    PERFORM pg_advisory_xact_lock(hashtext('korgo_sale_number_' || v_year));

    SELECT COALESCE(MAX(
             CASE WHEN SUBSTRING(s.sale_number FROM 10) ~ '^[0-9]+$'
                  THEN SUBSTRING(s.sale_number FROM 10)::integer
             END), 0)
      INTO v_max_seq
      FROM public.sales s
     WHERE s.sale_number LIKE 'FAC-' || v_year || '%';

    FOR v_tentative IN 1..100 LOOP
        v_number := 'FAC-' || v_year || '-'
                    || LPAD((v_max_seq + v_tentative)::text, 6, '0');
        BEGIN
            INSERT INTO public.sales (
                sale_number, customer_id, cashier_id, store_id, sale_date,
                subtotal, discount_amount, tax_amount, total_amount,
                amount_paid, change_amount, payment_method, payment_status,
                sale_status, notes, currency, type_document, statut, created_at)
            VALUES (
                v_number, p_customer_id, v_user_id, v_store_id, now(),
                v_subtotal, GREATEST(COALESCE(p_discount_amount, 0), 0),
                GREATEST(COALESCE(p_tax_amount, 0), 0), v_total,
                v_paid, v_change, v_method, v_status,
                'COMPLETED', NULLIF(BTRIM(COALESCE(p_notes, '')), ''), v_currency,
                'FACTURE', 'EMISE', now())
            RETURNING id INTO v_sale_id;
            EXIT;
        EXCEPTION WHEN unique_violation THEN
            v_sale_id := NULL;   -- numéro pris : on retente
        END;
    END LOOP;

    IF v_sale_id IS NULL THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Numéro de facture indisponible. Réessayez.');
    END IF;

    -- --- Lignes de vente ---------------------------------------------------
    INSERT INTO public.sale_items (
        sale_id, product_id, quantity, unit_price,
        discount_percent, discount_amount, line_total, notes)
    SELECT v_sale_id,
           (l->>'product_id')::integer,
           (l->>'quantity')::numeric,
           (l->>'unit_price')::numeric,
           (l->>'discount_percent')::numeric,
           (l->>'discount_amount')::numeric,
           (l->>'line_total')::numeric,
           NULLIF(l->>'notes', '')
      FROM jsonb_array_elements(v_lignes) AS l;

    -- --- Paiement (registre `payments`, comme le desktop) -------------------
    -- Une vente à terme (aucun acompte) n'est PAS un encaissement : écrire une
    -- ligne de 0 fausserait les états (le desktop additionne `payments.amount`).
    IF v_paid > 0.001 THEN
        INSERT INTO public.payments (
            sale_id, amount, payment_method, payment_date, collected_by)
        VALUES (v_sale_id, v_paid, v_method, now(), v_user_id);
    END IF;

    -- --- Client : la dette = ce qui n'a pas été payé ------------------------
    -- (CRÉDIT avec acompte : on n'inscrit que le reste dû, pas le total ;
    --  moyen de paiement différé non encaissé : le reliquat est dû aussi.)
    v_client_nom := NULL;
    IF p_customer_id IS NOT NULL THEN
        SELECT c.id, c.first_name, c.last_name, c.balance
          INTO v_customer
          FROM public.customers c
         WHERE c.id = p_customer_id;
        IF v_customer.id IS NOT NULL THEN
            v_client_nom := BTRIM(COALESCE(v_customer.first_name, '') || ' '
                                  || COALESCE(v_customer.last_name, ''));
            IF v_due > 0.001 THEN
                UPDATE public.customers
                   SET balance    = COALESCE(balance, 0) + v_due,
                       updated_at = now()
                 WHERE id = v_customer.id;
            END IF;
        END IF;
    END IF;

    -- --- Trésorerie : argent réellement encaissé (hors monnaie rendue) -----
    v_cash_in := v_paid - v_change;
    IF v_cash_in > 0.001 THEN
        -- Priorité : compte demandé, sinon compte de caisse actif, sinon
        -- premier compte actif (mêmes règles que default_cash_account()).
        v_account := NULL;
        IF p_account_id IS NOT NULL THEN
            SELECT a.id INTO v_account
              FROM public.treasury_accounts a
             WHERE a.id = p_account_id AND a.is_active;
        END IF;
        IF v_account IS NULL THEN
            SELECT a.id INTO v_account
              FROM public.treasury_accounts a
             WHERE a.is_active AND a.account_type = 'CASH'
             ORDER BY a.id LIMIT 1;
        END IF;
        IF v_account IS NULL THEN
            SELECT a.id INTO v_account
              FROM public.treasury_accounts a
             WHERE a.is_active ORDER BY a.id LIMIT 1;
        END IF;

        IF v_account IS NOT NULL THEN
            INSERT INTO public.treasury_movements (
                account_id, movement_type, amount, date, reference,
                description, category, reference_type, reference_id, user_id,
                created_at)
            VALUES (
                v_account, 'IN', v_cash_in, now(), v_number,
                'Encaissement vente ' || v_number, 'Ventes', 'SALE', v_sale_id,
                v_user_id, now());

            UPDATE public.treasury_accounts
               SET current_balance = COALESCE(current_balance, 0) + v_cash_in,
                   updated_at      = now()
             WHERE id = v_account;
        END IF;
    END IF;

    -- --- Journal d'audit des ventes (table admin : écrite ici en DEFINER) --
    INSERT INTO public.sale_logs (
        sale_id, sale_number, action, user_id, username, user_role,
        customer_id, customer_name, total_amount, payment_method,
        details, created_at)
    VALUES (
        v_sale_id, v_number, 'CREATE', v_user_id, v_username, v_role,
        p_customer_id, v_client_nom, v_total, v_method,
        format('Vente créée depuis mobile - %s article(s)', jsonb_array_length(v_lignes)),
        now());

    RETURN jsonb_build_object(
        'ok',             true,
        'message',        'Vente enregistrée.',
        'sale_id',        v_sale_id,
        'sale_number',    v_number,
        'store_id',       v_store_id,
        'items',          jsonb_array_length(v_lignes),
        'subtotal',       v_subtotal,
        'discount_amount', GREATEST(COALESCE(p_discount_amount, 0), 0),
        'tax_amount',     GREATEST(COALESCE(p_tax_amount, 0), 0),
        'total_amount',   v_total,
        'amount_paid',    v_paid,
        'due',            v_due,
        'change_amount',  v_change,
        'payment_status', v_status);
END;
$$;

REVOKE ALL ON FUNCTION public.app_create_sale(
    jsonb, integer, integer, numeric, numeric, text, numeric, text, text, integer
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_create_sale(
    jsonb, integer, integer, numeric, numeric, text, numeric, text, text, integer
) TO authenticated;


-- ----------------------------------------------------------------------------
-- 4) RPC : encaisser un paiement sur une facture existante
--
--    Réplique core/invoice_register_manager.py -> receive_payment :
--      * refus si le montant dépasse le reste dû ;
--      * amount_paid += montant ; PAYEE / PARTIELLEMENT_PAYEE ;
--      * mouvement de trésorerie IN + mise à jour du solde du compte ;
--      * ligne `payments` + journal `sale_logs` (action PAYMENT).
--
--    Droits : `create_sales` (caissier qui encaisse) ou `manage_treasury`.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_register_payment(
    p_sale_id        integer,
    p_amount         numeric,
    p_payment_method text    DEFAULT NULL,
    p_account_id     integer DEFAULT NULL,
    p_notes          text    DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id    integer;
    v_username   text;
    v_role       text;
    v_sale       record;
    v_due        numeric;
    v_new_paid   numeric;
    v_status     text;
    v_statut     text;
    v_method     text;
    v_account    integer;
    v_desc       text;
BEGIN
    IF NOT (app_security.can('create_sales') OR app_security.can('manage_treasury')) THEN
        RAISE EXCEPTION 'Encaissement non autorise pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » -----------------------
    -- (voir supabase_single_session.sql) : un encaissement venu d'un appareil
    -- dont la session a ete reprise ailleurs est refuse.
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    IF p_sale_id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Facture non précisée.');
    END IF;
    IF COALESCE(p_amount, 0) <= 0 THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Le montant doit être supérieur à 0.');
    END IF;

    SELECT u.id, u.username, u.role
      INTO v_user_id, v_username, v_role
      FROM public.users u
     WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
       AND u.active
     LIMIT 1;
    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Profil utilisateur actif introuvable pour ce compte.');
    END IF;

    SELECT s.id, s.sale_number, s.total_amount, s.amount_paid, s.payment_method,
           s.payment_status, s.sale_status, s.currency, s.customer_id
      INTO v_sale
      FROM public.sales s
     WHERE s.id = p_sale_id
     FOR UPDATE;

    IF v_sale.id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Facture introuvable.');
    END IF;
    IF v_sale.sale_status = 'CANCELLED' THEN
        RETURN jsonb_build_object('ok', false,
            'message', format('La facture %s est annulée : encaissement impossible.',
                              v_sale.sale_number));
    END IF;

    v_due := COALESCE(v_sale.total_amount, 0) - COALESCE(v_sale.amount_paid, 0);
    IF v_due <= 0.001 THEN
        RETURN jsonb_build_object('ok', false,
            'message', format('La facture %s est déjà entièrement réglée.',
                              v_sale.sale_number));
    END IF;
    IF p_amount > v_due + 0.001 THEN
        RETURN jsonb_build_object('ok', false,
            'message', format('Montant supérieur au reste dû (%s).', v_due));
    END IF;

    v_new_paid := COALESCE(v_sale.amount_paid, 0) + p_amount;
    IF v_new_paid >= COALESCE(v_sale.total_amount, 0) - 0.001 THEN
        v_status := 'PAID';
        v_statut := 'PAYEE';
    ELSE
        v_status := 'PARTIAL';
        v_statut := 'PARTIELLEMENT_PAYEE';
    END IF;

    v_method := UPPER(COALESCE(NULLIF(BTRIM(p_payment_method), ''),
                               NULLIF(BTRIM(v_sale.payment_method), ''),
                               'CASH'));

    UPDATE public.sales
       SET amount_paid    = v_new_paid,
           payment_status = v_status,
           statut         = v_statut,
           payment_method = v_method
     WHERE id = v_sale.id;

    -- --- Ligne de paiement -------------------------------------------------
    INSERT INTO public.payments (
        sale_id, amount, payment_method, payment_date, collected_by, notes)
    VALUES (v_sale.id, p_amount, v_method, now(), v_user_id,
            NULLIF(BTRIM(COALESCE(p_notes, '')), ''));

    -- --- Client : le solde dû est diminué du montant encaissé --------------
    -- Sans cela, une facture payée laissait le client « endetté » à vie :
    -- le crédit était ensuite bloqué par le plafond et les relances fausses.
    IF v_sale.customer_id IS NOT NULL THEN
        UPDATE public.customers
           SET balance    = GREATEST(COALESCE(balance, 0) - p_amount, 0),
               updated_at = now()
         WHERE id = v_sale.customer_id;
    END IF;

    -- --- Trésorerie : encaissement sur le compte de caisse par défaut ------
    v_account := NULL;
    IF p_account_id IS NOT NULL THEN
        SELECT a.id INTO v_account
          FROM public.treasury_accounts a
         WHERE a.id = p_account_id AND a.is_active;
    END IF;
    IF v_account IS NULL THEN
        SELECT a.id INTO v_account
          FROM public.treasury_accounts a
         WHERE a.is_active AND a.account_type = 'CASH'
         ORDER BY a.id LIMIT 1;
    END IF;
    IF v_account IS NULL THEN
        SELECT a.id INTO v_account
          FROM public.treasury_accounts a
         WHERE a.is_active ORDER BY a.id LIMIT 1;
    END IF;

    IF v_account IS NOT NULL THEN
        v_desc := 'Encaissement facture ' || v_sale.sale_number
                  || CASE WHEN COALESCE(BTRIM(p_notes), '') <> ''
                          THEN ' — ' || BTRIM(p_notes) ELSE '' END;

        INSERT INTO public.treasury_movements (
            account_id, movement_type, amount, date, reference, description,
            category, reference_type, reference_id, user_id, created_at)
        VALUES (v_account, 'IN', p_amount, now(), v_sale.sale_number, v_desc,
                'Ventes', 'SALE', v_sale.id, v_user_id, now());

        UPDATE public.treasury_accounts
           SET current_balance = COALESCE(current_balance, 0) + p_amount,
               updated_at      = now()
         WHERE id = v_account;
    END IF;

    -- --- Journal d'audit ---------------------------------------------------
    INSERT INTO public.sale_logs (
        sale_id, sale_number, action, user_id, username, user_role,
        total_amount, payment_method, details, created_at)
    VALUES (
        v_sale.id, v_sale.sale_number, 'PAYMENT', v_user_id, v_username, v_role,
        p_amount, v_method,
        format('Encaissement mobile : %s (reste dû : %s)',
               p_amount, GREATEST(COALESCE(v_sale.total_amount, 0) - v_new_paid, 0)),
        now());

    RETURN jsonb_build_object(
        'ok',             true,
        'message',        format('Paiement de %s enregistré sur %s.', p_amount,
                                 v_sale.sale_number),
        'sale_id',        v_sale.id,
        'sale_number',    v_sale.sale_number,
        'amount_paid',    v_new_paid,
        'due',            GREATEST(COALESCE(v_sale.total_amount, 0) - v_new_paid, 0),
        'payment_status', v_status);
END;
$$;

REVOKE ALL ON FUNCTION public.app_register_payment(
    integer, numeric, text, integer, text
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_register_payment(
    integer, numeric, text, integer, text
) TO authenticated;


-- ----------------------------------------------------------------------------
-- 5) RPC : mouvement de stock (inventaire terrain)
--
--    Réplique ui/views/stock_view.py -> NewMovementDialog :
--      * IN / ADJUST : products.quantity += quantité ;
--      * OUT / LOSS  : products.quantity -= quantité (refusé si insuffisant) ;
--      * unit_price et total_value renseignés pour IN/ADJUST seulement ;
--      * store_id = magasin du produit (sinon magasin transmis).
--
--    Droits : `manage_stock` (ADMIN, GESTIONNAIRE, SUPERVISEUR).
--    Un simple lecteur de stock (`view_stock`) ne peut donc pas ajuster.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_stock_movement(
    p_product_id    integer,
    p_movement_type text,
    p_quantity      numeric,
    p_reason        text    DEFAULT NULL,
    p_unit_cost     numeric DEFAULT NULL,
    p_reference     text    DEFAULT NULL,
    p_notes         text    DEFAULT NULL,
    p_store_id      integer DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id   integer;
    v_type      text := UPPER(COALESCE(BTRIM(p_movement_type), ''));
    v_produit   record;
    v_qty       numeric := ABS(COALESCE(p_quantity, 0));
    v_unite     numeric;
    v_stock     numeric;
    v_movement  integer;
BEGIN
    IF NOT app_security.can('manage_stock') THEN
        RAISE EXCEPTION 'Modification de stock non autorisee pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » -----------------------
    -- (voir supabase_single_session.sql) : un mouvement de stock venu d'un
    -- appareil dont la session a ete reprise ailleurs est refuse.
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    IF v_type NOT IN ('IN', 'OUT', 'ADJUST', 'LOSS') THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Type de mouvement invalide (IN, OUT, ADJUST ou LOSS).');
    END IF;
    IF v_qty <= 0 THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'La quantité doit être supérieure à 0.');
    END IF;

    SELECT u.id INTO v_user_id
      FROM public.users u
     WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
       AND u.active
     LIMIT 1;
    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Profil utilisateur actif introuvable pour ce compte.');
    END IF;

    SELECT p.id, p.name, p.quantity, p.store_id, p.purchase_price
      INTO v_produit
      FROM public.products p
     WHERE p.id = COALESCE(p_product_id, -1)
     FOR UPDATE;
    IF v_produit.id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Produit introuvable.');
    END IF;

    v_stock := COALESCE(v_produit.quantity, 0);
    IF v_type IN ('OUT', 'LOSS') AND v_qty > v_stock THEN
        RETURN jsonb_build_object('ok', false,
            'message', format('Stock insuffisant pour « %s » : %s disponible(s).',
                              v_produit.name, v_stock));
    END IF;

    IF v_type IN ('IN', 'ADJUST') THEN
        v_unite := COALESCE(p_unit_cost, v_produit.purchase_price);
        v_stock := v_stock + v_qty;
    ELSE
        v_unite := NULL;                       -- sortie : prix d'entrée non requis
        v_stock := v_stock - v_qty;
    END IF;

    UPDATE public.products
       SET quantity   = v_stock,
           updated_at = now()
     WHERE id = v_produit.id;

    INSERT INTO public.inventory_movements (
        product_id, movement_type, quantity, unit_price, total_value,
        reference, reason, notes, user_id, store_id, date, created_at)
    VALUES (
        v_produit.id, v_type, v_qty, v_unite,
        CASE WHEN v_unite IS NULL THEN NULL ELSE v_qty * v_unite END,
        NULLIF(BTRIM(COALESCE(p_reference, '')), ''),
        COALESCE(NULLIF(BTRIM(p_reason), ''), 'Opération manuelle'),
        NULLIF(BTRIM(COALESCE(p_notes, '')), ''),
        v_user_id,
        COALESCE(v_produit.store_id, p_store_id),
        now(), now())
    RETURNING id INTO v_movement;

    RETURN jsonb_build_object(
        'ok',            true,
        'message',       format('Mouvement %s de %s enregistré.', v_type, v_qty),
        'movement_id',   v_movement,
        'product_id',    v_produit.id,
        'product_name',  v_produit.name,
        'movement_type', v_type,
        'quantity',      v_qty,
        'new_quantity',  v_stock);
END;
$$;

REVOKE ALL ON FUNCTION public.app_stock_movement(
    integer, text, numeric, text, numeric, text, text, integer
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_stock_movement(
    integer, text, numeric, text, numeric, text, text, integer
) TO authenticated;


-- ----------------------------------------------------------------------------
-- ------------------------------------------------------------------------------
-- 6) RPC : annuler une vente (à terme, crédit, encaissée ou partiellement payée)
--
--    Réplique ui/views/sale_services.py -> cancel_sale, complétée par la
--    compensation de trésorerie de ui/views/stock_view.py :
--      * restaure le stock de chaque ligne vendue ;
--      * retire du solde du client la part encore due (crédit) ;
--      * compense chaque encaissement lié (mouvement OUT par mouvement IN) ;
--      * vente -> sale_status CANCELLED / statut ANNULEE / payment_status
--        CANCELLED (encaisser une facture annulée redevient impossible) ;
--      * journal d'audit `sale_logs` (action CANCEL), comme le desktop.
--
--    Droits : `cancel_sales` (ADMIN, GESTIONNAIRE, SUPERVISEUR) : un caissier ou
--    un assistant reçoit 42501 — même matrice que core/permissions.py.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_cancel_sale(
    p_sale_id integer,
    p_reason  text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id       integer;
    v_username      text;
    v_role          text;
    v_sale          record;
    v_customer_name text;
    v_due           numeric := 0;
    v_refund        numeric := 0;
    v_moves         integer := 0;
    v_items         integer := 0;
    v_item          record;
    v_mv            record;
    v_reason        text := NULLIF(BTRIM(COALESCE(p_reason, '')), '');
BEGIN
    -- --- Droits -------------------------------------------------------------
    IF NOT app_security.can('cancel_sales') THEN
        RAISE EXCEPTION 'Annulation de vente non autorisee pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » -----------------------
    -- (voir supabase_single_session.sql) : une annulation venu d'un appareil
    -- dont la session a ete reprise ailleurs est refusee.
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    -- --- Profil actif -------------------------------------------------------
    SELECT u.id, u.username, u.role
      INTO v_user_id, v_username, v_role
      FROM public.users u
     WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
       AND u.active
     LIMIT 1;
    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Profil utilisateur actif introuvable pour ce compte.');
    END IF;

    -- --- Vente (verrou : une 2e annulation simultanée est refusée ci-dessous) -
    SELECT s.id, s.sale_number, s.customer_id, s.total_amount, s.amount_paid,
           s.payment_method, s.payment_status, s.sale_status, s.statut
      INTO v_sale
      FROM public.sales s
     WHERE s.id = COALESCE(p_sale_id, -1)
       FOR UPDATE;
    IF v_sale.id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Vente introuvable.');
    END IF;
    IF v_sale.sale_status = 'CANCELLED' THEN
        RETURN jsonb_build_object('ok', false,
            'message', format('La vente %s est déjà annulée.', v_sale.sale_number));
    END IF;

    -- --- 1) Stock : remise en stock des quantités vendues --------------------
    FOR v_item IN
        SELECT si.product_id, si.quantity
          FROM public.sale_items si
         WHERE si.sale_id = v_sale.id
    LOOP
        UPDATE public.products
           SET quantity   = COALESCE(quantity, 0) + COALESCE(v_item.quantity, 0),
               updated_at = now()
         WHERE id = v_item.product_id;
        v_items := v_items + 1;
    END LOOP;

    -- --- 2) Dette du client : la part encore due disparaît -------------------
    v_due := GREATEST(COALESCE(v_sale.total_amount, 0)
                      - COALESCE(v_sale.amount_paid, 0), 0);
    IF v_sale.customer_id IS NOT NULL AND v_due > 0.001 THEN
        UPDATE public.customers
           SET balance    = GREATEST(COALESCE(balance, 0) - v_due, 0),
               updated_at = now()
         WHERE id = v_sale.customer_id;
    END IF;

    -- --- 3) Trésorerie : compensation des encaissements liés -----------------
    -- Chaque mouvement IN de la vente reçoit un mouvement OUT équivalent
    -- (remboursement), comme cancel_sale / stock_view côté desktop.
    FOR v_mv IN
        SELECT id, account_id, amount
          FROM public.treasury_movements
         WHERE reference_type = 'SALE'
           AND reference_id   = v_sale.id
           AND movement_type  = 'IN'
           AND COALESCE(amount, 0) > 0.001
    LOOP
        INSERT INTO public.treasury_movements (
            account_id, movement_type, amount, date, reference,
            description, category, reference_type, reference_id, user_id,
            created_at)
        VALUES (
            v_mv.account_id, 'OUT', v_mv.amount, now(), v_sale.sale_number,
            'Annulation vente ' || v_sale.sale_number
                || CASE WHEN v_reason IS NULL THEN '' ELSE ' : ' || v_reason END,
            'Ventes', 'SALE_CANCEL', v_sale.id, v_user_id, now());

        UPDATE public.treasury_accounts
           SET current_balance = GREATEST(COALESCE(current_balance, 0)
                                           - v_mv.amount, 0),
               updated_at      = now()
         WHERE id = v_mv.account_id;

        v_refund := v_refund + v_mv.amount;
        v_moves  := v_moves + 1;
    END LOOP;

    -- --- 4) Facture annulée (encaisser une telle facture devient impossible) --
    -- `sales` n'a PAS de colonne updated_at (schéma réel) : on ne la touche pas.
    UPDATE public.sales
       SET sale_status    = 'CANCELLED',
           statut         = 'ANNULEE',
           payment_status = 'CANCELLED',
           notes          = 'Annulée le ' || to_char(now(), 'DD/MM/YYYY HH24:MI')
                            || CASE WHEN v_reason IS NULL THEN ''
                                    ELSE ' : ' || v_reason END
                            || COALESCE(' — ' || NULLIF(BTRIM(notes), ''), '')
     WHERE id = v_sale.id;

    -- --- 5) Journal d'audit (table admin : écrite ici en DEFINER) ------------
    SELECT BTRIM(COALESCE(c.first_name, '') || ' ' || COALESCE(c.last_name, ''))
      INTO v_customer_name
      FROM public.customers c
     WHERE c.id = v_sale.customer_id;

    INSERT INTO public.sale_logs (
        sale_id, sale_number, action, user_id, username, user_role,
        customer_id, customer_name, total_amount, payment_method,
        details, created_at)
    VALUES (
        v_sale.id, v_sale.sale_number, 'CANCEL', v_user_id, v_username, v_role,
        v_sale.customer_id, NULLIF(COALESCE(v_customer_name, ''), ''),
        v_sale.total_amount, v_sale.payment_method,
        format('Vente annulée depuis mobile — %s',
               COALESCE(v_reason, 'aucun motif précisé')),
        now());

    RETURN jsonb_build_object(
        'ok',             true,
        'message',         format('Vente %s annulée : %s article(s) remis en stock, %s retirés de la caisse.',
                                  v_sale.sale_number, v_items, v_refund),
        'sale_id',        v_sale.id,
        'sale_number',    v_sale.sale_number,
        'items_restored', v_items,
        'due_cancelled',  v_due,
        'refunded',       v_refund,
        'movements',      v_moves);
END;
$$;

REVOKE ALL ON FUNCTION public.app_cancel_sale(integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_cancel_sale(integer, text) TO authenticated;

-- ---------------------------------------------------------------------------- 
-- 7) Trésorerie : comptes, mouvements, transferts, clôture mensuelle
--
--    Réplique la logique de :
--      * desktop : core/treasury_manager.py (create_account, add_movement,
--                  transfer, compute_month_summary, close_month)
--      * web     : web/src/api/treasuryApi.js (saveAccount, createMovement,
--                  computeMonthlyPreview, closeMonth)
--      * mobile  : mobile/src/api/treasuryApi.js
--
--    Le mobile ne peut PAS écrire en direct sur `treasury_accounts` /
--    `treasury_movements` / `monthly_closures` (RLS réservée aux admins) :
--    tout passe par ces fonctions qui vérifient le rôle côté serveur,
--    valident les saisies et mettent à jour les soldes dans la même
--    transaction que le mouvement (jamais un mouvement sans solde).
-- ----------------------------------------------------------------------------

-- 7a) Créer / modifier un compte de trésorerie.
--     p_id NULL  -> création (current_balance = initial_balance, comme
--                   TreasuryManager.create_account) ;
--     p_id fixé  -> modification (le solde courant n'est JAMAIS touché ici :
--                   il n'évolue que par les mouvements).
CREATE OR REPLACE FUNCTION public.app_treasury_save_account(
    p_id              integer DEFAULT NULL,
    p_name            text    DEFAULT NULL,
    p_account_type    text    DEFAULT 'CASH',
    p_currency        text    DEFAULT 'FCFA',
    p_initial_balance numeric DEFAULT 0,
    p_bank_name       text    DEFAULT NULL,
    p_account_number  text    DEFAULT NULL,
    p_phone_number    text    DEFAULT NULL,
    p_is_active       boolean DEFAULT true,
    p_is_default      boolean DEFAULT false,
    p_notes           text    DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_type      text := UPPER(COALESCE(NULLIF(BTRIM(p_account_type), ''), 'CASH'));
    v_name      text := BTRIM(COALESCE(p_name, ''));
    v_currency  text := COALESCE(NULLIF(BTRIM(p_currency), ''), 'FCFA');
    v_balance   numeric := COALESCE(p_initial_balance, 0);
    v_id        integer;
BEGIN
    -- --- Contrôle de droit (le serveur décide, pas l'application) -----------
    IF NOT app_security.can('manage_treasury') THEN
        RAISE EXCEPTION 'Gestion de la tresorerie non autorisee pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » -----------------------
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    -- --- Validations serveur ------------------------------------------------
    IF v_name = '' THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Nom du compte requis.');
    END IF;
    IF v_type NOT IN ('CASH', 'BANK', 'MOBILE_MONEY') THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Type de compte invalide (CASH, BANK ou MOBILE_MONEY).');
    END IF;

    IF p_id IS NULL THEN
        INSERT INTO public.treasury_accounts (
            name, account_type, currency, initial_balance, current_balance,
            bank_name, account_number, phone_number, is_active, is_default,
            notes, created_at, updated_at)
        VALUES (
            v_name, v_type, v_currency, v_balance, v_balance,
            NULLIF(BTRIM(COALESCE(p_bank_name, '')), ''),
            NULLIF(BTRIM(COALESCE(p_account_number, '')), ''),
            NULLIF(BTRIM(COALESCE(p_phone_number, '')), ''),
            COALESCE(p_is_active, true), COALESCE(p_is_default, false),
            NULLIF(BTRIM(COALESCE(p_notes, '')), ''), now(), now())
        RETURNING id INTO v_id;
    ELSE
        UPDATE public.treasury_accounts
           SET name           = v_name,
               account_type   = v_type,
               currency       = v_currency,
               initial_balance = v_balance,
               bank_name      = NULLIF(BTRIM(COALESCE(p_bank_name, '')), ''),
               account_number = NULLIF(BTRIM(COALESCE(p_account_number, '')), ''),
               phone_number   = NULLIF(BTRIM(COALESCE(p_phone_number, '')), ''),
               is_active      = COALESCE(p_is_active, true),
               is_default     = COALESCE(p_is_default, false),
               notes          = NULLIF(BTRIM(COALESCE(p_notes, '')), ''),
               updated_at     = now()
         WHERE id = p_id
         RETURNING id INTO v_id;

        IF v_id IS NULL THEN
            RETURN jsonb_build_object('ok', false,
                'message', 'Compte introuvable.');
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'ok', true,
        'message', CASE WHEN p_id IS NULL THEN 'Compte cree.'
                        ELSE 'Compte mis a jour.' END,
        'account_id', v_id);
END;
$$;

REVOKE ALL ON FUNCTION public.app_treasury_save_account(
    integer, text, text, text, numeric, text, text, text, boolean, boolean, text
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_treasury_save_account(
    integer, text, text, text, numeric, text, text, text, boolean, boolean, text
) TO authenticated;


-- 7b) Saisir un mouvement manuel (IN / OUT) et ajuster le solde du compte.
--     Même contrat que TreasuryManager.add_movement : montant strictement
--     positif, compte actif, solde ± amount dans la MÊME transaction.
CREATE OR REPLACE FUNCTION public.app_treasury_move(
    p_account_id     integer,
    p_movement_type  text,
    p_amount         numeric,
    p_reference      text DEFAULT NULL,
    p_description    text DEFAULT NULL,
    p_category       text DEFAULT NULL,
    p_movement_date  timestamptz DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id   integer;
    v_type      text := UPPER(COALESCE(NULLIF(BTRIM(p_movement_type), ''), ''));
    v_amount    numeric := COALESCE(p_amount, 0);
    v_account   record;
    v_mv_id     integer;
BEGIN
    -- --- Contrôle de droit ---------------------------------------------------
    IF NOT app_security.can('manage_treasury') THEN
        RAISE EXCEPTION 'Saisie de mouvement non autorisee pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » ------------------------
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    -- --- Identité (auteur du mouvement) --------------------------------------
    SELECT u.id INTO v_user_id
      FROM public.users u
     WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
       AND u.active
     LIMIT 1;

    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object(
            'ok', false,
            'message', 'Profil utilisateur actif introuvable pour ce compte.');
    END IF;

    -- --- Validations serveur --------------------------------------------------
    IF v_type NOT IN ('IN', 'OUT') THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Type de mouvement invalide (IN ou OUT).');
    END IF;
    IF v_amount <= 0 THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Le montant doit etre positif.');
    END IF;

    -- Verrou de ligne : deux saisies simultanées ne doivent pas perdre la
    -- mise à jour du solde (UPDATE perdu sinon en écriture concurrente).
    SELECT a.id, a.name, a.is_active
      INTO v_account
      FROM public.treasury_accounts a
     WHERE a.id = p_account_id
     FOR UPDATE;

    IF v_account.id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Compte introuvable.');
    END IF;
    IF NOT v_account.is_active THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Ce compte est inactif : mouvement refuse.');
    END IF;

    INSERT INTO public.treasury_movements (
        account_id, movement_type, amount, date, reference, description,
        category, reference_type, reference_id, user_id, created_at)
    VALUES (
        v_account.id, v_type, v_amount,
        COALESCE(p_movement_date, now()),
        NULLIF(BTRIM(COALESCE(p_reference, '')), ''),
        NULLIF(BTRIM(COALESCE(p_description, '')), ''),
        NULLIF(BTRIM(COALESCE(p_category, '')), ''),
        'MANUAL', NULL, v_user_id, now())
    RETURNING id INTO v_mv_id;

    UPDATE public.treasury_accounts
       SET current_balance = COALESCE(current_balance, 0)
                             + CASE WHEN v_type = 'IN' THEN v_amount
                                    ELSE -v_amount END,
           updated_at      = now()
     WHERE id = v_account.id;

    RETURN jsonb_build_object(
        'ok', true,
        'message', 'Mouvement enregistre.',
        'movement_id', v_mv_id,
        'account_id', v_account.id);
END;
$$;

REVOKE ALL ON FUNCTION public.app_treasury_move(
    integer, text, numeric, text, text, text, timestamptz
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_treasury_move(
    integer, text, numeric, text, text, text, timestamptz
) TO authenticated;


-- 7c) Transfert entre deux comptes (OUT sur l'origine + IN sur la
--     destination, reference_type TRANSFER) — miroir TreasuryManager.transfer.
CREATE OR REPLACE FUNCTION public.app_treasury_transfer(
    p_from_account_id integer,
    p_to_account_id   integer,
    p_amount          numeric,
    p_description     text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id   integer;
    v_amount    numeric := COALESCE(p_amount, 0);
    v_from      record;
    v_to        record;
    v_mv_out    integer;
    v_mv_in     integer;
BEGIN
    -- --- Contrôle de droit ---------------------------------------------------
    IF NOT app_security.can('manage_treasury') THEN
        RAISE EXCEPTION 'Transfert non autorise pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » ------------------------
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    -- --- Identité -------------------------------------------------------------
    SELECT u.id INTO v_user_id
      FROM public.users u
     WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
       AND u.active
     LIMIT 1;

    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object(
            'ok', false,
            'message', 'Profil utilisateur actif introuvable pour ce compte.');
    END IF;

    -- --- Validations serveur ---------------------------------------------------
    IF v_amount <= 0 THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Le montant doit etre positif.');
    END IF;
    IF p_from_account_id IS NULL OR p_to_account_id IS NULL
       OR p_from_account_id = p_to_account_id THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Choisissez deux comptes differents.');
    END IF;

    -- Verrouille les DEUX comptes (ordre des id implicite : deux transferts
    -- croisés simultanés ne peuvent ni mort-de-verrouiller ni perdre un solde).
    SELECT a.id, a.name, a.is_active INTO v_from
      FROM public.treasury_accounts a
     WHERE a.id = p_from_account_id
     FOR UPDATE;
    SELECT a.id, a.name, a.is_active INTO v_to
      FROM public.treasury_accounts a
     WHERE a.id = p_to_account_id
     FOR UPDATE;

    IF v_from.id IS NULL OR v_to.id IS NULL THEN
        RETURN jsonb_build_object('ok', false, 'message', 'Compte introuvable.');
    END IF;
    IF NOT v_from.is_active OR NOT v_to.is_active THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Les deux comptes doivent etre actifs.');
    END IF;

    INSERT INTO public.treasury_movements (
        account_id, movement_type, amount, date, reference, description,
        category, reference_type, reference_id, user_id, created_at)
    VALUES (
        v_from.id, 'OUT', v_amount, now(), NULL,
        'Transfert vers ' || v_to.name
            || CASE WHEN NULLIF(BTRIM(COALESCE(p_description, '')), '') IS NULL
                    THEN '' ELSE ' — ' || BTRIM(p_description) END,
        'Transfert', 'TRANSFER', NULL, v_user_id, now())
    RETURNING id INTO v_mv_out;

    INSERT INTO public.treasury_movements (
        account_id, movement_type, amount, date, reference, description,
        category, reference_type, reference_id, user_id, created_at)
    VALUES (
        v_to.id, 'IN', v_amount, now(), NULL,
        'Transfert depuis ' || v_from.name
            || CASE WHEN NULLIF(BTRIM(COALESCE(p_description, '')), '') IS NULL
                    THEN '' ELSE ' — ' || BTRIM(p_description) END,
        'Transfert', 'TRANSFER', NULL, v_user_id, now())
    RETURNING id INTO v_mv_in;

    UPDATE public.treasury_accounts
       SET current_balance = COALESCE(current_balance, 0) - v_amount,
           updated_at      = now()
     WHERE id = v_from.id;

    UPDATE public.treasury_accounts
       SET current_balance = COALESCE(current_balance, 0) + v_amount,
           updated_at      = now()
     WHERE id = v_to.id;

    RETURN jsonb_build_object(
        'ok', true,
        'message', format('Transfert de %s effectue : %s -> %s.',
                          v_amount, v_from.name, v_to.name),
        'movement_out_id', v_mv_out,
        'movement_in_id', v_mv_in);
END;
$$;

REVOKE ALL ON FUNCTION public.app_treasury_transfer(
    integer, integer, numeric, text
) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_treasury_transfer(
    integer, integer, numeric, text
) TO authenticated;


-- 7d) Aperçu des totaux d'une période 'YYYY-MM' (miroir
--     TreasuryManager.compute_month_summary / web computeMonthlyPreview).
--     Lecture seule : autorisée à tout rôle vue_trésorerie, sert à afficher
--     la confirmation avant `app_treasury_close_month`.
CREATE OR REPLACE FUNCTION public.app_treasury_month_preview(p_period text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_start   timestamptz;
    v_end     timestamptz;
    v_exists  record;
    v_count   integer;
    v_sales   numeric;
    v_collect numeric;
    v_out     numeric;
BEGIN
    IF NOT (app_security.can('view_treasury') OR app_security.can('manage_treasury')) THEN
        RAISE EXCEPTION 'Consultation de la tresorerie non autorisee pour votre role (%)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- Période attendue 'YYYY-MM' (rejet d'une saisie libre faussant les bornes).
    IF p_period !~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Periode invalide (format YYYY-MM attendu).');
    END IF;

    v_start := (p_period || '-01')::timestamptz;
    v_end   := v_start + interval '1 month';

    -- Ventes du mois : ni annulations, ni avoirs (mêmes filtres que desktop).
    SELECT COUNT(*),
           COALESCE(SUM(s.total_amount), 0),
           COALESCE(SUM(GREATEST(COALESCE(s.amount_paid, 0)
                                 - COALESCE(s.change_amount, 0), 0)), 0)
      INTO v_count, v_sales, v_collect
      FROM public.sales s
     WHERE s.sale_date >= v_start AND s.sale_date < v_end
       AND s.sale_status IS DISTINCT FROM 'CANCELLED'
       AND s.type_document IS DISTINCT FROM 'AVOIR';

    -- Dépenses : sorties hors encaissements de ventes (recalculés ici,
    -- le client n'est jamais cru).
    SELECT COALESCE(SUM(m.amount), 0)
      INTO v_out
      FROM public.treasury_movements m
     WHERE m.movement_type = 'OUT'
       AND m.reference_type IS DISTINCT FROM 'SALE'
       AND m.date >= v_start AND m.date < v_end;

    SELECT c.status, c.closed_at, c.sales_count, c.total_sales,
           c.total_collected, c.total_credit, c.total_out, c.net, c.notes
      INTO v_exists
      FROM public.monthly_closures c
     WHERE c.period = p_period;

    RETURN jsonb_build_object(
        'ok', true,
        'period', p_period,
        'sales_count', v_count,
        'total_sales', v_sales,
        'total_collected', v_collect,
        'total_credit', v_sales - v_collect,
        'total_out', v_out,
        'net', v_collect - v_out,
        'closed', COALESCE(v_exists.status = 'CLOSED', false),
        'closed_at', v_exists.closed_at,
        'notes', v_exists.notes);
END;
$$;

REVOKE ALL ON FUNCTION public.app_treasury_month_preview(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_treasury_month_preview(text) TO authenticated;


-- 7e) Clôture mensuelle : recalcule les totaux côté serveur puis fige la
--     période dans `monthly_closures` (statut CLOSED). Refus si déjà
--     clôturé — miroir TreasuryManager.close_month / web closeMonth.
--     Droits : ADMIN uniquement (identique au bouton web « réservé aux
--     administrateurs » ; `app_security.can('manage_treasury')` ne suffit pas).
CREATE OR REPLACE FUNCTION public.app_treasury_close_month(
    p_period text,
    p_notes  text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id   integer;
    v_start     timestamptz;
    v_end       timestamptz;
    v_status    text;
    v_count     integer;
    v_sales     numeric;
    v_collect   numeric;
    v_out       numeric;
    v_balances  text;
BEGIN
    -- --- Contrôle de droit : strictement admin (comme le web) ---------------
    IF app_security.current_role() IS DISTINCT FROM 'ADMIN' THEN
        RAISE EXCEPTION 'Cloture mensuelle reservee aux administrateurs (role %)',
            COALESCE(app_security.current_role(), 'inconnu')
            USING ERRCODE = '42501';
    END IF;

    -- --- Verrou « une seule session par utilisateur » ------------------------
    IF NOT app_security.session_is_active() THEN
        RETURN jsonb_build_object('ok', false, 'code', 'SESSION_CLOSED',
            'message', 'Session fermee : ce compte est utilise sur un autre '
                       'appareil. Reconnectez-vous pour reprendre la main.');
    END IF;

    -- --- Identité -------------------------------------------------------------
    SELECT u.id INTO v_user_id
      FROM public.users u
     WHERE u.email = (SELECT email FROM auth.users WHERE id = auth.uid())
       AND u.active
     LIMIT 1;

    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object(
            'ok', false,
            'message', 'Profil utilisateur actif introuvable pour ce compte.');
    END IF;

    -- --- Période ---------------------------------------------------------------
    IF p_period !~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Periode invalide (format YYYY-MM attendu).');
    END IF;

    SELECT c.status INTO v_status
      FROM public.monthly_closures c
     WHERE c.period = p_period;

    IF v_status = 'CLOSED' THEN
        RETURN jsonb_build_object('ok', false,
            'message', 'Ce mois est deja cloture.');
    END IF;

    -- --- Totaux recalculés par le serveur (le client n'est jamais cru) --------
    v_start := (p_period || '-01')::timestamptz;
    v_end   := v_start + interval '1 month';

    SELECT COUNT(*),
           COALESCE(SUM(s.total_amount), 0),
           COALESCE(SUM(GREATEST(COALESCE(s.amount_paid, 0)
                                 - COALESCE(s.change_amount, 0), 0)), 0)
      INTO v_count, v_sales, v_collect
      FROM public.sales s
     WHERE s.sale_date >= v_start AND s.sale_date < v_end
       AND s.sale_status IS DISTINCT FROM 'CANCELLED'
       AND s.type_document IS DISTINCT FROM 'AVOIR';

    SELECT COALESCE(SUM(m.amount), 0)
      INTO v_out
      FROM public.treasury_movements m
     WHERE m.movement_type = 'OUT'
       AND m.reference_type IS DISTINCT FROM 'SALE'
       AND m.date >= v_start AND m.date < v_end;

    -- Snapshot JSON des soldes (format du desktop : balances est une colonne
    -- TEXT contenant du JSON).
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'id', a.id, 'name', a.name,
               'account_type', a.account_type,
               'currency', a.currency,
               'balance', COALESCE(a.current_balance, 0)) ORDER BY a.id), '[]'::jsonb)::text
      INTO v_balances
      FROM public.treasury_accounts a
     WHERE a.is_active;

    -- --- UPSERT de la clôture --------------------------------------------------
    INSERT INTO public.monthly_closures (
        period, sales_count, total_sales, total_collected, total_credit,
        total_out, net, balances, status, closed_by, closed_at, notes, created_at)
    VALUES (
        p_period, v_count, v_sales, v_collect, v_sales - v_collect,
        v_out, v_collect - v_out, v_balances, 'CLOSED', v_user_id, now(),
        NULLIF(BTRIM(COALESCE(p_notes, '')), ''), now())
    ON CONFLICT (period) DO UPDATE
       SET sales_count     = EXCLUDED.sales_count,
           total_sales     = EXCLUDED.total_sales,
           total_collected = EXCLUDED.total_collected,
           total_credit    = EXCLUDED.total_credit,
           total_out       = EXCLUDED.total_out,
           net             = EXCLUDED.net,
           balances        = EXCLUDED.balances,
           status          = 'CLOSED',
           closed_by       = EXCLUDED.closed_by,
           closed_at       = EXCLUDED.closed_at,
           notes           = COALESCE(EXCLUDED.notes, monthly_closures.notes);

    RETURN jsonb_build_object(
        'ok', true,
        'message', 'Mois cloture : totaux figes.',
        'period', p_period,
        'sales_count', v_count,
        'total_sales', v_sales,
        'total_collected', v_collect,
        'total_credit', v_sales - v_collect,
        'total_out', v_out,
        'net', v_collect - v_out,
        'closed_by', v_user_id);
END;
$$;

REVOKE ALL ON FUNCTION public.app_treasury_close_month(text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.app_treasury_close_month(text, text) TO authenticated;


-- 8) Vérification : RPC mobiles installées + droits accordés
-- ----------------------------------------------------------------------------
SELECT p.proname                  AS fonction,
       pg_get_function_identity_arguments(p.oid) AS arguments
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname IN ('public', 'app_security')
  AND p.proname IN ('app_mobile_context', 'app_create_sale',
                    'app_register_payment', 'app_stock_movement',
                    'app_cancel_sale',
                    'app_treasury_save_account', 'app_treasury_move',
                    'app_treasury_transfer', 'app_treasury_month_preview',
                    'app_treasury_close_month',
                    'current_role', 'can')
ORDER BY p.proname;









