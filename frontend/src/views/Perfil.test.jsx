// @vitest-environment jsdom
// B11.1 — Perfil editable: precarga desde el contexto, persistencia con
// PATCH /api/auth/profile/, validaciones, estado de guardado y campos
// protegidos (email y rol no editables).
//
// Patrón de Navbar.test.jsx: api.js mockeado y AuthProvider con
// initialUsuario → no hay llamadas de red al montar (restore se corta en
// initialUsuario). actualizarPerfil (AuthContext) usa el mismo api.patch
// mockeado, así que la actualización del contexto se observa en el DOM.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import Perfil from './Perfil.jsx'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthCleared: vi.fn(() => vi.fn()),
}))

function usuarioDe(rol, overrides = {}) {
  return {
    id: 20,
    nombre: 'Carla Gómez',
    email: 'carla@holynails.test',
    username: 'carla',
    telefono: '11 5555-4321',
    role: rol,
    es_profesional: false,
    profesional_id: null,
    ...overrides,
  }
}

// Respuesta real del backend tras un PATCH: el perfil completo.
function perfilRespuesta(overrides = {}) {
  return {
    id: 20,
    username: 'carla',
    email: 'carla@holynails.test',
    nombre: 'Carla Gómez',
    telefono: '11 5555-4321',
    role: 'CLIENTE',
    es_profesional: false,
    profesional_id: null,
    ...overrides,
  }
}

function renderPerfil(usuario) {
  return render(
    <MemoryRouter>
      <AuthProvider initialUsuario={usuario}>
        <Perfil />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function inputNombre() {
  return screen.getByLabelText('Nombre y apellido')
}

function inputTelefono() {
  return screen.getByLabelText('Teléfono de contacto')
}

async function guardar() {
  fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
}

beforeEach(() => {
  api.patch.mockResolvedValue(perfilRespuesta())
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Perfil — precarga y accesibilidad por rol', () => {
  it('precarga el nombre y el teléfono actuales del contexto', () => {
    renderPerfil(usuarioDe('cliente'))

    expect(inputNombre().value).toBe('Carla Gómez')
    expect(inputTelefono().value).toBe('11 5555-4321')
  })

  it.each(['cliente', 'personal', 'admin'])(
    'el rol %s ve el formulario editable',
    (rol) => {
      renderPerfil(usuarioDe(rol))

      expect(inputNombre().disabled).toBe(false)
      expect(inputTelefono().disabled).toBe(false)
      expect(screen.getByRole('button', { name: 'Guardar cambios' })).toBeTruthy()
      // Email y rol se muestran como información, no como campos editables.
      expect(screen.getByText('carla@holynails.test')).toBeTruthy()
      expect(
        screen.getByText(
          { cliente: 'Clienta', personal: 'Personal', admin: 'Administración' }[rol],
        ),
      ).toBeTruthy()
    },
  )

  it('sólo expone dos campos de texto editables (nombre y teléfono)', () => {
    renderPerfil(usuarioDe('cliente'))

    const cajas = screen.getAllByRole('textbox')
    expect(cajas).toHaveLength(2)
    expect(cajas.every((c) => !c.disabled)).toBe(true)
    // No hay inputs para email ni rol: no se pueden modificar acá.
    expect(screen.queryByDisplayValue('carla@holynails.test')).toBeNull()
  })
})

describe('Perfil — persistencia con la API', () => {
  it('guarda exactamente nombre y teléfono (sin role, email ni username)', async () => {
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputNombre(), { target: { value: 'Carla Gomez' } })
    fireEvent.change(inputTelefono(), { target: { value: '011 4444 0000' } })

    await guardar()

    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1))
    expect(api.patch).toHaveBeenCalledWith('/api/auth/profile/', {
      nombre: 'Carla Gomez',
      telefono: '011 4444 0000',
    })
    // Payload exacto: ningún campo protegido viaja en la petición.
    expect(Object.keys(api.patch.mock.calls[0][1]).sort()).toEqual([
      'nombre',
      'telefono',
    ])
  })

  it('tras guardar, el contexto refresca los datos visibles', async () => {
    api.patch.mockResolvedValue(
      perfilRespuesta({ nombre: 'Carla Actualizada', telefono: '11 9999-0000' }),
    )
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputNombre(), { target: { value: 'Carla Actualizada' } })
    fireEvent.change(inputTelefono(), { target: { value: '11 9999-0000' } })

    await guardar()

    expect(
      await screen.findByRole('heading', { name: 'Carla Actualizada' }),
    ).toBeTruthy()
    expect((await screen.findByRole('status')).textContent).toBe('Perfil actualizado correctamente.')
    expect(inputNombre().value).toBe('Carla Actualizada')
    expect(inputTelefono().value).toBe('11 9999-0000')
  })

  it('muestra «Guardando…» y no duplica el envío ante doble clic', async () => {
    let resolver
    api.patch.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolver = resolve
        }),
    )
    renderPerfil(usuarioDe('cliente'))

    await guardar()
    expect(await screen.findByRole('button', { name: 'Guardando…' })).toBeTruthy()
    expect(inputNombre().disabled).toBe(true)

    // Segundo clic mientras la petición sigue en vuelo.
    fireEvent.click(screen.getByRole('button', { name: 'Guardando…' }))
    expect(api.patch).toHaveBeenCalledTimes(1)

    resolver(perfilRespuesta())
    expect(
      await screen.findByRole('button', { name: 'Guardar cambios' }),
    ).toBeTruthy()
  })
})

describe('Perfil — validaciones de campos', () => {
  it('un nombre vacío muestra error y no llama a la API', async () => {
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputNombre(), { target: { value: '   ' } })

    await guardar()

    expect((await screen.findByRole('alert')).textContent).toContain(
      'Completá tu nombre y apellido.',
    )
    expect(api.patch).not.toHaveBeenCalled()
  })

  it('un teléfono con letras muestra error y no llama a la API', async () => {
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputTelefono(), { target: { value: 'llamar tarde' } })

    await guardar()

    expect((await screen.findByRole('alert')).textContent).toContain(
      'El teléfono sólo puede contener números, espacios y los símbolos + - ( ) .',
    )
    expect(api.patch).not.toHaveBeenCalled()
    // El valor escrito se conserva (no se pierde el cambio).
    expect(inputTelefono().value).toBe('llamar tarde')
  })

  it('un teléfono de más de 30 caracteres muestra error y no llama a la API', async () => {
    renderPerfil(usuarioDe('cliente'))
    const largo = '1'.repeat(31)
    fireEvent.change(inputTelefono(), { target: { value: largo } })

    await guardar()

    expect((await screen.findByRole('alert')).textContent).toContain(
      'El teléfono no puede superar los 30 caracteres.',
    )
    expect(api.patch).not.toHaveBeenCalled()
    expect(inputTelefono().value).toBe(largo)
  })
})

describe('Perfil — errores de la API', () => {
  it('muestra el mensaje de error y conserva los campos editados', async () => {
    api.patch.mockRejectedValue(new Error('El nombre ya está en uso.'))
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputNombre(), { target: { value: 'Nombre Nuevo' } })
    fireEvent.change(inputTelefono(), { target: { value: '1122334455' } })

    await guardar()

    expect((await screen.findByRole('alert')).textContent).toContain('El nombre ya está en uso.')
    // No se pierden los cambios ni se resetea el formulario.
    expect(inputNombre().value).toBe('Nombre Nuevo')
    expect(inputTelefono().value).toBe('1122334455')
    expect(screen.queryByRole('status')).toBeNull()
    // El botón vuelve a habilitarse para reintentar.
    expect(screen.getByRole('button', { name: 'Guardar cambios' }).disabled).toBe(false)
  })

  it('un error limpio los mensajes previos al reintentar', async () => {
    api.patch.mockRejectedValue(new Error('No se pudo guardar el perfil.'))
    renderPerfil(usuarioDe('cliente'))

    await guardar()
    expect(await screen.findByRole('alert')).toBeTruthy()

    api.patch.mockResolvedValue(perfilRespuesta())
    await guardar()

    expect(await screen.findByRole('status')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('Perfil — foto de perfil (B11.1)', () => {
  // B11.2: el texto «La vista previa es local y no se guarda en tu cuenta»
  // quedó objetivamente obsoleto: la foto ahora SÍ se persiste en el
  // backend. El test pasa a cubrir el nuevo contrato (input + límites).
  it('ofrece elegir una imagen con el límite y los formatos admitidos', () => {
    renderPerfil(usuarioDe('cliente'))

    const input = screen.getByLabelText('Elegir imagen')
    expect(input.type).toBe('file')
    expect(screen.getByText(/JPEG, PNG o WebP de hasta 2 MB/)).toBeTruthy()
    // Sin foto guardada no hay botón de eliminar.
    expect(screen.queryByRole('button', { name: 'Eliminar foto' })).toBeNull()
  })
})
