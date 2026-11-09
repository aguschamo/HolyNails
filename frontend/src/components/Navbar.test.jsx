// @vitest-environment jsdom
// Navbar por rol (B9 + B10.0.2): «Mi agenda» solo con
// usuario.es_profesional (todo PERSONAL tiene vínculo; ADMIN solo si
// tiene Profesional asociado), el CTA «Agendar turno» y «Mis turnos» son
// del flujo de CLIENTE y ADMIN (o anónimo para entrar), y PERSONAL no ve
// el flujo de reservas. Con initialUsuario no hay llamadas de red; sin
// sesión, la restauración corta en getAccessToken() (localStorage vacío)
// sin pegarle al backend.
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { AuthProvider } from '../context/AuthContext.jsx'
import Navbar from './Navbar.jsx'

const USER_PERSONAL = {
  id: 10,
  nombre: 'María García',
  email: 'maria@holynails.test',
  username: 'maria_profesional',
  role: 'personal',
  es_profesional: true,
  profesional_id: 10,
}

const USER_CLIENTE = {
  id: 20,
  nombre: 'Cliente Uno',
  email: 'cliente@holynails.test',
  username: 'cliente1',
  role: 'cliente',
  es_profesional: false,
  profesional_id: null,
}

const USER_ADMIN = {
  id: 30,
  nombre: 'Admin Uno',
  email: 'admin@holynails.test',
  username: 'admin1',
  role: 'admin',
  es_profesional: false,
  profesional_id: null,
}

// ADMIN con Profesional asociado (B10.0.2): conserva el rol admin y
// además accede a «Mi agenda».
const USER_ADMIN_VINCULADO = {
  id: 31,
  nombre: 'Admin Dos',
  email: 'admin2@holynails.test',
  username: 'admin2',
  role: 'admin',
  es_profesional: true,
  profesional_id: 31,
}

function renderNavbar(usuario) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider initialUsuario={usuario}>
        <Navbar />
      </AuthProvider>
    </MemoryRouter>,
  )
}

function abrirMenuCuenta(usuario) {
  renderNavbar(usuario)
  fireEvent.click(
    screen.getByRole('button', { name: `Menú de cuenta de ${usuario.nombre}` }),
  )
}

afterEach(cleanup)

describe('Navbar — enlace Mi agenda', () => {
  it('muestra «Mi agenda» apuntando a /mi-agenda cuando el usuario es personal con vínculo', () => {
    renderNavbar(USER_PERSONAL)

    const link = screen.getByRole('link', { name: 'Mi agenda' })
    expect(link.getAttribute('href')).toBe('/mi-agenda')
  })

  it('no muestra «Mi agenda» a un cliente sin vínculo profesional', () => {
    renderNavbar(USER_CLIENTE)

    expect(screen.queryByRole('link', { name: 'Mi agenda' })).toBeNull()
    // el resto de la navegación sigue disponible
    expect(screen.getByRole('link', { name: 'Inicio' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Agendar turno' })).toBeTruthy()
  })

  it('no muestra «Mi agenda» sin sesión iniciada', () => {
    renderNavbar(null)

    expect(screen.queryByRole('link', { name: 'Mi agenda' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Iniciar sesión' })).toBeTruthy()
  })

  it('no muestra «Mi agenda» a un administrador sin Profesional (B10.0.2)', () => {
    renderNavbar(USER_ADMIN)

    expect(screen.queryByRole('link', { name: 'Mi agenda' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Panel admin' })).toBeTruthy()
  })

  it('muestra «Mi agenda» a un administrador con Profesional asociado (B10.0.2)', () => {
    renderNavbar(USER_ADMIN_VINCULADO)

    const link = screen.getByRole('link', { name: 'Mi agenda' })
    expect(link.getAttribute('href')).toBe('/mi-agenda')
    expect(screen.getByRole('link', { name: 'Panel admin' })).toBeTruthy()
  })
})

describe('Navbar — CTA «Agendar turno» por rol', () => {
  it('lo muestra a un cliente autenticado apuntando a /agendar', () => {
    renderNavbar(USER_CLIENTE)

    const cta = screen.getByRole('link', { name: 'Agendar turno' })
    expect(cta.getAttribute('href')).toBe('/agendar')
  })

  it('lo muestra a un anónimo apuntando a /login', () => {
    renderNavbar(null)

    const cta = screen.getByRole('link', { name: 'Agendar turno' })
    expect(cta.getAttribute('href')).toBe('/login')
  })

  it('no lo muestra a un usuario personal', () => {
    renderNavbar(USER_PERSONAL)

    expect(screen.queryByRole('link', { name: 'Agendar turno' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Mi agenda' })).toBeTruthy()
  })

  it('lo muestra a un administrador apuntando a /agendar (B10.0.2)', () => {
    renderNavbar(USER_ADMIN)

    const cta = screen.getByRole('link', { name: 'Agendar turno' })
    expect(cta.getAttribute('href')).toBe('/agendar')
    expect(screen.getByRole('link', { name: 'Panel admin' })).toBeTruthy()
  })
})

describe('Navbar — menú de cuenta por rol', () => {
  it('un cliente ve «Mis turnos» en su menú de cuenta', () => {
    abrirMenuCuenta(USER_CLIENTE)

    expect(
      screen.getByRole('link', { name: 'Mis turnos' }).getAttribute('href'),
    ).toBe('/mis-turnos')
    expect(screen.getByRole('link', { name: 'Mi perfil' })).toBeTruthy()
  })

  it('un usuario personal no ve «Mis turnos» (su agenda es /mi-agenda)', () => {
    abrirMenuCuenta(USER_PERSONAL)

    expect(screen.queryByRole('link', { name: 'Mis turnos' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Mi perfil' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeTruthy()
  })

  it('un administrador ve «Mis turnos» en su menú de cuenta (B10.0.2)', () => {
    abrirMenuCuenta(USER_ADMIN)

    expect(
      screen.getByRole('link', { name: 'Mis turnos' }).getAttribute('href'),
    ).toBe('/mis-turnos')
    expect(screen.getByRole('link', { name: 'Mi perfil' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Panel admin' })).toBeTruthy()
  })
})
