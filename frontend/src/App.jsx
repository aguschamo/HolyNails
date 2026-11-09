import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import RoleRoute from './components/RoleRoute.jsx'
import ProfesionalRoute from './components/ProfesionalRoute.jsx'
import AccesoDenegado from './views/AccesoDenegado.jsx'
import Admin from './views/Admin.jsx'
import AdminClientas from './views/AdminClientas.jsx'
import AdminHorarios from './views/AdminHorarios.jsx'
import AdminProfesionales from './views/AdminProfesionales.jsx'
import AdminServicios from './views/AdminServicios.jsx'
import AdminTurnos from './views/AdminTurnos.jsx'
import Agendar from './views/Agendar.jsx'
import Home from './views/Home.jsx'
import Login from './views/Login.jsx'
import MiAgenda from './views/MiAgenda.jsx'
import MisTurnos from './views/MisTurnos.jsx'
import Perfil from './views/Perfil.jsx'
import Register from './views/Register.jsx'

function HomeShell() {
  return (
    <>
      <Home />
      <Outlet />
    </>
  )
}

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Home siempre montado: /login y /register se superponen como modal */}
        <Route element={<HomeShell />}>
          <Route index element={<></>} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>

        {/* Cualquier usuario autenticado */}
        <Route element={<ProtectedRoute />}>
          <Route path="/perfil" element={<Perfil />} />
        </Route>

        {/* Flujo de reservas: CLIENTE y ADMIN (B10.0.2) */}
        <Route element={<RoleRoute roles={['cliente', 'admin']} />}>
          <Route path="/agendar" element={<Agendar />} />
          <Route path="/mis-turnos" element={<MisTurnos />} />
        </Route>

        {/* Solo administradores */}
        <Route element={<RoleRoute roles={['admin']} />}>
          <Route path="/admin" element={<Admin />} />
          <Route path="/admin/turnos" element={<AdminTurnos />} />
          <Route path="/admin/horarios" element={<AdminHorarios />} />
          <Route path="/admin/profesionales" element={<AdminProfesionales />} />
          <Route path="/admin/servicios" element={<AdminServicios />} />
          <Route path="/admin/clientas" element={<AdminClientas />} />
        </Route>

        {/* Solo profesionales (usuarios con es_profesional === true) */}
        <Route element={<ProfesionalRoute />}>
          <Route path="/mi-agenda" element={<MiAgenda />} />
        </Route>

        <Route path="/denegado" element={<AccesoDenegado />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App