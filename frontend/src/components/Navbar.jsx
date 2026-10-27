import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import logo from '../assets/galeria/logo.png'
import { useAuth } from '../context/AuthContext.jsx'
import Avatar from './Avatar.jsx'

function Navbar() {
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [cuentaAbierta, setCuentaAbierta] = useState(false)
  const { usuario, role, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const pendienteInicio = useRef(false)
  const cuentaRef = useRef(null)
  const cuentaTriggerRef = useRef(null)

  function cerrarMenu() {
    setMenuAbierto(false)
    setCuentaAbierta(false)
  }

  useEffect(() => {
    if (pendienteInicio.current && location.pathname === '/') {
      pendienteInicio.current = false
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [location.pathname])

  useEffect(() => {
    if (!cuentaAbierta) return

    function alPulsarFuera(e) {
      if (cuentaRef.current && !cuentaRef.current.contains(e.target)) {
        setCuentaAbierta(false)
      }
    }

    function alTeclar(e) {
      if (e.key === 'Escape') {
        setCuentaAbierta(false)
        cuentaTriggerRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', alPulsarFuera)
    document.addEventListener('keydown', alTeclar)
    return () => {
      document.removeEventListener('mousedown', alPulsarFuera)
      document.removeEventListener('keydown', alTeclar)
    }
  }, [cuentaAbierta])

  function irInicio(e) {
    cerrarMenu()
    if (location.pathname === '/') {
      e.preventDefault()
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      pendienteInicio.current = true
    }
  }

  function irASeccion(id) {
    cerrarMenu()
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

  function handleLogout() {
    setCuentaAbierta(false)
    logout()
    navigate('/login', { replace: true })
  }

  const enlaces = (
    <ul className="navbar-nav mx-auto mb-2 mb-lg-0 align-items-center">
      <li className="nav-item">
        <Link className="nav-link hn-nav-link" to="/" onClick={irInicio}>
          Inicio
        </Link>
      </li>
      <li className="nav-item">
        <Link className="nav-link hn-nav-link" to="/#servicios" onClick={() => irASeccion('servicios')}>
          Servicios
        </Link>
      </li>
      <li className="nav-item">
        <Link className="nav-link hn-nav-link" to="/#galeria" onClick={() => irASeccion('galeria')}>
          Galería
        </Link>
      </li>
      <li className="nav-item">
        <Link className="nav-link hn-nav-link" to="/#contacto" onClick={() => irASeccion('contacto')}>
          Contacto
        </Link>
      </li>

      {usuario && role === 'admin' && (
        <li className="nav-item">
          <Link className="nav-link hn-nav-link" to="/admin" onClick={cerrarMenu}>
            Panel admin
          </Link>
        </li>
      )}
    </ul>
  )

  return (
    <nav className="navbar navbar-expand-lg sticky-top hn-navbar">
      <div className="container">
        <Link className="navbar-brand hn-brand" to="/" onClick={irInicio}>
          <img
            src={logo}
            alt="Holy Nails"
            width={118}
            height={118}
            className="hn-brand-logo"
          />
        </Link>

        {/* Agendar turno: siempre visible en la barra superior */}
        <Link
          to={usuario ? '/agendar' : '/login'}
          className="btn btn-hn-dark"
          onClick={cerrarMenu}
        >
          Agendar turno
        </Link>

        <button
          className="navbar-toggler border-0"
          type="button"
          aria-controls="hnNavbarMenu"
          aria-expanded={menuAbierto}
          aria-label={menuAbierto ? 'Cerrar navegación' : 'Abrir navegación'}
          onClick={() => setMenuAbierto((prev) => !prev)}
        >
          <span className="navbar-toggler-icon"></span>
        </button>

        <div className={`collapse navbar-collapse${menuAbierto ? ' show' : ''}`} id="hnNavbarMenu">
          {enlaces}

          {/* Acceso a cuenta / autenticación dentro del menú colapsable */}
          {usuario ? (
            <div className="hn-account mt-2" ref={cuentaRef}>
              <button
                type="button"
                ref={cuentaTriggerRef}
                className="hn-account-trigger"
                aria-haspopup="true"
                aria-expanded={cuentaAbierta}
                aria-controls="hnAccountMenu"
                aria-label={`Menú de cuenta de ${usuario.nombre}`}
                onClick={() => setCuentaAbierta((prev) => !prev)}
              >
                <span aria-hidden="true">
                  <Avatar nombre={usuario.nombre} photo={usuario.photo} size="sm" />
                </span>
                <span className="hn-account-name">{usuario.nombre}</span>
                <svg
                  className="hn-account-chevron"
                  aria-hidden="true"
                  focusable="false"
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M2.5 4.5 6 8l3.5-3.5" />
                </svg>
              </button>

              {cuentaAbierta && (
                <div className="hn-account-menu" id="hnAccountMenu">
                  <Link
                    to="/perfil"
                    className="hn-account-item"
                    onClick={() => setCuentaAbierta(false)}
                  >
                    Mi perfil
                  </Link>
                  <Link
                    to="/mis-turnos"
                    className="hn-account-item"
                    onClick={() => setCuentaAbierta(false)}
                  >
                    Mis turnos
                  </Link>
                  <hr className="hn-account-sep" />
                  <button
                    type="button"
                    className="hn-account-item hn-account-logout"
                    onClick={handleLogout}
                  >
                    Cerrar sesión
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Link to="/login" className="hn-nav-link" onClick={cerrarMenu}>
                Iniciar sesión
              </Link>
              <Link to="/register" className="hn-nav-link" onClick={cerrarMenu}>
                Registrarme
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}

export default Navbar
