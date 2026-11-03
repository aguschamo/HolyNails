import { Link } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'

function AccesoDenegado() {
  const { usuario, role } = useAuth()

  const destino = role === 'admin' ? '/admin' : '/perfil'

  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="row justify-content-center">
          <div className="col-12 col-md-8 col-lg-6">
            <div className="card hn-card">
              <div className="card-body text-center p-4">
                <div className="display-4 mb-3">🔒</div>
                <h1 className="h4 fw-bold mb-2">Acceso denegado</h1>
                <p className="small text-muted mb-4">
                  {usuario
                    ? `Tu cuenta tiene el rol "${role}" y no tiene permisos para ver esta sección.`
                    : 'Necesitás iniciar sesión para ver esta sección.'}
                </p>
                <div className="d-flex flex-wrap justify-content-center gap-2">
                  {usuario ? (
                    <Link to={destino} className="btn btn-hn-dark">
                      Ir a mi área
                    </Link>
                  ) : (
                    <Link to="/login" className="btn btn-hn-dark">
                      Iniciar sesión
                    </Link>
                  )}
                  <Link to="/" className="btn btn-hn-outline">
                    Volver a la home
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default AccesoDenegado