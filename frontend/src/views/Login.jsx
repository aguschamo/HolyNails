import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'
import AuthModal from '../components/AuthModal.jsx'
import logo from '../assets/galeria/logo.png'

const RUTAS_CLIENTE = ['/agendar', '/mis-turnos', '/perfil']
const RUTAS_PERSONAL = ['/mi-agenda']

function Login() {
  const { login, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isLoading && isAuthenticated && !isSubmitting) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      const sesion = await login(email, password)
      // Destino por rol: ADMIN vuelve a su origen (o /admin) —incluido
      // el flujo de reservas al que accede desde B10.0.2, el panel y sus
      // subrutas /admin/* (B10.4), o /perfil—, PERSONAL a /mi-agenda y
      // CLIENTE a su flujo de reservas (o /).
      let destino = '/'
      if (sesion.role === 'admin') {
        const origenAdmin =
          from === '/admin' || (typeof from === 'string' && from.startsWith('/admin/'))
        destino = origenAdmin || RUTAS_CLIENTE.includes(from) ? from : '/'
      } else if (sesion.role === 'personal') {
        destino = RUTAS_PERSONAL.includes(from) ? from : '/mi-agenda'
      } else if (RUTAS_CLIENTE.includes(from)) {
        destino = from
      }
      // Éxito: NO se resetea isSubmitting. navigate() agenda la transición
      // de ruta y este componente se desmonta al confirmarse; un
      // setIsSubmitting(false) urgente acá provocaría un render en /login
      // donde el <Navigate to="/" /> de más arriba competiría con esa
      // transición pendiente y la ganaría (el usuario caería en la home
      // en lugar de su destino por rol).
      navigate(destino, { replace: true })
    } catch (err) {
      if (err.status === 0) {
        setError(err.message)
      } else if (err.status === 401) {
        setError('Credenciales incorrectas. Verificá tu correo y contraseña.')
      } else {
        setError(err.message || 'No se pudo iniciar sesión. Intentá nuevamente.')
      }
      // Solo en error: sin navegación pendiente, hay que reactivar el
      // formulario para corregir las credenciales.
      setIsSubmitting(false)
    }
  }

  function handleCerrar() {
    navigate('/', { replace: true })
  }

  return (
    <AuthModal
      ariaLabel="Iniciar sesión"
      closeLabel="Cerrar inicio de sesión"
      onClose={handleCerrar}
    >
      <h1 className="text-center mb-1">
        <img
          src={logo}
          alt="Holy Nails"
          className="hn-auth-logo"
          width={2000}
          height={2000}
        />
      </h1>
      <p className="text-center text-muted small mb-4">
        Iniciá sesión para reservar tus turnos
      </p>

      {error && (
        <div className="alert alert-danger py-2 small" role="alert">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <label htmlFor="loginEmail" className="form-label">
            Correo electrónico
          </label>
          <input
            id="loginEmail"
            type="email"
            className="form-control"
            placeholder="tucorreo@ejemplo.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>

        <div className="mb-4">
          <label htmlFor="loginPassword" className="form-label">
            Contraseña
          </label>
          <input
            id="loginPassword"
            type="password"
            className="form-control"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>

        <button
          type="submit"
          className="btn btn-hn-dark w-100"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Iniciando…' : 'Iniciar sesión'}
        </button>
      </form>

      <p className="small text-muted text-center mt-3 mb-0">
        ¿No tenés cuenta?{' '}
        <Link to="/register" className="fw-bold">
          Registrate
        </Link>
      </p>
    </AuthModal>
  )
}

export default Login
