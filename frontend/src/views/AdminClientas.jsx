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

// Sección del panel admin para gestionar las cuentas CLIENTE (B10.3):
// listado con búsqueda por nombre y email, detalle con el historial de
// turnos de la clienta, y activación / desactivación de la cuenta con
// confirmación. El backend es la autoridad: acá solo se muestran las
// cuentas que devuelve /api/clientas/ (rol CLIENTE) y sus errores se
// propagan a la vista. La ruta está protegida por RoleRoute; acá se
// revalida de forma defensiva.
function AdminClientas() {
  const { role, isLoading } = useAuth()

  // ---- Listado ----
  const [clientas, setClientas] = useState([])
  const [servicios, setServicios] = useState([])
  const [profesionales, setProfesionales] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Cada incremento vuelve a disparar la carga (tras una operación y con
  // el botón "Reintentar").
  const [intento, setIntento] = useState(0)

  // ---- Búsqueda ----
  const [buscar, setBuscar] = useState('')

  // ---- Detalle e historial ----
  const [seleccionadaId, setSeleccionadaId] = useState(null)
  const [detalle, setDetalle] = useState(null)
  const [historial, setHistorial] = useState([])
  const [cargandoDetalle, setCargandoDetalle] = useState(false)
  const [errorDetalle, setErrorDetalle] = useState(null)
  const [intentoDetalle, setIntentoDetalle] = useState(0)

  // ---- Mensajes de acciones ----
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
        // Consulta general de ADMIN (sólo cuentas CLIENTE según el
        // backend) más los catálogos para resolver servicio y
        // profesional en el historial.
        const [lista, listaServicios, listaProfesionales] = await Promise.all([
          fetchTodosLosRecursos('/api/clientas/'),
          fetchTodosLosRecursos('/api/servicios/'),
          fetchTodosLosRecursos('/api/profesionales/'),
        ])
        if (!cancelled) {
          setClientas(lista)
          setServicios(listaServicios)
          setProfesionales(listaProfesionales)
        }
      } catch (err) {
        if (!cancelled) {
          setClientas([])
          setError(err.message || 'No se pudieron cargar las clientas.')
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

  useEffect(() => {
    if (!esAdmin || seleccionadaId === null) return
    let cancelled = false

    async function cargar() {
      setCargandoDetalle(true)
      setErrorDetalle(null)
      try {
        // Ficha de la clienta + su historial acotado en el backend.
        const [datos, turnos] = await Promise.all([
          api.get(`/api/clientas/${seleccionadaId}/`),
          fetchTodosLosRecursos(`/api/clientas/${seleccionadaId}/turnos/`),
        ])
        if (!cancelled) {
          setDetalle(datos)
          setHistorial(turnos)
        }
      } catch (err) {
        if (!cancelled) {
          setDetalle(null)
          setHistorial([])
          setErrorDetalle(err.message || 'No se pudo cargar la clienta.')
        }
      } finally {
        if (!cancelled) setCargandoDetalle(false)
      }
    }

    cargar()
    return () => {
      cancelled = true
    }
  }, [esAdmin, seleccionadaId, intentoDetalle])

  // Búsqueda por nombre o email sobre la lista completa ya cargada.
  const filtradas = useMemo(() => {
    const texto = buscar.trim().toLowerCase()
    if (!texto) return clientas
    return clientas.filter((c) => {
      const nombre = String(c.nombre || '').toLowerCase()
      const email = String(c.email || '').toLowerCase()
      return nombre.includes(texto) || email.includes(texto)
    })
  }, [clientas, buscar])

  function nombreDeCliente(c) {
    return c.nombre || c.username || `Clienta N° ${c.id}`
  }

  function nombreDeServicio(id) {
    if (id === null || id === undefined) return 'Servicio no disponible'
    const servicio = servicios.find((s) => s.id === id)
    return servicio ? servicio.nombre : `Servicio N° ${id}`
  }

  function nombreDeProfesional(id) {
    if (id === null || id === undefined) return 'Sin profesional'
    const profesional = profesionales.find((p) => p.id === id)
    return profesional ? profesional.nombre : `Profesional N° ${id}`
  }

  // ---- Detalle ----
  function abrirDetalle(c) {
    setMensaje('')
    setAccionError('')
    setSeleccionadaId(c.id)
  }

  function volverAlListado() {
    setSeleccionadaId(null)
    setDetalle(null)
    setHistorial([])
    setErrorDetalle(null)
  }

  // ---- Activación / desactivación ----
  async function cambiarEstado(c, activar) {
    if (!activar) {
      const texto = `¿Estás segura de que querés desactivar la cuenta de ${nombreDeCliente(
        c,
      )} (${c.email})? Podés volver a activarla cuando quieras.`
      if (!window.confirm(texto)) return
    }

    setMensaje('')
    setAccionError('')
    setAccionandoId(c.id)
    try {
      // Baja lógica: is_active, nunca borrado físico. El backend valida
      // que la cuenta sea CLIENTE y que no sea la propia.
      await api.patch(`/api/clientas/${c.id}/`, { is_active: activar })
      setMensaje(
        activar
          ? 'Cuenta activada correctamente.'
          : 'Cuenta desactivada correctamente.',
      )
      // Refresco del listado (y de la ficha si está abierta).
      setIntento((n) => n + 1)
      if (seleccionadaId === c.id) setIntentoDetalle((n) => n + 1)
    } catch (err) {
      // Errores de permisos o de validación del backend llegan ya
      // traducidos en err.message.
      setAccionError(err.message || 'No se pudo actualizar la cuenta.')
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

  const viendoDetalle = seleccionadaId !== null

  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="row justify-content-center">
          <div className="col-12">
            <div className="text-center mb-4">
              <h1 className="hn-section-title mb-1">✦ CLIENTAS ✦</h1>
              <p className="text-muted small mb-0">
                Consultá las cuentas de las clientas y su historial de turnos.
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

            {!viendoDetalle && (
              <>
                {loading && (
                  <div className="card hn-card">
                    <div className="card-body text-center p-4">
                      <p className="text-muted small mb-0">Cargando clientas…</p>
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

                {!loading && !error && clientas.length === 0 && (
                  <div className="card hn-card">
                    <div className="card-body text-center p-4">
                      <div className="display-4 mb-3">👥</div>
                      <h2 className="h5 fw-bold mb-2">No hay clientas registradas</h2>
                      <p className="small text-muted mb-0">
                        Cuando alguien se registre como clienta, su cuenta va a
                        aparecer acá.
                      </p>
                    </div>
                  </div>
                )}

                {!loading && !error && clientas.length > 0 && (
                  <div className="card hn-card">
                    <div className="card-body p-4">
                      <div className="row g-3 mb-3">
                        <div className="col-12 col-md-6">
                          <label htmlFor="clientas-buscar" className="form-label small">
                            Buscar clienta
                          </label>
                          <input
                            id="clientas-buscar"
                            type="search"
                            className="form-control form-control-sm"
                            placeholder="Nombre o email"
                            value={buscar}
                            onChange={(e) => setBuscar(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
                        <span className="small text-muted mb-0">
                          {filtradas.length === clientas.length
                            ? `${clientas.length} ${
                                clientas.length === 1 ? 'clienta' : 'clientas'
                              }`
                            : `Mostrando ${filtradas.length} de ${clientas.length} clientas`}
                        </span>
                        <button
                          type="button"
                          className="btn btn-hn-outline btn-sm"
                          onClick={() => setBuscar('')}
                          disabled={buscar === ''}
                        >
                          Limpiar búsqueda
                        </button>
                      </div>

                      {filtradas.length === 0 && (
                        <div className="text-center py-4">
                          <p className="small text-muted mb-2">
                            No hay clientas para la búsqueda seleccionada.
                          </p>
                          <button
                            type="button"
                            className="btn btn-hn-outline btn-sm"
                            onClick={() => setBuscar('')}
                          >
                            Limpiar búsqueda
                          </button>
                        </div>
                      )}

                      {filtradas.length > 0 && (
                        <div className="table-responsive">
                          <table className="table table-hover mb-0">
                            <thead>
                              <tr>
                                <th>Clienta</th>
                                <th>Email</th>
                                <th>Cuenta</th>
                                <th>Estado</th>
                                <th className="text-end">Acciones</th>
                              </tr>
                            </thead>
                            <tbody>
                              {filtradas.map((c) => (
                                <tr key={c.id}>
                                  <td>{nombreDeCliente(c)}</td>
                                  <td>{c.email}</td>
                                  <td>{c.username}</td>
                                  <td>
                                    <span
                                      className={`badge ${
                                        c.is_active ? 'hn-badge-success' : 'hn-badge-danger'
                                      }`}
                                    >
                                      {c.is_active ? 'Activa' : 'Desactivada'}
                                    </span>
                                  </td>
                                  <td className="text-end">
                                    <button
                                      type="button"
                                      className="btn btn-hn-outline btn-sm me-2"
                                      onClick={() => abrirDetalle(c)}
                                      disabled={accionandoId === c.id}
                                    >
                                      Ver detalle
                                    </button>
                                    <button
                                      type="button"
                                      className={`btn btn-hn-outline btn-sm ${
                                        c.is_active ? 'text-danger' : ''
                                      }`}
                                      onClick={() => cambiarEstado(c, !c.is_active)}
                                      disabled={accionandoId === c.id}
                                    >
                                      {accionandoId === c.id
                                        ? 'Actualizando…'
                                        : c.is_active
                                          ? 'Desactivar'
                                          : 'Activar'}
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
              </>
            )}

            {viendoDetalle && (
              <>
                <div className="d-flex justify-content-start mb-3">
                  <button
                    type="button"
                    className="btn btn-hn-outline btn-sm"
                    onClick={volverAlListado}
                    disabled={cargandoDetalle}
                  >
                    Volver al listado
                  </button>
                </div>

                {cargandoDetalle && (
                  <div className="card hn-card">
                    <div className="card-body text-center p-4">
                      <p className="text-muted small mb-0">Cargando la ficha…</p>
                    </div>
                  </div>
                )}

                {!cargandoDetalle && errorDetalle && (
                  <div className="card hn-card">
                    <div className="card-body text-center p-4">
                      <div className="alert alert-warning py-2 small" role="alert">
                        {errorDetalle}
                      </div>
                      <button
                        type="button"
                        className="btn btn-hn-outline"
                        onClick={() => setIntentoDetalle((n) => n + 1)}
                      >
                        Reintentar
                      </button>
                    </div>
                  </div>
                )}

                {!cargandoDetalle && !errorDetalle && detalle && (
                  <>
                    <div className="card hn-card mb-4">
                      <div className="card-body p-4">
                        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
                          <h2 className="h5 fw-bold mb-0">Detalle de la clienta</h2>
                          <span
                            className={`badge ${
                              detalle.is_active ? 'hn-badge-success' : 'hn-badge-danger'
                            }`}
                          >
                            {detalle.is_active ? 'Activa' : 'Desactivada'}
                          </span>
                        </div>
                        <div className="row g-3 mb-3">
                          <div className="col-12 col-md-6">
                            <p className="small text-muted mb-1">Nombre</p>
                            <p className="fw-bold mb-0">
                              {nombreDeCliente(detalle)}
                            </p>
                          </div>
                          <div className="col-12 col-md-6">
                            <p className="small text-muted mb-1">Email</p>
                            <p className="fw-bold mb-0">{detalle.email}</p>
                          </div>
                          <div className="col-12 col-md-6">
                            <p className="small text-muted mb-1">Usuario</p>
                            <p className="fw-bold mb-0">{detalle.username}</p>
                          </div>
                        </div>
                        <button
                          type="button"
                          className={`btn btn-hn-outline btn-sm ${
                            detalle.is_active ? 'text-danger' : ''
                          }`}
                          onClick={() => cambiarEstado(detalle, !detalle.is_active)}
                          disabled={accionandoId === detalle.id}
                        >
                          {accionandoId === detalle.id
                            ? 'Actualizando…'
                            : detalle.is_active
                              ? 'Desactivar'
                              : 'Activar'}
                        </button>
                      </div>
                    </div>

                    <div className="card hn-card">
                      <div className="card-body p-4">
                        <h2 className="h5 fw-bold mb-3">Historial de turnos</h2>

                        {historial.length === 0 && (
                          <p className="small text-muted mb-0">
                            Esta clienta todavía no tiene turnos.
                          </p>
                        )}

                        {historial.length > 0 && (
                          <div className="table-responsive">
                            <table className="table table-hover mb-0">
                              <thead>
                                <tr>
                                  <th>Fecha</th>
                                  <th>Hora</th>
                                  <th>Servicio</th>
                                  <th>Profesional</th>
                                  <th>Estado</th>
                                </tr>
                              </thead>
                              <tbody>
                                {historial.map((t) => (
                                  <tr key={t.id}>
                                    <td>{formatearFecha(t.fecha)}</td>
                                    <td>{formatearHora(t.hora)}</td>
                                    <td>{nombreDeServicio(t.servicio)}</td>
                                    <td>{nombreDeProfesional(t.profesional)}</td>
                                    <td>
                                      <span
                                        className={`badge ${
                                          COLOR_ESTADO[t.estado] || 'hn-badge-pink'
                                        }`}
                                      >
                                        {ETIQUETA_ESTADO[t.estado] || t.estado}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export default AdminClientas
