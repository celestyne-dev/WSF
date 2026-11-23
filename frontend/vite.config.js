import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import selfHostedFonts from './scripts/selfHostedFonts.mjs'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), selfHostedFonts()],
})
