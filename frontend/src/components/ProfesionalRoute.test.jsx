// @vitest-environment jsdom
// Guard de la ruta /mi-agenda: profesional autenticado → Outlet (vista hija);
// cliente autenticado → /denegado; personal con Profesional inactivo →
// /denegado (nunca /login: sigue autenticado); ADMIN sin Profesional →
// /denegado y ADMIN con Profesional → agenda (B10.0.2); sin sesión →
// /login; isLoading → no renderiza nada (ni contenido ni
// redirecciones).
// api.js se mockea para controlar la restauración de la sesión.
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import { api, getAccessToken } from '../services/api.js'
import ProfesionalRoute from './ProfesionalRoute.jsx'

vi.mock('../services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn() },
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthCleared: vi.fn(() => vi.fn()),
}))

const USER_PROFESIONAL = {
  id: 10,
  nombre: 'María García',
  email: 'maria@holynails.test',
  username: 'maria_profesional',
  role: 'personal',
  es_profesional: true,
  profesional_id: 10,
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

// PERSONAL con Profesional inactivo (caso detectado en B9): la sesión es
// válida y el rol sigue siendo personal, pero no hay vínculo activo.
const USER_PERSONAL_INACTIVO = {
  id: 30,
  nombre: 'Personal Inactivo',
  email: 'inactivo@holynails.test',
  username: 'personal_inactivo',
  role: 'personal',
  es_profesional: false,
  profesional_id: null,
}

// ADMIN sin Profesional asociado (B10.0.2): no tiene agenda propia.
const USER_ADMIN_SIN_VINCULO = {
  id: 40,
  nombre: 'Admin Uno',
  email: 'admin@holynails.test',
  username: 'admin1',
  role: 'admin',
  es_profesional: false,
  profesional_id: null,
}

// ADMIN con Profesional asociado (B10.0.2): accede a su agenda.
const USER_ADMIN_VINCULADO = {
  id: 41,
  nombre: 'Admin Dos',
  email: 'admin2@holynails.test',
  username: 'admin2',
  role: 'admin',
  es_profesional: true,
  profesional_id: 41,
}

function rutas() {
  return (
    <Routes>
      <Route element={<ProfesionalRoute />}>
        <Route path="/mi-agenda" element={<div>agenda-contenido</div>} />
      </Route>
      <Route path="/login" element={<div>login-contenido</div>} />
      <Route path="/denegado" element={<div>denegado-contenido</div>} />
    </Routes>
  )
}

// Sin initialUsuario, AuthProvider restaura la sesión vía api.get (mockeada):
// getAccessToken con token + api.get pendiente => isLoading permanece en true.
function renderGuard(usuario) {
  const auth =
    usuario === undefined ? (
      <AuthProvider>{rutas()}</AuthProvider>
    ) : (
      <AuthProvider initialUsuario={usuario}>{rutas()}</AuthProvider>
    )
  return render(<MemoryRouter initialEntries={['/mi-agenda']}>{auth}</MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  getAccessToken.mockReturnValue(null)
  api.get.mockReset()
})

afterEach(cleanup)

describe('ProfesionalRoute', () => {
  it('permite el acceso a un usuario profesional autenticado', () => {
    renderGuard(USER_PROFESIONAL)

    expect(screen.getByText('agenda-contenido')).toBeTruthy()
    expect(screen.queryByText('denegado-contenido')).toBeNull()
    expect(screen.queryByText('login-contenido')).toBeNull()
  })

  it('permite el acceso a un ADMIN con Profesional asociado (B10.0.2)', () => {
    renderGuard(USER_ADMIN_VINCULADO)

    expect(screen.getByText('agenda-contenido')).toBeTruthy()
    expect(screen.queryByText('denegado-contenido')).toBeNull()
    expect(screen.queryByText('login-contenido')).toBeNull()
  })

  it('redirige a /denegado a un ADMIN sin Profesional asociado (B10.0.2)', () => {
    renderGuard(USER_ADMIN_SIN_VINCULO)

    expect(screen.getByText('denegado-contenido')).toBeTruthy()
    expect(screen.queryByText('agenda-contenido')).toBeNull()
    expect(screen.queryByText('login-contenido')).toBeNull()
  })

  it('redirige a /denegado a un cliente autenticado que no es profesional', () => {
    renderGuard(USER_CLIENTE)

    expect(screen.getByText('denegado-contenido')).toBeTruthy()
    expect(screen.queryByText('agenda-contenido')).toBeNull()
    expect(screen.queryByText('login-contenido')).toBeNull()
  })

  it('redirige a /denegado (no a /login) al personal con Profesional inactivo', () => {
    // No confundir Profesional inactivo con usuario no autenticado: la
    // sesión sigue viva, el destino es /denegado y /mi-agenda queda
    // inaccesible sin bucle (el destino de /denegado es /perfil).
    renderGuard(USER_PERSONAL_INACTIVO)

    expect(screen.getByText('denegado-contenido')).toBeTruthy()
    expect(screen.queryByText('agenda-contenido')).toBeNull()
    expect(screen.queryByText('login-contenido')).toBeNull()
  })

  it('redirige a /login cuando no hay sesión iniciada', async () => {
    renderGuard(undefined)

    expect(await screen.findByText('login-contenido')).toBeTruthy()
    expect(screen.queryByText('agenda-contenido')).toBeNull()
  })

  it('no renderiza nada mientras la sesión se está restaurando', () => {
    getAccessToken.mockReturnValue('token-vigente')
    // La restauración nunca termina: isLoading sigue en true.
    api.get.mockReturnValue(new Promise(() => {}))
    renderGuard(undefined)

    expect(screen.queryByText('agenda-contenido')).toBeNull()
    expect(screen.queryByText('login-contenido')).toBeNull()
    expect(screen.queryByText('denegado-contenido')).toBeNull()
  })
})
