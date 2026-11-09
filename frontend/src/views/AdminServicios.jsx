import { useEffect, useState } from 'react'

import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import { formatearDuracion, formatearPrecio } from '../services/formato.js'
import { fetchTodosLosRecursos } from '../services/paginacion.js'

const CAMPOS_INICIALES = { nombre: '', precio: '', duracion: '' }

// DurationField del backend ("1:00:00" / "01:15:00") → "HH:MM" para
// el input[type=time] del formulario.
function duracionAInput(duracion) {
  if (!duracion) return ''
  const partes = String(duracion).split(':')
  if (partes.length < 2) return ''
  const h = Number.parseInt(partes[0], 10)
  const m = Number.parseInt(partes[1], 10)
  if (Number.isNaN(h) || Number.isNaN(m)) return ''
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

// Sección del panel admin para gestionar servicios (alta, edición y baja
// lógica vía is_active; no se usa DELETE). El listado usa el mismo
// endpoint que el catálogo, pero como admin trae también los inactivos.
// El acceso depende del rol admin (la ruta ya está protegida por RoleRoute;
// acá se revalida de forma defensiva).
function AdminServicios() {
  const { role, isLoading } = useAuth()

  // ---- Listado ----
  const [servicios, setServicios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Cada incremento vuelve a disparar la carga (alta, edición, estado).
  const [intento, setIntento] = useState(0)

  // ---- Formulario crear / editar ----
  const [formMode, setFormMode] = useState(null) // null | 'crear' | 'editar'
  const [editandoId, setEditandoId] = useState(null)
  const [campos, setCampos] = useState(CAMPOS_INICIALES)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  // ---- Avisos ----
  const [mensaje, setMensaje] = useState('')
  const [accionError, setAccionError] = useState('')
  const [cambiandoId, setCambiandoId] = useState(null)

  const esAdmin = role === 'admin'

  useEffect(() => {
    if (!esAdmin) return
    let cancelled = false

    async function cargar() {
      setLoading(true)
      setError(null)
      try {
        const lista = await fetchTodosLosRecursos('/api/servicios/')
        if (!cancelled) setServicios(lista)
      } catch (err) {
        if (!cancelled) {
          setServicios([])
          setError(err.message || 'No se pudieron cargar los servicios.')
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

  function abrirCrear() {
    setFormMode('crear')
    setEditandoId(null)
    setCampos(CAMPOS_INICIALES)
    setFormError('')
    setMensaje('')
    setAccionError('')
  }

  function abrirEditar(s) {
    setFormMode('editar')
    setEditandoId(s.id)
    setCampos({
      nombre: s.nombre,
      precio: s.precio ?? '',
      duracion: duracionAInput(s.duracion),
    })
    setFormError('')
    setMensaje('')
    setAccionError('')
  }

  function cerrarFormulario() {
    setFormMode(null)
    setEditandoId(null)
    setCampos(CAMPOS_INICIALES)
    setFormError('')
  }

  function setCampo(nombre, valor) {
    setCampos((c) => ({ ...c, [nombre]: valor }))
  }

  async function guardar(e) {
    e.preventDefault()
    // Evita envíos duplicados mientras hay una operación en curso.
    if (saving) return
    setFormError('')

    if (!campos.nombre.trim() || !campos.precio.trim() || !campos.duracion) {
      setFormError('Completá todos los campos.')
      return
    }
    const precio = Number(campos.precio)
    if (Number.isNaN(precio)) {
      setFormError('Ingresá un precio válido.')
      return
    }
    if (precio < 0) {
      setFormError('El precio no puede ser negativo.')
      return
    }
    if (campos.duracion === '00:00') {
      setFormError('La duración debe ser al menos 1 minuto.')
      return
    }

    const payload = {
      nombre: campos.nombre.trim(),
      precio: campos.precio.trim(),
      duracion: `${campos.duracion}:00`,
    }

    setSaving(true)
    try {
      if (formMode === 'editar') {
        await api.patch(`/api/servicios/${editandoId}/`, payload)
        cerrarFormulario()
        setMensaje('Servicio actualizado correctamente.')
      } else {
        await api.post('/api/servicios/', payload)
        cerrarFormulario()
        setMensaje('Servicio creado correctamente.')
      }
      setIntento((n) => n + 1)
    } catch (err) {
      // Errores de validación del backend llegan ya traducidos en err.message.
      setFormError(err.message || 'No se pudo guardar el servicio.')
    } finally {
      setSaving(false)
    }
  }

  async function cambiarEstado(s) {
    const activar = !s.is_active
    const confirmado = window.confirm(
      activar
        ? `¿Querés activar el servicio ${s.nombre}?`
        : `¿Estás segura de que querés dar de baja el servicio ${s.nombre}?`,
    )
    if (!confirmado) return

    setMensaje('')
    setAccionError('')
    setCambiandoId(s.id)
    try {
      // Baja lógica: nunca se usa DELETE sobre el servicio.
      await api.patch(`/api/servicios/${s.id}/`, { is_active: activar })
      setMensaje(
        activar
          ? 'Servicio activado correctamente.'
          : 'Servicio desactivado correctamente.',
      )
      setIntento((n) => n + 1)
    } catch (err) {
      setAccionError(err.message || 'No se pudo cambiar el estado del servicio.')
    } finally {
      setCambiandoId(null)
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
              <h1 className="hn-section-title mb-1">✦ SERVICIOS ✦</h1>
              <p className="text-muted small mb-0">
                Creá, editá y activá los servicios de Holy Nails.
              </p>
            </div>

            <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
              <h2 className="h5 fw-bold mb-0">Listado de servicios</h2>
              <button
                type="button"
                className="btn btn-hn-dark btn-sm"
                onClick={abrirCrear}
                disabled={loading}
              >
                Nuevo servicio
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
                  <p className="text-muted small mb-0">Cargando servicios…</p>
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

            {!loading && !error && servicios.length === 0 && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <div className="display-4 mb-3">💅</div>
                  <h3 className="h5 fw-bold mb-2">Sin servicios cargados</h3>
                  <p className="small text-muted mb-0">
                    Cargá el primer servicio con su precio y duración.
                  </p>
                </div>
              </div>
            )}

            {!loading && !error && servicios.length > 0 && (
              <div className="card hn-card">
                <div className="card-body p-4">
                  <div className="table-responsive">
                    <table className="table table-hover mb-0">
                      <thead>
                        <tr>
                          <th>Servicio</th>
                          <th>Precio</th>
                          <th>Duración</th>
                          <th>Estado</th>
                          <th className="text-end">Acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {servicios.map((s) => (
                          <tr key={s.id}>
                            <td>{s.nombre}</td>
                            <td>{formatearPrecio(s.precio)}</td>
                            <td>{formatearDuracion(s.duracion)}</td>
                            <td>
                              <span
                                className={`badge ${s.is_active ? 'hn-badge-success' : 'hn-badge-danger'}`}
                              >
                                {s.is_active ? 'Activo' : 'Inactivo'}
                              </span>
                            </td>
                            <td className="text-end">
                              <button
                                type="button"
                                className="btn btn-hn-outline btn-sm me-2"
                                onClick={() => abrirEditar(s)}
                                disabled={cambiandoId === s.id}
                              >
                                Editar
                              </button>
                              <button
                                type="button"
                                className={`btn btn-hn-outline btn-sm${s.is_active ? ' text-danger' : ''}`}
                                onClick={() => cambiarEstado(s)}
                                disabled={cambiandoId === s.id}
                              >
                                {s.is_active ? 'Desactivar' : 'Activar'}
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

            {/* ---- Formulario crear / editar ---- */}
            {formMode && (
              <div className="card hn-card mt-4">
                <div className="card-body p-4">
                  <h2 className="h6 fw-bold mb-3">
                    {formMode === 'editar' ? 'Editar servicio' : 'Nuevo servicio'}
                  </h2>
                  <form onSubmit={guardar}>
                    {formError && (
                      <div className="alert alert-danger py-2 small" role="alert">
                        {formError}
                      </div>
                    )}
                    <div className="row g-3 mb-3">
                      <div className="col-12 col-md-4">
                        <label htmlFor="serv-nombre" className="form-label">
                          Nombre del servicio
                        </label>
                        <input
                          id="serv-nombre"
                          type="text"
                          className="form-control"
                          value={campos.nombre}
                          onChange={(e) => setCampo('nombre', e.target.value)}
                        />
                      </div>
                      <div className="col-12 col-md-4">
                        <label htmlFor="serv-precio" className="form-label">
                          Precio
                        </label>
                        <input
                          id="serv-precio"
                          type="number"
                          step="0.01"
                          className="form-control"
                          value={campos.precio}
                          onChange={(e) => setCampo('precio', e.target.value)}
                        />
                      </div>
                      <div className="col-12 col-md-4">
                        <label htmlFor="serv-duracion" className="form-label">
                          Duración
                        </label>
                        <input
                          id="serv-duracion"
                          type="time"
                          className="form-control"
                          value={campos.duracion}
                          onChange={(e) => setCampo('duracion', e.target.value)}
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
                            : 'Crear servicio'}
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

export default AdminServicios
