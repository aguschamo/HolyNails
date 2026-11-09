import { Navigate, Outlet, useLocation } from "react-router-dom"

import { useAuth } from "../context/AuthContext.jsx"

function ProfesionalRoute() {
  const { usuario, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return null
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (!usuario || !usuario.es_profesional) {
    return <Navigate to="/denegado" replace />
  }

  return <Outlet />
}

export default ProfesionalRoute

