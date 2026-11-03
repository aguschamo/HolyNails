// @vitest-environment jsdom
// Pruebas del hook compartido por Home y Agendar. Se mockea el cliente HTTP
// existente (src/services/api.js) para no depender de un backend corriendo.
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../services/api.js'
import { useServicios } from './useServicios.js'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

afterEach(() => {
  vi.clearAllMocks()
})

describe('useServicios', () => {
  it('carga el catálogo con GET /api/servicios/', async () => {
    api.get.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 1, nombre: 'Semipermanente', duracion: '01:00:00', precio: '5000.00' },
        { id: 7, nombre: 'Kapping', duracion: '01:30:00', precio: '8000.00' },
      ],
    })

    const { result } = renderHook(() => useServicios())

    // Estado de carga inicial
    expect(result.current.loading).toBe(true)
    expect(result.current.error).toBeNull()
    expect(result.current.servicios).toEqual([])

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.get).toHaveBeenCalledWith('/api/servicios/')
    expect(result.current.error).toBeNull()
    expect(result.current.servicios).toHaveLength(2)
    expect(result.current.servicios[0]).toEqual({
      id: 1,
      nombre: 'Semipermanente',
      duracion: '01:00:00',
      precio: '5000.00',
    })
    expect(result.current.servicios[1].id).toBe(7)
  })

  it('results vacío deja la lista vacía y sin error', async () => {
    api.get.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })

    const { result } = renderHook(() => useServicios())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.servicios).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('expone el mensaje de error cuando la API falla', async () => {
    api.get.mockRejectedValue(
      new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
    )

    const { result } = renderHook(() => useServicios())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.servicios).toEqual([])
    expect(result.current.error).toBe(
      'No se pudo conectar con el servidor. Verificá tu conexión.',
    )
  })

  it('normaliza a [] cuando results no es un array', async () => {
    api.get.mockResolvedValue({ count: 1, results: 'no-array' })

    const { result } = renderHook(() => useServicios())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.servicios).toEqual([])
    expect(result.current.error).toBeNull()
  })
})
