export const demoProducts = [
  { id: 'P001', name: 'Riz parfumé 5 kg', category: 'Alimentaire', stock: 48, threshold: 10, cost: 4200, price: 5500 },
  { id: 'P002', name: 'Huile végétale 1 L', category: 'Alimentaire', stock: 7, threshold: 12, cost: 900, price: 1250 },
  { id: 'P003', name: 'Savon multi-usage', category: 'Entretien', stock: 86, threshold: 20, cost: 350, price: 500 },
  { id: 'P004', name: 'Sucre 1 kg', category: 'Alimentaire', stock: 32, threshold: 10, cost: 650, price: 850 },
  { id: 'P005', name: 'Cahier 200 pages', category: 'Papeterie', stock: 4, threshold: 8, cost: 700, price: 1000 },
];

export const demoCustomers = [
  { id: 'C001', name: 'Client comptoir', phone: '—' },
  { id: 'C002', name: 'Établissements Konaté', phone: '+226 70 12 34 56' },
  { id: 'C003', name: 'Boutique Wendpanga', phone: '+226 25 30 40 50' },
  { id: 'C004', name: 'Aïcha Ouédraogo', phone: '+226 66 22 11 09' },
];

export const demoSales = [
  { id: 'V-2026-0184', date: '12 nov. 2026 · 10:42', customer: 'Client comptoir', amount: 26500, status: 'Payée' },
  { id: 'V-2026-0183', date: '12 nov. 2026 · 10:16', customer: 'Établissements Konaté', amount: 84000, status: 'Payée' },
  { id: 'V-2026-0182', date: '12 nov. 2026 · 09:58', customer: 'Boutique Wendpanga', amount: 12750, status: 'Partielle' },
  { id: 'V-2026-0181', date: '11 nov. 2026 · 17:21', customer: 'Client comptoir', amount: 19300, status: 'Payée' },
];

export const demoProformas = [
  { id: 'PF-2026-0042', customer: 'Établissements Konaté', date: '12 nov. 2026', due: '19 nov. 2026', amount: 128500, status: 'Envoyée' },
  { id: 'PF-2026-0041', customer: 'Boutique Wendpanga', date: '11 nov. 2026', due: '18 nov. 2026', amount: 76500, status: 'Brouillon' },
  { id: 'PF-2026-0040', customer: 'Aïcha Ouédraogo', date: '10 nov. 2026', due: '17 nov. 2026', amount: 34200, status: 'Acceptée' },
];

export const demoInvoices = [
  { id: 'FAC-2026-0184', customer: 'Client comptoir', date: '12 nov. 2026', total: 26500, paid: 26500, status: 'Payée' },
  { id: 'FAC-2026-0183', customer: 'Établissements Konaté', date: '12 nov. 2026', total: 84000, paid: 84000, status: 'Payée' },
  { id: 'FAC-2026-0182', customer: 'Boutique Wendpanga', date: '12 nov. 2026', total: 12750, paid: 5000, status: 'Partielle' },
  { id: 'FAC-2026-0179', customer: 'Aïcha Ouédraogo', date: '10 nov. 2026', total: 54000, paid: 0, status: 'À payer' },
];

export const demoAccounts = [
  { id: 'Caisse principale', type: 'Espèces', balance: 438500 },
  { id: 'Orange Money', type: 'Mobile money', balance: 186000 },
  { id: 'Compte bancaire', type: 'Banque', balance: 1250000 },
];

export const demoTreasuryMovements = [
  { date: '12 nov. · 10:42', label: 'Encaissement V-2026-0184', account: 'Caisse principale', type: 'Entrée', amount: 26500 },
  { date: '12 nov. · 09:58', label: 'Acompte V-2026-0182', account: 'Orange Money', type: 'Entrée', amount: 5000 },
  { date: '11 nov. · 16:05', label: 'Approvisionnement boutique', account: 'Caisse principale', type: 'Sortie', amount: 35000 },
];

export const demoUsers = [
  { name: 'Admin Korgo', email: 'admin@korgo.pro', role: 'ADMIN', status: 'Actif', lastSeen: 'Aujourd’hui, 10:30' },
  { name: 'Mariam Traoré', email: 'mariam@korgo.pro', role: 'GESTIONNAIRE', status: 'Actif', lastSeen: 'Aujourd’hui, 09:12' },
  { name: 'Issa Zongo', email: 'issa@korgo.pro', role: 'CAISSIER', status: 'Actif', lastSeen: 'Hier, 18:04' },
  { name: 'Awa Sawadogo', email: 'awa@korgo.pro', role: 'SUPERVISEUR', status: 'Inactif', lastSeen: '04 nov. 2026' },
];

export const formatMoney = (value, currency = 'FCFA') =>
  `${new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: currency === 'FCFA' ? 0 : 2,
    maximumFractionDigits: currency === 'FCFA' ? 0 : 2,
  }).format(Number(value) || 0)} ${currency}`;
