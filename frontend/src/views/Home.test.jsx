// @vitest-environment jsdom
// Home debe renderizar las tarjetas del catálogo que devuelve la API y
// mantener sus estados de carga / vacío / error.
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../services/api.js'
import Home from './Home.jsx'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderHome() {
  return render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  )
}

describe('Home — catálogo de servicios', () => {
  it('renderiza una tarjeta por servicio devuelto por la API', async () => {
    api.get.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 1, nombre: 'Semipermanente', duracion: '01:00:00', precio: '5000.00' },
        { id: 7, nombre: 'Kapping', duracion: '01:30:00', precio: '8000.00' },
      ],
    })
    renderHome()

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    expect(screen.getByText('Kapping')).toBeTruthy()

    // El markup anterior antepone el emoji 💰 al precio en la tarjeta.
    expect(screen.getByText(/5\.000/)).toBeTruthy()

    expect(api.get).toHaveBeenCalledWith('/api/servicios/')
    expect(screen.queryByText('No hay servicios disponibles por el momento.')).toBeNull()
  })

  it('lista vacía: muestra el estado vacío y no tarjetas', async () => {
    api.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    renderHome()

    expect(
      await screen.findByText('No hay servicios disponibles por el momento.'),
    ).toBeTruthy()
    expect(screen.queryByText(/Duración:/)).toBeNull()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('error de API: muestra el mensaje de error y no el estado vacío', async () => {
    api.get.mockRejectedValue(
      new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
    )
    renderHome()

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()
    expect(screen.queryByText('No hay servicios disponibles por el momento.')).toBeNull()
  })

  it('estado de carga inicial antes de la respuesta', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderHome()

    expect(screen.getByText('Cargando servicios…')).toBeTruthy()
  })

  it('no dispara una segunda petición tras el primer render', async () => {
    api.get.mockResolvedValue({ count: 0, results: [] })
    renderHome()

    await waitFor(() =>
      expect(screen.getByText('No hay servicios disponibles por el momento.')).toBeTruthy(),
    )
    expect(api.get).toHaveBeenCalledTimes(1)
  })
})
