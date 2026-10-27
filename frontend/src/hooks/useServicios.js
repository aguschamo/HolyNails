import { useEffect, useState } from 'react'

import { api } from '../services/api.js'

// Fuente única del catálogo de servicios para Home y Agendar.
// GET /api/servicios/ devuelve una página paginada; sólo se lee `results`
// (PAGE_SIZE=10 en el backend). Si la API falla, `error` queda con el
// mensaje ya listo para mostrar y `servicios` en [].
export function useServicios() {
  const [servicios, setServicios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function cargarServicios() {
      setLoading(true)
      setError(null)
      try {
        const data = await api.get('/api/servicios/')
        if (!cancelled) {
          setServicios(Array.isArray(data.results) ? data.results : [])
        }
      } catch (err) {
        if (!cancelled) {
          setServicios([])
          setError(err.message || 'No se pudieron cargar los servicios.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    cargarServicios()
    return () => {
      cancelled = true
    }
  }, [])

  return { servicios, loading, error }
}
