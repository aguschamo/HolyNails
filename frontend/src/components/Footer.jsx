import { Link } from 'react-router-dom'

function irASeccion(id) {
  let intentos = 0
  const intentar = () => {
    const seccion = document.getElementById(id)
    if (seccion) {
      seccion.scrollIntoView({ behavior: 'smooth' })
    } else if (intentos < 20) {
      intentos += 1
      setTimeout(intentar, 50)
    }
  }
  setTimeout(intentar, 0)
}

function Footer() {
  return (
    <footer className="hn-footer py-5 mt-auto">
      <div className="container">
        <div className="row g-4 text-center text-md-start align-items-center">
          <div className="col-12 col-md-4">
            <Link to="/" className="font-gothic text-white fs-1 text-decoration-none d-block mb-1">
              holy nails ✨
            </Link>
            <p className="text-secondary small mb-0">
              Estética cute & dark. Manicura y Nail Art exclusivo.
            </p>
          </div>

          <div className="col-12 col-md-4 text-center">
            <ul className="list-inline mb-2">
              <li className="list-inline-item mx-2">
                <Link to="/" className="small fw-semibold">INICIO</Link>
              </li>
              <li className="list-inline-item mx-2">
                <Link to="/#servicios" className="small fw-semibold" onClick={() => irASeccion('servicios')}>SERVICIOS</Link>
              </li>
              <li className="list-inline-item mx-2">
                <Link to="/#galeria" className="small fw-semibold" onClick={() => irASeccion('galeria')}>GALERÍA</Link>
              </li>
              <li className="list-inline-item mx-2">
                <Link to="/#contacto" className="small fw-semibold" onClick={() => irASeccion('contacto')}>CONTACTO</Link>
              </li>
            </ul>
            <p className="text-secondary small mb-0">
              Atención con turnos previos. Consultá disponibilidad.
            </p>
          </div>

          <div className="col-12 col-md-4 text-center text-md-end">
            <p className="small text-secondary mb-0">
              © 2025 Holy Nails. Todos los derechos reservados.
            </p>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default Footer
