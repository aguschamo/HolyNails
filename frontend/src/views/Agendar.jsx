import { useState } from 'react'

import { Link } from 'react-router-dom'

import agendarTurnoImg from '../assets/galeria/agendar-turno.png'
import { useServicios } from '../hooks/useServicios.js'
import { api } from '../services/api.js'

function fechaDeHoy() {
  const hoy = new Date()
  const anio = hoy.getFullYear()
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  const dia = String(hoy.getDate()).padStart(2, '0')
  return `${anio}-${mes}-${dia}`
}

function Agendar() {
  // `servicio` guarda el ID del catálogo (no el nombre): es lo que el
  // backend espera en el campo `servicio` de POST /api/turnos/.
  const [servicio, setServicio] = useState('')
  const [fecha, setFecha] = useState('')
  const [hora, setHora] = useState('')
  const [aviso, setAviso] = useState(false)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const {
    servicios,
    loading: serviciosLoading,
    error: serviciosError,
  } = useServicios()

  const sinServicios = !serviciosLoading && !serviciosError && servicios.length === 0

  async function handleSubmit(e) {
    e.preventDefault()
    setAviso(false)
    setError('')

    if (fecha < fechaDeHoy()) {
      setError('La fecha no puede ser anterior a hoy.')
      return
    }
    if (hora < '09:00' || hora > '20:00') {
      setError('Fecha u hora fuera del horario de atención (09:00 a 20:00).')
      return
    }
    if (!servicio) {
      setError('Seleccioná un servicio para continuar.')
      return
    }
    if (enviando) return

    setEnviando(true)
    try {
      await api.post('/api/turnos/', {
        fecha,
        hora,
        servicio: Number(servicio),
      })
      // Sólo se confirma después de una respuesta exitosa del backend.
      setAviso(true)
      setServicio('')
      setFecha('')
      setHora('')
    } catch (err) {
      setError(err.message || 'No se pudo registrar la reserva.')
    } finally {
      setEnviando(false)
    }
  }

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
                Elegí el servicio que quieras y el momento que te quede cómodo
              </p>
            </div>

            <div className="card hn-card">
              <div className="card-body p-4">
                {error && (
                  <div className="alert alert-danger py-2 small" role="alert">
                    {error}
                  </div>
                )}

                {aviso && (
                  <div className="alert alert-info py-2 small" role="alert">
                    Reserva registrada correctamente. Está pendiente de
                    confirmación.
                  </div>
                )}

                {serviciosError && (
                  <div className="alert alert-warning py-2 small" role="alert">
                    {serviciosError}
                  </div>
                )}

                <form onSubmit={handleSubmit}>
                  <div className="mb-3">
                    <label htmlFor="agendarServicio" className="form-label">
                      Servicio
                    </label>
                    <select
                      id="agendarServicio"
                      className="form-select"
                      value={servicio}
                      onChange={(e) => setServicio(e.target.value)}
                      required
                      disabled={serviciosLoading || servicios.length === 0}
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
                    {sinServicios && (
                      <div className="form-text text-muted">
                        No hay servicios disponibles por el momento.
                      </div>
                    )}
                  </div>

                  <div className="row g-3 mb-4">
                    <div className="col-12 col-sm-6">
                      <label htmlFor="agendarFecha" className="form-label">
                        Fecha
                      </label>
                      <input
                        id="agendarFecha"
                        type="date"
                        className="form-control"
                        min={fechaDeHoy()}
                        value={fecha}
                        onChange={(e) => setFecha(e.target.value)}
                        required
                      />
                    </div>
                    <div className="col-12 col-sm-6">
                      <label htmlFor="agendarHora" className="form-label">
                        Hora
                      </label>
                      <input
                        id="agendarHora"
                        type="time"
                        className="form-control"
                        min="09:00"
                        max="20:00"
                        step="900"
                        value={hora}
                        onChange={(e) => setHora(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-hn-dark w-100"
                    disabled={enviando || serviciosLoading || servicios.length === 0}
                  >
                    {enviando ? 'Enviando…' : 'Reservar turno'}
                  </button>
                </form>

                <p className="small text-center text-muted mt-3 mb-0">
                  ¿Ya tenés turnos?{' '}
                  <Link to="/mis-turnos" className="fw-bold">
                    Ver mis turnos
                  </Link>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default Agendar