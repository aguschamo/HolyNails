// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'

afterEach(cleanup)

function renderEn(ruta) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('rutas auth como modal sobre Home', () => {
  it('/login muestra el dialogo y la home detras', () => {
    renderEn('/login')
    expect(screen.getByRole('dialog', { name: 'Iniciar sesión' })).toBeTruthy()
    expect(screen.getByLabelText('Correo electrónico')).toBeTruthy()
    expect(
      screen.getByRole('heading', { level: 1, name: /empieza acá/ }),
    ).toBeTruthy()
  })

  it('/register muestra su dialogo con el formulario', () => {
    renderEn('/register')
    expect(screen.getByRole('dialog', { name: 'Registrarse' })).toBeTruthy()
    expect(screen.getByLabelText('Nombre de usuario')).toBeTruthy()
    expect(
      screen.getByRole('heading', { level: 1, name: /empieza acá/ }),
    ).toBeTruthy()
  })

  it('/ no muestra dialogo pero si la home', () => {
    renderEn('/')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(
      screen.getByRole('heading', { level: 1, name: /empieza acá/ }),
    ).toBeTruthy()
  })

  it('el dialogo tiene el boton de cierre accesible', () => {
    renderEn('/login')
    expect(
      screen.getByRole('button', { name: 'Cerrar inicio de sesión' }),
    ).toBeTruthy()
  })
})
