import { useEffect, useState } from 'react'

import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'
import { fetchTodosLosRecursos } from '../services/paginacion.js'

const CAMPOS_INICIALES = {
  nombre: '',
  username: '',
  email: '',
  password: '',
  nombre_profesional: '',
}

// Roles en lenguaje de la interfaz para el selector de cuentas (A3).
const ROL_TEXTO = {
  admin: 'Administración',
  personal: 'Personal',
  cliente: 'Cliente',
}

// Sección del panel admin para gestionar profesionales: listado, alta con
// cuenta de usuario (endpoint combinado), edición de nombre y activación /
// desactivación. El acceso depende del rol admin (la ruta ya está protegida
// por RoleRoute; acá se revalida de forma defensiva).
function AdminProfesionales() {
  const { role, isLoading } = useAuth()

  // ---- Listado ----
  const [profesionales, setProfesionales] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Cada incremento vuelve a disparar la carga (alta, edición, estado).
  const [intento, setIntento] = useState(0)

  // ---- Formulario crear / editar nombre ----
  const [formMode, setFormMode] = useState(null) // null | 'crear' | 'editar' | 'vincular'
  const [editandoId, setEditandoId] = useState(null)
  const [campos, setCampos] = useState(CAMPOS_INICIALES)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  // ---- Vincular cuenta existente (A3) ----
  const [cuentas, setCuentas] = useState([])
  const [cuentasLoading, setCuentasLoading] = useState(false)
  const [cuentasError, setCuentasError] = useState(null)
  const [intentoCuentas, setIntentoCuentas] = useState(0)
  const [cuentaId, setCuentaId] = useState('')

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
        const lista = await fetchTodosLosRecursos('/api/profesionales/')
        if (!cancelled) setProfesionales(lista)
      } catch (err) {
        if (!cancelled) {
          setProfesionales([])
          setError(err.message || 'No se pudieron cargar los profesionales.')
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

  // Cuentas disponibles para vincular: se cargan al abrir el panel de
  // asociación y se vuelven a pedir si se reintenta o tras una operación.
  useEffect(() => {
    if (formMode !== 'vincular') return
    let cancelled = false

    async function cargarCuentas() {
      setCuentasLoading(true)
      setCuentasError(null)
      try {
        const lista = await fetchTodosLosRecursos('/api/profesionales/cuentas-disponibles/')
        if (!cancelled) setCuentas(lista)
      } catch (err) {
        if (!cancelled) {
          setCuentas([])
          setCuentasError(err.message || 'No se pudieron cargar las cuentas disponibles.')
        }
      } finally {
        if (!cancelled) setCuentasLoading(false)
      }
    }

    cargarCuentas()
    return () => {
      cancelled = true
    }
  }, [formMode, intentoCuentas])

  function abrirCrear() {
    setFormMode('crear')
    setEditandoId(null)
    setCampos(CAMPOS_INICIALES)
    setFormError('')
    setMensaje('')
    setAccionError('')
  }

  function abrirEditar(p) {
    setFormMode('editar')
    setEditandoId(p.id)
    setCampos({ ...CAMPOS_INICIALES, nombre_profesional: p.nombre })
    setFormError('')
    setMensaje('')
    setAccionError('')
  }

  function abrirVincular(p) {
    setFormMode('vincular')
    setEditandoId(p.id)
    setCuentaId('')
    setCuentas([])
    setFormError('')
    setMensaje('')
    setAccionError('')
  }

  function cerrarFormulario() {
    setFormMode(null)
    setEditandoId(null)
    setCampos(CAMPOS_INICIALES)
    setFormError('')
    setCuentaId('')
    setCuentas([])
    setCuentasError(null)
  }

  function setCampo(nombre, valor) {
    setCampos((c) => ({ ...c, [nombre]: valor }))
  }

  async function guardar(e) {
    e.preventDefault()
    // Evita envíos duplicados mientras hay una operación en curso.
    if (saving) return
    setFormError('')

    // ---- Vincular cuenta existente (A3) ----
    if (formMode === 'vincular') {
      if (!cuentaId) {
        setFormError('Seleccioná una cuenta para asociar.')
        return
      }
      setSaving(true)
      try {
        // El backend valida que la cuenta no esté en otro profesional,
        // que el vínculo actual es inmutable y promueve CLIENTE→PERSONAL
        // (ADMIN conserva su rol). Los errores llegan en err.message.
        await api.patch(`/api/profesionales/${editandoId}/`, {
          usuario: Number(cuentaId),
        })
        cerrarFormulario()
        setMensaje('Cuenta asociada correctamente.')
        setIntento((n) => n + 1)
      } catch (err) {
        setFormError(err.message || 'No se pudo asociar la cuenta.')
      } finally {
        setSaving(false)
      }
      return
    }

    if (formMode === 'editar') {
      const nombre = campos.nombre_profesional.trim()
      if (!nombre) {
        setFormError('Ingresá el nombre de la profesional.')
        return
      }
      setSaving(true)
      try {
        await api.patch(`/api/profesionales/${editandoId}/`, { nombre })
        cerrarFormulario()
        setMensaje('Profesional actualizada correctamente.')
        setIntento((n) => n + 1)
      } catch (err) {
        setFormError(err.message || 'No se pudo guardar la profesional.')
      } finally {
        setSaving(false)
      }
      return
    }

    const faltan = ['nombre', 'username', 'email', 'password', 'nombre_profesional'].some(
      (k) => !campos[k].trim(),
    )
    if (faltan) {
      setFormError('Completá todos los campos.')
      return
    }

    setSaving(true)
    try {
      // Alta en una sola operación: el backend crea cuenta y vínculo.
      await api.post('/api/profesionales/crear-con-usuario/', {
        nombre: campos.nombre.trim(),
        username: campos.username.trim(),
        email: campos.email.trim(),
        password: campos.password,
        nombre_profesional: campos.nombre_profesional.trim(),
      })
      cerrarFormulario()
      setMensaje('Profesional creada correctamente.')
      setIntento((n) => n + 1)
    } catch (err) {
      // Errores de validación del backend (username/email duplicados,
      // contraseña débil, etc.) llegan ya traducidos en err.message.
      setFormError(err.message || 'No se pudo crear la profesional.')
    } finally {
      setSaving(false)
    }
  }

  async function cambiarEstado(p) {
    const activar = !p.is_active
    const confirmado = window.confirm(
      activar
        ? `¿Querés activar a ${p.nombre}?`
        : `¿Estás segura de que querés desactivar a ${p.nombre}?`,
    )
    if (!confirmado) return

    setMensaje('')
    setAccionError('')
    setCambiandoId(p.id)
    try {
      await api.patch(`/api/profesionales/${p.id}/`, { is_active: activar })
      setMensaje(
        activar
          ? 'Profesional activada correctamente.'
          : 'Profesional desactivada correctamente.',
      )
      setIntento((n) => n + 1)
    } catch (err) {
      setAccionError(err.message || 'No se pudo cambiar el estado de la profesional.')
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
              <h1 className="hn-section-title mb-1">✦ PROFESIONALES ✦</h1>
              <p className="text-muted small mb-0">
                Creá, editá y activá a las profesionales de Holy Nails.
              </p>
            </div>

            <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
              <h2 className="h5 fw-bold mb-0">Listado de profesionales</h2>
              <button
                type="button"
                className="btn btn-hn-dark btn-sm"
                onClick={abrirCrear}
                disabled={loading}
              >
                Nueva profesional
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
                  <p className="text-muted small mb-0">Cargando profesionales…</p>
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

            {!loading && !error && profesionales.length === 0 && (
              <div className="card hn-card">
                <div className="card-body text-center p-4">
                  <div className="display-4 mb-3">👩‍🎨</div>
                  <h3 className="h5 fw-bold mb-2">Sin profesionales cargados</h3>
                  <p className="small text-muted mb-0">
                    Cargá la primera profesional con su cuenta de usuario.
                  </p>
                </div>
              </div>
            )}

            {!loading && !error && profesionales.length > 0 && (
              <div className="card hn-card">
                <div className="card-body p-4">
                  <div className="table-responsive">
                    <table className="table table-hover mb-0">
                      <thead>
                        <tr>
                          <th>Profesional</th>
                          <th>Usuario</th>
                          <th>Estado</th>
                          <th className="text-end">Acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {profesionales.map((p) => (
                          <tr key={p.id}>
                            <td>{p.nombre}</td>
                            <td>
                              {p.usuario
                                ? `Usuario N° ${p.usuario}`
                                : 'Sin vincular'}
                            </td>
                            <td>
                              <span
                                className={`badge ${p.is_active ? 'hn-badge-success' : 'hn-badge-danger'}`}
                              >
                                {p.is_active ? 'Activo' : 'Inactivo'}
                              </span>
                            </td>
                            <td className="text-end">
                              <button
                                type="button"
                                className="btn btn-hn-outline btn-sm me-2"
                                onClick={() => abrirEditar(p)}
                                disabled={cambiandoId === p.id}
                              >
                                Editar
                              </button>
                              {!p.usuario && (
                                <button
                                  type="button"
                                  className="btn btn-hn-outline btn-sm me-2"
                                  onClick={() => abrirVincular(p)}
                                  disabled={cambiandoId === p.id}
                                >
                                  Vincular cuenta
                                </button>
                              )}
                              <button
                                type="button"
                                className={`btn btn-hn-outline btn-sm${p.is_active ? ' text-danger' : ''}`}
                                onClick={() => cambiarEstado(p)}
                                disabled={cambiandoId === p.id}
                              >
                                {p.is_active ? 'Desactivar' : 'Activar'}
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
                    {formMode === 'crear'
                      ? 'Nueva profesional'
                      : formMode === 'editar'
                        ? 'Editar profesional'
                        : `Asociar cuenta existente — ${profesionales.find((p) => p.id === editandoId)?.nombre || ''}`}
                  </h2>
                  <form onSubmit={guardar}>
                    {formError && (
                      <div className="alert alert-danger py-2 small" role="alert">
                        {formError}
                      </div>
                    )}
                    <div className="row g-3 mb-3">
                      {formMode === 'crear' && (
                        <>
                          <div className="col-12 col-md-6">
                            <label htmlFor="hn-prof-nombre" className="form-label">
                              Nombre de la cuenta
                            </label>
                            <input
                              id="hn-prof-nombre"
                              type="text"
                              className="form-control"
                              value={campos.nombre}
                              onChange={(e) => setCampo('nombre', e.target.value)}
                            />
                          </div>
                          <div className="col-12 col-md-6">
                            <label htmlFor="hn-prof-username" className="form-label">
                              Nombre de usuario
                            </label>
                            <input
                              id="hn-prof-username"
                              type="text"
                              className="form-control"
                              value={campos.username}
                              onChange={(e) => setCampo('username', e.target.value)}
                            />
                          </div>
                          <div className="col-12 col-md-6">
                            <label htmlFor="hn-prof-email" className="form-label">
                              Correo electrónico
                            </label>
                            <input
                              id="hn-prof-email"
                              type="email"
                              className="form-control"
                              value={campos.email}
                              onChange={(e) => setCampo('email', e.target.value)}
                            />
                          </div>
                          <div className="col-12 col-md-6">
                            <label htmlFor="hn-prof-password" className="form-label">
                              Contraseña
                            </label>
                            <input
                              id="hn-prof-password"
                              type="password"
                              className="form-control"
                              value={campos.password}
                              onChange={(e) => setCampo('password', e.target.value)}
                            />
                          </div>
                        </>
                      )}
                      {formMode === 'vincular' && (
                        <>
                      <div className="col-12">
                        <label htmlFor="hn-prof-cuenta" className="form-label">
                          Cuenta de usuario
                        </label>
                        {cuentasLoading && (
                          <p className="text-muted small mb-0">Cargando cuentas…</p>
                        )}
                        {!cuentasLoading && cuentasError && (
                          <div className="alert alert-warning py-2 small mb-0" role="alert">
                            {cuentasError}
                          </div>
                        )}
                        {!cuentasLoading && !cuentasError && cuentas.length === 0 && (
                          <div className="alert alert-warning py-2 small mb-0" role="alert">
                            No hay cuentas disponibles para vincular.
                          </div>
                        )}
                        {!cuentasLoading && !cuentasError && cuentas.length > 0 && (
                          <select
                            id="hn-prof-cuenta"
                            className="form-select"
                            value={cuentaId}
                            onChange={(e) => setCuentaId(e.target.value)}
                            disabled={saving}
                          >
                            <option value="">Seleccioná una cuenta…</option>
                            {cuentas.map((c) => (
                              <option key={c.id} value={c.id}>
                                {`${c.nombre || c.username} (@${c.username}) · ${c.email} · ${ROL_TEXTO[c.role] || c.role}${c.is_active ? '' : ' · inactiva'}`}
                              </option>
                            ))}
                          </select>
                        )}
                        {!cuentasLoading && cuentasError && (
                          <button
                            type="button"
                            className="btn btn-hn-outline btn-sm mt-2"
                            onClick={() => setIntentoCuentas((n) => n + 1)}
                          >
                            Reintentar
                          </button>
                        )}
                        <p className="form-text text-muted mb-0">
                          La cuenta quedará vinculada a esta profesional: si es
                          CLIENTE pasará a PERSONAL y una cuenta ADMIN conserva
                          su rol. No se crean cuentas ni se modifican contraseñas.
                        </p>
                      </div>
                    </>
                  )}
                  {formMode !== 'vincular' && (
                    <div className="col-12">
                      <label htmlFor="hn-prof-nombre-pro" className="form-label">
                        Nombre de la profesional
                      </label>
                      <input
                        id="hn-prof-nombre-pro"
                        type="text"
                        className="form-control"
                        value={campos.nombre_profesional}
                        onChange={(e) => setCampo('nombre_profesional', e.target.value)}
                      />
                    </div>
                  )}
                </div>
                    <div className="d-flex gap-2">
                      <button
                        type="submit"
                        className="btn btn-hn-dark w-auto"
                        disabled={saving}
                      >
                        {saving
                          ? formMode === 'crear'
                            ? 'Creando…'
                            : formMode === 'editar'
                              ? 'Guardando…'
                              : 'Asociando…'
                          : formMode === 'crear'
                            ? 'Crear profesional'
                            : formMode === 'editar'
                              ? 'Guardar'
                              : 'Asociar'}
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

export default AdminProfesionales
