import { useEffect, useState } from 'react'

import { fetchTodosLosRecursos } from '../services/paginacion.js'

// Fuente única del catálogo de servicios para Home y Agendar.
// GET /api/servicios/ viene paginado (PAGE_SIZE=10 en el backend):
// fetchTodosLosRecursos recorre todas las páginas para que el catálogo
// no se corte en los primeros elementos. Si la API falla, `error` queda
// con el mensaje ya listo para mostrar y `servicios` en [].
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
        const lista = await fetchTodosLosRecursos('/api/servicios/')
        if (!cancelled) {
          setServicios(lista)
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
