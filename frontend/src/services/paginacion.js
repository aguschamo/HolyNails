import { api } from './api.js'

// GET /api/... viene paginado (PAGE_SIZE=10 del backend): hay que recorrer
// todas las páginas para no cortar la lista en los primeros 10 elementos.
// `next` es una URL absoluta que api.js usa tal cual.
// Compartido por MiAgenda y la sección de profesionales del panel admin.
export async function fetchTodosLosRecursos(path) {
  const items = []
  let url = path
  while (url) {
    const pagina = await api.get(url)
    const resultados = Array.isArray(pagina?.results) ? pagina.results : []
    items.push(...resultados)
    url = pagina?.next || null
  }
  return items
}
