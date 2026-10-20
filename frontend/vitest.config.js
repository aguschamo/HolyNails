import { defineConfig } from 'vitest/config'

// Config propia de vitest: los tests de React viven en src/**/*.test.jsx.
// tests/*.test.mjs son del runner nativo de node (npm test) y no deben
// correr acá. El entorno jsdom se declara por docblock en cada archivo.
export default defineConfig({
  test: {
    include: ['src/**/*.test.jsx'],
  },
})
