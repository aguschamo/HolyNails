// @vitest-environment jsdom
// Pruebas de AdminTurnos (B10.1): listado general de turnos del salón
// (sin ?propios=true) con clienta, servicio, profesional, fecha, hora y
// estado; filtros combinables; transiciones confirmar/cancelar con sus
// confirmaciones y errores; estados de carga / vacío / error; y control de
// acceso por rol en la ruta /admin/turnos.
// api.js se mockea para no depender de un backend corriendo.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '../App.jsx'
import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import AdminTurnos from './AdminTurnos.jsx'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthCleared: vi.fn(() => vi.fn()),
}))

const USER_ADMIN = {
  id: 30,
  nombre: 'Admin Uno',
  email: 'admin@holynails.test',
  username: 'admin1',
  role: 'admin',
  es_profesional: false,
  profesional_id: null,
}

const USER_CLIENTE = {
  id: 20,
  nombre: 'Cliente Uno',
  email: 'cliente@holynails.test',
  username: 'cliente1',
  role: 'cliente',
  es_profesional: false,
  profesional_id: null,
}

const USER_PERSONAL = {
  id: 10,
  nombre: 'María García',
  email: 'maria@holynails.test',
  username: 'maria_profesional',
  role: 'personal',
  es_profesional: true,
  profesional_id: 10,
}

const TURNOS = [
  { id: 1, fecha: '2030-03-10', hora: '10:00:00', usuario: 21, usuario_nombre: 'Carla Gómez', servicio: 1, profesional: 10, estado: 'pendiente' },
  { id: 2, fecha: '2030-03-10', hora: '11:00:00', usuario: 22, usuario_nombre: 'Ana Pérez', servicio: 7, profesional: 11, estado: 'confirmado' },
  { id: 3, fecha: '2030-03-12', hora: '09:30:00', usuario: 21, usuario_nombre: 'Carla Gómez', servicio: 1, profesional: 10, estado: 'cancelado' },
]

const SERVICIOS = [
  { id: 1, nombre: 'Semipermanente', duracion: '1:00:00', precio: '5000.00' },
  { id: 7, nombre: 'Kapping', duracion: '0:45:00', precio: '8000.00' },
]

const PROFESIONALES = [
  { id: 10, nombre: 'María García' },
  { id: 11, nombre: 'Brenda López' },
]

function paginado(results, next = null) {
  return { count: results.length, next, results }
}

// Responde por prefijo de ruta (los tres listados que carga la pantalla).
function mockear({
  turnos = TURNOS,
  servicios = SERVICIOS,
  profesionales = PROFESIONALES,
  fallaTurnos = null,
} = {}) {
  api.get.mockImplementation((path) => {
    const p = String(path)
    if (p.startsWith('/api/turnos/')) {
      return fallaTurnos
        ? Promise.reject(fallaTurnos)
        : Promise.resolve(paginado(turnos))
    }
    if (p.startsWith('/api/servicios/')) return Promise.resolve(paginado(servicios))
    if (p.startsWith('/api/profesionales/')) return Promise.resolve(paginado(profesionales))
    return Promise.resolve(paginado([]))
  })
}

function renderPantalla(usuario = USER_ADMIN) {
  return render(
    <MemoryRouter initialEntries={['/admin/turnos']}>
      <AuthProvider initialUsuario={usuario}>
        <AdminTurnos />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function renderRuta(ruta, usuario) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider initialUsuario={usuario}>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

// Señal de "listado cargado" (el nombre de la clienta se repite en filas
// y el de profesional además en el select, así que se usa la tabla).
async function tablaCargada() {
  return screen.findByRole('table')
}

// Fila de la tabla que contiene la clienta y la fecha dadas.
function filaDe(clienta, fecha) {
  return screen
    .getAllByRole('row')
    .find((fila) => fila.textContent.includes(clienta) && fila.textContent.includes(fecha))
}

async function seleccionar(etiqueta, valor) {
  fireEvent.change(await screen.findByLabelText(etiqueta), { target: { value: valor } })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

describe('AdminTurnos — listado general', () => {
  it('lista los turnos con clienta, servicio, profesional, fecha, hora y estado', async () => {
    mockear()
    renderPantalla()

    const tabla = await tablaCargada()
    expect(within(tabla).getAllByText('Carla Gómez')).toHaveLength(2)
    expect(within(tabla).getByText('Ana Pérez')).toBeTruthy()
    expect(within(tabla).getAllByText('Semipermanente')).toHaveLength(2)
    expect(within(tabla).getByText('Kapping')).toBeTruthy()
    expect(within(tabla).getAllByText('María García')).toHaveLength(2)
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
    expect(within(tabla).getAllByText('10/03/2030')).toHaveLength(2)
    expect(within(tabla).getByText('12/03/2030')).toBeTruthy()
    expect(within(tabla).getByText('10:00')).toBeTruthy()
    expect(within(tabla).getByText('11:00')).toBeTruthy()
    expect(within(tabla).getByText('09:30')).toBeTruthy()
    expect(within(tabla).getByText('Pendiente')).toBeTruthy()
    expect(within(tabla).getByText('Confirmado')).toBeTruthy()
    expect(within(tabla).getByText('Cancelado')).toBeTruthy()
    expect(screen.getByText('3 turnos')).toBeTruthy()
  })

  it('consulta la lista general de admin, sin ?propios=true', async () => {
    mockear()
    renderPantalla()

    await tablaCargada()
    expect(api.get).toHaveBeenCalledWith('/api/turnos/')
    expect(api.get).not.toHaveBeenCalledWith('/api/turnos/?propios=true')
    // Los tres listados que usa la pantalla.
    expect(api.get).toHaveBeenCalledWith('/api/servicios/')
    expect(api.get).toHaveBeenCalledWith('/api/profesionales/')
  })

  it('muestra las acciones válidas para cada estado', async () => {
    mockear()
    renderPantalla()

    await tablaCargada()
    // Solo el turno pendiente admite confirmar; pendiente y confirmado,
    // cancelar; el cancelado no tiene acciones.
    expect(screen.getAllByRole('button', { name: 'Confirmar' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'Cancelar' })).toHaveLength(2)

    const filaCancelada = filaDe('Carla Gómez', '12/03/2030')
    expect(within(filaCancelada).queryByRole('button')).toBeNull()
  })

  it('estado de carga inicial antes de la respuesta', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderPantalla()

    expect(screen.getByText('Cargando turnos…')).toBeTruthy()
    expect(screen.queryByText('No hay turnos cargados')).toBeNull()
  })

  it('estado vacío: no hay turnos en el salón', async () => {
    mockear({ turnos: [] })
    renderPantalla()

    expect(await screen.findByText('No hay turnos cargados')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('error de API al cargar: muestra el mensaje y permite reintentar', async () => {
    mockear({
      fallaTurnos: new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
    })
    renderPantalla()

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()

    // El reintento vuelve a llamar a la API y muestra la lista.
    mockear()
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await tablaCargada()
  })
})

describe('AdminTurnos — filtros combinables', () => {
  it('filtra por estado', async () => {
    mockear()
    renderPantalla()
    const tabla = await tablaCargada()

    await seleccionar('Estado', 'confirmado')
    expect(within(tabla).getByText('Ana Pérez')).toBeTruthy()
    expect(within(tabla).queryByText('Carla Gómez')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 3 turnos')).toBeTruthy()
  })

  it('filtra por período (desde / hasta)', async () => {
    mockear()
    renderPantalla()
    const tabla = await tablaCargada()

    await seleccionar('Desde', '2030-03-11')
    expect(within(tabla).getAllByText('Carla Gómez')).toHaveLength(1)
    expect(within(tabla).queryByText('Ana Pérez')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 3 turnos')).toBeTruthy()

    await seleccionar('Hasta', '2030-03-11')
    expect(screen.queryByRole('table')).toBeNull()
    expect(
      screen.getByText('No hay turnos para los filtros seleccionados.'),
    ).toBeTruthy()
  })

  it('filtra por profesional', async () => {
    mockear()
    renderPantalla()
    const tabla = await tablaCargada()

    await seleccionar('Profesional', '11')
    expect(within(tabla).getByText('Ana Pérez')).toBeTruthy()
    expect(within(tabla).queryByText('Carla Gómez')).toBeNull()
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
    expect(within(tabla).queryByText('María García')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 3 turnos')).toBeTruthy()
  })

  it('busca por nombre de clienta (sin distinguir mayúsculas)', async () => {
    mockear()
    renderPantalla()
    const tabla = await tablaCargada()

    await seleccionar('Buscar clienta', 'ANA')
    expect(within(tabla).getByText('Ana Pérez')).toBeTruthy()
    expect(within(tabla).queryByText('Carla Gómez')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 3 turnos')).toBeTruthy()
  })

  it('combina los filtros y los limpia', async () => {
    mockear()
    renderPantalla()
    let tabla = await tablaCargada()

    await seleccionar('Estado', 'cancelado')
    await seleccionar('Buscar clienta', 'carla')
    expect(within(tabla).getAllByText('Carla Gómez')).toHaveLength(1)
    expect(within(tabla).queryByText('Ana Pérez')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 3 turnos')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }))
    tabla = await tablaCargada()
    expect(within(tabla).getAllByText('Carla Gómez')).toHaveLength(2)
    expect(within(tabla).getByText('Ana Pérez')).toBeTruthy()
    expect(screen.getByText('3 turnos')).toBeTruthy()
  })
})

describe('AdminTurnos — transiciones de estado', () => {
  it('confirma un turno pendiente y recarga el listado', async () => {
    mockear()
    api.post.mockResolvedValue({ id: 1, estado: 'confirmado' })
    renderPantalla()
    await tablaCargada()

    const fila = filaDe('Carla Gómez', '10/03/2030')
    fireEvent.click(within(fila).getByRole('button', { name: 'Confirmar' }))

    expect(await screen.findByText('Turno confirmado correctamente.')).toBeTruthy()
    expect(api.post).toHaveBeenCalledWith('/api/turnos/1/confirmar/')
    // Recarga completa: 3 iniciales + 3 tras la transición.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(6))
  })

  it('cancela un turno solo tras confirmarlo', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear()
    api.post.mockResolvedValue({ id: 1, estado: 'cancelado' })
    renderPantalla()
    await tablaCargada()

    const fila = filaDe('Carla Gómez', '10/03/2030')
    fireEvent.click(within(fila).getByRole('button', { name: 'Cancelar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Turno cancelado correctamente.')).toBeTruthy()
    expect(api.post).toHaveBeenCalledWith('/api/turnos/1/cancelar/')
  })

  it('no cancela si se rechaza la confirmación', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockear()
    renderPantalla()
    await tablaCargada()

    const fila = filaDe('Carla Gómez', '10/03/2030')
    fireEvent.click(within(fila).getByRole('button', { name: 'Cancelar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.queryByText('Turno cancelado correctamente.')).toBeNull()
  })

  it('muestra el error del backend ante una transición inválida', async () => {
    mockear()
    api.post.mockRejectedValue(
      new Error('Solo se pueden confirmar turnos pendientes.'),
    )
    renderPantalla()
    await tablaCargada()

    const fila = filaDe('Carla Gómez', '10/03/2030')
    fireEvent.click(within(fila).getByRole('button', { name: 'Confirmar' }))

    expect(
      await screen.findByText('Solo se pueden confirmar turnos pendientes.'),
    ).toBeTruthy()
    expect(screen.queryByText('Turno confirmado correctamente.')).toBeNull()
  })

  it('nunca edita turnos directamente (solo transiciones)', async () => {
    mockear()
    api.post.mockResolvedValue({ id: 1, estado: 'confirmado' })
    renderPantalla()
    await tablaCargada()

    const fila = filaDe('Carla Gómez', '10/03/2030')
    fireEvent.click(within(fila).getByRole('button', { name: 'Confirmar' }))
    await screen.findByText('Turno confirmado correctamente.')

    expect(api.patch).not.toHaveBeenCalled()
    expect(api.delete).not.toHaveBeenCalled()
  })
})

describe('AdminTurnos — acceso por rol', () => {
  it('la ruta /admin/turnos está disponible para un administrador', async () => {
    mockear()
    renderRuta('/admin/turnos', USER_ADMIN)

    expect(await screen.findByRole('heading', { level: 1, name: /turnos/i })).toBeTruthy()
    await tablaCargada()
  })

  it('un cliente no accede a la pantalla de turnos', () => {
    mockear()
    renderRuta('/admin/turnos', USER_CLIENTE)

    expect(screen.getByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('un usuario personal no accede a la pantalla de turnos', () => {
    mockear()
    renderRuta('/admin/turnos', USER_PERSONAL)

    expect(screen.getByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('el componente revalida el rol de forma defensiva', () => {
    mockear()
    renderPantalla(USER_CLIENTE)

    expect(screen.getByText('Acceso restringido')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })
})
