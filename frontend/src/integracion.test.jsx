// @vitest-environment jsdom
// Integración B10.4 — matriz de acceso por rol y navegación sobre
// App.jsx completa (Navbar + rutas + pantallas):
//
// - ADMIN accede al panel y a sus 5 módulos, a /agendar, /mis-turnos y
//   /perfil; con Profesional vinculado además accede a /mi-agenda sin
//   perder los permisos administrativos.
// - PERSONAL accede a /, /mi-agenda y /perfil; queda denegado en todo
//   el panel administrativo y en el flujo de reservas.
// - CLIENTE accede a /, /agendar, /mis-turnos y /perfil; queda denegado
//   en el panel y en /mi-agenda.
// - Sin sesión, las rutas protegidas redirigen a /login (sin bucles:
//   /denegado apunta al destino correcto de cada rol).
// - Los enlaces del panel y del Navbar apuntan a rutas existentes y
//   cerrar sesión limpia el estado de autenticación.
//
// api.js se mockea para no depender de un backend corriendo; con
// initialUsuario no hay llamada al perfil.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { api, clearTokens } from './services/api.js'

vi.mock('./services/api.js', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthCleared: vi.fn(() => vi.fn()),
}))

const ADMIN = {
  id: 30,
  nombre: 'Admin Uno',
  email: 'admin@holynails.test',
  username: 'admin1',
  role: 'admin',
  es_profesional: false,
  profesional_id: null,
}

// ADMIN con Profesional vinculado (B10.0.2): conserva el rol admin y
// además accede a «Mi agenda».
const ADMIN_VINCULADO = {
  ...ADMIN,
  id: 31,
  nombre: 'Admin Dos',
  username: 'admin2',
  es_profesional: true,
  profesional_id: 31,
}

const PERSONAL = {
  id: 10,
  nombre: 'María García',
  email: 'maria@holynails.test',
  username: 'maria_profesional',
  role: 'personal',
  es_profesional: true,
  profesional_id: 10,
}

// PERSONAL sin Profesional activo (es_profesional false): no puede entrar
// a /mi-agenda; el destino de /denegado tiene que ser /perfil para no
// entrar en un bucle de redirecciones.
const PERSONAL_SIN_VINCULO = {
  ...PERSONAL,
  id: 11,
  nombre: 'Sin Vínculo',
  username: 'sin_vinculo',
  es_profesional: false,
  profesional_id: null,
}

const CLIENTE = {
  id: 20,
  nombre: 'Cliente Uno',
  email: 'cliente@holynails.test',
  username: 'cliente1',
  role: 'cliente',
  es_profesional: false,
  profesional_id: null,
}

// Rutas definidas en App.jsx (los enlaces rotos apuntarían a rutas que
// caen en el comodín "*" y redirigen a la home).
const RUTAS_CONOCIDAS = new Set([
  '/',
  '/login',
  '/register',
  '/perfil',
  '/agendar',
  '/mis-turnos',
  '/admin',
  '/admin/turnos',
  '/admin/servicios',
  '/admin/profesionales',
  '/admin/horarios',
  '/admin/clientas',
  '/mi-agenda',
  '/denegado',
])

function renderApp(ruta, usuario) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider initialUsuario={usuario}>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

// Enlaces de la pantalla actual, sin las anclas de la home (/#servicios
// y similares, que sí existen como secciones de Home; el navegador los
// serializa como "#servicios").
function hrefsDeEnlaces() {
  return screen
    .getAllByRole('link')
    .map((a) => a.getAttribute('href'))
    .filter((h) => h && !h.startsWith('/#') && !h.startsWith('#'))
}

// Enlaces del Navbar (sólo rutas internas; la home puede tener enlaces
// externos a redes sociales que no son rutas de la aplicación).
function hrefsDeNavbar() {
  return within(screen.getByRole('navigation'))
    .getAllByRole('link')
    .map((a) => a.getAttribute('href'))
    .filter((h) => h && h.startsWith('/') && !h.startsWith('/#'))
}

async function expectAcceso(ruta, usuario, nombreTitulo) {
  renderApp(ruta, usuario)
  expect(
    await screen.findByRole('heading', { level: 1, name: nombreTitulo }),
  ).toBeTruthy()
  expect(screen.queryByRole('heading', { name: 'Acceso denegado' })).toBeNull()
}

async function expectDenegado(ruta, usuario) {
  renderApp(ruta, usuario)
  expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
  expect(screen.queryByRole('dialog', { name: 'Iniciar sesión' })).toBeNull()
}

beforeEach(() => {
  // Toda consulta GET devuelve una página vacía: las pantallas caen en
  // sus estados vacíos sin depender de un backend.
  api.get.mockResolvedValue({ count: 0, next: null, results: [] })
  api.post.mockResolvedValue({})
  api.patch.mockResolvedValue({})
  api.delete.mockResolvedValue(undefined)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('B10.4 — matriz de acceso: ADMIN', () => {
  it.each([
    ['/admin', /panel administrativo/i],
    ['/admin/turnos', /turnos/i],
    ['/admin/horarios', /horarios/i],
    ['/admin/clientas', /clientas/i],
    ['/admin/servicios', /servicios/i],
    ['/admin/profesionales', /profesionales/i],
    ['/agendar', 'Agendar turno'],
    ['/mis-turnos', /mis turnos/i],
    ['/perfil', 'Mi perfil'],
    ['/', /empieza acá/i],
  ])('ADMIN accede a %s', async (ruta, titulo) => {
    await expectAcceso(ruta, ADMIN, titulo)
  })

  it('ADMIN sin Profesional vinculado no accede a Mi agenda y su destino es el panel', async () => {
    renderApp('/mi-agenda', ADMIN)

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Ir a mi área' }).getAttribute('href')).toBe(
      '/admin',
    )
  })

  it('ADMIN con Profesional vinculado accede a Mi agenda y conserva el panel', async () => {
    renderApp('/mi-agenda', ADMIN_VINCULADO)

    expect(
      await screen.findByRole('heading', { level: 1, name: /mi agenda/i }),
    ).toBeTruthy()
    // Los permisos administrativos no se pierden por el vínculo.
    expect(screen.getByRole('link', { name: 'Panel admin' })).toBeTruthy()
    expect(
      screen.getByRole('link', { name: 'Mi agenda' }).getAttribute('href'),
    ).toBe('/mi-agenda')
  })

  it('ADMIN con Profesional vinculado accede al panel de administración', async () => {
    await expectAcceso('/admin', ADMIN_VINCULADO, /panel administrativo/i)
  })
})

describe('B10.4 — matriz de acceso: PERSONAL', () => {
  it.each([
    ['/', /empieza acá/i],
    ['/mi-agenda', /mi agenda/i],
    ['/perfil', 'Mi perfil'],
  ])('PERSONAL accede a %s', async (ruta, titulo) => {
    await expectAcceso(ruta, PERSONAL, titulo)
  })

  it.each([
    '/admin',
    '/admin/turnos',
    '/admin/horarios',
    '/admin/clientas',
    '/admin/servicios',
    '/admin/profesionales',
    '/agendar',
    '/mis-turnos',
  ])('PERSONAL no accede a %s', async (ruta) => {
    await expectDenegado(ruta, PERSONAL)
  })

  it('PERSONAL sin vínculo cae en /denegado con destino a /perfil (sin bucle)', async () => {
    renderApp('/mi-agenda', PERSONAL_SIN_VINCULO)

    expect(await screen.findByRole('heading', { name: 'Acceso denegado' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Ir a mi área' }).getAttribute('href')).toBe(
      '/perfil',
    )
  })

  it('el Navbar de PERSONAL muestra Mi agenda y oculta Panel admin y el CTA de agendar', async () => {
    renderApp('/mi-agenda', PERSONAL)
    await screen.findByRole('heading', { level: 1, name: /mi agenda/i })

    expect(screen.getByRole('link', { name: 'Mi agenda' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Panel admin' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Agendar turno' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Menú de cuenta de María García' }))
    expect(screen.queryByRole('link', { name: 'Mis turnos' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Mi perfil' })).toBeTruthy()
  })
})

describe('B10.4 — matriz de acceso: CLIENTE', () => {
  it.each([
    ['/', /empieza acá/i],
    ['/agendar', 'Agendar turno'],
    ['/mis-turnos', /mis turnos/i],
    ['/perfil', 'Mi perfil'],
  ])('CLIENTE accede a %s', async (ruta, titulo) => {
    await expectAcceso(ruta, CLIENTE, titulo)
  })

  it.each([
    '/admin',
    '/admin/turnos',
    '/admin/horarios',
    '/admin/clientas',
    '/admin/servicios',
    '/admin/profesionales',
    '/mi-agenda',
  ])('CLIENTE no accede a %s', async (ruta) => {
    await expectDenegado(ruta, CLIENTE)
  })

  it('el Navbar de CLIENTE muestra Agendar turno y oculta Mi agenda y Panel admin', async () => {
    renderApp('/agendar', CLIENTE)
    await screen.findByRole('heading', { level: 1, name: 'Agendar turno' })

    expect(
      screen.getByRole('link', { name: 'Agendar turno' }).getAttribute('href'),
    ).toBe('/agendar')
    expect(screen.queryByRole('link', { name: 'Mi agenda' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Panel admin' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Menú de cuenta de Cliente Uno' }))
    expect(
      screen.getByRole('link', { name: 'Mis turnos' }).getAttribute('href'),
    ).toBe('/mis-turnos')
  })
})

describe('B10.4 — sesión sin autenticar', () => {
  it.each(['/admin', '/admin/clientas', '/mi-agenda', '/mis-turnos'])(
    'sin sesión, %s redirige al login',
    async (ruta) => {
      renderApp(ruta, undefined)
      expect(
        await screen.findByRole('dialog', { name: 'Iniciar sesión' }),
      ).toBeTruthy()
      expect(screen.queryByRole('heading', { name: 'Acceso denegado' })).toBeNull()
    },
  )
})

describe('B10.4 — navegación y enlaces', () => {
  it('todos los enlaces del panel administrativo apuntan a rutas existentes', async () => {
    renderApp('/admin', ADMIN)
    await screen.findByRole('heading', { level: 1, name: /panel administrativo/i })

    const hrefs = hrefsDeEnlaces()
    expect(hrefs.length).toBeGreaterThan(0)
    for (const href of hrefs) {
      expect(RUTAS_CONOCIDAS.has(href), `enlace roto: ${href}`).toBe(true)
    }
  })

  it('los enlaces del Navbar de cada rol apuntan a rutas existentes', async () => {
    for (const usuario of [ADMIN_VINCULADO, PERSONAL, CLIENTE, undefined]) {
      const vista = renderApp('/', usuario)
      await screen.findByRole('navigation')
      for (const href of hrefsDeNavbar()) {
        expect(
          RUTAS_CONOCIDAS.has(href),
          `enlace roto (${usuario?.role ?? 'anónimo'}): ${href}`,
        ).toBe(true)
      }
      vista.unmount()
    }
  })

  it('cerrar sesión limpia el estado de autenticación y vuelve al login', async () => {
    renderApp('/admin', ADMIN)
    await screen.findByRole('heading', { level: 1, name: /panel administrativo/i })

    fireEvent.click(screen.getByRole('button', { name: 'Menú de cuenta de Admin Uno' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))

    expect(await screen.findByRole('dialog', { name: 'Iniciar sesión' })).toBeTruthy()
    expect(clearTokens).toHaveBeenCalled()
    // Sin sesión no quedan accesos administrativos en la navegación.
    expect(screen.queryByRole('link', { name: 'Panel admin' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Mi agenda' })).toBeNull()
  })
})
