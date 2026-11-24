import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const sharedEnvDirectory = fileURLToPath(new URL('../../web', import.meta.url));

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: sharedEnvDirectory,
  server: {
    port: 5173,
    strictPort: true,
  },
});
