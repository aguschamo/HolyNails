// Tests de lógica de sesión de src/services/api.js con el runner nativo de
// Node (node --test). No requieren dependencias nuevas: se mockean
// localStorage y fetch. La capa React (AuthContext) todavía no tiene
// framework de tests en este proyecto.
import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'
import { pathToFileURL } from 'node:url'

const API_PATH = path.resolve(import.meta.dirname, '../src/services/api.js')

function makeLocalStorage() {
  const store = new Map()
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  }
}

function jsonResponse(status, body) {
  const text = body === undefined ? '' : JSON.stringify(body)
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
    json: async () => body,
  }
}

// Importa una copia fresca del módulo (sessionEpoch es estado de módulo).
async function freshApi() {
  globalThis.localStorage = makeLocalStorage()
  const url = `${pathToFileURL(API_PATH).href}?t=${Date.now()}-${Math.random()}`
  return import(url)
}

test('refresh exitoso persiste el access y el refresh rotado', async () => {
  const api = await freshApi()
  api.setTokens({ access: 'a1', refresh: 'r1' })

  let protectedCalls = 0
  globalThis.fetch = async (url) => {
    if (url.endsWith('/api/auth/refresh/')) {
      return jsonResponse(200, { access: 'a2', refresh: 'r2' })
    }
    protectedCalls += 1
    if (protectedCalls === 1) return jsonResponse(401, { detail: 'expired' })
    return jsonResponse(200, { ok: true })
  }

  const res = await api.api.get('/api/servicios/')
  assert.deepEqual(res, { ok: true })
  assert.equal(localStorage.getItem('hn_access'), 'a2')
  // Con ROTATE_REFRESH_TOKENS el refresh nuevo DEBE persistirse:
  // si quedara 'r1', el próximo refresh daría 401 (r1 fue blacklisteado).
  assert.equal(localStorage.getItem('hn_refresh'), 'r2')
})

test('refresh inválido o vencido: lanza 401 y limpia la sesión local', async () => {
  const api = await freshApi()
  api.setTokens({ access: 'a1', refresh: 'r1' })
  const epochBefore = api.getSessionEpoch()

  globalThis.fetch = async (url) => {
    if (url.endsWith('/api/auth/refresh/')) {
      return jsonResponse(401, { detail: 'Token is invalid or expired' })
    }
    return jsonResponse(401, { detail: 'expired' })
  }

  await assert.rejects(
    () => api.api.get('/api/servicios/'),
    (err) => err.name === 'ApiError' && err.status === 401,
  )
  assert.equal(localStorage.getItem('hn_access'), null)
  assert.equal(localStorage.getItem('hn_refresh'), null)
  assert.ok(api.getSessionEpoch() > epochBefore)
})

test('sin refresh token: 401 y sesión limpia', async () => {
  const api = await freshApi()
  api.setTokens({ access: 'a1' }) // sin refresh

  globalThis.fetch = async () => jsonResponse(401, { detail: 'expired' })

  await assert.rejects(
    () => api.api.get('/api/servicios/'),
    (err) => err.name === 'ApiError' && err.status === 401,
  )
  assert.equal(localStorage.getItem('hn_access'), null)
})

test('logout concurrente con refresh en vuelo: los tokens quedan vacíos', async () => {
  const api = await freshApi()
  api.setTokens({ access: 'a1', refresh: 'r1' })

  let resolveRefresh
  const refreshPending = new Promise((resolve) => {
    resolveRefresh = resolve
  })
  let refreshStarted
  const refreshStartedPromise = new Promise((resolve) => {
    refreshStarted = resolve
  })
  let protectedCalls = 0
  globalThis.fetch = async (url) => {
    if (url.endsWith('/api/auth/refresh/')) {
      refreshStarted()
      await refreshPending
      return jsonResponse(200, { access: 'a2', refresh: 'r2' })
    }
    protectedCalls += 1
    if (protectedCalls === 1) return jsonResponse(401, { detail: 'expired' })
    return jsonResponse(200, { ok: true })
  }

  const inflight = api.api.get('/api/servicios/')
  // Esperamos a que el refresh realmente esté en vuelo (fetch disparado)
  // antes de simular el logout: así el test es determinista.
  await refreshStartedPromise
  api.clearTokens()
  const epochAfterLogout = api.getSessionEpoch()
  resolveRefresh()

  await assert.rejects(
    () => inflight,
    (err) => err.name === 'ApiError' && err.status === 401,
  )
  // El resultado del refresh es obsoleto: no escribió tokens.
  assert.equal(localStorage.getItem('hn_access'), null)
  assert.equal(localStorage.getItem('hn_refresh'), null)
  assert.equal(api.getSessionEpoch(), epochAfterLogout)
})

test('setTokens y clearTokens siempre avanzan el sessionEpoch', async () => {
  const api = await freshApi()
  const e0 = api.getSessionEpoch()
  api.setTokens({ access: 'a1', refresh: 'r1' })
  const e1 = api.getSessionEpoch()
  api.clearTokens()
  const e2 = api.getSessionEpoch()
  assert.ok(e1 > e0)
  assert.ok(e2 > e1)
})

test('onAuthCleared se notifica al limpiar la sesión', async () => {
  const api = await freshApi()
  let notified = 0
  const unsubscribe = api.onAuthCleared(() => {
    notified += 1
  })
  api.setTokens({ access: 'a1', refresh: 'r1' })
  assert.equal(notified, 0)
  api.clearTokens()
  assert.equal(notified, 1)
  unsubscribe()
  api.clearTokens()
  assert.equal(notified, 1)
})

test('apiRequest con 401 y skipAuth no intenta refresh ni limpia tokens', async () => {
  const api = await freshApi()
  api.setTokens({ access: 'a1', refresh: 'r1' })

  globalThis.fetch = async () => jsonResponse(401, { detail: 'bad' })
  await assert.rejects(
    () => api.api.get('/api/auth/profile/', { skipAuth: true }),
    (err) => err.status === 401,
  )
  // skipAuth no limpia la sesión: la usamos para login/register.
  assert.equal(localStorage.getItem('hn_access'), 'a1')
  assert.equal(localStorage.getItem('hn_refresh'), 'r1')
})
