import { Link } from 'react-router-dom'

function MisTurnos() {
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

            <div className="card hn-card border-0 shadow-sm p-4">
              <div className="card-body text-center py-4">
                <div className="display-4 mb-3">📖</div>
                <h2 className="h5 fw-bold mb-2">Todavía no tenés turnos</h2>
                <p className="small text-muted mb-4">
                  Cuando reserves, tus turnos van a aparecer acá. Esta vista se
                  conectará al backend en el TP8.
                </p>
                <Link to="/agendar" className="btn btn-hn-dark rounded-pill fw-bold">
                  AGENDAR TURNO ✨
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default MisTurnos