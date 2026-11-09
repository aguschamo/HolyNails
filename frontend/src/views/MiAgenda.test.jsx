// @vitest-environment jsdom
// Pruebas de MiAgenda: disponibilidades propias (CRUD vía
// /api/disponibilidades/) y turnos asignados (?como_profesional=true).
// Se mockea el cliente HTTP (src/services/api.js) para no depender de un
// backend corriendo. La query string va siempre en la URL porque api.js
// ignora la opción `params`.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import MiAgenda from './MiAgenda.jsx'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthCleared: vi.fn(() => vi.fn()),
}))

const USER_PROFESIONAL = {
  id: 10,
  nombre: 'María García',
  email: 'maria@holynails.com',
  username: 'maria_profesional',
  role: 'personal',
  es_profesional: true,
  profesional_id: 10,
}

const USER_CLIENTE = {
  id: 20,
  nombre: 'Cliente Uno',
  email: 'cliente@holynails.com',
  username: 'cliente1',
  role: 'cliente',
  es_profesional: false,
  profesional_id: null,
}

const CATALOGO = [
  { id: 1, nombre: 'Semipermanente', duracion: '01:00:00', precio: '5000.00' },
]

const DISPONIBILIDADES = [
  { id: 101, profesional: 10, fecha: '2030-01-15', hora_inicio: '09:00:00', hora_fin: '10:00:00' },
  { id: 102, profesional: 10, fecha: '2030-01-16', hora_inicio: '11:00:00', hora_fin: '12:00:00' },
]

const TURNOS = [
  { id: 1, fecha: '2030-01-15', hora: '09:00:00', usuario: 20, servicio: 1, profesional: 10, estado: 'pendiente' },
  { id: 2, fecha: '2030-01-16', hora: '14:00:00', usuario: 21, servicio: 1, profesional: 10, estado: 'confirmado' },
]

// Responde por ruta: disponibilidades, turnos y (por defecto) el catálogo
// de servicios que useServicios consume para resolver nombres.
function mockear({ disponibilidades = [], turnos = [], catalogo = CATALOGO } = {}) {
  api.get.mockImplementation((path) => {
    const url = String(path)
    if (url.startsWith('/api/disponibilidades/')) {
      return Promise.resolve({
        count: disponibilidades.length,
        next: null,
        results: disponibilidades,
      })
    }
    if (url.startsWith('/api/turnos/')) {
      return Promise.resolve({ count: turnos.length, next: null, results: turnos })
    }
    return Promise.resolve({ count: catalogo.length, next: null, results: catalogo })
  })
}

function renderMiAgenda(usuario = USER_PROFESIONAL) {
  return render(
    <MemoryRouter>
      <AuthProvider initialUsuario={usuario}>
        <MiAgenda />
      </AuthProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('MiAgenda — renderizado y contratos de API', () => {
  it('muestra el título y las secciones principales', async () => {
    mockear()
    renderMiAgenda()

    expect(await screen.findByRole('heading', { name: /mi agenda/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Mis horarios de atención' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Mis turnos asignados' })).toBeTruthy()
  })

  it('consulta los endpoints con los query params que espera el backend', async () => {
    mockear()
    renderMiAgenda()

    await screen.findByText('Sin horarios cargados')
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/disponibilidades/?profesional=10')
      expect(api.get).toHaveBeenCalledWith('/api/turnos/?como_profesional=true')
    })
  })

  it('estado de carga inicial antes de la respuesta', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderMiAgenda()

    expect(screen.getByText('Cargando disponibilidades…')).toBeTruthy()
    expect(screen.getByText('Cargando turnos…')).toBeTruthy()
  })

  it('estado vacío: sin disponibilidades ni turnos asignados', async () => {
    mockear()
    renderMiAgenda()

    expect(await screen.findByText('Sin horarios cargados')).toBeTruthy()
    expect(screen.getByText(/aún no tenés turnos asignados/i)).toBeTruthy()
  })

  it('lista las disponibilidades propias con fecha y horarios formateados', async () => {
    mockear({ disponibilidades: DISPONIBILIDADES })
    renderMiAgenda()

    expect(await screen.findByText('15/01/2030')).toBeTruthy()
    expect(screen.getByText('16/01/2030')).toBeTruthy()
    expect(screen.getByText('09:00')).toBeTruthy()
    expect(screen.getByText('12:00')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Editar' })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: 'Eliminar' })).toHaveLength(2)
  })

  it('lista los turnos asignados con cliente, servicio y estado', async () => {
    mockear({ turnos: TURNOS })
    renderMiAgenda()

    expect((await screen.findAllByText('Semipermanente'))).toHaveLength(2)
    expect(screen.getByText('Cliente N° 20')).toBeTruthy()
    expect(screen.getByText('Cliente N° 21')).toBeTruthy()
    expect(screen.getByText('Pendiente')).toBeTruthy()
    expect(screen.getByText('Confirmado')).toBeTruthy()
    expect(screen.getByText('15/01/2030')).toBeTruthy()
    expect(screen.getByText('14:00')).toBeTruthy()
  })

  it('muestra el nombre real de la clienta cuando el backend lo envía (A1)', async () => {
    // `usuario_nombre` llega en el serializer de turnos (B10.1).
    mockear({
      turnos: [
        { id: 1, fecha: '2030-01-15', hora: '09:00:00', usuario: 20, usuario_nombre: 'Carla Gómez', servicio: 1, profesional: 10, estado: 'pendiente' },
        // Sin nombre (defensivo): conserva la referencia por ID.
        { id: 2, fecha: '2030-01-16', hora: '14:00:00', usuario: 21, usuario_nombre: null, servicio: 1, profesional: 10, estado: 'confirmado' },
      ],
    })
    renderMiAgenda()

    expect(await screen.findByText('Carla Gómez')).toBeTruthy()
    expect(screen.getByText('Cliente N° 21')).toBeTruthy()
    expect(screen.queryByText('Cliente N° 20')).toBeNull()
  })
})

describe('MiAgenda — filtro por fecha', () => {
  it('filtra las disponibilidades, avisa si no hay resultados y permite limpiar', async () => {
    mockear({ disponibilidades: DISPONIBILIDADES })
    renderMiAgenda()

    expect(await screen.findByText('15/01/2030')).toBeTruthy()
    expect(screen.getByText('16/01/2030')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Filtrar por fecha'), {
      target: { value: '2030-01-16' },
    })
    expect(screen.getByText('16/01/2030')).toBeTruthy()
    expect(screen.queryByText('15/01/2030')).toBeNull()

    fireEvent.change(screen.getByLabelText('Filtrar por fecha'), {
      target: { value: '2030-05-01' },
    })
    expect(screen.getByText('Sin disponibilidades para esa fecha')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Limpiar' }))
    expect(screen.getByText('15/01/2030')).toBeTruthy()
    expect(screen.getByText('16/01/2030')).toBeTruthy()
  })
})

describe('MiAgenda — gestión de disponibilidades', () => {
  it('crea una disponibilidad con el payload esperado', async () => {
    mockear()
    api.post.mockResolvedValue({
      id: 201, profesional: 10, fecha: '2030-02-01',
      hora_inicio: '14:00:00', hora_fin: '15:00:00',
    })
    renderMiAgenda()

    await screen.findByText('Sin horarios cargados')
    fireEvent.click(screen.getByRole('button', { name: 'Agregar disponibilidad' }))
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2030-02-01' } })
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '14:00' } })
    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '15:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/api/disponibilidades/', {
        profesional: 10,
        fecha: '2030-02-01',
        hora_inicio: '14:00:00',
        hora_fin: '15:00:00',
      }),
    )
    // Tras guardar se cierra el formulario
    await waitFor(() => expect(screen.queryByLabelText('Fecha')).toBeNull())
  })

  it('valida el rango horario antes de enviar', async () => {
    mockear()
    renderMiAgenda()

    await screen.findByText('Sin horarios cargados')
    fireEvent.click(screen.getByRole('button', { name: 'Agregar disponibilidad' }))
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2030-02-01' } })
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '08:00' } })
    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '09:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByText(/entre las 09:00 y las 20:00/i)).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('edita una disponibilidad existente', async () => {
    mockear({ disponibilidades: [DISPONIBILIDADES[0]] })
    api.patch.mockResolvedValue({})
    renderMiAgenda()

    await screen.findByText('15/01/2030')
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))

    expect(await screen.findByRole('heading', { name: 'Editar disponibilidad' })).toBeTruthy()
    expect(screen.getByLabelText('Fecha').value).toBe('2030-01-15')

    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '11:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/disponibilidades/101/', {
        profesional: 10,
        fecha: '2030-01-15',
        hora_inicio: '09:00:00',
        hora_fin: '11:00:00',
      }),
    )
  })

  it('elimina una disponibilidad solo tras confirmar', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear({ disponibilidades: [DISPONIBILIDADES[0]] })
    api.delete.mockResolvedValue({})
    renderMiAgenda()

    await screen.findByText('15/01/2030')
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/api/disponibilidades/101/'))
  })

  it('no elimina si se cancela la confirmación', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockear({ disponibilidades: [DISPONIBILIDADES[0]] })
    renderMiAgenda()

    await screen.findByText('15/01/2030')
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(api.delete).not.toHaveBeenCalled()
    expect(screen.getByText('15/01/2030')).toBeTruthy()
  })

  it('muestra el error del backend al eliminar una franja con turnos', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear({ disponibilidades: [DISPONIBILIDADES[0]] })
    api.delete.mockRejectedValue(
      new Error(
        'No se puede eliminar esta disponibilidad: existen turnos pendientes o confirmados que dependen de esta franja horaria.',
      ),
    )
    renderMiAgenda()

    await screen.findByText('15/01/2030')
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar' }))

    expect(await screen.findByText(/existen turnos pendientes o confirmados/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeTruthy()
  })

  it('evita envíos duplicados mientras guarda', async () => {
    mockear()
    api.post.mockImplementation(() => new Promise(() => {}))
    renderMiAgenda()

    await screen.findByText('Sin horarios cargados')
    fireEvent.click(screen.getByRole('button', { name: 'Agregar disponibilidad' }))
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2030-02-01' } })
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '14:00' } })
    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '15:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    const guardando = await screen.findByRole('button', { name: /guardando/i })
    expect(guardando.disabled).toBe(true)

    fireEvent.click(guardando)
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
  })
})

describe('MiAgenda — errores de carga', () => {
  it('muestra el error de la API y permite reintentar', async () => {
    let llamadasDisponibilidades = 0
    api.get.mockImplementation((path) => {
      if (String(path).startsWith('/api/disponibilidades/')) {
        llamadasDisponibilidades += 1
        if (llamadasDisponibilidades === 1) {
          return Promise.reject(
            new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
          )
        }
        return Promise.resolve({ count: 1, next: null, results: [DISPONIBILIDADES[0]] })
      }
      return Promise.resolve({ count: 0, next: null, results: [] })
    })
    renderMiAgenda()

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()
    expect(screen.queryByText('Sin horarios cargados')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('15/01/2030')).toBeTruthy()
    await waitFor(() => expect(llamadasDisponibilidades).toBe(2))
  })
})

describe('MiAgenda — acceso restringido', () => {
  it('no muestra la agenda a un usuario que no es profesional', async () => {
    mockear()
    renderMiAgenda(USER_CLIENTE)

    expect(await screen.findByText(/esta sección es solo para profesionales/i)).toBeTruthy()
    expect(screen.queryByRole('heading', { name: /mi agenda/i })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Mis horarios de atención' })).toBeNull()
  })
})
