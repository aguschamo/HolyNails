import { useEffect, useRef, useState } from 'react'

import { Link } from 'react-router-dom'

import { useServicios } from '../hooks/useServicios.js'
import { api } from '../services/api.js'

const ETIQUETA_ESTADO = {
  pendiente: 'Pendiente',
  confirmado: 'Confirmado',
  cancelado: 'Cancelado',
}

// Estados cancelables según el backend (B11.4): la acción
// POST /api/turnos/{id}/cancelar/ sólo admite pendiente o confirmado →
// cancelado. Lista cerrada: cualquier otro estado (cancelado, o estados
// futuros como iniciado / finalizado) no muestra la acción.
const ESTADOS_CANCELABLES = ['pendiente', 'confirmado']

// GET /api/turnos/?propios=true viene paginado (PAGE_SIZE=10 del backend).
// El parámetro «propios» lo resuelve el backend con el usuario del token
// autenticado (nunca con un ID enviado por acá), así que solo llegan las
// reservas propias; hay que recorrer todas las páginas para no cortar la
// lista en 10.
async function fetchTodosLosTurnos() {
  const turnos = []
  let path = '/api/turnos/?propios=true'
  while (path) {
    const pagina = await api.get(path)
    const resultados = Array.isArray(pagina?.results) ? pagina.results : []
    turnos.push(...resultados)
    // `next` es una URL absoluta (http://127.0.0.1:8000/...); api.js la usa
    // tal cual cuando la cadena empieza con "http".
    path = pagina?.next || null
  }
  return turnos
}

// Orden cronológico ascendente: el backend no define Meta.ordering, así que
// sin este orden la lista dependería del orden de inserción en la base.
function ordenarPorFecha(turnos) {
  return [...turnos].sort((a, b) =>
    `${a.fecha} ${a.hora}`.localeCompare(`${b.fecha} ${b.hora}`),
  )
}

// El turno sólo trae el ID del servicio; el nombre se resuelve con el catálogo
// público (useServicios, la misma fuente que usan Home y Agendar).
function formatearFecha(fecha) {
  if (!fecha) return ''
  const partes = fecha.split('-')
  if (partes.length !== 3) return fecha
  const [anio, mes, dia] = partes
  return `${dia}/${mes}/${anio}`
}

function formatearHora(hora) {
  if (!hora) return ''
  // DRF serializa TimeField como "HH:MM:SS"; en pantalla va "HH:MM".
  return hora.length >= 5 ? hora.slice(0, 5) : hora
}

function MisTurnos() {
  const [turnos, setTurnos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Cada incremento vuelve a disparar la carga (botón "Reintentar").
  const [intento, setIntento] = useState(0)

  // ---- Cancelación de turnos propios (B11.4) ----
  const [cancelandoId, setCancelandoId] = useState(null)
  const [mensaje, setMensaje] = useState(null) // { id, texto }
  const [accionError, setAccionError] = useState(null) // { id, texto }
  // Guard con ref: evita POST duplicados si se hace doble clic antes del
  // re-render (el estado `cancelandoId` tarda un tick en reflejarse).
  const cancelandoRef = useRef(false)

  const { servicios, loading: serviciosLoading } = useServicios()

  useEffect(() => {
    let cancelled = false

    fetchTodosLosTurnos()
      .then((lista) => {
        if (!cancelled) setTurnos(ordenarPorFecha(lista))
      })
      .catch((err) => {
        if (!cancelled) {
          setTurnos([])
          setError(err.message || 'No se pudieron cargar tus turnos.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [intento])

  // El estado de carga/error se resetea en el handler (no en el effect) para
  // no disparar renders en cascada; en el primer montaje `loading` ya es true.
  function reintentar() {
    setLoading(true)
    setError(null)
    setIntento((n) => n + 1)
  }

  function nombreDeServicio(id) {
    if (id === null || id === undefined) return 'Servicio no disponible'
    // Aún no llegó el catálogo: se evita mostrar un fallback prematuro.
    if (serviciosLoading) return '…'
    const servicio = servicios.find((s) => s.id === id)
    // Si el ID no está en el catálogo público (servicio dado de baja o fuera
    // de la primera página), se conserva el dato en lugar de ocultarlo.
    return servicio ? servicio.nombre : `Servicio N° ${id}`
  }

  // ---- Cancelación de un turno propio (B11.4) ----
  // El backend es la autoridad: la misma acción POST /api/turnos/{id}/cancelar/
  // que usa AdminTurnos, acá siempre sobre turnos propios (el listado ya viene
  // filtrado con ?propios=true). Sólo se ofrece en estados cancelables; el
  // error real del servidor se muestra sin simular el éxito.
  async function cancelarTurno(t) {
    if (cancelandoRef.current) return

    // Confirmación previa (mismo patrón que AdminTurnos).
    const textoConfirmacion = `¿Estás segura de que querés cancelar tu turno del ${formatearFecha(
      t.fecha,
    )} a las ${formatearHora(t.hora)}?`
    if (!window.confirm(textoConfirmacion)) return

    setMensaje(null)
    setAccionError(null)
    cancelandoRef.current = true
    setCancelandoId(t.id)
    try {
      // La respuesta trae el turno ya actualizado (estado cancelado).
      const actualizado = await api.post(`/api/turnos/${t.id}/cancelar/`)
      setTurnos((lista) =>
        lista.map((x) =>
          x.id === t.id
            ? { ...x, ...(actualizado || { estado: 'cancelado' }) }
            : x,
        ),
      )
      setMensaje({ id: t.id, texto: 'Turno cancelado correctamente.' })
    } catch (err) {
      // Errores reales del backend (400 de transición inválida, 403, red):
      // no se cambia el estado en pantalla y queda el botón para reintentar.
      setAccionError({
        id: t.id,
        texto: err.message || 'No se pudo cancelar el turno.',
      })
    } finally {
      cancelandoRef.current = false
      setCancelandoId(null)
    }
  }

  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="row justify-content-center">
          <div className="col-12 col-md-8 col-lg-6">
            <div className="text-center mb-4">
              <h1 className="hn-section-title mb-1">✦ MIS TURNOS ✦</h1>
              <p className="text-muted small mb-0">
                Acá vas a poder ver y gestionar tus reservas
              </p>
            </div>

            {loading && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <p className="text-muted small mb-0">Cargando tus turnos…</p>
                </div>
              </div>
            )}

            {!loading && error && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <div className="alert alert-warning py-2 small" role="alert">
                    {error}
                  </div>
                  <button
                    type="button"
                    className="btn btn-hn-outline"
                    onClick={reintentar}
                  >
                    Reintentar
                  </button>
                </div>
              </div>
            )}

            {!loading && !error && turnos.length === 0 && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <div className="display-4 mb-3">📖</div>
                  <h2 className="h5 fw-bold mb-2">Todavía no tenés turnos</h2>
                  <p className="small text-muted mb-4">
                    Cuando reserves, tus turnos van a aparecer acá.
                  </p>
                  <Link to="/agendar" className="btn btn-hn-dark">
                    Agendar turno
                  </Link>
                </div>
              </div>
            )}

            {!loading && !error && turnos.length > 0 && (
              <>
                <p className="small text-muted text-center mb-3">
                  {turnos.length === 1
                    ? 'Tenés 1 turno'
                    : `Tenés ${turnos.length} turnos`}
                </p>

                {turnos.map((t) => (
                  <article className="card hn-card mb-3" key={t.id}>
                    <div className="card-body p-4">
                      <div className="d-flex flex-wrap justify-content-between align-items-start gap-2">
                        <div>
                          <h2 className="h5 fw-bold mb-1">
                            {`${formatearFecha(t.fecha)} · ${formatearHora(t.hora)}`}
                          </h2>
                          <p className="small text-muted mb-0">
                            {nombreDeServicio(t.servicio)}
                          </p>
                        </div>
                        <span className="badge hn-badge-pink">
                          {ETIQUETA_ESTADO[t.estado] || t.estado}
                        </span>
                      </div>

                      {(mensaje?.id === t.id ||
                        accionError?.id === t.id ||
                        ESTADOS_CANCELABLES.includes(t.estado)) && (
                        <div className="d-flex flex-wrap justify-content-end align-items-center gap-2 mt-3">
                          {mensaje?.id === t.id && (
                            <span className="small text-success mb-0">
                              {mensaje.texto}
                            </span>
                          )}
                          {accionError?.id === t.id && (
                            <span className="small text-danger mb-0" role="alert">
                              {accionError.texto}
                            </span>
                          )}
                          {ESTADOS_CANCELABLES.includes(t.estado) && (
                            <button
                              type="button"
                              className="btn btn-hn-outline btn-sm text-danger"
                              onClick={() => cancelarTurno(t)}
                              disabled={cancelandoId !== null}
                            >
                              {cancelandoId === t.id
                                ? 'Cancelando…'
                                : 'Cancelar turno'}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export default MisTurnos
