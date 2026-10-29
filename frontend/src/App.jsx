import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import RoleRoute from './components/RoleRoute.jsx'
import AccesoDenegado from './views/AccesoDenegado.jsx'
import Admin from './views/Admin.jsx'
import Agendar from './views/Agendar.jsx'
import Home from './views/Home.jsx'
import Login from './views/Login.jsx'
import MisTurnos from './views/MisTurnos.jsx'
import Perfil from './views/Perfil.jsx'
import Register from './views/Register.jsx'

function App() {
  return (
    <Routes>
      {/* Rutas públicas standalone */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Vistas con Navbar + Footer */}
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />

        {/* Cualquier usuario autenticado */}
        <Route element={<ProtectedRoute />}>
          <Route path="/perfil" element={<Perfil />} />
        </Route>

        {/* Solo clientes */}
        <Route element={<RoleRoute roles={['cliente']} />}>
          <Route path="/agendar" element={<Agendar />} />
          <Route path="/mis-turnos" element={<MisTurnos />} />
        </Route>

        {/* Solo administradores */}
        <Route element={<RoleRoute roles={['admin']} />}>
          <Route path="/admin" element={<Admin />} />
        </Route>

        <Route path="/denegado" element={<AccesoDenegado />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App