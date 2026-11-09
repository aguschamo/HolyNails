import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

import {
  api,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  onAuthCleared,
  setTokens,
} from '../services/api.js'

const AuthContext = createContext(null)

function normalizeRole(role) {
  return role ? role.toLowerCase() : null
}

function normalizeUser(profile) {
  if (!profile) return null
  return {
    id: profile.id,
    nombre: profile.nombre || '',
    email: profile.email || '',
    username: profile.username || '',
    telefono: profile.telefono || '',
    // B11.2: URL de la foto persistida en el backend (null = sin foto).
    // No es la vista previa local: sobrevive a cerrar y abrir sesión.
    photo: profile.foto_url || null,
    role: normalizeRole(profile.role),
    es_profesional: profile.es_profesional ?? false,
    profesional_id: profile.profesional_id ?? null,
  }
}

export function AuthProvider({ children, initialUsuario }) {
  const [usuario, setUsuario] = useState(initialUsuario || null)
  const [isLoading, setIsLoading] = useState(!initialUsuario)
  // Se activa cuando ocurre login o logout mientras restore() está pendiente,
  // para que restore no sobrescriba el resultado de esa acción posterior.
  const authActionRef = useRef(false)

  // Restaura la sesión al montar: si hay access token, verifica el perfil contra el backend.
  // api.js maneja el refresh automático si el access está vencido.
  useEffect(() => {
    if (initialUsuario) return
    let cancelled = false

    async function restore() {
      if (!getAccessToken()) {
        if (!cancelled) setIsLoading(false)
        return
      }
      try {
        const profile = await api.get('/api/auth/profile/')
        if (!cancelled && !authActionRef.current) setUsuario(normalizeUser(profile))
      } catch {
        if (!cancelled && !authActionRef.current) setUsuario(null)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [initialUsuario])

  // Si api.js limpia los tokens (refresh falló), sincroniza el estado.
  useEffect(() => {
    return onAuthCleared(() => {
      setUsuario(null)
    })
  }, [])

  const login = useCallback(async (email, password) => {
    authActionRef.current = true
    const data = await api.post(
      '/api/auth/login/',
      { email, password },
      { skipAuth: true },
    )
    setTokens({ access: data.access, refresh: data.refresh })
    try {
      const profile = await api.get('/api/auth/profile/')
      const user = normalizeUser(profile)
      setUsuario(user)
      return user
    } catch (err) {
      // Sin profile no hay sesión confiable: no dejamos tokens huérfanos
      // en localStorage. clearTokens() incrementa el sessionEpoch, por lo
      // que un refresh en vuelo no podrá restaurarlos.
      clearTokens()
      throw err
    }
  }, [])

  const register = useCallback(async ({ nombre, username, email, password }) => {
    await api.post(
      '/api/auth/register/',
      { nombre, username, email, password },
      { skipAuth: true },
    )
    // El backend no devuelve tokens: el usuario debe iniciar sesión después.
  }, [])

  const logout = useCallback(() => {
    authActionRef.current = true
    // Capturamos los tokens ANTES de limpiar: el request al backend los
    // necesita (no hay tokens en storage una vez limpiada la sesión).
    const refresh = getRefreshToken()
    const access = getAccessToken()
    clearTokens()
    setUsuario(null)
    // Revocación en el backend: fire-and-forget. Si falla (offline,
    // backend caído), la sesión local igualmente queda limpia; el refresh
    // seguirá siendo válido hasta expirar o rotarse.
    if (refresh) {
      api
        .post(
          '/api/auth/logout/',
          { refresh },
          { skipAuth: true, headers: { Authorization: `Bearer ${access}` } },
        )
        .catch(() => {})
    }
  }, [])

  // B11.1: persiste el perfil en el backend y sincroniza el contexto con
  // la respuesta (la única fuente de verdad). Si el PATCH falla, lanza y
  // el estado del usuario queda intacto: nada se limpia localmente.
  const actualizarPerfil = useCallback(async (datos) => {
    const profile = await api.patch('/api/auth/profile/', datos)
    const user = normalizeUser(profile)
    setUsuario(user)
    return user
  }, [])

  // B11.2: sube la foto (multipart) y reemplaza el contexto con la
  // respuesta del backend. Ante un error se propaga y el usuario conserva
  // su foto anterior (el estado no se toca).
  const subirFoto = useCallback(async (formData) => {
    const profile = await api.post('/api/auth/profile/foto/', formData)
    const user = normalizeUser(profile)
    setUsuario(user)
    return user
  }, [])

  // B11.2: elimina la foto propia (DELETE) y limpia el contexto con la
  // respuesta. El backend sólo acepta la foto del usuario autenticado.
  const eliminarFoto = useCallback(async () => {
    const profile = await api.delete('/api/auth/profile/foto/')
    const user = normalizeUser(profile)
    setUsuario(user)
    return user
  }, [])

  const value = useMemo(
    () => ({
      usuario,
      role: usuario ? usuario.role : null,
      isAuthenticated: Boolean(usuario),
      isLoading,
      login,
      register,
      logout,
      actualizarPerfil,
      subirFoto,
      eliminarFoto,
    }),
    [usuario, isLoading, login, register, logout, actualizarPerfil, subirFoto, eliminarFoto],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
