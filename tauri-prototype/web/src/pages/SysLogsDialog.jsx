import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui';

export default function SysLogsDialog() {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Journaux système</div>
          <div className="page-subtitle">Korgo Pro</div>
        </div>
        <Link to="/dashboard" className="btn btn-outline">Retour</Link>
      </div>

      <Card>
        <p>Page des journaux système - à implémenter</p>
      </Card>
    </div>
  );
}