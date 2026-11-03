// En Vite, import.meta.env existe y define reemplaza VITE_API_URL en build.
// El chequeo typeof permite que api.js también se importe en Node
// (tests con node --test) sin tirar TypeError.
const API_URL =
  (typeof import.meta.env !== 'undefined' && import.meta.env.VITE_API_URL) ||
  'http://127.0.0.1:8000'

const ACCESS_KEY = 'hn_access'
const REFRESH_KEY = 'hn_refresh'

// Generación de sesión: se incrementa en cada mutación de tokens (set o clear).
// Una operación de refresh que haya capturado una generación obsoleta no debe
// escribir tokens ni limpiar una sesión posterior.
let sessionEpoch = 0

function bumpEpoch() {
  sessionEpoch += 1
  return sessionEpoch
}

export function getSessionEpoch() {
  return sessionEpoch
}

const authClearedListeners = new Set()

export function onAuthCleared(listener) {
  authClearedListeners.add(listener)
  return () => authClearedListeners.delete(listener)
}

function notifyAuthCleared() {
  authClearedListeners.forEach((listener) => listener())
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens({ access, refresh }) {
  bumpEpoch()
  if (access) localStorage.setItem(ACCESS_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens() {
  bumpEpoch()
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  notifyAuthCleared()
}

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

let refreshPromise = null

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise
  const epochAtStart = sessionEpoch

  refreshPromise = (async () => {
    const refresh = getRefreshToken()
    if (!refresh) throw new ApiError('No refresh token', 401)

    const res = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })

    if (!res.ok) throw new ApiError('Refresh failed', res.status)
    const data = await res.json()

    // Si la sesión cambió durante el fetch (logout o login nuevo),
    // no escribimos tokens: el resultado es obsoleto.
    if (sessionEpoch !== epochAtStart) {
      throw new ApiError('Session changed during refresh', 401)
    }

    // Con ROTATE_REFRESH_TOKENS el backend devuelve un refresh nuevo y
    // pone el anterior en la blacklist: hay que persistirlo o el próximo
    // refresh fallirá.
    setTokens({ access: data.access, refresh: data.refresh })
    return data.access
  })()

  try {
    return await refreshPromise
  } finally {
    refreshPromise = null
  }
}

async function parseBody(res) {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function buildHeaders(token, extraHeaders) {
  const headers = { ...extraHeaders }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

function extractErrorMessage(data, status) {
  if (data && typeof data === 'object') {
    if (data.detail) return data.detail
    const firstKey = Object.keys(data)[0]
    if (firstKey && Array.isArray(data[firstKey])) return data[firstKey][0]
    if (firstKey && typeof data[firstKey] === 'string') return data[firstKey]
  }
  if (status === 401) return 'Credenciales incorrectas.'
  if (status === 403) return 'No tenés permiso para realizar esta acción.'
  if (status === 404) return 'Recurso no encontrado.'
  if (status >= 500) return 'Error del servidor. Intentá más tarde.'
  return 'Ocurrió un error inesperado.'
}

export async function apiRequest(
  path,
  { method = 'GET', body, headers = {}, skipAuth = false, _isRetry = false } = {},
) {
  const url = path.startsWith('http') ? path : `${API_URL}${path}`
  const token = skipAuth ? null : getAccessToken()

  const fetchOptions = { method, headers: buildHeaders(token, headers) }
  if (body !== undefined) {
    fetchOptions.headers['Content-Type'] = 'application/json'
    fetchOptions.body = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(url, fetchOptions)
  } catch {
    throw new ApiError('No se pudo conectar con el servidor. Verificá tu conexión.', 0)
  }

  if (res.status === 401 && !skipAuth && !_isRetry && getRefreshToken()) {
    const epochBefore = sessionEpoch
    try {
      await refreshAccessToken()
    } catch {
      // Solo cerramos la sesión si el epoch no cambió: si cambió, fue
      // porque se hizo logout o login nuevo, y no debemos borrar esos tokens.
      if (sessionEpoch === epochBefore) {
        clearTokens()
      }
      throw new ApiError('La sesión expiró. Iniciá sesión nuevamente.', 401)
    }
    return apiRequest(path, { method, body, headers, skipAuth, _isRetry: true })
  }

  const data = await parseBody(res)

  if (!res.ok) {
    if (res.status === 401 && !skipAuth) {
      clearTokens()
    }
    throw new ApiError(extractErrorMessage(data, res.status), res.status, data)
  }

  return data
}

export const api = {
  get: (path, opts) => apiRequest(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => apiRequest(path, { ...opts, method: 'POST', body }),
  patch: (path, body, opts) => apiRequest(path, { ...opts, method: 'PATCH', body }),
  put: (path, body, opts) => apiRequest(path, { ...opts, method: 'PUT', body }),
  delete: (path, opts) => apiRequest(path, { ...opts, method: 'DELETE' }),
}
