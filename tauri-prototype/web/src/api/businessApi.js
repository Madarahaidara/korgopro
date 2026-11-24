import { supabase } from './supabase';

const PRODUCT_COLUMNS = 'id,organization_id,store_id,supplier_id,code,name,category,quantity,min_stock,max_stock,purchase_price,sale_price,active,suppliers(name,code)';
const SALE_COLUMNS = 'id,organization_id,store_id,sale_number,sale_date,total_amount,amount_paid,change_amount,payment_status,sale_status,type_document,payment_method,currency,customer_id,customers(first_name,last_name,company)';
const PROFORMA_COLUMNS = 'id,organization_id,proforma_number,created_date,valid_until,total_amount,status,customer_id,customers(first_name,last_name,company)';

function client() {
  if (!supabase) throw new Error('Supabase n’est pas configuré.');
  return supabase;
}

function requireOrganization(organizationId) {
  if (!organizationId) throw new Error('Sélectionnez une entreprise avant de continuer.');
  return organizationId;
}

async function run(query) {
  const { data, error } = await query;
  if (error) {
    const failure = new Error(error.message || 'Erreur Supabase.');
    failure.code = error.code;
    throw failure;
  }
  return data;
}

async function runAllPages(queryFactory, pageSize = 500) {
  const rows = [];
  let offset = 0;
  while (true) {
    const { data: page, error, count } = await queryFactory().range(offset, offset + pageSize - 1);
    if (error) {
      const failure = new Error(error.message || 'Erreur Supabase.');
      failure.code = error.code;
      throw failure;
    }
    const pageRows = Array.isArray(page) ? page : [];
    rows.push(...pageRows);
    if (!pageRows.length || (count != null ? offset + pageRows.length >= count : pageRows.length < pageSize)) return rows;
    offset += pageRows.length;
  }
}

async function rpc(name, params) {
  const { data, error } = await client().rpc(name, params);
  if (error) {
    const failure = new Error(error.message || `L’opération ${name} a échoué.`);
    failure.code = error.code;
    throw failure;
  }
  if (data && typeof data === 'object' && data.ok === false) {
    throw new Error(data.message || `L’opération ${name} a été refusée.`);
  }
  return data;
}

function customerName(customer) {
  if (!customer) return 'Client de passage';
  return [customer.first_name, customer.last_name].filter(Boolean).join(' ')
    || customer.company
    || 'Client';
}

function mapProduct(row) {
  return {
    ...row,
    supplier_name: row.suppliers?.name || '',
    supplier_code: row.suppliers?.code || '',
    stock: Number(row.quantity) || 0,
    threshold: Number(row.min_stock) || 0,
    cost: Number(row.purchase_price) || 0,
    price: Number(row.sale_price) || 0,
  };
}

function mapSale(row) {
  const total = Number(row.total_amount) || 0;
  const paid = Number(row.amount_paid) || 0;
  return {
    ...row,
    sale_id: row.id,
    id: row.sale_number,
    date: row.sale_date ? new Date(row.sale_date).toLocaleString('fr-FR') : '',
    customer: customerName(row.customers),
    amount: total,
    total,
    paid,
    due: Math.max(total - paid, 0),
    status: row.sale_status === 'CANCELLED'
      ? 'Annulée'
      : row.payment_status === 'PAID'
        ? 'Payée'
        : row.payment_status === 'PARTIAL'
          ? 'Partielle'
          : 'À payer',
  };
}

function mapAccount(row) {
  const accountTypes = { CASH: 'Espèces', BANK: 'Banque', MOBILE_MONEY: 'Mobile money' };
  return {
    ...row,
    type: accountTypes[row.account_type] || row.account_type,
    balance: Number(row.current_balance) || 0,
    status: row.is_active ? 'Actif' : 'Inactif',
  };
}

function filterStore(query, storeId, includeUnassigned) {
  if (storeId == null) return query;
  return includeUnassigned
    ? query.or(`store_id.eq.${storeId},store_id.is.null`)
    : query.eq('store_id', storeId);
}

export async function listStores(organizationId, includeInactive = false) {
  requireOrganization(organizationId);
  let query = client()
    .from('stores')
    .select('id,organization_id,code,name,address,phone,manager_name,notes,active,is_default')
    .eq('organization_id', organizationId)
    .order('is_default', { ascending: false })
    .order('name', { ascending: true });
  if (!includeInactive) query = query.eq('active', true);
  return run(query);
}

export async function saveStore(organizationId, store) {
  requireOrganization(organizationId);
  return rpc('app_tauri_save_store', {
    p_organization_id: organizationId,
    p_store_id: store.id || null,
    p_code: store.code,
    p_name: store.name,
    p_address: store.address || null,
    p_phone: store.phone || null,
    p_manager_name: store.manager_name || null,
    p_notes: store.notes || null,
  });
}

export async function setStoreActive(organizationId, storeId, active) {
  requireOrganization(organizationId);
  return rpc('app_tauri_set_store_active', {
    p_organization_id: organizationId,
    p_store_id: storeId,
    p_active: Boolean(active),
  });
}

export async function loadBusinessContext() {
  const data = await rpc('app_tauri_context', {});
  if (!data.profile || !Array.isArray(data.organizations)) {
    throw new Error('Le contexte entreprise renvoyé par Supabase est invalide.');
  }
  return data;
}

export async function listProducts(organizationId, storeId = null, includeUnassigned = false, includeInactive = false) {
  requireOrganization(organizationId);
  const query = () => {
    let builder = client()
      .from('products')
      .select(PRODUCT_COLUMNS, { count: 'exact' })
      .eq('organization_id', organizationId)
      .order('name', { ascending: true })
      .order('id', { ascending: true });
    builder = filterStore(builder, storeId, includeUnassigned);
    if (!includeInactive) builder = builder.eq('active', true);
    return builder;
  };
  return (await runAllPages(query)).map(mapProduct);
}

export async function listCustomers(organizationId, includeInactive = false) {
  requireOrganization(organizationId);
  const query = () => {
    let builder = client()
      .from('customers')
      .select('id,organization_id,first_name,last_name,company,email,phone,mobile,address,city,country,customer_type,credit_limit,balance,notes,active', { count: 'exact' })
      .eq('organization_id', organizationId)
      .order('first_name', { ascending: true })
      .order('id', { ascending: true });
    if (!includeInactive) builder = builder.eq('active', true);
    return builder;
  };
  const rows = await runAllPages(query);
  return rows.map((row) => ({ ...row, name: customerName(row) }));
}

export async function saveCustomer(organizationId, customer) {
  requireOrganization(organizationId);
  return rpc('app_tauri_save_customer', {
    p_organization_id: organizationId,
    p_customer_id: customer.id || null,
    p_first_name: customer.first_name,
    p_last_name: customer.last_name,
    p_company: customer.company || null,
    p_email: customer.email || null,
    p_phone: customer.phone || null,
    p_mobile: customer.mobile || null,
    p_address: customer.address || null,
    p_city: customer.city || null,
    p_country: customer.country || null,
    p_customer_type: customer.customer_type || 'RETAIL',
    p_credit_limit: Number(customer.credit_limit) || 0,
    p_notes: customer.notes || null,
  });
}

export async function setCustomerActive(organizationId, customerId, active) {
  requireOrganization(organizationId);
  return rpc('app_tauri_set_customer_active', {
    p_organization_id: organizationId,
    p_customer_id: customerId,
    p_active: Boolean(active),
  });
}

export async function listSales(organizationId, storeId = null, limit = 100, includeUnassigned = false) {
  requireOrganization(organizationId);
  const query = () => {
    const builder = client()
      .from('sales')
      .select(SALE_COLUMNS, { count: 'exact' })
      .eq('organization_id', organizationId)
      .order('sale_date', { ascending: false })
      .order('id', { ascending: false });
    return filterStore(builder, storeId, includeUnassigned);
  };
  const rows = limit == null
    ? await runAllPages(query)
    : await run(query().limit(limit));
  return rows.map(mapSale);
}

export async function loadInvoiceDetails(organizationId, saleId) {
  requireOrganization(organizationId);
  if (!saleId) throw new Error('Facture introuvable.');

  const db = client();
  const [sale, itemRows, company] = await Promise.all([
    run(db.from('sales')
      .select('id,organization_id,store_id,sale_number,sale_date,subtotal,discount_amount,tax_amount,total_amount,amount_paid,change_amount,payment_status,sale_status,type_document,payment_method,currency,notes,customer_id,customers(first_name,last_name,company,phone,email)')
      .eq('organization_id', organizationId)
      .eq('id', saleId)
      .single()),
    run(db.from('sale_items')
      .select('id,organization_id,sale_id,product_id,quantity,unit_price,discount_percent,discount_amount,line_total,products(name,code)')
      .eq('organization_id', organizationId)
      .eq('sale_id', saleId)
      .order('id', { ascending: true })),
    loadSettings(organizationId),
  ]);

  return {
    invoice: mapSale(sale),
    company,
    items: itemRows.map((item) => ({
      ...item,
      name: item.products?.name || `Produit #${item.product_id}`,
      code: item.products?.code || '',
      quantity: Number(item.quantity) || 0,
      unitPrice: Number(item.unit_price) || 0,
      discount: Number(item.discount_amount) || 0,
      total: Number(item.line_total) || 0,
    })),
  };
}

export async function listProformas(organizationId, limit = 200) {
  requireOrganization(organizationId);
  const query = () => client()
    .from('proforma_invoices')
    .select(PROFORMA_COLUMNS, { count: 'exact' })
    .eq('organization_id', organizationId)
    .order('created_date', { ascending: false })
    .order('id', { ascending: false });
  const rows = limit == null ? await runAllPages(query) : await run(query().limit(limit));
  return rows.map((row) => ({
    ...row,
    proforma_id: row.id,
    id: row.proforma_number,
    customer: customerName(row.customers),
    date: row.created_date,
    due: row.valid_until,
    amount: Number(row.total_amount) || 0,
    status: ({
      BROUILLON: 'Brouillon',
      EN_ATTENTE: 'En attente',
      ENVOYEE: 'Envoyée',
      ACCEPTEE: 'Acceptée',
      REFUSEE: 'Refusée',
      EXPIREE: 'Expirée',
      CONVERTIE: 'Convertie',
    })[row.status] || row.status,
  }));
}

export async function loadProformaDetails(organizationId, proformaId) {
  requireOrganization(organizationId);
  const row = await run(client()
    .from('proforma_invoices')
    .select('*,customers(first_name,last_name,company,phone,email),proforma_invoice_items(id,description,quantity,unit_price,discount_amount,line_total,products(name,code))')
    .eq('organization_id', organizationId)
    .eq('id', proformaId)
    .single());
  const company = await loadSettings(organizationId);
  return {
    document: {
      ...row,
      customer: customerName(row.customers),
      date: row.created_date ? new Date(row.created_date).toLocaleDateString('fr-FR') : '',
      items: (row.proforma_invoice_items || []).map((item) => ({
        ...item,
        name: item.description || item.products?.name || 'Article',
        code: item.products?.code || '',
        quantity: Number(item.quantity) || 0,
        unitPrice: Number(item.unit_price) || 0,
        discount: Number(item.discount_amount) || 0,
        total: Number(item.line_total) || 0,
      })),
    },
    company,
  };
}

export async function listInventoryMovements(organizationId, storeId = null, limit = 300, includeUnassigned = false) {
  requireOrganization(organizationId);
  const query = () => {
    const builder = client()
      .from('inventory_movements')
      .select('id,organization_id,store_id,product_id,movement_type,quantity,unit_price,total_value,reference,reason,date,products(name,code)', { count: 'exact' })
      .eq('organization_id', organizationId)
      .order('date', { ascending: false })
      .order('id', { ascending: false });
    return filterStore(builder, storeId, includeUnassigned);
  };
  const rows = limit == null ? await runAllPages(query) : await run(query().limit(limit));
  return rows.map((row) => ({
    ...row,
    date: row.date ? new Date(row.date).toLocaleString('fr-FR') : '',
    product: row.products?.name || `Produit #${row.product_id}`,
    type: ({ IN: 'Entrée', OUT: 'Sortie', ADJUST: 'Ajustement', LOSS: 'Perte', RETURN: 'Retour' })[row.movement_type] || row.movement_type,
    quantity: ['OUT', 'LOSS'].includes(row.movement_type) ? -Math.abs(Number(row.quantity)) : Number(row.quantity),
    source: row.reason || row.reference || 'Mouvement de stock',
  }));
}

export async function listAccounts(organizationId) {
  requireOrganization(organizationId);
  const rows = await run(client()
    .from('treasury_accounts')
    .select('id,organization_id,name,account_type,currency,initial_balance,current_balance,is_active,is_default')
    .eq('organization_id', organizationId)
    .eq('is_active', true)
    .order('id', { ascending: true }));
  return rows.map(mapAccount);
}

export async function createTreasuryAccount({
  organizationId, name, accountType, initialBalance, bankName, accountNumber, phoneNumber, isDefault,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_create_treasury_account', {
    p_organization_id: organizationId,
    p_name: name,
    p_account_type: accountType,
    p_initial_balance: Number(initialBalance) || 0,
    p_bank_name: bankName || null,
    p_account_number: accountNumber || null,
    p_phone_number: phoneNumber || null,
    p_is_default: Boolean(isDefault),
  });
}

export async function listTreasuryMovements(organizationId, limit = 300) {
  requireOrganization(organizationId);
  const query = () => client()
    .from('treasury_movements')
    .select('id,organization_id,account_id,movement_type,amount,date,reference,description,category,reference_type', { count: 'exact' })
    .eq('organization_id', organizationId)
    .order('date', { ascending: false })
    .order('id', { ascending: false });
  const rows = limit == null ? await runAllPages(query) : await run(query().limit(limit));
  const accounts = await listAccounts(organizationId);
  const accountNames = new Map(accounts.map((account) => [account.id, account.name]));
  return rows.map((row) => ({
    ...row,
    date: row.date ? new Date(row.date).toISOString() : '',
    label: row.description || row.reference || 'Mouvement',
    account: accountNames.get(row.account_id) || `Compte #${row.account_id}`,
    type: row.movement_type === 'IN' ? 'Entrée' : 'Sortie',
    amount: Number(row.amount) || 0,
  }));
}

export async function loadMonthlyTreasuryPreview(organizationId, period) {
  requireOrganization(organizationId);
  return rpc('app_tauri_monthly_treasury_preview', {
    p_organization_id: organizationId,
    p_period: period,
  });
}

export async function listTreasuryMonthClosures(organizationId, limit = 60) {
  requireOrganization(organizationId);
  return run(client()
    .from('monthly_closures')
    .select('id,organization_id,period,sales_count,total_sales,total_collected,total_credit,total_out,net,balances,status,closed_by,closed_at,notes')
    .eq('organization_id', organizationId)
    .order('period', { ascending: false })
    .limit(limit));
}

export async function closeTreasuryMonth(organizationId, period, notes = '') {
  requireOrganization(organizationId);
  return rpc('app_tauri_close_treasury_month', {
    p_organization_id: organizationId,
    p_period: period,
    p_notes: notes || null,
  });
}

export async function listOpenCashSession(organizationId, userId) {
  requireOrganization(organizationId);
  if (!userId) return null;
  const session = await run(client()
    .from('cash_register_sessions')
    .select('id,organization_id,account_id,user_id,opened_at,opening_amount,expected_amount,total_in,total_out,status')
    .eq('organization_id', organizationId)
    .eq('user_id', userId)
    .eq('status', 'OPEN')
    .maybeSingle());
  if (!session) return null;
  return {
    ...session,
    expected_amount: (Number(session.opening_amount) || 0)
      + (Number(session.total_in) || 0)
      - (Number(session.total_out) || 0),
  };
}

export async function loadDashboard(organizationId, storeId, includeUnassigned = false) {
  const [sales, products] = await Promise.all([
    listSales(organizationId, storeId, null, includeUnassigned),
    listProducts(organizationId, storeId, includeUnassigned),
  ]);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const salesToday = sales.filter((sale) => new Date(sale.sale_date) >= today && sale.sale_status !== 'CANCELLED');
  const lowStock = products.filter((product) => product.stock <= product.threshold);
  const recent = sales.filter((sale) => sale.sale_status !== 'CANCELLED');
  const unpaid = recent.reduce((sum, sale) => sum + sale.due, 0);
  const chart = Array.from({ length: 7 }, (_, index) => {
    const day = new Date();
    day.setHours(0, 0, 0, 0);
    day.setDate(day.getDate() - (6 - index));
    const next = new Date(day);
    next.setDate(next.getDate() + 1);
    const amount = recent
      .filter((sale) => new Date(sale.sale_date) >= day && new Date(sale.sale_date) < next)
      .reduce((sum, sale) => sum + sale.total, 0);
    return {
      day: day.toLocaleDateString('fr-FR', { weekday: 'short' }),
      label: day.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }),
      amount,
    };
  });
  return {
    sales,
    products,
    lowStock,
    unpaid,
    salesToday,
    totalToday: salesToday.reduce((sum, sale) => sum + sale.total, 0),
    totalWeek: chart.reduce((sum, point) => sum + point.amount, 0),
    chart,
  };
}

export async function createSale({
  organizationId, storeId, customerId, items, discountAmount, paymentMethod, amountPaid, accountId, notes,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_create_sale', {
    p_organization_id: organizationId,
    p_store_id: storeId,
    p_customer_id: customerId || null,
    p_items: items.map((item) => ({ product_id: item.product_id, quantity: item.quantity })),
    p_discount_amount: Number(discountAmount) || 0,
    p_payment_method: paymentMethod,
    p_amount_paid: Number(amountPaid) || 0,
    p_account_id: accountId || null,
    p_notes: notes || null,
  });
}

export async function createProduct({
  organizationId, storeId, supplierId, name, category, initialQuantity, minStock, maxStock, purchasePrice, salePrice,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_create_product', {
    p_organization_id: organizationId,
    p_store_id: storeId,
    p_name: name,
    p_category: category,
    p_initial_quantity: Number(initialQuantity) || 0,
    p_min_stock: Number(minStock) || 0,
    p_purchase_price: Number(purchasePrice) || 0,
    p_sale_price: Number(salePrice) || 0,
    p_max_stock: Number(maxStock) || 0,
    p_supplier_id: supplierId ? Number(supplierId) : null,
  });
}

export async function updateProduct(organizationId, product) {
  requireOrganization(organizationId);
  return rpc('app_tauri_update_product', {
    p_organization_id: organizationId,
    p_product_id: product.id,
    p_name: product.name,
    p_category: product.category,
    p_min_stock: Number(product.minStock) || 0,
    p_max_stock: Number(product.maxStock) || 0,
    p_purchase_price: Number(product.purchasePrice) || 0,
    p_sale_price: Number(product.salePrice) || 0,
    p_supplier_id: product.supplierId ? Number(product.supplierId) : null,
  });
}

export async function setProductActive(organizationId, productId, active) {
  requireOrganization(organizationId);
  return rpc('app_tauri_set_product_active', {
    p_organization_id: organizationId,
    p_product_id: productId,
    p_active: Boolean(active),
  });
}

export async function listSuppliers(organizationId, includeInactive = false) {
  requireOrganization(organizationId);
  const query = () => {
    let builder = client()
      .from('suppliers')
      .select('id,organization_id,code,name,contact_person,email,phone,address,city,country,website,notes,payment_terms,active', { count: 'exact' })
      .eq('organization_id', organizationId)
      .order('name', { ascending: true })
      .order('id', { ascending: true });
    if (!includeInactive) builder = builder.eq('active', true);
    return builder;
  };
  return runAllPages(query);
}

export async function saveSupplier(organizationId, supplier) {
  requireOrganization(organizationId);
  return rpc('app_tauri_save_supplier', {
    p_organization_id: organizationId,
    p_supplier_id: supplier.id || null,
    p_code: supplier.code,
    p_name: supplier.name,
    p_contact_person: supplier.contact_person || null,
    p_email: supplier.email || null,
    p_phone: supplier.phone || null,
    p_address: supplier.address || null,
    p_city: supplier.city || null,
    p_country: supplier.country || null,
    p_website: supplier.website || null,
    p_notes: supplier.notes || null,
    p_payment_terms: supplier.payment_terms || null,
  });
}

export async function setSupplierActive(organizationId, supplierId, active) {
  requireOrganization(organizationId);
  return rpc('app_tauri_set_supplier_active', {
    p_organization_id: organizationId,
    p_supplier_id: supplierId,
    p_active: Boolean(active),
  });
}

export async function listPurchaseOrders(organizationId, includePayments = false) {
  requireOrganization(organizationId);
  const db = client();
  const [orders, items, payments] = await Promise.all([
    runAllPages(() => db.from('purchase_orders')
      .select('id,organization_id,order_number,supplier_id,status,total_amount,notes,expected_delivery,received_date,user_id,created_at,suppliers(name,code)', { count: 'exact' })
      .eq('organization_id', organizationId)
      .order('created_at', { ascending: false })
      .order('id', { ascending: false })),
    runAllPages(() => db.from('purchase_order_items')
      .select('id,organization_id,order_id,product_id,quantity,unit_price,total_price,received_quantity,products(name,code)', { count: 'exact' })
      .eq('organization_id', organizationId)
      .order('id', { ascending: true })),
    includePayments ? runAllPages(() => db.from('treasury_movements')
      .select('reference_id,amount', { count: 'exact' })
      .eq('organization_id', organizationId)
      .eq('reference_type', 'PURCHASE_ORDER')
      .eq('movement_type', 'OUT')
      .order('id', { ascending: true })) : Promise.resolve([]),
  ]);
  const paidByOrder = new Map();
  for (const movement of payments) {
    paidByOrder.set(movement.reference_id, (paidByOrder.get(movement.reference_id) || 0) + (Number(movement.amount) || 0));
  }
  const itemsByOrder = new Map();
  for (const row of items) {
    const bucket = itemsByOrder.get(row.order_id) || [];
    bucket.push({
      ...row,
      name: row.products?.name || `Produit #${row.product_id}`,
      code: row.products?.code || '',
      quantity: Number(row.quantity) || 0,
      unit_price: Number(row.unit_price) || 0,
      total_price: Number(row.total_price) || 0,
      received_quantity: Number(row.received_quantity) || 0,
    });
    itemsByOrder.set(row.order_id, bucket);
  }
  return orders.map((order) => ({
    ...order,
    total_amount: Number(order.total_amount) || 0,
    amount_paid: Math.min(Number((paidByOrder.get(order.id) || 0).toFixed(2)), Number(order.total_amount) || 0),
    supplier_name: order.suppliers?.name || 'Fournisseur inconnu',
    supplier_code: order.suppliers?.code || '',
    items: itemsByOrder.get(order.id) || [],
  }));
}

export async function payPurchaseOrder({ organizationId, orderId, accountId, amount, paymentMethod, notes }) {
  requireOrganization(organizationId);
  return rpc('app_tauri_pay_purchase_order', {
    p_organization_id: organizationId,
    p_order_id: Number(orderId),
    p_account_id: Number(accountId),
    p_amount: Number(amount),
    p_payment_method: paymentMethod || 'CASH',
    p_notes: notes || null,
  });
}

export async function createPurchaseOrder({ organizationId, storeId, supplierId, items, expectedDelivery, notes }) {
  requireOrganization(organizationId);
  return rpc('app_tauri_create_purchase_order', {
    p_organization_id: organizationId,
    p_store_id: Number(storeId),
    p_supplier_id: Number(supplierId),
    p_items: items.map((item) => ({
      product_id: Number(item.productId),
      quantity: Number(item.quantity),
      unit_price: Number(item.unitPrice),
    })),
    p_expected_delivery: expectedDelivery || null,
    p_notes: notes || null,
  });
}

export async function receivePurchaseOrder({ organizationId, orderId, storeId, items, notes }) {
  requireOrganization(organizationId);
  return rpc('app_tauri_receive_purchase_order', {
    p_organization_id: organizationId,
    p_order_id: Number(orderId),
    p_store_id: Number(storeId),
    p_items: items.map((item) => ({ item_id: Number(item.itemId), quantity: Number(item.quantity) })),
    p_notes: notes || null,
  });
}

export async function cancelPurchaseOrder(organizationId, orderId) {
  requireOrganization(organizationId);
  return rpc('app_tauri_cancel_purchase_order', {
    p_organization_id: organizationId,
    p_order_id: Number(orderId),
  });
}

export async function createStockMovement({
  organizationId, productId, type, quantity, reason, unitCost, reference, notes,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_stock_movement', {
    p_organization_id: organizationId,
    p_product_id: productId,
    p_movement_type: type,
    p_quantity: Number(quantity),
    p_reason: reason || null,
    p_unit_cost: unitCost == null ? null : Number(unitCost),
    p_reference: reference || null,
    p_notes: notes || null,
  });
}

export async function createProforma({
  organizationId, customerId, items, validUntil, notes,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_create_proforma', {
    p_organization_id: organizationId,
    p_customer_id: customerId || null,
    p_items: items.map((item) => ({
      product_id: Number(item.productId),
      quantity: Number(item.quantity),
    })),
    p_valid_until: validUntil,
    p_notes: notes || null,
  });
}

export async function setProformaStatus(organizationId, proformaId, status) {
  requireOrganization(organizationId);
  return rpc('app_tauri_set_proforma_status', {
    p_organization_id: organizationId,
    p_proforma_id: proformaId,
    p_status: status,
  });
}

export async function convertProforma(organizationId, proformaId, storeId) {
  requireOrganization(organizationId);
  if (!storeId) throw new Error('Sélectionnez un magasin avant de convertir la pro forma.');
  return rpc('app_tauri_convert_proforma', {
    p_organization_id: organizationId,
    p_proforma_id: proformaId,
    p_store_id: Number(storeId),
  });
}

export async function registerPayment({
  organizationId, saleId, amount, paymentMethod, accountId, notes,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_register_payment', {
    p_organization_id: organizationId,
    p_sale_id: saleId,
    p_amount: Number(amount),
    p_payment_method: paymentMethod || null,
    p_account_id: accountId || null,
    p_notes: notes || null,
  });
}

export async function cancelSale(organizationId, saleId, reason) {
  requireOrganization(organizationId);
  return rpc('app_tauri_cancel_sale', {
    p_organization_id: organizationId,
    p_sale_id: saleId,
    p_reason: reason,
  });
}

export async function createTreasuryMovement({
  organizationId, accountId, movementType, amount, reference, description, category,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_treasury_move', {
    p_organization_id: organizationId,
    p_account_id: accountId,
    p_movement_type: movementType,
    p_amount: Number(amount),
    p_reference: reference || null,
    p_description: description || null,
    p_category: category || null,
  });
}

export async function updateCashSession({
  organizationId, action, accountId, sessionId, amount, notes,
}) {
  requireOrganization(organizationId);
  return rpc('app_tauri_cash_session', {
    p_organization_id: organizationId,
    p_action: action,
    p_account_id: accountId || null,
    p_session_id: sessionId || null,
    p_amount: Number(amount) || 0,
    p_notes: notes || null,
  });
}

export async function loadSettings(organizationId) {
  requireOrganization(organizationId);
  const db = client();
  const [organization, settings] = await Promise.all([
    run(db.from('organizations')
      .select('id,name,code,email,phone,address,currency,tax_rate')
      .eq('id', organizationId)
      .single()),
    run(db.from('organization_settings')
      .select('data')
      .eq('organization_id', organizationId)
      .maybeSingle()),
  ]);
  const preferences = settings?.data || {};
  return {
    companyName: organization.name || '',
    companyCode: organization.code || '',
    email: organization.email || '',
    phone: organization.phone || '',
    address: organization.address || '',
    currency: organization.currency || 'FCFA',
    language: preferences.language || 'Français',
    theme: preferences.theme || 'Clair',
    taxRate: String(organization.tax_rate ?? 0),
    invoicePrefix: preferences.invoice_prefix || 'FAC',
    proformaPrefix: preferences.proforma_prefix || 'PF',
    invoiceFooter: preferences.invoice_footer || '',
  };
}

export async function saveSettings(organizationId, settings) {
  requireOrganization(organizationId);
  return rpc('app_tauri_save_settings', {
    p_organization_id: organizationId,
    p_company: {
      name: settings.companyName,
      code: settings.companyCode,
      email: settings.email,
      phone: settings.phone,
      address: settings.address,
      currency: settings.currency,
      tax_rate: Number(settings.taxRate),
    },
    p_preferences: {
      language: settings.language,
      theme: settings.theme,
      invoice_prefix: settings.invoicePrefix,
      proforma_prefix: settings.proformaPrefix,
      invoice_footer: settings.invoiceFooter,
    },
  });
}

export async function listOrganizationMembers(organizationId) {
  requireOrganization(organizationId);
  return rpc('app_tauri_list_members', { p_organization_id: organizationId });
}

export async function addOrganizationMember(organizationId, email, role) {
  requireOrganization(organizationId);
  return rpc('app_tauri_add_member', {
    p_organization_id: organizationId,
    p_email: email,
    p_role: role,
  });
}

export async function updateOrganizationMember(organizationId, email, role, active) {
  requireOrganization(organizationId);
  return rpc('app_tauri_update_member', {
    p_organization_id: organizationId,
    p_email: email,
    p_role: role,
    p_active: active,
  });
}

async function invokeAdminUserManagement(body) {
  const { data, error } = await client().functions.invoke('admin-user-management', { body });
  if (error) {
    throw new Error(error.message || 'Le service sécurisé de gestion des comptes a échoué.');
  }
  if (!data || data.ok !== true) {
    throw new Error(data?.message || 'Le service sécurisé de gestion des comptes a échoué.');
  }
  return data;
}

export async function inviteOrganizationMember(organizationId, email, username, role) {
  requireOrganization(organizationId);
  return invokeAdminUserManagement({
    action: 'invite',
    organizationId,
    email,
    username,
    role,
  });
}

export async function sendOrganizationMemberPasswordReset(organizationId, email) {
  requireOrganization(organizationId);
  return invokeAdminUserManagement({
    action: 'reset_password',
    organizationId,
    email,
  });
}

export async function removeOrganizationMember(organizationId, email) {
  requireOrganization(organizationId);
  return rpc('app_tauri_remove_member', {
    p_organization_id: organizationId,
    p_email: email,
  });
}

export async function listOrganizationRolePermissions(organizationId) {
  requireOrganization(organizationId);
  return rpc('app_tauri_list_role_permissions', {
    p_organization_id: organizationId,
  });
}

export async function saveOrganizationRolePermissions(organizationId, permissions) {
  requireOrganization(organizationId);
  return rpc('app_tauri_update_role_permissions', {
    p_organization_id: organizationId,
    p_permissions: permissions,
  });
}

export async function resetOrganizationRolePermissions(organizationId) {
  requireOrganization(organizationId);
  return rpc('app_tauri_reset_role_permissions', {
    p_organization_id: organizationId,
  });
}

export async function cleanupOrganizationActivityLogs(organizationId) {
  requireOrganization(organizationId);
  return rpc('app_tauri_cleanup_old_activity_logs', {
    p_organization_id: organizationId,
  });
}

export async function listOrganizationDatabaseTables(organizationId) {
  requireOrganization(organizationId);
  return rpc('app_tauri_list_database_tables', {
    p_organization_id: organizationId,
  });
}

export async function readOrganizationDatabaseTable(organizationId, tableName, limit = 100, offset = 0) {
  requireOrganization(organizationId);
  return rpc('app_tauri_read_database_table', {
    p_organization_id: organizationId,
    p_table_name: tableName,
    p_limit: limit,
    p_offset: offset,
  });
}

export async function canManageAllDatabase() {
  return Boolean(await rpc('app_tauri_can_manage_all_database', {}));
}

export async function exportAllOrganizationsData() {
  return rpc('app_tauri_export_all_data', {});
}

export async function restoreAllOrganizationsData(backup) {
  if (!backup || typeof backup !== 'object') {
    throw new Error('Le fichier de sauvegarde est invalide.');
  }
  return rpc('app_tauri_restore_all_data', { p_backup: backup });
}

export async function listActivityLogs(organizationId, limit = 100) {
  requireOrganization(organizationId);
  return run(client()
    .from('activity_logs')
    .select('id,organization_id,username,action,created_at')
    .eq('organization_id', organizationId)
    .order('created_at', { ascending: false })
    .limit(limit));
}

export async function listSaleLogs(organizationId, limit = 100) {
  requireOrganization(organizationId);
  return run(client()
    .from('sale_logs')
    .select('id,organization_id,sale_number,action,username,user_role,total_amount,created_at,details')
    .eq('organization_id', organizationId)
    .order('created_at', { ascending: false })
    .limit(limit));
}
