// @vitest-environment jsdom
// normalizeUser (privada de AuthContext.jsx) conserva es_profesional y
// profesional_id: se ejerce a través de los flujos públicos que la usan
// (login y restore de sesión) con fetch mockeado, replicando el patrón de
// AuthContext.test.jsx (módulos frescos por test vía vi.resetModules).
import { act, cleanup, render } from '@testing-library/react'
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

// Profile con profesional activo vinculado (B9: el vínculo define PERSONAL)
const PROFILE_PROFESIONAL = {
  id: 10,
  username: 'maria',
  email: 'maria@holynails.test',
  nombre: 'María García',
  role: 'PERSONAL',
  es_profesional: true,
  profesional_id: 7,
}

// Profile de usuario sin vínculo profesional
const PROFILE_CLIENTE = {
  id: 20,
  username: 'cliente1',
  email: 'cliente1@holynails.test',
  nombre: 'Cliente Uno',
  role: 'CLIENTE',
  es_profesional: false,
  profesional_id: null,
}

// Profile sin los campos (respuesta de un backend anterior o incompleto)
const PROFILE_SIN_CAMPOS = {
  id: 21,
  username: 'sin_campos',
  email: 'sin_campos@holynails.test',
  nombre: 'Sin Campos',
  role: 'CLIENTE',
}

describe('AuthContext — normalizeUser: campos de profesional', () => {
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

  function routeFetch(routes) {
    fetchMock.mockImplementation(async (url, opts = {}) => {
      const method = (opts.method || 'GET').toUpperCase()
      for (const r of routes) {
        if (String(url).endsWith(r.path) && method === r.method) {
          return r.respond()
        }
      }
      throw new Error(`fetch no mockeado: ${method} ${url}`)
    })
  }

  async function mountAuth() {
    const { AuthProvider, useAuth } = await import('./AuthContext.jsx')
    let ctx = null
    function Probe() {
      ctx = useAuth()
      return null
    }
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    return { getCtx: () => ctx }
  }

  it('login conserva es_profesional=true y profesional_id del profile', async () => {
    routeFetch([
      { method: 'POST', path: '/api/auth/login/', respond: () => jsonResponse(200, { access: 'a1', refresh: 'r1' }) },
      { method: 'GET', path: '/api/auth/profile/', respond: () => jsonResponse(200, PROFILE_PROFESIONAL) },
    ])
    const { getCtx } = await mountAuth()

    await act(async () => {
      await getCtx().login('maria@holynails.test', 'Passw0rd-123')
    })

    expect(getCtx().usuario.es_profesional).toBe(true)
    expect(getCtx().usuario.profesional_id).toBe(7)
  })

  it('login conserva es_profesional=false y profesional_id=null', async () => {
    routeFetch([
      { method: 'POST', path: '/api/auth/login/', respond: () => jsonResponse(200, { access: 'a1', refresh: 'r1' }) },
      { method: 'GET', path: '/api/auth/profile/', respond: () => jsonResponse(200, PROFILE_CLIENTE) },
    ])
    const { getCtx } = await mountAuth()

    await act(async () => {
      await getCtx().login('cliente1@holynails.test', 'Passw0rd-123')
    })

    expect(getCtx().usuario.es_profesional).toBe(false)
    expect(getCtx().usuario.profesional_id).toBeNull()
  })

  it('profile sin los campos aplica los defaults: false y null', async () => {
    routeFetch([
      { method: 'POST', path: '/api/auth/login/', respond: () => jsonResponse(200, { access: 'a1', refresh: 'r1' }) },
      { method: 'GET', path: '/api/auth/profile/', respond: () => jsonResponse(200, PROFILE_SIN_CAMPOS) },
    ])
    const { getCtx } = await mountAuth()

    await act(async () => {
      await getCtx().login('sin_campos@holynails.test', 'Passw0rd-123')
    })

    expect(getCtx().usuario.es_profesional).toBe(false)
    expect(getCtx().usuario.profesional_id).toBeNull()
  })

  it('restore de sesión conserva los campos de profesional', async () => {
    localStorage.setItem('hn_access', 'old-access')
    routeFetch([
      { method: 'GET', path: '/api/auth/profile/', respond: () => jsonResponse(200, PROFILE_PROFESIONAL) },
    ])
    const { getCtx } = await mountAuth()

    // Deja resolver la cadena de restore() y alinea el render pendiente:
    // los asserts van después del bloque act (patrón de AuthContext.test.jsx).
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0))
    })

    expect(getCtx().isLoading).toBe(false)
    expect(getCtx().usuario.es_profesional).toBe(true)
    expect(getCtx().usuario.profesional_id).toBe(7)
  })
})
