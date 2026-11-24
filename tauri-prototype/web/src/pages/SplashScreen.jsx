import React from 'react';
import { Link } from 'react-router-dom';
import BrandLogo from '../components/BrandLogo';

export default function SplashScreen() {
  return (
    <main className="erp-splash">
      <BrandLogo className="erp-brand-mark" alt="Logo Korgo Pro" />
      <p className="erp-splash-overline">GESTION COMMERCIALE</p>
      <h1>Korgo Pro</h1>
      <p>Ventes, stock et trésorerie réunis dans un seul espace.</p>
      <span className="erp-splash-demo">VERSION DE DÉMONSTRATION</span>
      <Link to="/login" className="erp-button erp-button-primary">Continuer</Link>
    </main>
  );
}
