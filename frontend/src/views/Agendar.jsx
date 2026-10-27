import { useState } from 'react'

import { Link } from 'react-router-dom'

import agendarTurnoImg from '../assets/galeria/agendar-turno.png'

function fechaDeHoy() {
  const hoy = new Date()
  const anio = hoy.getFullYear()
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  const dia = String(hoy.getDate()).padStart(2, '0')
  return `${anio}-${mes}-${dia}`
}

function Agendar() {
  const [servicio, setServicio] = useState('')
  const [fecha, setFecha] = useState('')
  const [hora, setHora] = useState('')
  const [aviso, setAviso] = useState(false)
  const [error, setError] = useState('')

  function handleSubmit(e) {
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
    setAviso(true)
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
                    La reserva se conectará al backend en el TP8. Por ahora solo
                    queda registrada la vista.
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
                    >
                      <option value="" disabled>
                        Seleccioná un servicio...
                      </option>
                      <option>SEMIPERMANENTE</option>
                      <option>KAPPING</option>
                      <option>ESCULPIDAS</option>
                    </select>
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

                  <button type="submit" className="btn btn-hn-dark w-100">
                    Reservar turno
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