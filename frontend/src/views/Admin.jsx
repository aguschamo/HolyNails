import { Link } from 'react-router-dom'

const MODULOS = [
  {
    icono: '🗓️',
    titulo: 'Gestionar turnos',
    desc: 'Ver, confirmar y cancelar turnos de clientas.',
    to: '/admin/turnos',
    cta: 'Gestionar turnos',
  },
  {
    icono: '💅',
    titulo: 'Gestionar servicios',
    desc: 'Alta, baja y modificación de servicios ofrecidos.',
    to: '/admin/servicios',
    cta: 'Gestionar servicios',
  },
  {
    icono: '👩‍🎨',
    titulo: 'Profesionales',
    desc: 'Crear, editar y activar profesionales con su cuenta de usuario.',
    to: '/admin/profesionales',
    cta: 'Gestionar profesionales',
  },
  {
    icono: '🕐',
    titulo: 'Horarios / disponibilidad',
    desc: 'Definir franjas horarias y días de atención.',
    to: '/admin/horarios',
    cta: 'Gestionar horarios',
  },
  {
    icono: '👥',
    titulo: 'Clientas',
    desc: 'Administrar las cuentas de las clientas.',
    to: '/admin/clientas',
    cta: 'Gestionar clientas',
  },
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
              <div className="card hn-card h-100">
                <div className="card-body p-4">
                  <div className="hn-card-icon mb-2">{m.icono}</div>
                  <h2 className="h6 fw-bold mb-1">{m.titulo}</h2>
                  <p className="small text-muted mb-0">{m.desc}</p>
                  <Link to={m.to} className="btn btn-hn-outline btn-sm mt-3">
                    {m.cta}
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="text-center mt-5">
          <Link to="/perfil" className="btn btn-hn-outline">
            Ver mi perfil
          </Link>
        </div>
      </div>
    </section>
  )
}

export default Admin