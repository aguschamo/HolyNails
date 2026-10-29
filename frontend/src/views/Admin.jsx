import { Link } from 'react-router-dom'

const MODULOS = [
  { icono: '🗓️', titulo: 'Gestionar turnos', desc: 'Ver, confirmar y cancelar turnos de clientas.' },
  { icono: '💅', titulo: 'Gestionar servicios', desc: 'Alta, baja y modificación de servicios ofrecidos.' },
  { icono: '🕐', titulo: 'Horarios / disponibilidad', desc: 'Definir franjas horarias y días de atención.' },
  { icono: '👥', titulo: 'Clientas', desc: 'Administrar las cuentas de las clientas.' },
]

function Admin() {
  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="text-center mb-5">
          <h1 className="hn-section-title mb-1">✦ PANEL ADMINISTRATIVO ✦</h1>
          <p className="text-muted small mb-0">
            Gestión de Holy Nails
          </p>
        </div>

        <div className="row g-4">
          {MODULOS.map((m) => (
            <div className="col-12 col-md-6" key={m.titulo}>
              <div className="card hn-card border-0 shadow-sm h-100">
                <div className="card-body p-4">
                  <div className="hn-card-icon mb-2">{m.icono}</div>
                  <h2 className="h6 fw-bold mb-1">{m.titulo}</h2>
                  <p className="small text-muted mb-0">{m.desc}</p>
                  <p className="small text-secondary mt-2 mb-0">
                    Disponible al conectar la API (TP8).
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="text-center mt-5">
          <Link to="/perfil" className="btn btn-hn-outline rounded-pill fw-bold">
            VER MI PERFIL
          </Link>
        </div>
      </div>
    </section>
  )
}

export default Admin