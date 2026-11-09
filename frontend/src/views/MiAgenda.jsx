import { useEffect, useState } from 'react'

import { useAuth } from '../context/AuthContext.jsx'
import { useServicios } from '../hooks/useServicios.js'
import { api } from '../services/api.js'
import { fetchTodosLosRecursos } from '../services/paginacion.js'

const ETIQUETA_ESTADO = {
  pendiente: 'Pendiente',
  confirmado: 'Confirmado',
  cancelado: 'Cancelado',
}

const ETIQUETA_COLOR = {
  pendiente: 'hn-badge-pink',
  confirmado: 'hn-badge-success',
  cancelado: 'hn-badge-danger',
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

function MiAgenda() {
  const { usuario } = useAuth()
  const { servicios, loading: serviciosLoading } = useServicios()

  // ---- Disponibilidades ----
  const [disponibilidades, setDisponibilidades] = useState([])
  const [disponibilidadesLoading, setDisponibilidadesLoading] = useState(true)
  const [disponibilidadesError, setDisponibilidadesError] = useState(null)

  // ---- Turnos asignados ----
  const [turnos, setTurnos] = useState([])
  const [turnosLoading, setTurnosLoading] = useState(true)
  const [turnosError, setTurnosError] = useState(null)

  // Cada incremento vuelve a disparar la carga (guardado, borrado, "Reintentar").
  const [intento, setIntento] = useState(0)

  // Filtro por fecha sobre las disponibilidades ya cargadas.
  const [filtroFecha, setFiltroFecha] = useState('')

  // ---- Formulario de disponibilidad ----
  const [formOpen, setFormOpen] = useState(false)
  const [editandoId, setEditandoId] = useState(null)
  const [formFecha, setFormFecha] = useState('')
  const [formHoraInicio, setFormHoraInicio] = useState('')
  const [formHoraFin, setFormHoraFin] = useState('')
  const [formError, setFormError] = useState('')
  const [formSaving, setFormSaving] = useState(false)
  const [eliminandoId, setEliminandoId] = useState(null)

  const profesionalId = usuario ? usuario.profesional_id : null
  const esProfesional = Boolean(usuario && usuario.es_profesional && profesionalId)

  useEffect(() => {
    if (!esProfesional) return
    let cancelled = false

    async function cargarDisponibilidades() {
      setDisponibilidadesLoading(true)
      setDisponibilidadesError(null)
      try {
        const lista = await fetchTodosLosRecursos(
          `/api/disponibilidades/?profesional=${profesionalId}`,
        )
        // Filtro defensivo: nunca mostrar franjas de otra profesional.
        if (!cancelled) {
          setDisponibilidades(lista.filter((d) => d.profesional == profesionalId))
        }
      } catch (err) {
        if (!cancelled) {
          setDisponibilidades([])
          setDisponibilidadesError(err.message || 'No se pudieron cargar las disponibilidades.')
        }
      } finally {
        if (!cancelled) setDisponibilidadesLoading(false)
      }
    }

    async function cargarTurnos() {
      setTurnosLoading(true)
      setTurnosError(null)
      try {
        const lista = await fetchTodosLosRecursos('/api/turnos/?como_profesional=true')
        // Filtro defensivo: nunca mostrar turnos de otra profesional.
        if (!cancelled) {
          setTurnos(lista.filter((t) => t.profesional == profesionalId))
        }
      } catch (err) {
        if (!cancelled) {
          setTurnos([])
          setTurnosError(err.message || 'No se pudieron cargar los turnos.')
        }
      } finally {
        if (!cancelled) setTurnosLoading(false)
      }
    }

    cargarDisponibilidades()
    cargarTurnos()

    return () => {
      cancelled = true
    }
  }, [esProfesional, profesionalId, intento])

  const disponibilidadesFiltradas = filtroFecha
    ? disponibilidades.filter((d) => d.fecha === filtroFecha)
    : disponibilidades

  // El turno sólo trae el ID del servicio; el nombre se resuelve con el
  // catálogo público (misma fuente que usan Home, Agendar y MisTurnos).
  function nombreDeServicio(id) {
    if (id === null || id === undefined) return 'Servicio no disponible'
    if (serviciosLoading) return '…'
    const servicio = servicios.find((s) => s.id === id)
    return servicio ? servicio.nombre : `Servicio N° ${id}`
  }

  function nombreDeCliente(t) {
    // `usuario_nombre` viene del backend (B10.1): nombre o username de la
    // cuenta asociada al turno. Si el serializer lo devuelve en null
    // (defensivo; el modelo exige usuario), se muestra la referencia del
    // turno, sin inventar datos.
    return t.usuario_nombre || `Cliente N° ${t.usuario}`
  }

  function abrirCrear() {
    setEditandoId(null)
    setFormFecha('')
    setFormHoraInicio('')
    setFormHoraFin('')
    setFormError('')
    setFormOpen(true)
  }

  function abrirEditar(d) {
    setEditandoId(d.id)
    setFormFecha(d.fecha)
    setFormHoraInicio(d.hora_inicio.slice(0, 5))
    setFormHoraFin(d.hora_fin.slice(0, 5))
    setFormError('')
    setFormOpen(true)
  }

  function cerrarFormulario() {
    setFormOpen(false)
    setEditandoId(null)
    setFormFecha('')
    setFormHoraInicio('')
    setFormHoraFin('')
    setFormError('')
  }

  async function guardarDisponibilidad(e) {
    e.preventDefault()
    if (formSaving) return
    setFormError('')

    if (!formFecha || !formHoraInicio || !formHoraFin) {
      setFormError('Completá fecha, hora de inicio y hora de fin.')
      return
    }
    if (formHoraInicio >= formHoraFin) {
      setFormError('La hora de inicio debe ser anterior a la hora de fin.')
      return
    }
    if (formHoraInicio < '09:00' || formHoraFin > '20:00') {
      setFormError('El horario debe estar entre las 09:00 y las 20:00.')
      return
    }

    setFormSaving(true)
    try {
      const payload = {
        profesional: Number(profesionalId),
        fecha: formFecha,
        hora_inicio: `${formHoraInicio}:00`,
        hora_fin: `${formHoraFin}:00`,
      }
      if (editandoId) {
        await api.patch(`/api/disponibilidades/${editandoId}/`, payload)
      } else {
        await api.post('/api/disponibilidades/', payload)
      }
      cerrarFormulario()
      setIntento((n) => n + 1)
    } catch (err) {
      // Errores del backend (p. ej. franjas que afectan turnos existentes)
      // llegan ya traducidos por api.js en err.message.
      setFormError(err.message || 'No se pudo guardar la disponibilidad.')
    } finally {
      setFormSaving(false)
    }
  }

  async function eliminarDisponibilidad(id) {
    const confirmado = window.confirm(
      '¿Estás segura de que querés eliminar esta disponibilidad?',
    )
    if (!confirmado) return
    setEliminandoId(id)
    try {
      await api.delete(`/api/disponibilidades/${id}/`)
      setIntento((n) => n + 1)
    } catch (err) {
      setDisponibilidadesError(err.message || 'No se pudo eliminar la disponibilidad.')
    } finally {
      setEliminandoId(null)
    }
  }

  // ---- Acceso restringido ----
  if (!esProfesional) {
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
                    Esta sección es solo para profesionales.
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
          <div className="col-12 col-lg-10">
            <div className="text-center mb-4">
              <h1 className="hn-section-title mb-1">✦ MI AGENDA ✦</h1>
              <p className="text-muted small mb-0">
                Gestioná tus horarios y consultá tus turnos asignados.
              </p>
            </div>

            {/* ---- Disponibilidades ---- */}
            <div className="mb-4">
              <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
                <h2 className="h5 fw-bold mb-0">Mis horarios de atención</h2>
                <div className="d-flex flex-wrap align-items-center gap-2">
                  <label htmlFor="hn-filtro-fecha" className="form-label mb-0 small">
                    Filtrar por fecha
                  </label>
                  <input
                    id="hn-filtro-fecha"
                    type="date"
                    className="form-control form-control-sm w-auto"
                    value={filtroFecha}
                    onChange={(e) => setFiltroFecha(e.target.value)}
                  />
                  {filtroFecha && (
                    <button
                      type="button"
                      className="btn btn-hn-outline btn-sm"
                      onClick={() => setFiltroFecha('')}
                    >
                      Limpiar
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-hn-dark btn-sm"
                    onClick={abrirCrear}
                    disabled={disponibilidadesLoading}
                  >
                    Agregar disponibilidad
                  </button>
                </div>
              </div>

              {disponibilidadesLoading && (
                <div className="card hn-card">
                  <div className="card-body text-center p-4">
                    <p className="text-muted small mb-0">Cargando disponibilidades…</p>
                  </div>
                </div>
              )}

              {!disponibilidadesLoading && disponibilidadesError && (
                <div className="card hn-card">
                  <div className="card-body text-center p-4">
                    <div className="alert alert-warning py-2 small" role="alert">
                      {disponibilidadesError}
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

              {!disponibilidadesLoading && !disponibilidadesError && disponibilidadesFiltradas.length === 0 && (
                <div className="card hn-card">
                  <div className="card-body text-center p-4">
                    <div className="display-4 mb-3">📅</div>
                    <h2 className="h5 fw-bold mb-2">
                      {filtroFecha ? 'Sin disponibilidades para esa fecha' : 'Sin horarios cargados'}
                    </h2>
                    <p className="small text-muted mb-0">
                      {filtroFecha
                        ? 'Probá con otra fecha o limpiá el filtro.'
                        : 'Agregá tu primer horario de atención.'}
                    </p>
                  </div>
                </div>
              )}

              {!disponibilidadesLoading && !disponibilidadesError && disponibilidadesFiltradas.length > 0 && (
                <div className="card hn-card">
                  <div className="card-body p-4">
                    <div className="table-responsive">
                      <table className="table table-hover mb-0">
                        <thead>
                          <tr>
                            <th>Fecha</th>
                            <th>Desde</th>
                            <th>Hasta</th>
                            <th className="text-end">Acciones</th>
                          </tr>
                        </thead>
                        <tbody>
                          {disponibilidadesFiltradas.map((d) => (
                            <tr key={d.id}>
                              <td>{formatearFecha(d.fecha)}</td>
                              <td>{formatearHora(d.hora_inicio)}</td>
                              <td>{formatearHora(d.hora_fin)}</td>
                              <td className="text-end">
                                <button
                                  type="button"
                                  className="btn btn-hn-outline btn-sm me-2"
                                  onClick={() => abrirEditar(d)}
                                  disabled={eliminandoId === d.id}
                                >
                                  Editar
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-hn-outline btn-sm text-danger"
                                  onClick={() => eliminarDisponibilidad(d.id)}
                                  disabled={eliminandoId === d.id}
                                >
                                  Eliminar
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* ---- Turnos asignados ---- */}
            <div className="mt-5">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h2 className="h5 fw-bold mb-0">Mis turnos asignados</h2>
              </div>

              {turnosLoading && (
                <div className="card hn-card">
                  <div className="card-body text-center p-4">
                    <p className="text-muted small mb-0">Cargando turnos…</p>
                  </div>
                </div>
              )}

              {!turnosLoading && turnosError && (
                <div className="card hn-card">
                  <div className="card-body text-center p-4">
                    <div className="alert alert-warning py-2 small" role="alert">
                      {turnosError}
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

              {!turnosLoading && !turnosError && turnos.length === 0 && (
                <div className="card hn-card">
                  <div className="card-body text-center p-4">
                    <div className="display-4 mb-3">📖</div>
                    <h2 className="h5 fw-bold mb-2">Sin turnos asignados</h2>
                    <p className="small text-muted mb-0">
                      Aún no tenés turnos asignados como profesional.
                    </p>
                  </div>
                </div>
              )}

              {!turnosLoading && !turnosError && turnos.length > 0 && (
                <div className="card hn-card">
                  <div className="card-body p-4">
                    <div className="table-responsive">
                      <table className="table table-hover mb-0">
                        <thead>
                          <tr>
                            <th>Fecha</th>
                            <th>Horario</th>
                            <th>Cliente</th>
                            <th>Servicio</th>
                            <th className="text-end">Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {turnos.map((t) => (
                            <tr key={t.id}>
                              <td>{formatearFecha(t.fecha)}</td>
                              <td>{formatearHora(t.hora)}</td>
                              <td>{nombreDeCliente(t)}</td>
                              <td>{nombreDeServicio(t.servicio)}</td>
                              <td className="text-end">
                                <span
                                  className={`badge ${ETIQUETA_COLOR[t.estado] || 'hn-badge-pink'}`}
                                >
                                  {ETIQUETA_ESTADO[t.estado] || t.estado}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* ---- Formulario de disponibilidad ---- */}
            {formOpen && (
              <div className="card hn-card mt-4">
                <div className="card-body p-4">
                  <h3 className="h6 fw-bold mb-3">
                    {editandoId ? 'Editar disponibilidad' : 'Nueva disponibilidad'}
                  </h3>
                  <form onSubmit={guardarDisponibilidad}>
                    {formError && (
                      <div className="alert alert-danger py-2 small" role="alert">
                        {formError}
                      </div>
                    )}
                    <div className="row g-3 mb-3">
                      <div className="col-12 col-md-4">
                        <label htmlFor="hn-disp-fecha" className="form-label">
                          Fecha
                        </label>
                        <input
                          id="hn-disp-fecha"
                          type="date"
                          className="form-control"
                          value={formFecha}
                          onChange={(e) => setFormFecha(e.target.value)}
                          required
                        />
                      </div>
                      <div className="col-12 col-md-4">
                        <label htmlFor="hn-disp-inicio" className="form-label">
                          Hora de inicio
                        </label>
                        <input
                          id="hn-disp-inicio"
                          type="time"
                          className="form-control"
                          value={formHoraInicio}
                          onChange={(e) => setFormHoraInicio(e.target.value)}
                          required
                        />
                      </div>
                      <div className="col-12 col-md-4">
                        <label htmlFor="hn-disp-fin" className="form-label">
                          Hora de fin
                        </label>
                        <input
                          id="hn-disp-fin"
                          type="time"
                          className="form-control"
                          value={formHoraFin}
                          onChange={(e) => setFormHoraFin(e.target.value)}
                          required
                        />
                      </div>
                    </div>
                    <div className="d-flex gap-2">
                      <button
                        type="submit"
                        className="btn btn-hn-dark w-auto"
                        disabled={formSaving}
                      >
                        {formSaving ? 'Guardando…' : 'Guardar'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-hn-outline w-auto"
                        onClick={cerrarFormulario}
                      >
                        Cancelar
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export default MiAgenda
