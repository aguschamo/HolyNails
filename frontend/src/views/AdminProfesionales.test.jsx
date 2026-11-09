// @vitest-environment jsdom
// Pruebas de la sección de profesionales del panel admin: listado paginado,
// alta vía POST /api/profesionales/crear-con-usuario/ (una sola solicitud),
// edición de nombre, activación/desactivación y control de acceso.
// api.js se mockea para no depender de un backend corriendo; la query string
// va siempre en la URL porque api.js ignora la opción `params`.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import AdminProfesionales from './AdminProfesionales.jsx'

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

const MARIA = { id: 1, nombre: 'María', usuario: 10, is_active: true }
const BRENDA = { id: 2, nombre: 'Brenda', usuario: null, is_active: false }

function paginado(results, next = null) {
  return { count: results.length, next, results }
}

function mockear(profesionales = [MARIA, BRENDA]) {
  api.get.mockResolvedValue(paginado(profesionales))
}

function renderSeccion(usuario = USER_ADMIN) {
  return render(
    <MemoryRouter>
      <AuthProvider initialUsuario={usuario}>
        <AdminProfesionales />
      </AuthProvider>
    </MemoryRouter>,
  )
}

async function abrirFormularioCrear() {
  await screen.findByText('Sin profesionales cargados')
  fireEvent.click(screen.getByRole('button', { name: 'Nueva profesional' }))
  return screen.findByLabelText('Nombre de la cuenta')
}

function completarFormulario() {
  fireEvent.change(screen.getByLabelText('Nombre de la cuenta'), {
    target: { value: 'María García' },
  })
  fireEvent.change(screen.getByLabelText('Nombre de usuario'), {
    target: { value: 'maria' },
  })
  fireEvent.change(screen.getByLabelText('Correo electrónico'), {
    target: { value: 'maria@holynails.test' },
  })
  fireEvent.change(screen.getByLabelText('Contraseña'), {
    target: { value: 'Clave-S3gura-2026' },
  })
  fireEvent.change(screen.getByLabelText('Nombre de la profesional'), {
    target: { value: 'María' },
  })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('AdminProfesionales — listado', () => {
  it('lista los profesionales con nombre, usuario asociado y estado', async () => {
    mockear()
    renderSeccion()

    expect(await screen.findByText('María')).toBeTruthy()
    expect(screen.getByText('Brenda')).toBeTruthy()
    expect(screen.getByText('Usuario N° 10')).toBeTruthy()
    expect(screen.getByText('Sin vincular')).toBeTruthy()
    expect(screen.getByText('Activo')).toBeTruthy()
    expect(screen.getByText('Inactivo')).toBeTruthy()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/profesionales/'))
  })

  it('recorre todas las páginas de la respuesta paginada', async () => {
    api.get
      .mockResolvedValueOnce(
        paginado([MARIA], 'http://127.0.0.1:8000/api/profesionales/?page=2'),
      )
      .mockResolvedValueOnce(paginado([BRENDA]))
    renderSeccion()

    expect(await screen.findByText('María')).toBeTruthy()
    expect(await screen.findByText('Brenda')).toBeTruthy()
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/profesionales/?page=2',
    )
  })

  it('muestra el estado de carga inicial', () => {
    api.get.mockReturnValue(new Promise(() => {}))
    renderSeccion()

    expect(screen.getByText('Cargando profesionales…')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Nueva profesional' }).disabled).toBe(true)
  })

  it('muestra el estado vacío', async () => {
    mockear([])
    renderSeccion()

    expect(await screen.findByText('Sin profesionales cargados')).toBeTruthy()
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
      return Promise.resolve(paginado([MARIA]))
    })
    renderSeccion()

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()
    expect(screen.queryByText('Sin profesionales cargados')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('María')).toBeTruthy()
    await waitFor(() => expect(llamadas).toBe(2))
  })
})

describe('AdminProfesionales — creación', () => {
  it('crea una profesional con el endpoint combinado y recarga el listado', async () => {
    mockear([])
    api.post.mockResolvedValue({ id: 3, nombre: 'María', usuario: 11, is_active: true })
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Crear profesional' }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/api/profesionales/crear-con-usuario/', {
        nombre: 'María García',
        username: 'maria',
        email: 'maria@holynails.test',
        password: 'Clave-S3gura-2026',
        nombre_profesional: 'María',
      }),
    )
    // Una sola solicitud: no se crean cuenta y profesional por separado.
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Profesional creada correctamente.')).toBeTruthy()
    // El formulario se cierra y el listado se vuelve a cargar.
    expect(screen.queryByLabelText('Nombre de usuario')).toBeNull()
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('valida los campos obligatorios antes de enviar', async () => {
    mockear([])
    renderSeccion()

    await abrirFormularioCrear()
    fireEvent.click(screen.getByRole('button', { name: 'Crear profesional' }))

    expect(await screen.findByText('Completá todos los campos.')).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('muestra el error de validación del backend sin cerrar el formulario', async () => {
    mockear([])
    api.post.mockRejectedValue(new Error('Ya existe una cuenta con ese username.'))
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Crear profesional' }))

    expect(await screen.findByText('Ya existe una cuenta con ese username.')).toBeTruthy()
    expect(screen.getByLabelText('Nombre de usuario')).toBeTruthy()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('evita envíos duplicados mientras crea', async () => {
    mockear([])
    api.post.mockImplementation(() => new Promise(() => {}))
    renderSeccion()

    await abrirFormularioCrear()
    completarFormulario()
    fireEvent.click(screen.getByRole('button', { name: 'Crear profesional' }))

    const creando = await screen.findByRole('button', { name: /creando/i })
    expect(creando.disabled).toBe(true)

    fireEvent.click(creando)
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
  })
})

describe('AdminProfesionales — edición y estado', () => {
  it('edita el nombre de la profesional y recarga el listado', async () => {
    mockear([MARIA])
    api.patch.mockResolvedValue({})
    renderSeccion()

    expect(await screen.findByText('María')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Editar' }))

    const input = await screen.findByLabelText('Nombre de la profesional')
    expect(input.value).toBe('María')
    fireEvent.change(input, { target: { value: 'María García' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/profesionales/1/', {
        nombre: 'María García',
      }),
    )
    expect(await screen.findByText('Profesional actualizada correctamente.')).toBeTruthy()
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
  })

  it('desactiva una profesional solo tras confirmar', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear([MARIA])
    api.patch.mockResolvedValue({})
    renderSeccion()

    expect(await screen.findByText('María')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/profesionales/1/', {
        is_active: false,
      }),
    )
    expect(await screen.findByText('Profesional desactivada correctamente.')).toBeTruthy()
  })

  it('activa una profesional desactivada', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear([BRENDA])
    api.patch.mockResolvedValue({})
    renderSeccion()

    expect(await screen.findByText('Brenda')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Activar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/profesionales/2/', {
        is_active: true,
      }),
    )
  })

  it('no cambia el estado si se cancela la confirmación', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mockear([MARIA])
    renderSeccion()

    expect(await screen.findByText('María')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))

    expect(confirmar).toHaveBeenCalledTimes(1)
    expect(api.patch).not.toHaveBeenCalled()
    expect(screen.getByText('Activo')).toBeTruthy()
  })

  it('muestra el error del backend al cambiar el estado', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockear([MARIA])
    api.patch.mockRejectedValue(new Error('No tenés permiso para realizar esta acción.'))
    renderSeccion()

    expect(await screen.findByText('María')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Desactivar' }))

    expect(
      await screen.findByText('No tenés permiso para realizar esta acción.'),
    ).toBeTruthy()
    // El listado sigue intacto y sin recargar.
    expect(api.get).toHaveBeenCalledTimes(1)
  })
})

describe('AdminProfesionales — vincular cuenta existente (A3)', () => {
  const SIN_CUENTA = { id: 2, nombre: 'Brenda', usuario: null, is_active: true }
  const CUENTA = {
    id: 31,
    username: 'carla',
    nombre: 'Carla Gómez',
    email: 'carla@holynails.test',
    role: 'cliente',
    is_active: true,
  }

  // Profesionales y cuentas viven en endpoints distintos: se mockea por URL
  // (cuentas-disponibles usa URLs absolutas cuando pagina `next`).
  function mockearCuentas(cuentas = [CUENTA], profesionales = [SIN_CUENTA]) {
    api.get.mockImplementation((url) => {
      const u = String(url)
      if (u.includes('cuentas-disponibles')) {
        return Promise.resolve(paginado(cuentas))
      }
      return Promise.resolve(paginado(profesionales))
    })
  }

  it('asocia una cuenta existente a un profesional sin vínculo', async () => {
    mockearCuentas()
    api.patch.mockResolvedValue({})
    renderSeccion()

    fireEvent.click(await screen.findByRole('button', { name: 'Vincular cuenta' }))

    const select = await screen.findByLabelText('Cuenta de usuario')
    // La opción informa nombre, username, email y rol para distinguir cuentas.
    expect(screen.getByText(/Carla Gómez \(@carla\) · carla@holynails\.test · Cliente/)).toBeTruthy()

    fireEvent.change(select, { target: { value: '31' } })
    fireEvent.click(screen.getByRole('button', { name: 'Asociar' }))

    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/api/profesionales/2/', { usuario: 31 }),
    )
    expect(await screen.findByText('Cuenta asociada correctamente.')).toBeTruthy()
    // Tras asociar se cierra el panel y se recarga el listado.
    await waitFor(() =>
      expect(screen.queryByLabelText('Cuenta de usuario')).toBeNull(),
    )
  })

  it('no envía sin seleccionar una cuenta', async () => {
    mockearCuentas()
    renderSeccion()

    fireEvent.click(await screen.findByRole('button', { name: 'Vincular cuenta' }))
    await screen.findByLabelText('Cuenta de usuario')
    fireEvent.click(screen.getByRole('button', { name: 'Asociar' }))

    expect(await screen.findByText('Seleccioná una cuenta para asociar.')).toBeTruthy()
    expect(api.patch).not.toHaveBeenCalled()
  })

  it('muestra el error del backend si la cuenta ya está vinculada', async () => {
    mockearCuentas()
    api.patch.mockRejectedValue(new Error('Ese usuario ya está vinculado a otra profesional.'))
    renderSeccion()

    fireEvent.click(await screen.findByRole('button', { name: 'Vincular cuenta' }))
    fireEvent.change(await screen.findByLabelText('Cuenta de usuario'), {
      target: { value: '31' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Asociar' }))

    expect(
      await screen.findByText('Ese usuario ya está vinculado a otra profesional.'),
    ).toBeTruthy()
    // El panel permanece abierto para reintentar.
    expect(screen.getByRole('button', { name: 'Asociar' })).toBeTruthy()
  })

  it('no ofrece vincular a un profesional que ya tiene cuenta', async () => {
    mockearCuentas([], [MARIA]) // MARIA tiene usuario: 10
    renderSeccion()

    expect(await screen.findByText('María')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Vincular cuenta' })).toBeNull()
  })

  it('sin cuentas disponibles muestra el estado vacío', async () => {
    mockearCuentas([], [SIN_CUENTA])
    renderSeccion()

    fireEvent.click(await screen.findByRole('button', { name: 'Vincular cuenta' }))

    expect(await screen.findByText('No hay cuentas disponibles para vincular.')).toBeTruthy()
    expect(screen.queryByLabelText('Cuenta de usuario')).toBeNull()
    expect(api.patch).not.toHaveBeenCalled()
  })

  it('muestra el error de carga de cuentas y permite reintentar', async () => {
    let llamadas = 0
    api.get.mockImplementation((url) => {
      const u = String(url)
      if (u.includes('cuentas-disponibles')) {
        llamadas += 1
        if (llamadas === 1) {
          return Promise.reject(new Error('No se pudo conectar con el servidor. Verificá tu conexión.'))
        }
        return Promise.resolve(paginado([CUENTA]))
      }
      return Promise.resolve(paginado([SIN_CUENTA]))
    })
    renderSeccion()

    fireEvent.click(await screen.findByRole('button', { name: 'Vincular cuenta' }))

    expect(
      await screen.findByText('No se pudo conectar con el servidor. Verificá tu conexión.'),
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByLabelText('Cuenta de usuario')).toBeTruthy()
    await waitFor(() => expect(llamadas).toBe(2))
  })
})

describe('AdminProfesionales — acceso restringido', () => {
  it('no muestra la sección a un usuario que no es admin', async () => {
    mockear()
    renderSeccion(USER_CLIENTE)

    expect(await screen.findByText(/acceso restringido/i)).toBeTruthy()
    expect(screen.queryByRole('heading', { name: /profesionales/i })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Nueva profesional' })).toBeNull()
    expect(api.get).not.toHaveBeenCalled()
  })
})
