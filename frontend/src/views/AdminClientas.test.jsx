// @vitest-environment jsdom
// Pruebas de AdminClientas (B10.3): listado de cuentas CLIENTE con
// búsqueda por nombre y email, paginación completa, detalle con el
// historial de turnos (estados, fecha, hora, servicio y profesional),
// activación / desactivación con confirmación, estados de carga / vacío /
// error, errores de la API y control de acceso por rol en la ruta
// /admin/clientas. api.js se mockea para no depender de un backend.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '../App.jsx'
import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import AdminClientas from './AdminClientas.jsx'

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

const CLIENTAS = [
  {
    id: 1,
    username: 'carla',
    email: 'carla@holynails.test',
    nombre: 'Carla Gómez',
    role: 'CLIENTE',
    is_active: true,
  },
  {
    id: 2,
    username: 'ana',
    email: 'ana@holynails.test',
    nombre: 'Ana Pérez',
    role: 'CLIENTE',
    is_active: false,
  },
]

const CLIENTA_PAGINA_2 = {
  id: 3,
  username: 'lucia',
  email: 'lucia@holynails.test',
  nombre: 'Lucía Ríos',
  role: 'CLIENTE',
  is_active: true,
}

const SERVICIOS = [
  { id: 1, nombre: 'Semi permanente' },
  { id: 2, nombre: 'Esculpidas' },
]

const PROFESIONALES = [
  { id: 10, nombre: 'María García' },
  { id: 11, nombre: 'Brenda López' },
]

const HISTORIAL = [
  {
    id: 101,
    fecha: '2030-05-01',
    hora: '09:00:00',
    usuario: 1,
    usuario_nombre: 'Carla Gómez',
    servicio: 1,
    profesional: 10,
    estado: 'pendiente',
  },
  {
    id: 102,
    fecha: '2030-04-10',
    hora: '15:30:00',
    usuario: 1,
    usuario_nombre: 'Carla Gómez',
    servicio: 2,
    profesional: 11,
    estado: 'confirmado',
  },
  {
    id: 103,
    fecha: '2030-03-05',
    hora: '11:00:00',
    usuario: 1,
    usuario_nombre: 'Carla Gómez',
    servicio: 1,
    profesional: 10,
    estado: 'cancelado',
  },
]

function paginado(results, next = null) {
  return { count: results.length, next, results }
}

// Responde por prefijo de ruta (listado, ficha, historial y catálogos).
function mockear({
  clientas = CLIENTAS,
  servicios = SERVICIOS,
  profesionales = PROFESIONALES,
  historial = HISTORIAL,
  detalle = null,
  pagina2 = null,
  fallaClientas = null,
  fallaDetalle = null,
} = {}) {
  api.get.mockImplementation((path) => {
    const p = String(path)
    if (p.startsWith('/api/clientas/') && p.includes('page=2')) {
      return Promise.resolve(paginado([pagina2 || CLIENTA_PAGINA_2]))
    }
    if (p.startsWith('/api/clientas/') && p.includes('/turnos')) {
      return Promise.resolve(paginado(historial))
    }
    if (/^\/api\/clientas\/\d+\/?$/.test(p)) {
      if (fallaDetalle) return Promise.reject(fallaDetalle)
      if (detalle) return Promise.resolve(detalle)
      const id = Number(p.match(/\/(\d+)\/?$/)[1])
      const encontrada = clientas.find((c) => c.id === id)
      return encontrada
        ? Promise.resolve(encontrada)
        : Promise.reject(new Error('No encontrada.'))
    }
    if (p.startsWith('/api/clientas/')) {
      return fallaClientas
        ? Promise.reject(fallaClientas)
        : Promise.resolve(paginado(clientas, pagina2 ? '/api/clientas/?page=2' : null))
    }
    if (p.startsWith('/api/servicios/')) return Promise.resolve(paginado(servicios))
    if (p.startsWith('/api/profesionales/')) return Promise.resolve(paginado(profesionales))
    return Promise.resolve(paginado([]))
  })
}

function renderPantalla(usuario = USER_ADMIN) {
  return render(
    <MemoryRouter initialEntries={['/admin/clientas']}>
      <AuthProvider initialUsuario={usuario}>
        <AdminClientas />
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

// Fila de la tabla que contiene el nombre de la clienta.
function filaDe(nombre) {
  return screen
    .getAllByRole('row')
    .find((fila) => fila.textContent.includes(nombre))
}

async function buscar(texto) {
  fireEvent.change(await screen.findByLabelText('Buscar clienta'), {
    target: { value: texto },
  })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

describe('AdminClientas — listado', () => {
  it('lista las clientas con nombre, email, cuenta y estado', async () => {
    mockear()
    renderPantalla()

    const tabla = await screen.findByRole('table')
    expect(within(tabla).getByText('Carla Gómez')).toBeTruthy()
    expect(within(tabla).getByText('carla@holynails.test')).toBeTruthy()
    expect(within(tabla).getByText('carla')).toBeTruthy()
    expect(within(tabla).getByText('Activa')).toBeTruthy()
    expect(within(tabla).getByText('Ana Pérez')).toBeTruthy()
    expect(within(tabla).getByText('Desactivada')).toBeTruthy()
    expect(screen.getByText('2 clientas')).toBeTruthy()
  })

  it('recorre toda la paginación disponible', async () => {
    mockear({ pagina2: CLIENTA_PAGINA_2 })
    renderPantalla()

    const tabla = await screen.findByRole('table')
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/clientas/?page=2'))
    expect(within(tabla).getByText('Carla Gómez')).toBeTruthy()
    expect(within(tabla).getByText('Lucía Ríos')).toBeTruthy()
    expect(within(tabla).getByText('lucia@holynails.test')).toBeTruthy()
  })

  it('estado de carga inicial antes de la respuesta', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderPantalla()

    expect(screen.getByText('Cargando clientas…')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('estado vacío: no hay clientas registradas', async () => {
    mockear({ clientas: [] })
    renderPantalla()

    expect(await screen.findByText('No hay clientas registradas')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('error de API al cargar: muestra el mensaje y permite reintentar', async () => {
    mockear({
      fallaClientas: new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
    })
    renderPantalla()

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()

    // El reintento vuelve a llamar a la API y muestra la lista.
    mockear()
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(await screen.findByRole('table')).toBeTruthy()
  })
})

describe('AdminClientas — búsqueda', () => {
  it('busca por nombre', async () => {
    mockear()
    renderPantalla()
    await screen.findByRole('table')

    await buscar('Pérez')
    const tabla = screen.getByRole('table')
    expect(within(tabla).getByText('Ana Pérez')).toBeTruthy()
    expect(within(tabla).queryByText('Carla Gómez')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 2 clientas')).toBeTruthy()
  })

  it('busca por email', async () => {
    mockear()
    renderPantalla()
    await screen.findByRole('table')

    await buscar('carla@holynails.test')
    const tabla = screen.getByRole('table')
    expect(within(tabla).getByText('Carla Gómez')).toBeTruthy()
    expect(within(tabla).queryByText('Ana Pérez')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 2 clientas')).toBeTruthy()
  })

  it('estado vacío por búsqueda sin resultados con opción de limpiar', async () => {
    mockear()
    renderPantalla()
    await screen.findByRole('table')

    await buscar('no-existe@nada.test')
    expect(
      screen.getByText('No hay clientas para la búsqueda seleccionada.'),
    ).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()

    // Hay dos botones "Limpiar búsqueda" (cabecera y estado vacío); ambos
    // limpian la misma búsqueda.
    fireEvent.click(screen.getAllByRole('button', { name: 'Limpiar búsqueda' })[0])
    expect(await screen.findByRole('table')).toBeTruthy()
  })
})

describe('AdminClientas — detalle e historial', () => {
  it('abre el detalle con los datos de la clienta', async () => {
    mockear()
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Ver detalle' }),
    )

    expect(await screen.findByRole('heading', { name: 'Detalle de la clienta' })).toBeTruthy()
    expect(api.get).toHaveBeenCalledWith('/api/clientas/1/')
    expect(screen.getByText('carla@holynails.test')).toBeTruthy()
    expect(screen.getByText('carla')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Desactivar' })).toBeTruthy()
    // La vista de listado no queda montada en paralelo.
    expect(screen.queryByRole('button', { name: 'Ver detalle' })).toBeNull()
  })

  it('muestra el historial con estados, fecha, hora, servicio y profesional', async () => {
    mockear()
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Ver detalle' }),
    )

    expect(
      await screen.findByRole('heading', { name: 'Historial de turnos' }),
    ).toBeTruthy()
    expect(api.get).toHaveBeenCalledWith('/api/clientas/1/turnos/')

    const tabla = screen.getByRole('table')
    expect(within(tabla).getAllByText('Pendiente')).toHaveLength(1)
    expect(within(tabla).getAllByText('Confirmado')).toHaveLength(1)
    expect(within(tabla).getAllByText('Cancelado')).toHaveLength(1)
    expect(within(tabla).getByText('01/05/2030')).toBeTruthy()
    expect(within(tabla).getByText('09:00')).toBeTruthy()
    expect(within(tabla).getByText('15:30')).toBeTruthy()
    expect(within(tabla).getAllByText('Semi permanente')).toHaveLength(2)
    expect(within(tabla).getByText('Esculpidas')).toBeTruthy()
    expect(within(tabla).getAllByText('María García')).toHaveLength(2)
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
  })

  it('historial vacío: mensaje claro sin inventar datos', async () => {
    mockear({ historial: [] })
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Ver detalle' }),
    )

    expect(
      await screen.findByText('Esta clienta todavía no tiene turnos.'),
    ).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('error de API en el detalle: muestra el mensaje y permite reintentar', async () => {
    mockear({
      fallaDetalle: new Error('No se pudo cargar la clienta.'),
    })
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Ver detalle' }),
    )

    expect(await screen.findByText('No se pudo cargar la clienta.')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()

    // El reintento vuelve a consultar ficha e historial.
    mockear()
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    expect(
      await screen.findByRole('heading', { name: 'Historial de turnos' }),
    ).toBeTruthy()
  })

  it('vuelve al listado desde el detalle', async () => {
    mockear()
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Ver detalle' }),
    )
    await screen.findByRole('heading', { name: 'Detalle de la clienta' })

    fireEvent.click(screen.getByRole('button', { name: 'Volver al listado' }))

    expect(await screen.findByRole('table')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Detalle de la clienta' })).toBeNull()
  })
})

describe('AdminClientas — activación y desactivación', () => {
  it('desactiva una cuenta solo tras confirmar', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear()
    api.patch.mockResolvedValue({})
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Desactivar' }),
    )

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(confirmar.mock.calls[0][0]).toContain('Carla Gómez')
    expect(await screen.findByText('Cuenta desactivada correctamente.')).toBeTruthy()
    expect(api.patch).toHaveBeenCalledWith('/api/clientas/1/', { is_active: false })
    // Refresco completo del listado tras la operación:
    // 3 iniciales (clientas + catálogos) + 3 tras el PATCH.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(6))
  })

  it('no desactiva si se rechaza la confirmación', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockear()
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Desactivar' }),
    )

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(api.patch).not.toHaveBeenCalled()
    expect(screen.queryByText('Cuenta desactivada correctamente.')).toBeNull()
    expect(screen.getByText('2 clientas')).toBeTruthy()
  })

  it('activa una cuenta desactivada sin pedir confirmación', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear()
    api.patch.mockResolvedValue({})
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(within(filaDe('Ana Pérez')).getByRole('button', { name: 'Activar' }))

    expect(confirmar).not.toHaveBeenCalled()
    expect(await screen.findByText('Cuenta activada correctamente.')).toBeTruthy()
    expect(api.patch).toHaveBeenCalledWith('/api/clientas/2/', { is_active: true })
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(6))
  })

  it('muestra el error del backend sin modificar la cuenta', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear()
    api.patch.mockRejectedValue(
      new Error('No podés desactivar tu propia cuenta desde la gestión de clientas.'),
    )
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Desactivar' }),
    )

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(
      await screen.findByText(
        'No podés desactivar tu propia cuenta desde la gestión de clientas.',
      ),
    ).toBeTruthy()
    expect(screen.queryByText('Cuenta desactivada correctamente.')).toBeNull()
    expect(screen.getByText('2 clientas')).toBeTruthy()
  })

  it('permite desactivar desde el detalle con refresco de la ficha', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear()
    api.patch.mockResolvedValue({})
    renderPantalla()
    await screen.findByRole('table')

    fireEvent.click(
      within(filaDe('Carla Gómez')).getByRole('button', { name: 'Ver detalle' }),
    )
    await screen.findByRole('heading', { name: 'Detalle de la clienta' })

    fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Cuenta desactivada correctamente.')).toBeTruthy()
    expect(api.patch).toHaveBeenCalledWith('/api/clientas/1/', { is_active: false })
    // La ficha se vuelve a consultar tras la operación.
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/clientas/1/'))
    expect(screen.getByRole('heading', { name: 'Detalle de la clienta' })).toBeTruthy()
  })
})

describe('AdminClientas — acceso por rol', () => {
  it('la ruta /admin/clientas está disponible para un administrador', async () => {
    mockear()
    renderRuta('/admin/clientas', USER_ADMIN)

    expect(await screen.findByRole('heading', { level: 1, name: /clientas/i })).toBeTruthy()
    expect(await screen.findByRole('table')).toBeTruthy()
  })

  it('un cliente no accede a la pantalla de clientas', () => {
    mockear()
    renderRuta('/admin/clientas', USER_CLIENTE)

    expect(screen.getByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('un usuario personal no accede a la pantalla de clientas', () => {
    mockear()
    renderRuta('/admin/clientas', USER_PERSONAL)

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
