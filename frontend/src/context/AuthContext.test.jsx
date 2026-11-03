// @vitest-environment jsdom
// Pruebas de integración de AuthContext con api.js real, fetch mockeado y
// localStorage de jsdom. Cada test importa módulos frescos (vi.resetModules)
// porque sessionEpoch y los listeners de onAuthCleared son estado de módulo.
import { act, cleanup, render, screen } from '@testing-library/react'
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

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const PROFILE_OK = {
  id: 1,
  username: 'ana',
  email: 'ana@holy.test',
  nombre: 'Ana',
  role: 'ADMIN',
}

describe('AuthContext', () => {
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

  async function mountAuth() {
    const { AuthProvider, useAuth } = await import('./AuthContext.jsx')
    let ctx = null
    function Probe() {
      ctx = useAuth()
      return (
        <div>
          <span data-testid="auth">{String(ctx.isAuthenticated)}</span>
          <span data-testid="loading">{String(ctx.isLoading)}</span>
          <span data-testid="user">
            {ctx.usuario ? `${ctx.usuario.username}:${ctx.usuario.role}` : ''}
          </span>
        </div>
      )
    }
    const view = render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )
    return { view, getCtx: () => ctx }
  }

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

  it('caso A1: profile con error HTTP tras login limpia tokens y no autentica', async () => {
    routeFetch([
      { method: 'POST', path: '/api/auth/login/', respond: () => jsonResponse(200, { access: 'a1', refresh: 'r1' }) },
      { method: 'GET', path: '/api/auth/profile/', respond: () => jsonResponse(500, { detail: 'boom' }) },
    ])
    const { getCtx } = await mountAuth()

    let error = null
    await act(async () => {
      try {
        await getCtx().login('ana@holy.test', 'Passw0rd-123')
      } catch (err) {
        error = err
      }
    })

    expect(error).not.toBeNull()
    expect(error.status).toBe(500)
    expect(localStorage.getItem('hn_access')).toBeNull()
    expect(localStorage.getItem('hn_refresh')).toBeNull()
    expect(getCtx().isAuthenticated).toBe(false)
    expect(getCtx().usuario).toBeNull()
  })

  it('caso A2: error de red en profile tras login limpia tokens y no autentica', async () => {
    routeFetch([
      { method: 'POST', path: '/api/auth/login/', respond: () => jsonResponse(200, { access: 'a1', refresh: 'r1' }) },
      {
        method: 'GET',
        path: '/api/auth/profile/',
        respond: () => {
          throw new TypeError('Failed to fetch')
        },
      },
    ])
    const { getCtx } = await mountAuth()

    let error = null
    await act(async () => {
      try {
        await getCtx().login('ana@holy.test', 'Passw0rd-123')
      } catch (err) {
        error = err
      }
    })

    expect(error).not.toBeNull()
    expect(error.status).toBe(0)
    expect(localStorage.getItem('hn_access')).toBeNull()
    expect(localStorage.getItem('hn_refresh')).toBeNull()
    expect(getCtx().isAuthenticated).toBe(false)
    expect(getCtx().usuario).toBeNull()
  })

  it('caso A3: login y profile exitosos guardan tokens y normalizan el rol', async () => {
    routeFetch([
      { method: 'POST', path: '/api/auth/login/', respond: () => jsonResponse(200, { access: 'a1', refresh: 'r1' }) },
      { method: 'GET', path: '/api/auth/profile/', respond: () => jsonResponse(200, PROFILE_OK) },
    ])
    const { getCtx } = await mountAuth()

    let user = null
    await act(async () => {
      user = await getCtx().login('ana@holy.test', 'Passw0rd-123')
    })

    expect(user).not.toBeNull()
    expect(localStorage.getItem('hn_access')).toBe('a1')
    expect(localStorage.getItem('hn_refresh')).toBe('r1')
    expect(getCtx().isAuthenticated).toBe(true)
    // normalizeRole pasa el rol a minúscula
    expect(getCtx().usuario.role).toBe('admin')
    expect(getCtx().usuario.username).toBe('ana')
    expect(screen.getByTestId('user').textContent).toBe('ana:admin')
  })

  it('caso B1: restore pendiente + logout => la respuesta tardía no restaura usuario', async () => {
    localStorage.setItem('hn_access', 'old-access')
    const profile = deferred()
    routeFetch([
      { method: 'GET', path: '/api/auth/profile/', respond: () => profile.promise },
    ])
    const { getCtx } = await mountAuth()
    // restore quedó pendiente en el profile
    expect(getCtx().isLoading).toBe(true)

    await act(async () => {
      getCtx().logout()
    })
    expect(getCtx().isAuthenticated).toBe(false)
    expect(localStorage.getItem('hn_access')).toBeNull()

    await act(async () => {
      profile.resolve(jsonResponse(200, PROFILE_OK))
      await profile.promise
    })

    // authActionRef impide que el profile tardío reautentique
    expect(getCtx().isAuthenticated).toBe(false)
    expect(getCtx().usuario).toBeNull()
    expect(getCtx().isLoading).toBe(false)
  })

  it('caso B2: restore pendiente + login nuevo => la respuesta vieja no pisa al usuario nuevo', async () => {
    localStorage.setItem('hn_access', 'old-access')
    const oldProfile = deferred()
    let profileCalls = 0
    fetchMock.mockImplementation(async (url, opts = {}) => {
      const method = (opts.method || 'GET').toUpperCase()
      if (method === 'POST' && String(url).endsWith('/api/auth/login/')) {
        return jsonResponse(200, { access: 'new-access', refresh: 'new-refresh' })
      }
      if (method === 'GET' && String(url).endsWith('/api/auth/profile/')) {
        profileCalls += 1
        if (profileCalls === 1) return oldProfile.promise
        return jsonResponse(200, { ...PROFILE_OK, username: 'nueva', role: 'CLIENTE' })
      }
      throw new Error(`fetch no mockeado: ${method} ${url}`)
    })
    const { getCtx } = await mountAuth()
    expect(getCtx().isLoading).toBe(true)

    await act(async () => {
      await getCtx().login('nueva@holy.test', 'Passw0rd-123')
    })
    expect(getCtx().usuario.username).toBe('nueva')
    expect(getCtx().isAuthenticated).toBe(true)

    await act(async () => {
      oldProfile.resolve(jsonResponse(200, PROFILE_OK))
      await oldProfile.promise
    })

    // El profile viejo (de la sesión anterior) no sobrescribe al login nuevo
    expect(getCtx().usuario.username).toBe('nueva')
    expect(localStorage.getItem('hn_access')).toBe('new-access')
  })

  it('caso B3: logout sin refresh limpia la sesión sin pegarle a /api/auth/logout/', async () => {
    // Sin tokens en storage: restore termina enseguida y no hay red
    routeFetch([])
    const { getCtx } = await mountAuth()
    await act(async () => {
      await Promise.resolve()
    })
    expect(getCtx().isLoading).toBe(false)

    await act(async () => {
      getCtx().logout()
    })

    expect(getCtx().isAuthenticated).toBe(false)
    expect(getCtx().usuario).toBeNull()
    expect(localStorage.getItem('hn_access')).toBeNull()
    expect(localStorage.getItem('hn_refresh')).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
