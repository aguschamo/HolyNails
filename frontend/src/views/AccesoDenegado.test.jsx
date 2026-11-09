// @vitest-environment jsdom
// AccesoDenegado (B9/B9.1): el destino de «Ir a mi área» depende del rol:
// admin → /admin, personal CON Profesional activo → /mi-agenda, personal
// SIN Profesional activo → /perfil (sin bucle con ProfesionalRoute),
// resto → /perfil. Sin sesión se ofrece /login. Con initialUsuario no hay
// llamadas de red.
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import ProfesionalRoute from '../components/ProfesionalRoute.jsx'
import AccesoDenegado from './AccesoDenegado.jsx'

function usuario(role, extra = {}) {
  return {
    id: 10,
    nombre: 'Usuario Test',
    email: 'test@holy.test',
    username: 'usuario_test',
    role,
    es_profesional: role === 'personal',
    profesional_id: role === 'personal' ? 10 : null,
    ...extra,
  }
}

function renderDenegado(usuarioInicial) {
  return render(
    <MemoryRouter initialEntries={['/denegado']}>
      <AuthProvider initialUsuario={usuarioInicial}>
        <Routes>
          <Route path="/denegado" element={<AccesoDenegado />} />
          <Route path="/admin" element={<div>destino-admin</div>} />
          <Route path="/mi-agenda" element={<div>destino-mi-agenda</div>} />
          <Route path="/perfil" element={<div>destino-perfil</div>} />
          <Route path="/login" element={<div>destino-login</div>} />
          <Route path="/" element={<div>destino-home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

afterEach(cleanup)

describe('AccesoDenegado — destino por rol', () => {
  it('un administrador es dirigido a /admin', () => {
    renderDenegado(usuario('admin'))

    const link = screen.getByRole('link', { name: 'Ir a mi área' })
    expect(link.getAttribute('href')).toBe('/admin')
    expect(screen.getByText(/el rol "admin"/)).toBeTruthy()
  })

  it('un usuario personal es dirigido a /mi-agenda', () => {
    renderDenegado(usuario('personal'))

    const link = screen.getByRole('link', { name: 'Ir a mi área' })
    expect(link.getAttribute('href')).toBe('/mi-agenda')
    expect(screen.getByText(/el rol "personal"/)).toBeTruthy()
  })

  it('un cliente es dirigido a /perfil', () => {
    renderDenegado(usuario('cliente'))

    const link = screen.getByRole('link', { name: 'Ir a mi área' })
    expect(link.getAttribute('href')).toBe('/perfil')
    expect(screen.getByText(/el rol "cliente"/)).toBeTruthy()
  })

  it('sin sesión ofrece iniciar sesión en lugar de un área', () => {
    renderDenegado(null)

    const link = screen.getByRole('link', { name: 'Iniciar sesión' })
    expect(link.getAttribute('href')).toBe('/login')
    expect(screen.queryByRole('link', { name: 'Ir a mi área' })).toBeNull()
    expect(
      screen.getByText('Necesitás iniciar sesión para ver esta sección.'),
    ).toBeTruthy()
  })

  it('siempre permite volver a la home', () => {
    renderDenegado(usuario('personal'))

    expect(
      screen.getByRole('link', { name: 'Volver a la home' }).getAttribute('href'),
    ).toBe('/')
  })

  it('un personal con Profesional inactivo va a /perfil, no a /mi-agenda', () => {
    // Caso detectado en B9: ProfesionalRoute rechaza /mi-agenda → /denegado,
    // así que el botón hacia /mi-agenda creaba un bucle de redirecciones.
    renderDenegado(
      usuario('personal', { es_profesional: false, profesional_id: null }),
    )

    const link = screen.getByRole('link', { name: 'Ir a mi área' })
    expect(link.getAttribute('href')).toBe('/perfil')
  })

  it('un personal con Profesional inactivo no se confunde con un anónimo', () => {
    renderDenegado(
      usuario('personal', { es_profesional: false, profesional_id: null }),
    )

    // Sigue autenticado: mensaje de rol, botón «Ir a mi área» y sin /login.
    expect(screen.getByText(/el rol "personal"/)).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Iniciar sesión' })).toBeNull()
  })

  it('no entra en bucle: ProfesionalRoute + AccesoDenegado sin Profesional activo', () => {
    // Reproduce el escenario completo de B9 con un click: /denegado →
    // «Ir a mi área» → /perfil debe quedar estable (sin volver a /denegado
    // ni caer en /login), montando la ruta real /mi-agenda con
    // ProfesionalRoute.
    const personalInactivo = usuario('personal', {
      es_profesional: false,
      profesional_id: null,
    })
    render(
      <MemoryRouter initialEntries={['/denegado']}>
        <AuthProvider initialUsuario={personalInactivo}>
          <Routes>
            <Route path="/denegado" element={<AccesoDenegado />} />
            <Route element={<ProfesionalRoute />}>
              <Route path="/mi-agenda" element={<div>agenda-contenido</div>} />
            </Route>
            <Route path="/perfil" element={<div>perfil-contenido</div>} />
            <Route path="/login" element={<div>login-contenido</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('link', { name: 'Ir a mi área' }))

    expect(screen.getByText('perfil-contenido')).toBeTruthy()
    expect(screen.queryByText('denegado-contenido')).toBeNull()
    expect(screen.queryByText('agenda-contenido')).toBeNull()
    expect(screen.queryByText('login-contenido')).toBeNull()
  })
})
