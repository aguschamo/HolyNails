// @vitest-environment jsdom
// Hub del panel administrativo: mantiene los módulos existentes y agrega el
// acceso a la gestión de profesionales.
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import Admin from './Admin.jsx'

afterEach(cleanup)

describe('Admin — panel administrativo', () => {
  it('muestra el título y los módulos del panel', () => {
    render(
      <MemoryRouter>
        <Admin />
      </MemoryRouter>,
    )

    expect(
      screen.getByRole('heading', { level: 1, name: /panel administrativo/i }),
    ).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Gestionar turnos' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Gestionar servicios' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Horarios / disponibilidad' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Clientas' })).toBeTruthy()
  })

  it('enlaza a la gestión de profesionales', () => {
    render(
      <MemoryRouter>
        <Admin />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'Gestionar profesionales' })
    expect(link.getAttribute('href')).toBe('/admin/profesionales')
    expect(screen.getByRole('heading', { name: 'Profesionales' })).toBeTruthy()
  })

  it('todos los módulos del panel están conectados a su pantalla', () => {
    // Con B10.3 no queda ningún módulo sin conectar: cada tarjeta ofrece
    // su enlace y desaparece el aviso "Disponible al conectar la API".
    render(
      <MemoryRouter>
        <Admin />
      </MemoryRouter>,
    )

    expect(screen.queryByText(/disponible al conectar la api/i)).toBeNull()
    expect(screen.getByRole('link', { name: 'Gestionar turnos' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Gestionar servicios' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Gestionar profesionales' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Gestionar horarios' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Gestionar clientas' })).toBeTruthy()
  })

  it('enlaza a la gestión de servicios', () => {
    render(
      <MemoryRouter>
        <Admin />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'Gestionar servicios' })
    expect(link.getAttribute('href')).toBe('/admin/servicios')
  })

  it('enlaza a la gestión de turnos (B10.1)', () => {
    render(
      <MemoryRouter>
        <Admin />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'Gestionar turnos' })
    expect(link.getAttribute('href')).toBe('/admin/turnos')
  })

  it('enlaza a la gestión de horarios / disponibilidad (B10.2)', () => {
    render(
      <MemoryRouter>
        <Admin />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'Gestionar horarios' })
    expect(link.getAttribute('href')).toBe('/admin/horarios')
  })

  it('enlaza a la gestión de clientas (B10.3)', () => {
    render(
      <MemoryRouter>
        <Admin />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'Gestionar clientas' })
    expect(link.getAttribute('href')).toBe('/admin/clientas')
    expect(screen.getByRole('heading', { name: 'Clientas' })).toBeTruthy()
  })
})
