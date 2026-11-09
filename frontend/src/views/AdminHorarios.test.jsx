// @vitest-environment jsdom
// Pruebas de AdminHorarios (B10.2): listado de disponibilidades con
// profesional, día, inicio y fin; filtros combinables por profesional y
// período; alta, edición y eliminación con confirmación; estados de
// carga / vacío / error; errores de validación de la API; y control de
// acceso por rol en la ruta /admin/horarios.
// api.js se mockea para no depender de un backend corriendo.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from '../App.jsx'
import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import AdminHorarios from './AdminHorarios.jsx'

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

const PROFESIONALES = [
  { id: 10, nombre: 'María García' },
  { id: 11, nombre: 'Brenda López' },
]

const DISPONIBILIDADES = [
  { id: 1, profesional: 10, fecha: '2030-03-10', hora_inicio: '09:00:00', hora_fin: '12:00:00' },
  { id: 2, profesional: 10, fecha: '2030-03-12', hora_inicio: '15:00:00', hora_fin: '18:00:00' },
  { id: 3, profesional: 11, fecha: '2030-03-11', hora_inicio: '10:00:00', hora_fin: '13:00:00' },
]

function paginado(results, next = null) {
  return { count: results.length, next, results }
}

// Responde por prefijo de ruta (los dos listados que carga la pantalla).
function mockear({
  disponibilidades = DISPONIBILIDADES,
  profesionales = PROFESIONALES,
  fallaDisponibilidades = null,
} = {}) {
  api.get.mockImplementation((path) => {
    const p = String(path)
    if (p.startsWith('/api/disponibilidades/')) {
      return fallaDisponibilidades
        ? Promise.reject(fallaDisponibilidades)
        : Promise.resolve(paginado(disponibilidades))
    }
    if (p.startsWith('/api/profesionales/')) return Promise.resolve(paginado(profesionales))
    return Promise.resolve(paginado([]))
  })
}

function renderPantalla(usuario = USER_ADMIN) {
  return render(
    <MemoryRouter initialEntries={['/admin/horarios']}>
      <AuthProvider initialUsuario={usuario}>
        <AdminHorarios />
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

// Señal de "listado cargado" (el nombre del profesional se repite en
// filas y selects, así que se busca sólo dentro de la tabla).
async function tablaCargada() {
  return screen.findByRole('table')
}

// Fila de la tabla que contiene el profesional y la fecha dadas.
function filaDe(profesional, fecha) {
  return screen
    .getAllByRole('row')
    .find((fila) => fila.textContent.includes(profesional) && fila.textContent.includes(fecha))
}

async function seleccionar(etiqueta, valor) {
  fireEvent.change(await screen.findByLabelText(etiqueta), { target: { value: valor } })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

describe('AdminHorarios — listado general', () => {
  it('lista las disponibilidades con profesional, día, inicio y fin', async () => {
    mockear()
    renderPantalla()

    const tabla = await tablaCargada()
    expect(within(tabla).getAllByText('María García')).toHaveLength(2)
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
    expect(within(tabla).getByText('10/03/2030')).toBeTruthy()
    expect(within(tabla).getByText('12/03/2030')).toBeTruthy()
    expect(within(tabla).getByText('11/03/2030')).toBeTruthy()
    expect(within(tabla).getAllByText('09:00')).toHaveLength(1)
    expect(within(tabla).getByText('12:00')).toBeTruthy()
    expect(within(tabla).getByText('15:00')).toBeTruthy()
    expect(within(tabla).getByText('18:00')).toBeTruthy()
    expect(within(tabla).getByText('10:00')).toBeTruthy()
    expect(within(tabla).getByText('13:00')).toBeTruthy()
    expect(screen.getByText('3 franjas')).toBeTruthy()
  })

  it('consulta las disponibilidades y el catálogo de profesionales', async () => {
    mockear()
    renderPantalla()

    await tablaCargada()
    expect(api.get).toHaveBeenCalledWith('/api/disponibilidades/')
    expect(api.get).toHaveBeenCalledWith('/api/profesionales/')
  })

  it('estado de carga inicial antes de la respuesta', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderPantalla()

    expect(screen.getByText('Cargando disponibilidades…')).toBeTruthy()
    expect(screen.queryByText('Sin horarios cargados')).toBeNull()
  })

  it('estado vacío: no hay disponibilidades cargadas', async () => {
    mockear({ disponibilidades: [] })
    renderPantalla()

    expect(await screen.findByText('Sin horarios cargados')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('error de API al cargar: muestra el mensaje y permite reintentar', async () => {
    mockear({
      fallaDisponibilidades: new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
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

describe('AdminHorarios — filtros combinables', () => {
  it('filtra por profesional', async () => {
    mockear()
    renderPantalla()
    const tabla = await tablaCargada()

    await seleccionar('Filtrar por profesional', '11')
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
    expect(within(tabla).queryByText('María García')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 3 franjas')).toBeTruthy()
  })

  it('filtra por período (desde / hasta)', async () => {
    mockear()
    renderPantalla()
    const tabla = await tablaCargada()

    await seleccionar('Desde', '2030-03-11')
    expect(within(tabla).getAllByText('María García')).toHaveLength(1)
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
    expect(screen.getByText('Mostrando 2 de 3 franjas')).toBeTruthy()

    await seleccionar('Hasta', '2030-03-11')
    expect(within(tabla).queryByText('María García')).toBeNull()
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
    expect(screen.getByText('Mostrando 1 de 3 franjas')).toBeTruthy()
  })

  it('combina los filtros y los limpia', async () => {
    mockear()
    renderPantalla()
    let tabla = await tablaCargada()

    await seleccionar('Filtrar por profesional', '10')
    await seleccionar('Desde', '2030-03-12')
    expect(within(tabla).getByText('12/03/2030')).toBeTruthy()
    expect(within(tabla).queryByText('10/03/2030')).toBeNull()
    expect(within(tabla).queryByText('Brenda López')).toBeNull()
    expect(screen.getByText('Mostrando 1 de 3 franjas')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }))
    tabla = await tablaCargada()
    expect(within(tabla).getAllByText('María García')).toHaveLength(2)
    expect(within(tabla).getByText('Brenda López')).toBeTruthy()
    expect(screen.getByText('3 franjas')).toBeTruthy()
  })

  it('estado vacío por filtros con opción de limpiar', async () => {
    mockear()
    renderPantalla()
    await tablaCargada()

    await seleccionar('Desde', '2031-01-01')
    expect(
      screen.getByText('No hay disponibilidades para los filtros seleccionados.'),
    ).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()

    // Hay dos botones "Limpiar filtros" (cabecera y estado vacío); ambos
    // limpian los mismos filtros.
    fireEvent.click(screen.getAllByRole('button', { name: 'Limpiar filtros' })[0])
    await tablaCargada()
  })
})

describe('AdminHorarios — creación', () => {
  it('crea una disponibilidad y recarga el listado', async () => {
    mockear()
    api.post.mockResolvedValue({ id: 4 })
    renderPantalla()
    await tablaCargada()

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo horario' }))
    fireEvent.change(await screen.findByLabelText('Profesional'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2030-03-15' } })
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '09:00' } })
    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '12:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear horario' }))

    expect(await screen.findByText('Disponibilidad creada correctamente.')).toBeTruthy()
    expect(api.post).toHaveBeenCalledWith('/api/disponibilidades/', {
      profesional: 10,
      fecha: '2030-03-15',
      hora_inicio: '09:00:00',
      hora_fin: '12:00:00',
    })
    expect(screen.queryByRole('button', { name: 'Crear horario' })).toBeNull()
    // Recarga completa: 2 iniciales + 2 tras la operación.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(4))
  })

  it('valida los campos obligatorios antes de enviar', async () => {
    mockear()
    renderPantalla()
    await tablaCargada()

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo horario' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Crear horario' }))

    expect(
      screen.getByText('Completá profesional, fecha, hora de inicio y hora de fin.'),
    ).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('valida que la hora de fin sea posterior a la de inicio', async () => {
    mockear()
    renderPantalla()
    await tablaCargada()

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo horario' }))
    fireEvent.change(await screen.findByLabelText('Profesional'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2030-03-15' } })
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '12:00' } })
    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '12:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear horario' }))

    expect(
      screen.getByText('La hora de inicio debe ser anterior a la hora de fin.'),
    ).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('valida el rango horario del salón', async () => {
    mockear()
    renderPantalla()
    await tablaCargada()

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo horario' }))
    fireEvent.change(await screen.findByLabelText('Profesional'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2030-03-15' } })
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '08:00' } })
    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '12:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear horario' }))

    expect(
      screen.getByText('El horario debe estar entre las 09:00 y las 20:00.'),
    ).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('muestra el error de validación del backend sin cerrar el formulario', async () => {
    mockear()
    api.post.mockRejectedValue(
      new Error('Ya existe una disponibilidad para ese profesional, fecha y hora de inicio.'),
    )
    renderPantalla()
    await tablaCargada()

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo horario' }))
    fireEvent.change(await screen.findByLabelText('Profesional'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2030-03-10' } })
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '09:00' } })
    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '12:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Crear horario' }))

    expect(
      await screen.findByText(
        'Ya existe una disponibilidad para ese profesional, fecha y hora de inicio.',
      ),
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Crear horario' })).toBeTruthy()
  })
})

describe('AdminHorarios — edición y eliminación', () => {
  it('edita una disponibilidad con los datos precargados', async () => {
    mockear()
    api.patch.mockResolvedValue({})
    renderPantalla()
    const tabla = await tablaCargada()

    fireEvent.click(
      within(filaDe('María García', '10/03/2030')).getByRole('button', { name: 'Editar' }),
    )

    // El formulario viene precargado con la franja seleccionada.
    expect((await screen.findByLabelText('Profesional')).value).toBe('10')
    expect(screen.getByLabelText('Fecha').value).toBe('2030-03-10')
    expect(screen.getByLabelText('Hora de inicio').value).toBe('09:00')
    expect(screen.getByLabelText('Hora de fin').value).toBe('12:00')

    fireEvent.change(screen.getByLabelText('Hora de fin'), { target: { value: '11:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByText('Disponibilidad actualizada correctamente.')).toBeTruthy()
    expect(api.patch).toHaveBeenCalledWith('/api/disponibilidades/1/', {
      profesional: 10,
      fecha: '2030-03-10',
      hora_inicio: '09:00:00',
      hora_fin: '11:00:00',
    })
    expect(screen.queryByRole('button', { name: 'Guardar' })).toBeNull()
    // Recarga completa: 2 iniciales + 2 tras la operación.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(4))
    expect(tabla).toBeTruthy()
  })

  it('elimina una disponibilidad solo tras confirmar', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear()
    api.delete.mockResolvedValue(undefined)
    renderPantalla()
    await tablaCargada()

    fireEvent.click(
      within(filaDe('Brenda López', '11/03/2030')).getByRole('button', { name: 'Eliminar' }),
    )

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Disponibilidad eliminada correctamente.')).toBeTruthy()
    expect(api.delete).toHaveBeenCalledWith('/api/disponibilidades/3/')
    // Recarga completa: 2 iniciales + 2 tras la operación.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(4))
  })

  it('no elimina si se rechaza la confirmación', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockear()
    renderPantalla()
    await tablaCargada()

    fireEvent.click(
      within(filaDe('Brenda López', '11/03/2030')).getByRole('button', { name: 'Eliminar' }),
    )

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(api.delete).not.toHaveBeenCalled()
    expect(screen.queryByText('Disponibilidad eliminada correctamente.')).toBeNull()
    // El listado sigue intacto.
    expect(screen.getByText('3 franjas')).toBeTruthy()
  })

  it('muestra el error del backend al eliminar', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear()
    api.delete.mockRejectedValue(
      new Error(
        'No se puede eliminar esta disponibilidad: existen turnos futuros pendientes o confirmados que dependen de esta franja horaria.',
      ),
    )
    renderPantalla()
    await tablaCargada()

    fireEvent.click(
      within(filaDe('Brenda López', '11/03/2030')).getByRole('button', { name: 'Eliminar' }),
    )

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(
      await screen.findByText(
        'No se puede eliminar esta disponibilidad: existen turnos futuros pendientes o confirmados que dependen de esta franja horaria.',
      ),
    ).toBeTruthy()
    expect(screen.getByText('3 franjas')).toBeTruthy()
  })
})

describe('AdminHorarios — acceso por rol', () => {
  it('la ruta /admin/horarios está disponible para un administrador', async () => {
    mockear()
    renderRuta('/admin/horarios', USER_ADMIN)

    expect(await screen.findByRole('heading', { level: 1, name: /horarios/i })).toBeTruthy()
    await tablaCargada()
  })

  it('un cliente no accede a la pantalla de horarios', () => {
    mockear()
    renderRuta('/admin/horarios', USER_CLIENTE)

    expect(screen.getByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })

  it('un usuario personal no accede a la pantalla de horarios', () => {
    mockear()
    renderRuta('/admin/horarios', USER_PERSONAL)

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
