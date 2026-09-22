  import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getDashboardStats } from '../api/statsApi';
import { formatMoney } from '../api/db';
import { Stat } from '../components/ui';
import Icon from '../components/Icon';
import PieChart from '../components/PieChart';

export default function Dashboard() {
  const { user, settings } = useAuth();
  const s = getDashboardStats();
  const currency = settings.currency || 'FCFA';

  const maxAmount = Math.max(1, ...s.last7.map((d) => d.amount));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Bonjour, {user?.username} </div>
          <div className="page-subtitle">Voici l'activité de votre entreprise.</div>
        </div>
        <Link to="/ventes" className="btn btn-primary">+ Nouvelle vente</Link>
      </div>

      <div className="grid grid-4">
        <Stat icon={<Icon name="receipt" size={22} />} label={`Ventes (total)`} value={formatMoney(s.totalSales, currency)} color="#2f6fed" />
        <Stat icon={<Icon name="cash" size={22} />} label="Ventes du jour" value={formatMoney(s.salesToday, currency)} color="#1a9e5e" />
        <Stat icon={<Icon name="stock" size={22} />} label="Valeur du stock" value={formatMoney(s.stockValue, currency)} color="#e5a50a" />
        <Stat icon={<Icon name="wallet" size={22} />} label="Trésorerie" value={formatMoney(s.cashBalance, currency)} color="#0ea5c9" />
      </div>

      <div className="grid grid-3 mt-16">
        <div className="card">
          <div className="card-title"><Icon name="chart" size={16} style={{ verticalAlign: '-2px' }} /> Ventes — 7 derniers jours</div>
          <div className="chart-bars">
            {s.last7.map((d, i) => (
              <div className="chart-col" key={i} title={`${d.label}: ${formatMoney(d.amount, currency)}`}>
                <div className="chart-value">{Math.round(d.amount) === 0 ? '' : '·'}</div>
                <div
                  className="chart-bar"
                  style={{ height: `${Math.max(4, (d.amount / maxAmount) * 100)}%` }}
                />
                <div className="chart-label">{d.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title"><Icon name="alert" size={16} style={{ verticalAlign: '-2px' }} /> Alertes stock</div>
          <div className="flex justify-between mb-12">
            <div><span className="badge badge-warning">Stock bas</span> <b>{s.lowStock}</b></div>
            <div><span className="badge badge-danger">Rupture</span> <b>{s.outOfStock}</b></div>
          </div>
          <Link to="/stock" className="btn btn-sm">Gérer le stock <Icon name="arrowRight" size={16} style={{ verticalAlign: '-2px' }} /></Link>
        </div>

        <div className="card">
          <div className="card-title"><Icon name="chart" size={16} style={{ verticalAlign: '-2px' }} /> Vue d'ensemble</div>
          <div className="metric-2">
            <Metric label="Produits" value={s.productCount} />
            <Metric label="Clients" value={s.customerCount} />
            <Metric label="Ventes enregistrées" value={s.salesCount} />
            <Metric label="Proformas en attente" value={s.proformaPending} />
          </div>
        </div>
      </div>

      <div className="grid grid-2 mt-16">
        <div className="card">
          <div className="card-title"><Icon name="refresh" size={16} style={{ verticalAlign: '-2px' }} /> Trésorerie</div>
          <div className="metric-3">
            <Metric label="Entrées" value={formatMoney(s.totalIn, currency)} />
            <Metric label="Sorties" value={formatMoney(s.totalOut, currency)} />
            <Metric label="Solde" value={formatMoney(s.cashBalance, currency)} />
          </div>
          <Link to="/tresorerie" className="btn btn-sm mt-16">Détails <Icon name="arrowRight" size={16} style={{ verticalAlign: '-2px' }} /></Link>
        </div>

        <div className="card">
          <div className="card-title"><Icon name="sale" size={16} style={{ verticalAlign: '-2px' }} /> Modules disponibles</div>
          <div className="flex" style={{ flexWrap: 'wrap', gap: 8 }}>
            {[
              ['/ventes', 'Ventes'],
              ['/stock', 'Stock'],
              ['/tresorerie', 'Trésorerie'],
              ['/proformas', 'Proformas'],
              ['/factures', 'Facturation'],
              ['/clients', 'Clients'],
            ].map(([to, label]) => (
              <Link key={to} to={to} className="btn btn-sm">{label}</Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 17, fontWeight: 800 }}>{value}</div>
      <div className="text-muted" style={{ fontSize: 12 }}>{label}</div>
    </div>
  );
}