import { useEffect, useMemo, useState } from 'react'

import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import { fetchTodosLosRecursos } from '../services/paginacion.js'

const CAMPOS_INICIALES = {
  profesional: '',
  fecha: '',
  hora_inicio: '',
  hora_fin: '',
}

const FILTROS_INICIALES = {
  profesional: '',
  desde: '',
  hasta: '',
}

// Mismos límites que el backend (HORARIO_INICIO / HORARIO_FIN) y que el
// formulario de MiAgenda: el cliente evita enviar franjas inválidas y el
// backend sigue siendo la autoridad final.
const HORARIO_MIN = '09:00'
const HORARIO_MAX = '20:00'

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

// Filtros del listado administrativo (B10.2): se aplican sobre la
// consulta general ya cargada y se combinan entre sí. `desde`/`hasta`
// comparan la fecha ISO (YYYY-MM-DD) lexicográficamente, que coincide con
// el orden cronológico.
function filtrarDisponibilidades(lista, { profesional, desde, hasta }) {
  return lista.filter((d) => {
    if (profesional && String(d.profesional) !== String(profesional)) return false
    if (desde && d.fecha < desde) return false
    if (hasta && d.fecha > hasta) return false
    return true
  })
}

// Sección del panel admin para gestionar horarios / disponibilidades
// (B10.2): listado de todas las franjas del salón con filtros por
// profesional y período, alta, edición y baja con confirmación. Usa los
// endpoints existentes de /api/disponibilidades/; el backend es la
// autoridad de permisos y validaciones. La ruta está protegida por
// RoleRoute; acá se revalida de forma defensiva.
function AdminHorarios() {
  const { role, isLoading } = useAuth()

  // ---- Listado ----
  const [disponibilidades, setDisponibilidades] = useState([])
  const [profesionales, setProfesionales] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Cada incremento vuelve a disparar la carga (tras una operación y con
  // el botón "Reintentar").
  const [intento, setIntento] = useState(0)

  // ---- Filtros ----
  const [filtros, setFiltros] = useState(FILTROS_INICIALES)

  // ---- Formulario crear / editar ----
  const [formMode, setFormMode] = useState(null)
  const [editandoId, setEditandoId] = useState(null)
  const [campos, setCampos] = useState(CAMPOS_INICIALES)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  // ---- Mensajes de acciones ----
  const [mensaje, setMensaje] = useState('')
  const [accionError, setAccionError] = useState('')
  const [eliminandoId, setEliminandoId] = useState(null)

  const esAdmin = role === 'admin'

  useEffect(() => {
    if (!esAdmin) return
    let cancelled = false

    async function cargar() {
      setLoading(true)
      setError(null)
      try {
        // Consulta general de ADMIN (el backend devuelve todas las
        // franjas para este rol) y el catálogo de profesionales para
        // resolver nombres y alimentar el filtro.
        const [lista, listaProfesionales] = await Promise.all([
          fetchTodosLosRecursos('/api/disponibilidades/'),
          fetchTodosLosRecursos('/api/profesionales/'),
        ])
        if (!cancelled) {
          setDisponibilidades(lista)
          setProfesionales(listaProfesionales)
        }
      } catch (err) {
        if (!cancelled) {
          setDisponibilidades([])
          setError(err.message || 'No se pudieron cargar las disponibilidades.')
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

  const filtradas = useMemo(
    () => filtrarDisponibilidades(disponibilidades, filtros),
    [disponibilidades, filtros],
  )

  const hayFiltros = Object.values(filtros).some((v) => v !== '')

  function setFiltro(nombre, valor) {
    setFiltros((f) => ({ ...f, [nombre]: valor }))
  }

  function limpiarFiltros() {
    setFiltros(FILTROS_INICIALES)
  }

  function setCampo(nombre, valor) {
    setCampos((c) => ({ ...c, [nombre]: valor }))
  }

  function nombreDeProfesional(id) {
    if (id === null || id === undefined) return 'Sin profesional'
    const profesional = profesionales.find((p) => p.id === id)
    return profesional ? profesional.nombre : `Profesional N° ${id}`
  }

  // ---- Formulario ----
  function abrirCrear() {
    setFormMode('crear')
    setEditandoId(null)
    setCampos(CAMPOS_INICIALES)
    setFormError('')
  }

  function abrirEditar(d) {
    setFormMode('editar')
    setEditandoId(d.id)
    setCampos({
      profesional: String(d.profesional),
      fecha: d.fecha,
      hora_inicio: formatearHora(d.hora_inicio),
      hora_fin: formatearHora(d.hora_fin),
    })
    setFormError('')
  }

  function cerrarFormulario() {
    setFormMode(null)
    setEditandoId(null)
    setCampos(CAMPOS_INICIALES)
    setFormError('')
  }

  async function guardar(e) {
    e.preventDefault()
    // Evita envíos duplicados mientras hay una operación en curso.
    if (saving) return
    setFormError('')

    if (!campos.profesional || !campos.fecha || !campos.hora_inicio || !campos.hora_fin) {
      setFormError('Completá profesional, fecha, hora de inicio y hora de fin.')
      return
    }
    if (campos.hora_inicio >= campos.hora_fin) {
      setFormError('La hora de inicio debe ser anterior a la hora de fin.')
      return
    }
    if (campos.hora_inicio < HORARIO_MIN || campos.hora_fin > HORARIO_MAX) {
      setFormError('El horario debe estar entre las 09:00 y las 20:00.')
      return
    }

    setSaving(true)
    try {
      const payload = {
        profesional: Number(campos.profesional),
        fecha: campos.fecha,
        hora_inicio: `${campos.hora_inicio}:00`,
        hora_fin: `${campos.hora_fin}:00`,
      }
      if (formMode === 'editar') {
        await api.patch(`/api/disponibilidades/${editandoId}/`, payload)
        cerrarFormulario()
        setMensaje('Disponibilidad actualizada correctamente.')
      } else {
        await api.post('/api/disponibilidades/', payload)
        cerrarFormulario()
        setMensaje('Disponibilidad creada correctamente.')
      }
      setIntento((n) => n + 1)
    } catch (err) {
      // Errores de validación del backend (solape, horario, turnos que
      // dependen de la franja) llegan traducidos en err.message.
      setFormError(err.message || 'No se pudo guardar la disponibilidad.')
    } finally {
      setSaving(false)
    }
  }

  // ---- Eliminar con confirmación ----
  async function eliminar(d) {
    const confirmado = window.confirm(
      `¿Estás segura de que querés eliminar el horario de ${nombreDeProfesional(
        d.profesional,
      )} del ${formatearFecha(d.fecha)} (${formatearHora(d.hora_inicio)} a las ${formatearHora(
        d.hora_fin,
      )})?`,
    )
    if (!confirmado) return

    setMensaje('')
    setAccionError('')
    setEliminandoId(d.id)
    try {
      await api.delete(`/api/disponibilidades/${d.id}/`)
      setMensaje('Disponibilidad eliminada correctamente.')
      setIntento((n) => n + 1)
    } catch (err) {
      setAccionError(err.message || 'No se pudo eliminar la disponibilidad.')
    } finally {
      setEliminandoId(null)
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
          <div className="col-12 col-lg-10">
            <div className="text-center mb-4">
              <h1 className="hn-section-title mb-1">✦ HORARIOS ✦</h1>
              <p className="text-muted small mb-0">
                Definí las franjas de atención de cada profesional.
              </p>
            </div>

            <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
              <h2 className="h5 fw-bold mb-0">Disponibilidades cargadas</h2>
              <button
                type="button"
                className="btn btn-hn-dark btn-sm"
                onClick={abrirCrear}
                disabled={loading}
              >
                Nuevo horario
              </button>
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
                  <p className="text-muted small mb-0">Cargando disponibilidades…</p>
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

            {!loading && !error && disponibilidades.length === 0 && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <div className="display-4 mb-3">🕐</div>
                  <h3 className="h5 fw-bold mb-2">Sin horarios cargados</h3>
                  <p className="small text-muted mb-0">
                    Cargá la primera franja de atención para empezar a recibir turnos.
                  </p>
                </div>
              </div>
            )}

            {!loading && !error && disponibilidades.length > 0 && (
              <div className="card hn-card">
                <div className="card-body p-4">
                  {/* ---- Filtros combinables ---- */}
                  <div className="row g-3 mb-3">
                    <div className="col-12 col-md-4">
                      <label
                        htmlFor="hor-filtro-profesional"
                        className="form-label small"
                      >
                        Filtrar por profesional
                      </label>
                      <select
                        id="hor-filtro-profesional"
                        className="form-select form-select-sm"
                        value={filtros.profesional}
                        onChange={(e) => setFiltro('profesional', e.target.value)}
                      >
                        <option value="">Todos</option>
                        {profesionales.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.nombre}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-6 col-md-4">
                      <label htmlFor="hor-filtro-desde" className="form-label small">
                        Desde
                      </label>
                      <input
                        id="hor-filtro-desde"
                        type="date"
                        className="form-control form-control-sm"
                        value={filtros.desde}
                        onChange={(e) => setFiltro('desde', e.target.value)}
                      />
                    </div>
                    <div className="col-6 col-md-4">
                      <label htmlFor="hor-filtro-hasta" className="form-label small">
                        Hasta
                      </label>
                      <input
                        id="hor-filtro-hasta"
                        type="date"
                        className="form-control form-control-sm"
                        value={filtros.hasta}
                        onChange={(e) => setFiltro('hasta', e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
                    <span className="small text-muted mb-0">
                      {filtradas.length === disponibilidades.length
                        ? `${disponibilidades.length} ${
                            disponibilidades.length === 1 ? 'franja' : 'franjas'
                          }`
                        : `Mostrando ${filtradas.length} de ${disponibilidades.length} franjas`}
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

                  {filtradas.length === 0 && (
                    <div className="text-center py-4">
                      <p className="small text-muted mb-2">
                        No hay disponibilidades para los filtros seleccionados.
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

                  {filtradas.length > 0 && (
                    <div className="table-responsive">
                      <table className="table table-hover mb-0">
                        <thead>
                          <tr>
                            <th>Profesional</th>
                            <th>Día</th>
                            <th>Inicio</th>
                            <th>Fin</th>
                            <th className="text-end">Acciones</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filtradas.map((d) => (
                            <tr key={d.id}>
                              <td>{nombreDeProfesional(d.profesional)}</td>
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
                                  onClick={() => eliminar(d)}
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
                  )}
                </div>
              </div>
            )}

            {/* ---- Formulario crear / editar ---- */}
            {formMode && (
              <div className="card hn-card mt-4">
                <div className="card-body p-4">
                  <h2 className="h6 fw-bold mb-3">
                    {formMode === 'editar' ? 'Editar horario' : 'Nuevo horario'}
                  </h2>
                  <form onSubmit={guardar}>
                    {formError && (
                      <div className="alert alert-danger py-2 small" role="alert">
                        {formError}
                      </div>
                    )}
                    <div className="row g-3 mb-3">
                      <div className="col-12 col-md-3">
                        <label htmlFor="hor-profesional" className="form-label">
                          Profesional
                        </label>
                        <select
                          id="hor-profesional"
                          className="form-select"
                          value={campos.profesional}
                          onChange={(e) => setCampo('profesional', e.target.value)}
                        >
                          <option value="">Elegí un profesional</option>
                          {profesionales.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.nombre}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="col-12 col-md-3">
                        <label htmlFor="hor-fecha" className="form-label">
                          Fecha
                        </label>
                        <input
                          id="hor-fecha"
                          type="date"
                          className="form-control"
                          value={campos.fecha}
                          onChange={(e) => setCampo('fecha', e.target.value)}
                        />
                      </div>
                      <div className="col-6 col-md-3">
                        <label htmlFor="hor-inicio" className="form-label">
                          Hora de inicio
                        </label>
                        <input
                          id="hor-inicio"
                          type="time"
                          className="form-control"
                          value={campos.hora_inicio}
                          onChange={(e) => setCampo('hora_inicio', e.target.value)}
                        />
                      </div>
                      <div className="col-6 col-md-3">
                        <label htmlFor="hor-fin" className="form-label">
                          Hora de fin
                        </label>
                        <input
                          id="hor-fin"
                          type="time"
                          className="form-control"
                          value={campos.hora_fin}
                          onChange={(e) => setCampo('hora_fin', e.target.value)}
                        />
                      </div>
                    </div>
                    <div className="d-flex gap-2">
                      <button
                        type="submit"
                        className="btn btn-hn-dark w-auto"
                        disabled={saving}
                      >
                        {saving
                          ? 'Guardando…'
                          : formMode === 'editar'
                            ? 'Guardar'
                            : 'Crear horario'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-hn-outline w-auto"
                        onClick={cerrarFormulario}
                        disabled={saving}
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

export default AdminHorarios
