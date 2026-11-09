// @vitest-environment jsdom
// Pruebas de MisTurnos: lista traída de GET /api/turnos/?propios=true
// (paginada; el filtro de propios lo resuelve el backend desde el token),
// join del ID de servicio con el catálogo público, estados de carga /
// vacío / error y cancelación de turnos propios (B11.4). Se mockea el
// cliente HTTP existente (src/services/api.js) para no depender de un
// backend corriendo.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import MisTurnos from './MisTurnos.jsx'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn() },
  // Exports que AuthContext consume (para el test con rol ADMIN, B11.4);
  // con initialUsuario no hay llamadas de red al montar.
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthCleared: vi.fn(() => vi.fn()),
}))

const CATALOGO = [
  { id: 1, nombre: 'Semipermanente', duracion: '01:00:00', precio: '5000.00' },
  { id: 7, nombre: 'Kapping', duracion: '01:30:00', precio: '8000.00' },
]

// Responde por ruta: /api/turnos/?propios=true con la página de turnos y
// el resto (o sea /api/servicios/) con el catálogo.
function mockear({ turnos = [], next = null, catalogo = CATALOGO } = {}) {
  api.get.mockImplementation((path) => {
    if (String(path).startsWith('/api/turnos/')) {
      return Promise.resolve({ count: turnos.length, next, results: turnos })
    }
    return Promise.resolve({ count: catalogo.length, next: null, results: catalogo })
  })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  // Restaura los spies de window.confirm usados en la cancelación (B11.4).
  vi.restoreAllMocks()
})

function renderMisTurnos() {
  return render(
    <MemoryRouter>
      <MisTurnos />
    </MemoryRouter>,
  )
}

// Usuario ADMIN autenticado (initialUsuario → sin llamadas de red al montar).
// MisTurnos no lee el rol: comparte la misma ruta y debe seguir pidiendo
// ?propios=true también para ADMIN (B11.4).
const USER_ADMIN = {
  id: 30,
  nombre: 'Admin Uno',
  email: 'admin@holynails.test',
  username: 'admin1',
  role: 'admin',
  es_profesional: false,
  profesional_id: null,
}

function renderMisTurnosComoAdmin() {
  return render(
    <MemoryRouter>
      <AuthProvider initialUsuario={USER_ADMIN}>
        <MisTurnos />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('MisTurnos — lista de turnos', () => {
  it('lista los turnos con fecha, hora, servicio y estado, en orden cronológico', async () => {
    mockear({
      turnos: [
        { id: 3, fecha: '2030-03-10', hora: '15:00:00', usuario: 1, servicio: 7, estado: 'confirmado' },
        { id: 1, fecha: '2030-01-15', hora: '10:00:00', usuario: 1, servicio: 1, estado: 'pendiente' },
        { id: 2, fecha: '2030-02-20', hora: '11:30:00', usuario: 1, servicio: null, estado: 'cancelado' },
        { id: 4, fecha: '2030-04-01', hora: '09:00:00', usuario: 1, servicio: 99, estado: 'pendiente' },
      ],
    })
    renderMisTurnos()

    // El nombre del servicio se resuelve con el catálogo (join por ID)
    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    expect(screen.getByText('Kapping')).toBeTruthy()
    // Servicio eliminado (FK null) e ID fuera del catálogo: sin datos perdidos
    expect(screen.getByText('Servicio no disponible')).toBeTruthy()
    expect(screen.getByText('Servicio N° 99')).toBeTruthy()

    // Estados visibles (dos turnos quedan en "pendiente")
    expect(screen.getAllByText('Pendiente')).toHaveLength(2)
    expect(screen.getByText('Confirmado')).toBeTruthy()
    expect(screen.getByText('Cancelado')).toBeTruthy()

    expect(screen.getByText('Tenés 4 turnos')).toBeTruthy()
    expect(api.get).toHaveBeenCalledWith('/api/turnos/?propios=true')
    // Nunca pide la lista general sin el filtro de propios.
    expect(api.get).not.toHaveBeenCalledWith('/api/turnos/')

    // Orden cronológico ascendente, independientemente del orden de llegada
    expect(
      screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent),
    ).toEqual([
      '15/01/2030 · 10:00',
      '20/02/2030 · 11:30',
      '10/03/2030 · 15:00',
      '01/04/2030 · 09:00',
    ])
  })

  it('recorre todas las páginas de la API (PAGE_SIZE=10) y junta los resultados', async () => {
    api.get.mockImplementation((path) => {
      if (path === '/api/turnos/?propios=true') {
        return Promise.resolve({
          count: 3,
          // DRF conserva los query params en `next` (B10.0.2: el filtro
          // de propios se mantiene también en la página 2).
          next: 'http://127.0.0.1:8000/api/turnos/?propios=true&page=2',
          results: [
            { id: 1, fecha: '2030-01-15', hora: '10:00:00', servicio: 1, estado: 'pendiente' },
            { id: 2, fecha: '2030-02-20', hora: '11:30:00', servicio: 1, estado: 'pendiente' },
          ],
        })
      }
      if (path === 'http://127.0.0.1:8000/api/turnos/?propios=true&page=2') {
        return Promise.resolve({
          count: 3,
          next: null,
          results: [
            { id: 3, fecha: '2030-03-10', hora: '15:00:00', servicio: 7, estado: 'confirmado' },
          ],
        })
      }
      return Promise.resolve({ count: CATALOGO.length, next: null, results: CATALOGO })
    })
    renderMisTurnos()

    expect(await screen.findByText('Tenés 3 turnos')).toBeTruthy()
    expect(screen.getByText('10/03/2030 · 15:00')).toBeTruthy()
    expect(api.get).toHaveBeenCalledWith('/api/turnos/?propios=true')
    expect(api.get).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/turnos/?propios=true&page=2',
    )
  })

  it('estado vacío: muestra el mensaje amigable y no tarjetas', async () => {
    mockear({ turnos: [] })
    renderMisTurnos()

    expect(await screen.findByText('Todavía no tenés turnos')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Agendar turno' })).toBeTruthy()
    // Ninguna tarjeta de turno (los títulos de tarjeta llevan "fecha · hora")
    expect(screen.queryByText(/·/)).toBeNull()
  })

  it('estado de carga inicial antes de la respuesta', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderMisTurnos()

    expect(screen.getByText('Cargando tus turnos…')).toBeTruthy()
    expect(screen.queryByText('Todavía no tenés turnos')).toBeNull()
  })

  it('error de API: muestra el mensaje, no el estado vacío, y permite reintentar', async () => {
    let llamadasTurnos = 0
    api.get.mockImplementation((path) => {
      if (String(path).startsWith('/api/turnos/')) {
        llamadasTurnos += 1
        if (llamadasTurnos === 1) {
          return Promise.reject(
            new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
          )
        }
        return Promise.resolve({
          count: 1,
          next: null,
          results: [
            { id: 1, fecha: '2030-01-15', hora: '10:00:00', servicio: 1, estado: 'pendiente' },
          ],
        })
      }
      return Promise.resolve({ count: CATALOGO.length, next: null, results: CATALOGO })
    })
    renderMisTurnos()

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()
    expect(screen.queryByText('Todavía no tenés turnos')).toBeNull()
    expect(screen.queryByText('Cargando tus turnos…')).toBeNull()

    // El reintento vuelve a llamar a la API y muestra la lista
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    await waitFor(() => expect(llamadasTurnos).toBe(2))
    expect(screen.queryByText('No se pudo conectar con el servidor. Verificá tu conexión.')).toBeNull()
  })
})

describe('MisTurnos — cancelación de turnos propios (B11.4)', () => {
  const TURNO_PENDIENTE = {
    id: 1, fecha: '2030-01-15', hora: '10:00:00', usuario: 1, servicio: 1, estado: 'pendiente',
  }
  const TURNO_CONFIRMADO = {
    id: 2, fecha: '2030-02-20', hora: '11:30:00', usuario: 1, servicio: 1, estado: 'confirmado',
  }

  it('ofrece cancelar en turnos pendientes y confirmados; no en cancelados ni en estados no cancelables', async () => {
    mockear({
      turnos: [
        TURNO_PENDIENTE,
        TURNO_CONFIRMADO,
        { id: 3, fecha: '2030-03-10', hora: '15:00:00', usuario: 1, servicio: 1, estado: 'cancelado' },
        // Estados fuera del catálogo actual del backend: la lista cerrada
        // de cancelables no ofrece la acción por seguridad.
        { id: 4, fecha: '2030-04-01', hora: '09:00:00', usuario: 1, servicio: 1, estado: 'iniciado' },
        { id: 5, fecha: '2030-04-02', hora: '09:00:00', usuario: 1, servicio: 1, estado: 'finalizado' },
      ],
    })
    renderMisTurnos()

    expect(await screen.findByText('Tenés 5 turnos')).toBeTruthy()
    // Sólo pendiente y confirmado muestran la acción (2 de 5 tarjetas)
    expect(screen.getAllByRole('button', { name: 'Cancelar turno' })).toHaveLength(2)
  })

  it('solicita confirmación previa y no llama al backend si el usuario la rechaza', async () => {
    mockear({ turnos: [TURNO_PENDIENTE] })
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderMisTurnos()

    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar turno' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    // El texto de confirmación identifica fecha y hora del turno
    expect(confirmar.mock.calls[0][0]).toContain('15/01/2030')
    expect(confirmar.mock.calls[0][0]).toContain('10:00')
    expect(api.post).not.toHaveBeenCalled()
    // El turno sigue pendiente en pantalla
    expect(screen.getByText('Pendiente')).toBeTruthy()
  })

  it('cancela tras confirmar: POST correcto y estado actualizado en pantalla', async () => {
    mockear({ turnos: [TURNO_PENDIENTE] })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.post.mockResolvedValue({ id: 1, estado: 'cancelado' })
    renderMisTurnos()

    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar turno' }))

    expect(await screen.findByText('Turno cancelado correctamente.')).toBeTruthy()
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/api/turnos/1/cancelar/')
    // La tarjeta muestra el estado CANCELADO y desaparece la acción
    expect(screen.getByText('Cancelado')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Cancelar turno' })).toBeNull()
    expect(screen.queryByText('Pendiente')).toBeNull()
  })

  it('muestra el estado de procesamiento y evita solicitudes duplicadas', async () => {
    mockear({ turnos: [TURNO_PENDIENTE, TURNO_CONFIRMADO] })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    let resolver
    api.post.mockReturnValue(new Promise((resolve) => { resolver = resolve }))
    renderMisTurnos()

    // Hay dos tarjetas cancelables; se interactúa con la primera
    expect(await screen.findByText('Tenés 2 turnos')).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button', { name: 'Cancelar turno' })[0])

    // Estado de carga: texto y botón deshabilitado mientras procesa
    const procesando = await screen.findByRole('button', { name: 'Cancelando…' })
    expect(procesando.disabled).toBe(true)

    // Doble clic durante el procesamiento: un solo POST
    fireEvent.click(procesando)
    fireEvent.click(procesando)
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post).toHaveBeenCalledWith('/api/turnos/1/cancelar/')

    resolver({ id: 1, estado: 'cancelado' })
    expect(await screen.findByText('Turno cancelado correctamente.')).toBeTruthy()
  })

  it('informa el error del servidor sin simular el éxito y permite reintentar', async () => {
    mockear({ turnos: [TURNO_PENDIENTE] })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.post
      .mockRejectedValueOnce(new Error('No se puede cambiar el estado de un turno que ya comenzó.'))
      .mockResolvedValueOnce({ id: 1, estado: 'cancelado' })
    renderMisTurnos()

    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar turno' }))

    // Error real del backend, sin éxito simulado y sin cambiar el estado
    expect(
      await screen.findByText('No se puede cambiar el estado de un turno que ya comenzó.'),
    ).toBeTruthy()
    expect(screen.queryByText('Turno cancelado correctamente.')).toBeNull()
    expect(screen.getByText('Pendiente')).toBeTruthy()

    // Reintento: vuelve a estar disponible y ahora tiene éxito
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar turno' }))
    expect(await screen.findByText('Turno cancelado correctamente.')).toBeTruthy()
    expect(api.post).toHaveBeenCalledTimes(2)
    expect(screen.getByText('Cancelado')).toBeTruthy()
  })

  it('ADMIN: sigue listando sólo sus turnos con ?propios=true y puede cancelar', async () => {
    mockear({ turnos: [TURNO_PENDIENTE] })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.post.mockResolvedValue({ id: 1, estado: 'cancelado' })
    renderMisTurnosComoAdmin()

    expect(await screen.findByText('Tenés 1 turno')).toBeTruthy()
    // Mismo listado propio que un CLIENTE: nunca la consulta general
    expect(api.get).toHaveBeenCalledWith('/api/turnos/?propios=true')
    expect(api.get).not.toHaveBeenCalledWith('/api/turnos/')

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar turno' }))
    expect(await screen.findByText('Turno cancelado correctamente.')).toBeTruthy()
    expect(api.post).toHaveBeenCalledWith('/api/turnos/1/cancelar/')
  })
})
