import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui';

export default function SaleWidgets() {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Widgets de vente</div>
          <div className="page-subtitle">Korgo Pro</div>
        </div>
        <Link to="/dashboard" className="btn btn-outline">Retour</Link>
      </div>

      <Card>
        <p>Page des widgets de vente - à implémenter</p>
      </Card>
    </div>
  );
}