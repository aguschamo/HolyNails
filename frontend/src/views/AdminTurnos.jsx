import { useEffect, useMemo, useState } from 'react'

import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import { fetchTodosLosRecursos } from '../services/paginacion.js'

const ETIQUETA_ESTADO = {
  pendiente: 'Pendiente',
  confirmado: 'Confirmado',
  cancelado: 'Cancelado',
}

const COLOR_ESTADO = {
  pendiente: 'hn-badge-pink',
  confirmado: 'hn-badge-success',
  cancelado: 'hn-badge-danger',
}

const FILTROS_INICIALES = {
  estado: '',
  desde: '',
  hasta: '',
  profesional: '',
  buscar: '',
}

// Filtros del listado administrativo (B10.1): se aplican sobre la
// consulta general ya cargada y se combinan entre sí. `desde`/`hasta`
// comparan la fecha ISO (YYYY-MM-DD) lexicográficamente, que coincide con
// el orden cronológico.
function filtrarTurnos(turnos, { estado, desde, hasta, profesional, buscar }) {
  const texto = buscar.trim().toLowerCase()
  return turnos.filter((t) => {
    if (estado && t.estado !== estado) return false
    if (desde && t.fecha < desde) return false
    if (hasta && t.fecha > hasta) return false
    if (profesional && String(t.profesional) !== String(profesional)) return false
    if (texto) {
      const cliente = String(t.usuario_nombre || '').toLowerCase()
      if (!cliente.includes(texto)) return false
    }
    return true
  })
}

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

// Sección del panel admin para gestionar turnos: listado de todos los
// turnos del salón (consulta general, sin ?propios=true) con filtros y
// las transiciones de estado permitidas (confirmar / cancelar). El
// backend es la autoridad: acá solo se muestran las acciones válidas y
// sus errores se propagan a la vista. La ruta está protegida por
// RoleRoute; acá se revalida de forma defensiva.
function AdminTurnos() {
  const { role, isLoading } = useAuth()

  // ---- Listado ----
  const [turnos, setTurnos] = useState([])
  const [servicios, setServicios] = useState([])
  const [profesionales, setProfesionales] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Cada incremento vuelve a disparar la carga (tras una transición y
  // con el botón "Reintentar").
  const [intento, setIntento] = useState(0)

  // ---- Filtros ----
  const [filtros, setFiltros] = useState(FILTROS_INICIALES)

  // ---- Acciones sobre un turno ----
  const [mensaje, setMensaje] = useState('')
  const [accionError, setAccionError] = useState('')
  const [accionandoId, setAccionandoId] = useState(null)

  const esAdmin = role === 'admin'

  useEffect(() => {
    if (!esAdmin) return
    let cancelled = false

    async function cargar() {
      setLoading(true)
      setError(null)
      try {
        // Consulta general de ADMIN (sin ?propios=true): todos los turnos
        // del salón, más los catálogos para resolver nombres y el filtro
        // por profesional.
        const [listaTurnos, listaServicios, listaProfesionales] =
          await Promise.all([
            fetchTodosLosRecursos('/api/turnos/'),
            fetchTodosLosRecursos('/api/servicios/'),
            fetchTodosLosRecursos('/api/profesionales/'),
          ])
        if (!cancelled) {
          setTurnos(listaTurnos)
          setServicios(listaServicios)
          setProfesionales(listaProfesionales)
        }
      } catch (err) {
        if (!cancelled) {
          setTurnos([])
          setError(err.message || 'No se pudieron cargar los turnos.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    cargar()
    return () => {
      cancelled = true
    }
  }, [esAdmin, intento])

  const turnosFiltrados = useMemo(
    () => filtrarTurnos(turnos, filtros),
    [turnos, filtros],
  )

  const hayFiltros = Object.values(filtros).some((v) => v !== '')

  function setFiltro(nombre, valor) {
    setFiltros((f) => ({ ...f, [nombre]: valor }))
  }

  function limpiarFiltros() {
    setFiltros(FILTROS_INICIALES)
  }

  // ---- Resolución de nombres (los turnos traen IDs) ----
  function nombreDeServicio(id) {
    if (id === null || id === undefined) return 'Servicio no disponible'
    const servicio = servicios.find((s) => s.id === id)
    return servicio ? servicio.nombre : `Servicio N° ${id}`
  }

  function nombreDeCliente(t) {
    // `usuario_nombre` viene del backend (B10.1); el fallback conserva la
    // referencia del turno para respuestas antiguas o mockeadas.
    return t.usuario_nombre || `Cliente N° ${t.usuario}`
  }

  function nombreDeProfesional(id) {
    if (id === null || id === undefined) return 'Sin profesional'
    const profesional = profesionales.find((p) => p.id === id)
    return profesional ? profesional.nombre : `Profesional N° ${id}`
  }

  // ---- Transiciones de estado (solo las permitidas por el backend) ----
  async function transicionar(t, accion) {
    // Confirmación explícita antes de cancelar (la confirmación de un
    // turno pendiente no es destructiva y no la pide).
    if (accion === 'cancelar') {
      const texto = `¿Estás segura de que querés cancelar el turno de ${nombreDeCliente(
        t,
      )} del ${formatearFecha(t.fecha)} a las ${formatearHora(t.hora)}?`
      if (!window.confirm(texto)) return
    }

    setMensaje('')
    setAccionError('')
    setAccionandoId(t.id)
    try {
      await api.post(`/api/turnos/${t.id}/${accion}/`)
      setMensaje(
        accion === 'confirmar'
          ? 'Turno confirmado correctamente.'
          : 'Turno cancelado correctamente.',
      )
      setIntento((n) => n + 1)
    } catch (err) {
      // Errores de transición inválida del backend (400) y de permisos
      // llegan ya traducidos en err.message.
      setAccionError(err.message || 'No se pudo actualizar el turno.')
    } finally {
      setAccionandoId(null)
    }
  }

  // ---- Acceso restringido ----
  if (isLoading) return null
  if (!esAdmin) {
    return (
      <section className="hn-auth-bg py-5">
        <div className="container py-4">
          <div className="row justify-content-center">
            <div className="col-12 col-md-8 col-lg-6">
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <div className="display-4 mb-3">🔒</div>
                  <h1 className="h4 fw-bold mb-2">Acceso restringido</h1>
                  <p className="small text-muted mb-0">
                    Esta sección es solo para administradores.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="row justify-content-center">
          <div className="col-12">
            <div className="text-center mb-4">
              <h1 className="hn-section-title mb-1">✦ TURNOS ✦</h1>
              <p className="text-muted small mb-0">
                Consultá, confirmá y cancelá los turnos del salón.
              </p>
            </div>

            {mensaje && (
              <div className="alert alert-success py-2 small" role="status">
                {mensaje}
              </div>
            )}
            {accionError && (
              <div className="alert alert-danger py-2 small" role="alert">
                {accionError}
              </div>
            )}

            {loading && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <p className="text-muted small mb-0">Cargando turnos…</p>
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
                    onClick={() => setIntento((n) => n + 1)}
                  >
                    Reintentar
                  </button>
                </div>
              </div>
            )}

            {!loading && !error && turnos.length === 0 && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <div className="display-4 mb-3">🗓️</div>
                  <h2 className="h5 fw-bold mb-2">No hay turnos cargados</h2>
                  <p className="small text-muted mb-0">
                    Cuando las clientas reserven, los turnos van a aparecer acá.
                  </p>
                </div>
              </div>
            )}

            {!loading && !error && turnos.length > 0 && (
              <div className="card hn-card">
                <div className="card-body p-4">
                  {/* ---- Filtros combinables ---- */}
                  <div className="row g-3 mb-3">
                    <div className="col-12 col-md-3">
                      <label htmlFor="turnos-estado" className="form-label small">
                        Estado
                      </label>
                      <select
                        id="turnos-estado"
                        className="form-select form-select-sm"
                        value={filtros.estado}
                        onChange={(e) => setFiltro('estado', e.target.value)}
                      >
                        <option value="">Todos</option>
                        <option value="pendiente">Pendiente</option>
                        <option value="confirmado">Confirmado</option>
                        <option value="cancelado">Cancelado</option>
                      </select>
                    </div>
                    <div className="col-6 col-md-2">
                      <label htmlFor="turnos-desde" className="form-label small">
                        Desde
                      </label>
                      <input
                        id="turnos-desde"
                        type="date"
                        className="form-control form-control-sm"
                        value={filtros.desde}
                        onChange={(e) => setFiltro('desde', e.target.value)}
                      />
                    </div>
                    <div className="col-6 col-md-2">
                      <label htmlFor="turnos-hasta" className="form-label small">
                        Hasta
                      </label>
                      <input
                        id="turnos-hasta"
                        type="date"
                        className="form-control form-control-sm"
                        value={filtros.hasta}
                        onChange={(e) => setFiltro('hasta', e.target.value)}
                      />
                    </div>
                    <div className="col-12 col-md-2">
                      <label
                        htmlFor="turnos-profesional"
                        className="form-label small"
                      >
                        Profesional
                      </label>
                      <select
                        id="turnos-profesional"
                        className="form-select form-select-sm"
                        value={filtros.profesional}
                        onChange={(e) => setFiltro('profesional', e.target.value)}
                      >
                        <option value="">Todas</option>
                        {profesionales.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.nombre}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-12 col-md-3">
                      <label htmlFor="turnos-buscar" className="form-label small">
                        Buscar clienta
                      </label>
                      <input
                        id="turnos-buscar"
                        type="search"
                        className="form-control form-control-sm"
                        placeholder="Nombre de la clienta"
                        value={filtros.buscar}
                        onChange={(e) => setFiltro('buscar', e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
                    <span className="small text-muted mb-0">
                      {turnosFiltrados.length === turnos.length
                        ? `${turnos.length} ${turnos.length === 1 ? 'turno' : 'turnos'}`
                        : `Mostrando ${turnosFiltrados.length} de ${turnos.length} turnos`}
                    </span>
                    <button
                      type="button"
                      className="btn btn-hn-outline btn-sm"
                      onClick={limpiarFiltros}
                      disabled={!hayFiltros}
                    >
                      Limpiar filtros
                    </button>
                  </div>

                  {turnosFiltrados.length === 0 && (
                    <div className="text-center py-4">
                      <p className="small text-muted mb-2">
                        No hay turnos para los filtros seleccionados.
                      </p>
                      <button
                        type="button"
                        className="btn btn-hn-outline btn-sm"
                        onClick={limpiarFiltros}
                      >
                        Limpiar filtros
                      </button>
                    </div>
                  )}

                  {turnosFiltrados.length > 0 && (
                    <div className="table-responsive">
                      <table className="table table-hover mb-0">
                        <thead>
                          <tr>
                            <th>Clienta</th>
                            <th>Servicio</th>
                            <th>Profesional</th>
                            <th>Fecha</th>
                            <th>Hora</th>
                            <th>Estado</th>
                            <th className="text-end">Acciones</th>
                          </tr>
                        </thead>
                        <tbody>
                          {turnosFiltrados.map((t) => (
                            <tr key={t.id}>
                              <td>{nombreDeCliente(t)}</td>
                              <td>{nombreDeServicio(t.servicio)}</td>
                              <td>{nombreDeProfesional(t.profesional)}</td>
                              <td>{formatearFecha(t.fecha)}</td>
                              <td>{formatearHora(t.hora)}</td>
                              <td>
                                <span
                                  className={`badge ${COLOR_ESTADO[t.estado] || 'hn-badge-pink'}`}
                                >
                                  {ETIQUETA_ESTADO[t.estado] || t.estado}
                                </span>
                              </td>
                              <td className="text-end">
                                {t.estado === 'pendiente' && (
                                  <button
                                    type="button"
                                    className="btn btn-hn-outline btn-sm me-2"
                                    onClick={() => transicionar(t, 'confirmar')}
                                    disabled={accionandoId === t.id}
                                  >
                                    Confirmar
                                  </button>
                                )}
                                {(t.estado === 'pendiente' ||
                                  t.estado === 'confirmado') && (
                                  <button
                                    type="button"
                                    className="btn btn-hn-outline btn-sm text-danger"
                                    onClick={() => transicionar(t, 'cancelar')}
                                    disabled={accionandoId === t.id}
                                  >
                                    Cancelar
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export default AdminTurnos
