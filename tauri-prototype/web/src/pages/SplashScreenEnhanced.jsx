import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui';

export default function SplashScreenEnhanced() {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Écran de lancement amélioré</div>
          <div className="page-subtitle">Korgo Pro</div>
        </div>
        <Link to="/dashboard" className="btn btn-outline">Retour</Link>
      </div>

      <Card>
        <p>Page d'écran de lancement amélioré - à implémenter</p>
      </Card>
    </div>
  );
}