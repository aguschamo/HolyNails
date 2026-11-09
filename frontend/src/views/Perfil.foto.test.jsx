// @vitest-environment jsdom
// B11.2 — foto de perfil persistente en Perfil.jsx:
// - muestra la foto guardada en el backend al cargar (no una preview);
// - selección con vista previa local y cancelación;
// - subida en multipart con FormData a POST /api/auth/profile/foto/;
// - estado «Subiendo…» y anti-duplicados;
// - actualización del contexto tras subir/eliminar;
// - conservación de la foto anterior y errores de validación;
// - eliminación de la foto propia;
// - mismo comportamiento para los tres roles.
//
// Patrón de Perfil.test.jsx: api.js mockeado, AuthProvider con
// initialUsuario (sin llamadas de red al montar) y URL.createObjectURL
// stubbeado (jsdom no lo implementa).
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

const FOTO_GUARDADA = 'http://127.0.0.1:8000/media/perfiles/user_20_abc.jpg'

function usuarioDe(rol, overrides = {}) {
  return {
    id: 20,
    nombre: 'Carla Gómez',
    email: 'carla@holynails.test',
    username: 'carla',
    telefono: '11 5555-4321',
    photo: FOTO_GUARDADA,
    role: rol,
    es_profesional: false,
    profesional_id: null,
    ...overrides,
  }
}

// Respuesta real del backend tras subir/eliminar: el perfil con foto_url.
function perfilRespuesta(fotoUrl) {
  return {
    id: 20,
    username: 'carla',
    email: 'carla@holynails.test',
    nombre: 'Carla Gómez',
    telefono: '11 5555-4321',
    foto_url: fotoUrl,
    role: 'CLIENTE',
    es_profesional: false,
    profesional_id: null,
  }
}

function archivoImagen(nombre = 'selfie.jpg', tipo = 'image/jpeg', bytes = 1024) {
  return new File([new Uint8Array(bytes)], nombre, { type: tipo })
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

function inputFoto() {
  return screen.getByLabelText('Elegir imagen')
}

function avatar() {
  return screen.getByAltText('Foto de perfil de Carla Gómez')
}

let contadorBlobs = 0

beforeEach(() => {
  contadorBlobs = 0
  // jsdom no implementa object URLs: se stubbean para poder verificar la
  // limpieza (revokeObjectURL) de las vistas previas.
  URL.createObjectURL = vi.fn(() => `blob:preview-${++contadorBlobs}`)
  URL.revokeObjectURL = vi.fn()
  api.post.mockResolvedValue(perfilRespuesta('http://127.0.0.1:8000/media/perfiles/nueva.jpg'))
  api.delete.mockResolvedValue(perfilRespuesta(null))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Perfil — foto persistida al cargar', () => {
  it('muestra la foto guardada en el backend y la opción de eliminarla', () => {
    renderPerfil(usuarioDe('cliente'))

    expect(avatar().getAttribute('src')).toBe(FOTO_GUARDADA)
    expect(screen.getByRole('button', { name: 'Eliminar foto' })).toBeTruthy()
    // No hay vista previa pendiente: no se ofrece «Subir foto».
    expect(screen.queryByRole('button', { name: 'Subir foto' })).toBeNull()
  })

  it('sin foto guardada muestra la inicial y sin botón de eliminar', () => {
    renderPerfil(usuarioDe('cliente', { photo: null }))

    expect(screen.queryByAltText('Foto de perfil de Carla Gómez')).toBeNull()
    expect(screen.getByLabelText('Foto de perfil de Carla Gómez')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Eliminar foto' })).toBeNull()
    expect(inputFoto().type).toBe('file')
  })

  it.each(['cliente', 'personal', 'admin'])(
    'el rol %s ve su foto persistida y las acciones disponibles',
    (rol) => {
      renderPerfil(usuarioDe(rol))

      expect(avatar().getAttribute('src')).toBe(FOTO_GUARDADA)
      expect(screen.getByRole('button', { name: 'Eliminar foto' })).toBeTruthy()
    },
  )
})

describe('Perfil — selección y vista previa', () => {
  it('seleccionar una imagen muestra su vista previa antes de subirla', () => {
    renderPerfil(usuarioDe('cliente'))

    fireEvent.change(inputFoto(), { target: { files: [archivoImagen()] } })

    expect(avatar().getAttribute('src')).toBe('blob:preview-1')
    expect(screen.getByText(/Vista previa: todavía no se guardó/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Subir foto' })).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()  // nada se subió todavía
  })

  it('cancelar la selección descarta la vista previa y libera el object URL', () => {
    renderPerfil(usuarioDe('cliente'))

    fireEvent.change(inputFoto(), { target: { files: [archivoImagen()] } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview-1')
    // Vuelve a la foto persistida en el backend.
    expect(avatar().getAttribute('src')).toBe(FOTO_GUARDADA)
    expect(screen.queryByRole('button', { name: 'Subir foto' })).toBeNull()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('rechaza localmente un formato no admitido sin llamar a la API', () => {
    renderPerfil(usuarioDe('cliente'))

    fireEvent.change(inputFoto(), {
      target: { files: [archivoImagen('animada.gif', 'image/gif')] },
    })

    expect(screen.getByRole('alert').textContent).toContain('Formato no admitido')
    expect(screen.queryByRole('button', { name: 'Subir foto' })).toBeNull()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('rechaza localmente una imagen de más de 2 MB sin llamar a la API', () => {
    renderPerfil(usuarioDe('cliente'))

    fireEvent.change(inputFoto(), {
      target: { files: [archivoImagen('grande.jpg', 'image/jpeg', 3 * 1024 * 1024)] },
    })

    expect(screen.getByRole('alert').textContent).toContain('2 MB')
    expect(screen.queryByRole('button', { name: 'Subir foto' })).toBeNull()
    expect(api.post).not.toHaveBeenCalled()
  })
})

describe('Perfil — subida de la foto', () => {
  it('sube la imagen en FormData a /api/auth/profile/foto/ y actualiza el contexto', async () => {
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputFoto(), { target: { files: [archivoImagen()] } })

    fireEvent.click(screen.getByRole('button', { name: 'Subir foto' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [ruta, cuerpo] = api.post.mock.calls[0]
    expect(ruta).toBe('/api/auth/profile/foto/')
    expect(cuerpo).toBeInstanceOf(FormData)
    expect(cuerpo.get('foto')).toBeInstanceOf(File)
    expect(cuerpo.get('foto').name).toBe('selfie.jpg')

    // Éxito: mensaje, foto persistida visible (contexto actualizado) y
    // vista previa local liberada.
    expect((await screen.findByRole('status')).textContent).toBe(
      'Foto actualizada correctamente.',
    )
    expect(avatar().getAttribute('src')).toBe(
      'http://127.0.0.1:8000/media/perfiles/nueva.jpg',
    )
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview-1')
    expect(screen.queryByRole('button', { name: 'Subir foto' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Eliminar foto' })).toBeTruthy()
  })

  it('muestra «Subiendo…» y evita subidas duplicadas', async () => {
    let resolver
    api.post.mockImplementation(
      () => new Promise((resolve) => { resolver = resolve }),
    )
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputFoto(), { target: { files: [archivoImagen()] } })

    fireEvent.click(screen.getByRole('button', { name: 'Subir foto' }))
    expect(await screen.findByRole('button', { name: 'Subiendo…' })).toBeTruthy()

    // Segundo clic con la petición en vuelo.
    fireEvent.click(screen.getByRole('button', { name: 'Subiendo…' }))
    expect(api.post).toHaveBeenCalledTimes(1)

    resolver(perfilRespuesta('http://127.0.0.1:8000/media/perfiles/nueva.jpg'))
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Subiendo…' })).toBeNull(),
    )
  })

  it('conserva la foto anterior y muestra el error si la subida falla', async () => {
    api.post.mockRejectedValue(new Error('Error del servidor. Intentá más tarde.'))
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputFoto(), { target: { files: [archivoImagen()] } })

    fireEvent.click(screen.getByRole('button', { name: 'Subir foto' }))

    expect((await screen.findByRole('alert')).textContent).toContain(
      'Error del servidor',
    )
    // La foto persistida no cambió y la vista previa queda para reintentar.
    expect(avatar().getAttribute('src')).toBe('blob:preview-1')
    expect(screen.getByRole('button', { name: 'Subir foto' })).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('muestra el error de validación devuelto por la API', async () => {
    api.post.mockRejectedValue(
      new Error('La imagen no puede superar los 2 MB.'),
    )
    renderPerfil(usuarioDe('cliente'))
    fireEvent.change(inputFoto(), { target: { files: [archivoImagen()] } })

    fireEvent.click(screen.getByRole('button', { name: 'Subir foto' }))

    expect((await screen.findByRole('alert')).textContent).toContain('2 MB')
    expect(api.delete).not.toHaveBeenCalled()
  })

  it.each(['cliente', 'personal', 'admin'])(
    'el rol %s sube su foto con éxito',
    async (rol) => {
      renderPerfil(usuarioDe(rol, { photo: null }))
      fireEvent.change(inputFoto(), { target: { files: [archivoImagen()] } })

      fireEvent.click(screen.getByRole('button', { name: 'Subir foto' }))

      await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
      expect(
        await screen.findByRole('status'),
      ).toBeTruthy()
      expect(avatar().getAttribute('src')).toBe(
        'http://127.0.0.1:8000/media/perfiles/nueva.jpg',
      )
    },
  )
})

describe('Perfil — eliminación de la foto', () => {
  it('elimina la foto propia con DELETE y limpia el contexto', async () => {
    renderPerfil(usuarioDe('cliente'))

    fireEvent.click(screen.getByRole('button', { name: 'Eliminar foto' }))

    await waitFor(() => expect(api.delete).toHaveBeenCalledTimes(1))
    expect(api.delete.mock.calls[0][0]).toBe('/api/auth/profile/foto/')

    expect((await screen.findByRole('status')).textContent).toBe('Foto eliminada.')
    // Sin foto: vuelve a la inicial y desaparece el botón de eliminar.
    expect(screen.queryByAltText('Foto de perfil de Carla Gómez')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Eliminar foto' })).toBeNull()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('si la eliminación falla, la foto se conserva y se muestra el error', async () => {
    api.delete.mockRejectedValue(new Error('No se pudo eliminar la foto.'))
    renderPerfil(usuarioDe('cliente'))

    fireEvent.click(screen.getByRole('button', { name: 'Eliminar foto' }))

    expect((await screen.findByRole('alert')).textContent).toContain(
      'No se pudo eliminar la foto.',
    )
    expect(avatar().getAttribute('src')).toBe(FOTO_GUARDADA)
    expect(screen.getByRole('button', { name: 'Eliminar foto' })).toBeTruthy()
  })
})
