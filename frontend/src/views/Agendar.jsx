import { useState, useEffect } from 'react'

import { Link } from 'react-router-dom'

import agendarTurnoImg from '../assets/galeria/agendar-turno.png'
import { useServicios } from '../hooks/useServicios.js'
import { api } from '../services/api.js'
import { mensajeDeReserva } from '../services/mensajesReserva.js'
import { fetchTodosLosRecursos } from '../services/paginacion.js'
import { formatearDuracion, formatearPrecio } from '../services/formato.js'

function fechaDeHoy() {
  const hoy = new Date()
  const anio = hoy.getFullYear()
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  const dia = String(hoy.getDate()).padStart(2, '0')
  return `${anio}-${mes}-${dia}`
}

function pasosActivos(pasoActual) {
  const pasos = ['servicio', 'fecha', 'profesional', 'horario', 'confirmacion']
  return pasos.filter((p) => pasos.indexOf(p) <= pasos.indexOf(pasoActual))
}

function Agendar() {
  const [paso, setPaso] = useState('servicio')
  const [servicioId, setServicioId] = useState('')
  const [servicioSeleccionado, setServicioSeleccionado] = useState(null)
  const [fecha, setFecha] = useState('')
  const [profesionales, setProfesionales] = useState([])
  const [profesionalId, setProfesionalId] = useState('')
  const [horarios, setHorarios] = useState([])
  const [horaSeleccionada, setHoraSeleccionada] = useState('')
  const [reserva, setReserva] = useState(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [cargandoProfesionales, setCargandoProfesionales] = useState(false)
  const [cargandoHorarios, setCargandoHorarios] = useState(false)

  const {
    servicios,
    loading: serviciosLoading,
    error: serviciosError,
  } = useServicios()

  const sinServicios = !serviciosLoading && !serviciosError && servicios.length === 0

  // Paso 2: al elegir servicio y fecha, consultar profesionales disponibles.
  useEffect(() => {
    if (!servicioId || !fecha) return
    let cancelled = false

    Promise.resolve().then(async () => {
      setCargandoProfesionales(true)
      setProfesionales([])
      setProfesionalId('')
      setHorarios([])
      setHoraSeleccionada('')
      setError('')
      try {
        // Listado paginado (PAGE_SIZE=10): se recorren todas las páginas
        // para no mostrar sólo los primeros 10 profesionales (A2).
        const lista = await fetchTodosLosRecursos('/api/profesionales/')
        if (!cancelled) {
          const activos = lista.filter((p) => p.is_active)
          setProfesionales(activos)
          if (activos.length === 0) {
            setError('No hay profesionales disponibles para este servicio en la fecha seleccionada.')
          }
          setPaso('profesional')
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'No se pudieron cargar los profesionales.')
          setPaso('fecha')
        }
      } finally {
        if (!cancelled) setCargandoProfesionales(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [servicioId, fecha])

  // Paso 4: al elegir profesional, consultar horarios disponibles.
  useEffect(() => {
    if (!servicioId || !fecha || !profesionalId) return
    let cancelled = false

    Promise.resolve().then(async () => {
      setCargandoHorarios(true)
      setHorarios([])
      setHoraSeleccionada('')
      setError('')
      try {
        const url = `/api/turnos/disponibles/?servicio=${servicioId}&fecha=${fecha}&profesional=${profesionalId}`
        const data = await api.get(url)
        if (!cancelled) {
          const lista = Array.isArray(data) ? data : (Array.isArray(data.results) ? data.results : [])
          setHorarios(lista)
          if (lista.length === 0) {
            setError('No hay horarios disponibles para este profesional en la fecha seleccionada.')
          } else {
            setError('')
          }
          setPaso('horario')
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'No se pudieron cargar los horarios disponibles.')
          setPaso('profesional')
        }
      } finally {
        if (!cancelled) setCargandoHorarios(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [servicioId, fecha, profesionalId])

  function handleSeleccionarServicio(e) {
    const id = e.target.value
    if (!id) return
    setServicioId(id)
    const servicio = servicios.find((s) => String(s.id) === id)
    setServicioSeleccionado(servicio ?? null)
    setFecha('')
    setProfesionalId('')
    setHorarios([])
    setHoraSeleccionada('')
    setError('')
    setPaso('fecha')
  }

  function handleSeleccionarFecha(e) {
    const valor = e.target.value
    if (!valor) return
    setFecha(valor)
    setProfesionalId('')
    setHorarios([])
    setHoraSeleccionada('')
    setError('')
  }

  function handleSeleccionarProfesional(e) {
    const id = e.target.value
    if (!id) return
    setProfesionalId(id)
    setHorarios([])
    setHoraSeleccionada('')
    setError('')
  }

  function handleSeleccionarHora(e) {
    const valor = e.target.value
    if (!valor) return
    setHoraSeleccionada(valor)
    setError('')
  }

  async function handleReservar(e) {
    e.preventDefault()
    setError('')
    if (enviando) return
    if (!servicioId || !fecha || !profesionalId || !horaSeleccionada) {
      setError('Completá todos los pasos para continuar.')
      return
    }

    setEnviando(true)
    try {
      const data = await api.post('/api/turnos/', {
        fecha,
        hora: horaSeleccionada,
        servicio: Number(servicioId),
        profesional: Number(profesionalId),
      })
      const profesional = profesionales.find((p) => String(p.id) === profesionalId)
      setReserva({
        id: data.id,
        fecha: data.fecha,
        hora: data.hora,
        servicio: servicioSeleccionado,
        profesional,
        estado: data.estado,
      })
      setPaso('confirmacion')
    } catch (err) {
      // El detalle específico del backend se conserva; sólo se recurre a
      // un texto propio si es técnico (401) o no hay mensaje (A5).
      setError(mensajeDeReserva(err))
      // Ante un 400 se reconsulta la grilla: el horario elegido puede
      // haber cambiado (p. ej. tomado por otra persona), lo que habilita
      // el reintento. Si la reconsulta falla, el mensaje del error
      // original sigue visible y no se produce un rechazo sin manejar.
      if (err?.status === 400 && servicioId && fecha && profesionalId) {
        const url = `/api/turnos/disponibles/?servicio=${servicioId}&fecha=${fecha}&profesional=${profesionalId}`
        api.get(url)
          .then((data) => {
            const lista = Array.isArray(data) ? data : (Array.isArray(data.results) ? data.results : [])
            setHorarios(lista)
            setHoraSeleccionada('')
          })
          .catch(() => {})
      }
    } finally {
      setEnviando(false)
    }
  }

  function volverAPaso(anterior) {
    setError('')
    setPaso(anterior)
  }

  function reiniciar() {
    setPaso('servicio')
    setServicioId('')
    setServicioSeleccionado(null)
    setFecha('')
    setProfesionales([])
    setProfesionalId('')
    setHorarios([])
    setHoraSeleccionada('')
    setReserva(null)
    setError('')
  }

  // ---------- Renderizado por paso ----------
  const servicio = servicioSeleccionado || (servicios.find((s) => String(s.id) === servicioId) || null)

  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="row justify-content-center">
          <div className="col-12 col-md-8 col-lg-6">
            <div className="text-center mb-4">
              <h1 className="hn-section-title hn-page-title mb-1">
                <img
                  src={agendarTurnoImg}
                  alt="Agendar turno"
                  className="hn-page-title-img"
                />
              </h1>
              <p className="text-muted small mb-0">
                Elegí el servicio, la fecha, la profesional y el horario
              </p>
            </div>

            <div className="mb-4">
              {pasosActivos(paso).map((p) => {
                const labels = {
                  servicio: 'Servicio',
                  fecha: 'Fecha',
                  profesional: 'Profesional',
                  horario: 'Horario',
                  confirmacion: 'Reserva',
                }
                const activo = p === paso
                return (
                  <span
                    key={p}
                    className={`d-inline-block me-2 ${activo ? 'fw-bold' : 'text-muted'}`}
                  >
                    {activo ? '✦' : '○'} {labels[p]}
                  </span>
                )
              })}
            </div>

            <div className="card hn-card">
              <div className="card-body p-4">
                {error && (
                  <div className="alert alert-danger py-2 small" role="alert">
                    {error}
                  </div>
                )}

                {serviciosError && (
                  <div className="alert alert-warning py-2 small" role="alert">
                    {serviciosError}
                  </div>
                )}

                {/* Paso 1: Servicio */}
                {paso === 'servicio' && (
                  <>
                    {sinServicios && (
                      <div className="alert alert-warning py-2 small text-center" role="alert">
                        No hay servicios disponibles por el momento.
                      </div>
                    )}
                    <form onSubmit={(e) => e.preventDefault()}>
                      <div className="mb-3">
                        <label htmlFor="agendarServicio" className="form-label">
                          Servicio
                        </label>
                        <select
                          id="agendarServicio"
                          data-testid="agendarServicio"
                          className="form-select"
                          value={servicioId}
                          onChange={handleSeleccionarServicio}
                          required
                          disabled={serviciosLoading || sinServicios}
                        >
                          <option value="" disabled>
                            {serviciosLoading
                              ? 'Cargando servicios…'
                              : 'Seleccioná un servicio...'}
                          </option>
                          {servicios.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.nombre}
                            </option>
                          ))}
                        </select>
                      </div>
                    </form>
                    {servicio && !sinServicios && !serviciosLoading && (
                      <div className="text-center mt-3">
                        <button
                          type="button"
                          className="btn btn-hn-dark w-100"
                          onClick={() => setPaso('fecha')}
                        >
                          Elegir fecha
                        </button>
                      </div>
                    )}
                  </>
                )}

                {/* Paso 2: Fecha */}
                {paso === 'fecha' && servicio && (
                  <>
                    <div className="mb-3">
                      <label htmlFor="agendarServicioActual" className="form-label">
                        Servicio seleccionado
                      </label>
                      <input
                        id="agendarServicioActual"
                        className="form-control"
                        value={`${servicio.nombre} · ${formatearPrecio(servicio.precio)} · ${formatearDuracion(servicio.duracion)}`}
                        readOnly
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="agendarFecha" className="form-label">
                        Fecha
                      </label>
                      <input
                        id="agendarFecha"
                        data-testid="agendarFecha"
                        type="date"
                        className="form-control"
                        min={fechaDeHoy()}
                        value={fecha}
                        onChange={handleSeleccionarFecha}
                        required
                      />
                    </div>
                    <div className="d-grid gap-2">
                      <button
                        type="button"
                        className="btn btn-hn-outline"
                        onClick={() => volverAPaso('servicio')}
                      >
                        Volver
                      </button>
                      {fecha && (
                        <button
                          type="button"
                          className="btn btn-hn-dark w-auto"
                          disabled={cargandoProfesionales}
                          onClick={() => setPaso('profesional')}
                        >
                          {cargandoProfesionales ? 'Cargando profesionales…' : 'Elegir profesional'}
                        </button>
                      )}
                    </div>
                  </>
                )}

                {/* Paso 3: Profesional */}
                {paso === 'profesional' && servicio && (
                  <>
                    <div className="mb-3">
                      <label htmlFor="agendarFechaActual" className="form-label">
                        Fecha seleccionada
                      </label>
                      <input
                        id="agendarFechaActual"
                        className="form-control"
                        value={fecha}
                        readOnly
                      />
                    </div>
                    {cargandoProfesionales && (
                      <div className="text-center mb-3">
                        <p className="text-muted small mb-0">Cargando profesionales…</p>
                      </div>
                    )}
                    {!cargandoProfesionales && profesionales.length === 0 && !error && (
                      <div className="alert alert-warning py-2 small text-center" role="alert">
                        No hay profesionales disponibles para esta fecha.
                      </div>
                    )}
                    {!cargandoProfesionales && profesionales.length > 0 && (
                      <div className="mb-3">
                        <label htmlFor="agendarProfesional" className="form-label">
                          Profesional
                        </label>
                        <select
                          id="agendarProfesional"
                          data-testid="agendarProfesional"
                          className="form-select"
                          value={profesionalId}
                          onChange={handleSeleccionarProfesional}
                          required
                        >
                          <option value="" disabled>
                            Seleccioná una profesional…
                          </option>
                          {profesionales.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.nombre}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    <div className="d-grid gap-2">
                      <button
                        type="button"
                        className="btn btn-hn-outline"
                        onClick={() => volverAPaso('fecha')}
                      >
                        Volver
                      </button>
                      {profesionalId && !cargandoProfesionales && (
                        <button
                          type="button"
                          className="btn btn-hn-dark w-auto"
                          disabled={cargandoHorarios}
                          onClick={() => setPaso('horario')}
                        >
                          {cargandoHorarios ? 'Cargando horarios…' : 'Elegir horario'}
                        </button>
                      )}
                    </div>
                  </>
                )}

                {/* Paso 4: Horario */}
                {paso === 'horario' && servicio && (
                  <>
                    <div className="mb-3">
                      <label htmlFor="agendarProfesionalActual" className="form-label">
                        Profesional seleccionado
                      </label>
                      <input
                        id="agendarProfesionalActual"
                        className="form-control"
                        value={profesionales.find((p) => String(p.id) === profesionalId)?.nombre || ''}
                        readOnly
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="agendarFechaActual2" className="form-label">
                        Fecha seleccionada
                      </label>
                      <input
                        id="agendarFechaActual2"
                        className="form-control"
                        value={fecha}
                        readOnly
                      />
                    </div>
                    {cargandoHorarios && (
                      <div className="text-center mb-3">
                        <p className="text-muted small mb-0">Cargando horarios disponibles…</p>
                      </div>
                    )}
                    {!cargandoHorarios && horarios.length === 0 && !error && (
                      <div className="alert alert-warning py-2 small text-center" role="alert">
                        No hay horarios disponibles para esta profesional en la fecha seleccionada.
                      </div>
                    )}
                    {!cargandoHorarios && horarios.length > 0 && (
                      <div className="mb-3">
                        <label htmlFor="agendarHora" className="form-label">
                          Horario disponible
                        </label>
                        <select
                          id="agendarHora"
                          data-testid="agendarHora"
                          className="form-select"
                          value={horaSeleccionada}
                          onChange={handleSeleccionarHora}
                          required
                        >
                          <option value="" disabled>
                            Seleccioná un horario…
                          </option>
                          {horarios.map((h) => (
                            <option key={`${h.fecha} ${h.hora}`} value={h.hora}>
                              {h.hora}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    <div className="d-grid gap-2">
                      <button
                        type="button"
                        className="btn btn-hn-outline"
                        onClick={() => volverAPaso('profesional')}
                      >
                        Volver
                      </button>
                      {horaSeleccionada && !cargandoHorarios && (
                        <button
                          type="button"
                          className="btn btn-hn-dark w-auto"
                          disabled={enviando}
                          onClick={handleReservar}
                        >
                          {enviando ? 'Enviando…' : 'Reservar turno'}
                        </button>
                      )}
                    </div>
                  </>
                )}

                {/* Paso 5: Confirmación */}
                {paso === 'confirmacion' && reserva && (
                  <>
                    <div className="text-center mb-4">
                      <div className="display-4 mb-3">✦</div>
                      <h2 className="h5 fw-bold mb-2">Reserva enviada</h2>
                      <p className="text-muted small mb-0">
                        Tu turno quedó registrado y está pendiente de confirmación.
                      </p>
                    </div>

                    <div className="mb-4">
                      <table className="table table-borderless">
                        <tbody>
                          <tr>
                            <td className="fw-bold" width="30%">Servicio</td>
                            <td>{reserva.servicio?.nombre || '—'}</td>
                          </tr>
                          <tr>
                            <td className="fw-bold" width="30%">Profesional</td>
                            <td>{reserva.profesional?.nombre || '—'}</td>
                          </tr>
                          <tr>
                            <td className="fw-bold" width="30%">Fecha</td>
                            <td>{reserva.fecha}</td>
                          </tr>
                          <tr>
                            <td className="fw-bold" width="30%">Hora</td>
                            <td>{reserva.hora}</td>
                          </tr>
                          <tr>
                            <td className="fw-bold" width="30%">Duración</td>
                            <td>{formatearDuracion(reserva.servicio?.duracion)}</td>
                          </tr>
                          <tr>
                            <td className="fw-bold" width="30%">Precio</td>
                            <td>{formatearPrecio(reserva.servicio?.precio)}</td>
                          </tr>
                          <tr>
                            <td className="fw-bold" width="30%">Estado</td>
                            <td>
                              <span className="badge hn-badge-pink">
                                {reserva.estado === 'pendiente' ? 'Pendiente' : reserva.estado}
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div className="d-grid gap-2">
                      <Link to="/mis-turnos" className="btn btn-hn-dark w-100">
                        Ver mis turnos
                      </Link>
                      <Link to="/" className="btn btn-hn-outline w-100">
                        Volver al inicio
                      </Link>
                    </div>
                    <div className="text-center mt-3">
                      <button
                        type="button"
                        className="btn btn-hn-outline btn-sm"
                        onClick={reiniciar}
                      >
                        Reservar otro turno
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>

            <p className="small text-center text-muted mt-3 mb-0">
              ¿Ya tenés turnos?{' '}
              <Link to="/mis-turnos" className="fw-bold">
                Ver mis turnos
              </Link>
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

export default Agendar