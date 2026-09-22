import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Configuration Vite pour la version web de Korgo Pro.
// - `host: true` expose le serveur sur le réseau local (0.0.0.0) afin que
//   d'autres appareils du même réseau puissent y accéder via l'IP de la machine.
// - Le port par défaut est 5173.
// Utilisation :
//   npm run dev            -> accessible sur http://localhost:5173
//   npm run dev -- --host  -> force l'exposition réseau
export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    host: true,
    port: 5173,
    open: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});