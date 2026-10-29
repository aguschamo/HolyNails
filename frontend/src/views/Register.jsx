import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'

function Register() {
  const { register, isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()

  const [nombre, setNombre] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isLoading && isAuthenticated) {
    return <Navigate to="/perfil" replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!nombre.trim()) {
      setError('El nombre es obligatorio.')
      return
    }
    if (!username.trim()) {
      setError('El nombre de usuario es obligatorio.')
      return
    }
    if (password !== confirmar) {
      setError('Las contraseñas no coinciden.')
      return
    }

    setIsSubmitting(true)
    try {
      await register({
        nombre: nombre.trim(),
        username: username.trim(),
        email: email.trim().toLowerCase(),
        password,
      })
      navigate('/login', { replace: true, state: { registroOk: true } })
    } catch (err) {
      if (err.status === 0) {
        setError(err.message)
      } else if (err.data && typeof err.data === 'object') {
        // Mostrar el primer error de campo devuelto por Django
        const firstKey = Object.keys(err.data)[0]
        if (firstKey && Array.isArray(err.data[firstKey])) {
          setError(err.data[firstKey][0])
        } else if (firstKey && typeof err.data[firstKey] === 'string') {
          setError(err.data[firstKey])
        } else {
          setError(err.message || 'No se pudo crear la cuenta.')
        }
      } else {
        setError(err.message || 'No se pudo crear la cuenta.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-vh-100 d-flex align-items-center hn-auth-bg py-5">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12 col-sm-8 col-md-6 col-lg-4">
            <div className="card hn-card border-0 shadow-sm p-4">
              <div className="card-body">
                <h1 className="hn-section-title fs-3 text-center mb-1">
                  holy nails ✨
                </h1>
                <p className="text-center text-muted small mb-4">
                  Creá tu cuenta de clienta para reservar turnos
                </p>

                {error && (
                  <div className="alert alert-danger py-2 small" role="alert">
                    {error}
                  </div>
                )}

                <form onSubmit={handleSubmit}>
                  <div className="mb-3">
                    <label htmlFor="registerNombre" className="form-label">
                      Nombre y apellido
                    </label>
                    <input
                      id="registerNombre"
                      type="text"
                      className="form-control"
                      placeholder="Tu nombre"
                      value={nombre}
                      onChange={(e) => setNombre(e.target.value)}
                      required
                      autoComplete="name"
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="registerUsername" className="form-label">
                      Nombre de usuario
                    </label>
                    <input
                      id="registerUsername"
                      type="text"
                      className="form-control"
                      placeholder="Elegí un usuario"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      autoComplete="username"
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="registerEmail" className="form-label">
                      Correo electrónico
                    </label>
                    <input
                      id="registerEmail"
                      type="email"
                      className="form-control"
                      placeholder="tucorreo@ejemplo.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      autoComplete="email"
                    />
                  </div>

                  <div className="mb-3">
                    <label htmlFor="registerPassword" className="form-label">
                      Contraseña
                    </label>
                    <input
                      id="registerPassword"
                      type="password"
                      className="form-control"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={8}
                      pattern="(?=.*[A-Za-z])(?=.*\d).{8,}"
                      title="Mínimo 8 caracteres, una letra y un número"
                      autoComplete="new-password"
                    />
                  </div>

                  <div className="mb-4">
                    <label htmlFor="registerConfirmar" className="form-label">
                      Repetí la contraseña
                    </label>
                    <input
                      id="registerConfirmar"
                      type="password"
                      className="form-control"
                      placeholder="••••••••"
                      value={confirmar}
                      onChange={(e) => setConfirmar(e.target.value)}
                      required
                      minLength={8}
                      pattern="(?=.*[A-Za-z])(?=.*\d).{8,}"
                      title="Mínimo 8 caracteres, una letra y un número"
                      autoComplete="new-password"
                    />
                  </div>

                  <button
                    type="submit"
                    className="btn btn-hn-dark w-100 fw-bold"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? 'CREANDO CUENTA…' : 'CREAR CUENTA'}
                  </button>
                </form>

                <p className="small text-muted text-center mt-3 mb-0">
                  ¿Ya tenés cuenta?{' '}
                  <Link to="/login" className="fw-bold">
                    Iniciá sesión
                  </Link>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Register
