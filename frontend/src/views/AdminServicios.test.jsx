// @vitest-environment jsdom
// Pruebas de la sección de servicios del panel admin: listado (incluidos
// inactivos) con precio/duración formateados, paginación, alta, edición,
// baja lógica vía is_active (nunca DELETE) y control de acceso.
// api.js se mockea para no depender de un backend corriendo.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import AdminServicios from './AdminServicios.jsx'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthCleared: vi.fn(() => vi.fn()),
}))

const USER_ADMIN = {
  id: 1,
  nombre: 'Admin',
  email: 'admin@holynails.test',
  username: 'admin',
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

const SEMI = { id: 1, nombre: 'Semipermanente', duracion: '1:00:00', precio: '5000.00', is_active: true }
const KAPPING = { id: 2, nombre: 'Kapping', duracion: '0:45:00', precio: '8000.00', is_active: false }
const FRANCES = { id: 3, nombre: 'Frances', duracion: '2:30:00', precio: '12000.00', is_active: true }

function paginado(results, next = null) {
  return { count: results.length, next, results }
}

function mockear(servicios = [SEMI, KAPPING, FRANCES]) {
  api.get.mockResolvedValue(paginado(servicios))
}

function renderSeccion(usuario = USER_ADMIN) {
  return render(
    <MemoryRouter>
      <AuthProvider initialUsuario={usuario}>
        <AdminServicios />
      </AuthProvider>
    </MemoryRouter>,
  )
}

async function abrirFormularioCrear() {
  await screen.findByText('Sin servicios cargados')
  fireEvent.click(screen.getByRole('button', { name: 'Nuevo servicio' }))
  return screen.findByLabelText('Nombre del servicio')
}

function completarFormulario({
  nombre = 'Manicura',
  precio = '4500',
  duracion = '01:15',
} = {}) {
  fireEvent.change(screen.getByLabelText('Nombre del servicio'), {
    target: { value: nombre },
  })
  fireEvent.change(screen.getByLabelText('Precio'), { target: { value: precio } })
  fireEvent.change(screen.getByLabelText('Duración'), { target: { value: duracion } })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('AdminServicios — listado', () => {
  it('lista los servicios con precio, duración y estado formateados', async () => {
    mockear()
    renderSeccion()

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    expect(screen.getByText('Kapping')).toBeTruthy()
    expect(screen.getByText('Frances')).toBeTruthy()

    // Precio con el mismo formato que Home/Agendar.
    expect(screen.getByText('$ 5.000')).toBeTruthy()
    expect(screen.getByText('$ 8.000')).toBeTruthy()
    expect(screen.getByText('$ 12.000')).toBeTruthy()

    // Duración: horas y minutos, o solo minutos si es < 1 h.
    expect(screen.getByText('1 h')).toBeTruthy()
    expect(screen.getByText('45 min')).toBeTruthy()
    expect(screen.getByText('2 h 30 min')).toBeTruthy()

    // Inactivos incluidos en el listado del admin.
    expect(screen.getAllByText('Activo')).toHaveLength(2)
    expect(screen.getByText('Inactivo')).toBeTruthy()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/servicios/'))
  })

  it('recorre todas las páginas de la respuesta paginada', async () => {
    api.get
      .mockResolvedValueOnce(
        paginado([SEMI], 'http://127.0.0.1:8000/api/servicios/?page=2'),
      )
      .mockResolvedValueOnce(paginado([KAPPING]))
    renderSeccion()

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    expect(await screen.findByText('Kapping')).toBeTruthy()
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenCalledWith('http://127.0.0.1:8000/api/servicios/?page=2')
  })

  it('muestra el estado de carga inicial', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderSeccion()

    expect(screen.getByText('Cargando servicios…')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Nuevo servicio' }).disabled).toBe(true)
  })

  it('muestra el estado vacío', async () => {
    mockear([])
    renderSeccion()

    expect(await screen.findByText('Sin servicios cargados')).toBeTruthy()
  })

  it('muestra el error de la API y permite reintentar', async () => {
    let llamadas = 0
    api.get.mockImplementation(() => {
      llamadas += 1
      if (llamadas === 1) {
        return Promise.reject(
          new Error('No se pudo conectar con el servidor. Verificá tu conexión.'),
        )
      }
      return Promise.resolve(paginado([SEMI]))
    })
    renderSeccion()

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()
    expect(screen.queryByText('Sin servicios cargados')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    await waitFor(() => expect(llamadas).toBe(2))
  })
})

describe('AdminServicios — creación', () => {
  it('crea un servicio con el payload esperado y recarga el listado', async () => {
    mockear([])
    api.post.mockResolvedValue({ id: 4, nombre: 'Manicura' })
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Crear servicio' }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/api/servicios/', {
        nombre: 'Manicura',
        precio: '4500',
        duracion: '01:15:00',
      }),
    )
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Servicio creado correctamente.')).toBeTruthy()
    expect(screen.queryByLabelText('Nombre del servicio')).toBeNull()
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('valida los campos obligatorios antes de enviar', async () => {
    mockear([])
    renderSeccion()

    await abrirFormularioCrear()
    fireEvent.click(screen.getByRole('button', { name: 'Crear servicio' }))

    expect(await screen.findByText('Completá todos los campos.')).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('valida que el precio no sea negativo', async () => {
    mockear([])
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario({ precio: '-5' })
    fireEvent.click(screen.getByRole('button', { name: 'Crear servicio' }))

    expect(await screen.findByText('El precio no puede ser negativo.')).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('valida que la duración sea al menos un minuto', async () => {
    mockear([])
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario({ duracion: '00:00' })
    fireEvent.click(screen.getByRole('button', { name: 'Crear servicio' }))

    expect(
      await screen.findByText('La duración debe ser al menos 1 minuto.'),
    ).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('muestra el error de validación del backend sin cerrar el formulario', async () => {
    mockear([])
    api.post.mockRejectedValue(new Error('This field is required.'))
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Crear servicio' }))

    expect(await screen.findByText('This field is required.')).toBeTruthy()
    expect(screen.getByLabelText('Nombre del servicio')).toBeTruthy()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('evita envíos duplicados mientras guarda', async () => {
    mockear([])
    api.post.mockImplementation(() => new Promise(() => {}))
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Crear servicio' }))

    const guardando = await screen.findByRole('button', { name: /guardando/i })
    expect(guardando.disabled).toBe(true)

    fireEvent.click(guardando)
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
  })
})

describe('AdminServicios — edición y estado', () => {
  it('edita un servicio con los valores precargados', async () => {
    mockear([SEMI])
    api.patch.mockResolvedValue({})
    renderSeccion()

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))

    const inputNombre = await screen.findByLabelText('Nombre del servicio')
    expect(inputNombre.value).toBe('Semipermanente')
    expect(screen.getByLabelText('Precio').value).toBe('5000.00')
    expect(screen.getByLabelText('Duración').value).toBe('01:00')

    fireEvent.change(screen.getByLabelText('Precio'), {
      target: { value: '6000.00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/servicios/1/', {
        nombre: 'Semipermanente',
        precio: '6000.00',
        duracion: '01:00:00',
      }),
    )
    expect(await screen.findByText('Servicio actualizado correctamente.')).toBeTruthy()
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('desactiva un servicio solo tras confirmar (baja lógica, sin DELETE)', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear([SEMI])
    api.patch.mockResolvedValue({})
    renderSeccion()

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/servicios/1/', {
        is_active: false,
      }),
    )
    expect(api.delete).not.toHaveBeenCalled()
    expect(await screen.findByText('Servicio desactivado correctamente.')).toBeTruthy()
  })

  it('activa un servicio dado de baja', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear([KAPPING])
    api.patch.mockResolvedValue({})
    renderSeccion()

    expect(await screen.findByText('Kapping')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Activar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/servicios/2/', {
        is_active: true,
      }),
    )
  })

  it('no cambia el estado si se cancela la confirmación', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockear([SEMI])
    renderSeccion()

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(api.patch).not.toHaveBeenCalled()
    expect(screen.getByText('Activo')).toBeTruthy()
  })

  it('muestra el error del backend al cambiar el estado', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear([SEMI])
    api.patch.mockRejectedValue(new Error('No tenés permiso para realizar esta acción.'))
    renderSeccion()

    expect(await screen.findByText('Semipermanente')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))

    expect(
      await screen.findByText('No tenés permiso para realizar esta acción.'),
    ).toBeTruthy()
    // El listado sigue intacto y sin recargar.
    expect(api.get).toHaveBeenCalledTimes(1)
  })
})

describe('AdminServicios — acceso restringido', () => {
  it('no muestra la sección a un usuario que no es admin', async () => {
    mockear()
    renderSeccion(USER_CLIENTE)

    expect(await screen.findByText(/acceso restringido/i)).toBeTruthy()
    expect(screen.queryByRole('heading', { name: /servicios/i })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Nuevo servicio' })).toBeNull()
    expect(api.get).not.toHaveBeenCalled()
  })
})
