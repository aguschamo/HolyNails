// @vitest-environment jsdom
// Login: destino por rol tras autenticar (B9). Patrón de
// AuthContext.test.jsx: fetch mockeado por ruta, módulos frescos por test
// (vi.resetModules) y localStorage de jsdom limpio. Las rutas destino se
// resuelven con marcadores en MemoryRouter.
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function jsonResponse(status, body) {
  const text = body === undefined ? '' : JSON.stringify(body)
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
    json: async () => body,
  }
}

const PROFILE_PERSONAL = {
  id: 10,
  username: 'maria',
  email: 'maria@holy.test',
  nombre: 'María García',
  role: 'PERSONAL',
  es_profesional: true,
  profesional_id: 7,
}

const PROFILE_CLIENTE = {
  id: 20,
  username: 'cliente1',
  email: 'cliente1@holy.test',
  nombre: 'Cliente Uno',
  role: 'CLIENTE',
  es_profesional: false,
  profesional_id: null,
}

const PROFILE_ADMIN = {
  id: 30,
  username: 'admin1',
  email: 'admin@holy.test',
  nombre: 'Admin Uno',
  role: 'ADMIN',
  es_profesional: false,
  profesional_id: null,
}

describe('Login — redirect por rol', () => {
  let fetchMock

  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    fetchMock = vi.fn()
    globalThis.fetch = fetchMock
  })

  afterEach(() => {
    cleanup()
  })

  function routeFetch(profile) {
    fetchMock.mockImplementation(async (url, opts = {}) => {
      const method = (opts.method || 'GET').toUpperCase()
      if (String(url).endsWith('/api/auth/login/') && method === 'POST') {
        return jsonResponse(200, { access: 'a1', refresh: 'r1' })
      }
      if (String(url).endsWith('/api/auth/profile/') && method === 'GET') {
        return jsonResponse(200, profile)
      }
      throw new Error(`fetch no mockeado: ${method} ${url}`)
    })
  }

  async function mountLogin(initialEntries, profile) {
    routeFetch(profile)
    const { AuthProvider } = await import('../context/AuthContext.jsx')
    const { default: Login } = await import('./Login.jsx')

    return render(
      <MemoryRouter initialEntries={initialEntries}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/mi-agenda" element={<div>destino-mi-agenda</div>} />
            <Route path="/admin" element={<div>destino-admin</div>} />
            <Route path="/admin/turnos" element={<div>destino-admin-turnos</div>} />
            <Route path="/perfil" element={<div>destino-perfil</div>} />
            <Route path="/agendar" element={<div>destino-agendar</div>} />
            <Route path="/" element={<div>destino-home</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )
  }

  async function iniciarSesion() {
    fireEvent.change(screen.getByLabelText('Correo electrónico'), {
      target: { value: 'maria@holy.test' },
    })
    fireEvent.change(screen.getByLabelText('Contraseña'), {
      target: { value: 'Passw0rd-123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar sesión' }))
  }

  it('un usuario personal sin origen cae en /mi-agenda', async () => {
    await mountLogin(['/login'], PROFILE_PERSONAL)
    await iniciarSesion()

    expect(await screen.findByText('destino-mi-agenda')).toBeTruthy()
    expect(screen.queryByText('destino-home')).toBeNull()
    expect(screen.queryByText('destino-perfil')).toBeNull()
  })

  it('un usuario personal con origen fuera de su área no vuelve al origen', async () => {
    // /perfil es ruta de cliente: el destino es /mi-agenda, no el origen.
    await mountLogin(
      [{ pathname: '/login', state: { from: { pathname: '/perfil' } } }],
      PROFILE_PERSONAL,
    )
    await iniciarSesion()

    expect(await screen.findByText('destino-mi-agenda')).toBeTruthy()
    expect(screen.queryByText('destino-perfil')).toBeNull()
  })

  it('un cliente conserva su origen de reservas (/agendar)', async () => {
    await mountLogin(
      [{ pathname: '/login', state: { from: { pathname: '/agendar' } } }],
      PROFILE_CLIENTE,
    )
    await iniciarSesion()

    expect(await screen.findByText('destino-agendar')).toBeTruthy()
  })

  it('un cliente sin origen cae en la home', async () => {
    await mountLogin(['/login'], PROFILE_CLIENTE)
    await iniciarSesion()

    expect(await screen.findByText('destino-home')).toBeTruthy()
  })

  it('un administrador conserva el origen /admin', async () => {
    await mountLogin(
      [{ pathname: '/login', state: { from: { pathname: '/admin' } } }],
      PROFILE_ADMIN,
    )
    await iniciarSesion()

    expect(await screen.findByText('destino-admin')).toBeTruthy()
  })

  it('un administrador conserva el origen /agendar (B10.0.2)', async () => {
    await mountLogin(
      [{ pathname: '/login', state: { from: { pathname: '/agendar' } } }],
      PROFILE_ADMIN,
    )
    await iniciarSesion()

    expect(await screen.findByText('destino-agendar')).toBeTruthy()
    expect(screen.queryByText('destino-home')).toBeNull()
  })

  it('un administrador conserva el origen de una subruta del panel (B10.4)', async () => {
    await mountLogin(
      [{ pathname: '/login', state: { from: { pathname: '/admin/turnos' } } }],
      PROFILE_ADMIN,
    )
    await iniciarSesion()

    expect(await screen.findByText('destino-admin-turnos')).toBeTruthy()
    expect(screen.queryByText('destino-home')).toBeNull()
  })

  it('un administrador sin destino previo cae en la home', async () => {
    await mountLogin(['/login'], PROFILE_ADMIN)
    await iniciarSesion()

    expect(await screen.findByText('destino-home')).toBeTruthy()
    expect(screen.queryByText('destino-admin')).toBeNull()
  })
})
