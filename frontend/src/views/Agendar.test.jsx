// @vitest-environment jsdom
// Pruebas del formulario de reserva: catálogo dinámico por ID, bloqueo sin
// servicio, payload de POST /api/turnos/ y manejo de éxito/error del backend.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '../services/api.js'
import Agendar from './Agendar.jsx'

vi.mock('../services/api.js', () => {
  class ApiError extends Error {
    constructor(message, status, data) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.data = data
    }
  }
  return { api: { get: vi.fn(), post: vi.fn() }, ApiError }
})

const CATALOGO = [
  { id: 1, nombre: 'Semipermanente', duracion: '01:00:00', precio: '5000.00' },
  { id: 7, nombre: 'Kapping', duracion: '01:30:00', precio: '8000.00' },
]

const FECHA = '2030-01-15'
const HORA = '10:00'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderAgendar() {
  return render(
    <MemoryRouter>
      <Agendar />
    </MemoryRouter>,
  )
}

async function renderConCatalogo(catalogo = CATALOGO) {
  api.get.mockResolvedValue({ count: catalogo.length, next: null, results: catalogo })
  const view = renderAgendar()
  const select = await screen.findByLabelText('Servicio')
  await waitFor(() => expect(select.disabled).toBe(false))
  return view
}

function llenarFormulario() {
  fireEvent.change(screen.getByLabelText('Servicio'), { target: { value: '7' } })
  fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: FECHA } })
  fireEvent.change(screen.getByLabelText('Hora'), { target: { value: HORA } })
}

function enviarFormulario() {
  const boton = screen.getByRole('button', { name: /Reservar turno|Enviando/ })
  fireEvent.submit(boton.closest('form'))
}

describe('Agendar — catálogo', () => {
  it('puebla el select con los servicios de la API usando el ID como valor', async () => {
    await renderConCatalogo()

    const opciones = screen.getAllByRole('option')
    // placeholder + 2 servicios
    expect(opciones).toHaveLength(3)
    expect(opciones[1].value).toBe('1')
    expect(opciones[1].textContent).toBe('Semipermanente')
    expect(opciones[2].value).toBe('7')
    expect(opciones[2].textContent).toBe('Kapping')
    // Nunca se envía el nombre del servicio
    expect(opciones.map((o) => o.value)).not.toContain('KAPPING')
  })

  it('estado vacío: sin servicios el select y el botón quedan bloqueados', async () => {
    api.get.mockResolvedValue({ count: 0, next: null, results: [] })
    renderAgendar()

    expect(
      await screen.findByText('No hay servicios disponibles por el momento.'),
    ).toBeTruthy()
    expect(screen.getByLabelText('Servicio').disabled).toBe(true)
    expect(screen.getByRole('button', { name: 'Reservar turno' }).disabled).toBe(true)
  })

  it('error de API al cargar el catálogo se muestra y bloquea el envío', async () => {
    api.get.mockRejectedValue(new Error('No se pudo conectar con el servidor.'))
    renderAgendar()

    expect(await screen.findByText('No se pudo conectar con el servidor.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Reservar turno' }).disabled).toBe(true)
  })
})

describe('Agendar — reserva', () => {
  it('envía fecha, hora y el ID del servicio a POST /api/turnos/', async () => {
    await renderConCatalogo()
    api.post.mockResolvedValue({
      id: 42,
      fecha: FECHA,
      hora: HORA,
      servicio: 7,
      estado: 'pendiente',
    })

    llenarFormulario()
    enviarFormulario()

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/api/turnos/', {
        fecha: FECHA,
        hora: HORA,
        servicio: 7,
      }),
    )
    // El payload lleva el ID numérico, no el nombre
    const [, payload] = api.post.mock.calls[0]
    expect(typeof payload.servicio).toBe('number')
    expect(payload).not.toHaveProperty('nombre')
  })

  it('muestra la confirmación sólo después de una respuesta exitosa', async () => {
    await renderConCatalogo()
    api.post.mockResolvedValue({ id: 42, estado: 'pendiente' })

    expect(screen.queryByText(/Reserva registrada correctamente/)).toBeNull()

    llenarFormulario()
    enviarFormulario()

    expect(await screen.findByText(/Reserva registrada correctamente/)).toBeTruthy()
    expect(screen.queryByText(/no se pudo/i)).toBeNull()
    // El formulario queda limpio tras el éxito
    expect(screen.getByLabelText('Fecha').value).toBe('')
    expect(screen.getByLabelText('Hora').value).toBe('')
    expect(screen.getByLabelText('Servicio').value).toBe('')
  })

  it('rechazo del backend: muestra el mensaje y NO muestra confirmación', async () => {
    await renderConCatalogo()
    api.post.mockRejectedValue(
      new ApiError(
        'Este horario ya se encuentra ocupado. Por favor, elija otra fecha u hora.',
        400,
      ),
    )

    llenarFormulario()
    enviarFormulario()

    expect(
      await screen.findByText(
        'Este horario ya se encuentra ocupado. Por favor, elija otra fecha u hora.',
      ),
    ).toBeTruthy()
    expect(screen.queryByText(/Reserva registrada correctamente/)).toBeNull()
  })

  it('error de red: muestra mensaje genérico y NO muestra confirmación', async () => {
    await renderConCatalogo()
    api.post.mockRejectedValue(new ApiError('No se pudo conectar con el servidor.', 0))

    llenarFormulario()
    enviarFormulario()

    expect(await screen.findByText('No se pudo conectar con el servidor.')).toBeTruthy()
    expect(screen.queryByText(/Reserva registrada correctamente/)).toBeNull()
    // Vuelve a quedar habilitado para reintentar
    expect(screen.getByRole('button', { name: 'Reservar turno' }).disabled).toBe(false)
  })

  it('validación local: fecha anterior a hoy no dispara el request', async () => {
    await renderConCatalogo()
    api.post.mockResolvedValue({ id: 1 })

    fireEvent.change(screen.getByLabelText('Servicio'), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: '2020-01-01' } })
    fireEvent.change(screen.getByLabelText('Hora'), { target: { value: HORA } })
    enviarFormulario()

    expect(await screen.findByText('La fecha no puede ser anterior a hoy.')).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('validación local: hora fuera del horario no dispara el request', async () => {
    await renderConCatalogo()
    api.post.mockResolvedValue({ id: 1 })

    fireEvent.change(screen.getByLabelText('Servicio'), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText('Fecha'), { target: { value: FECHA } })
    fireEvent.change(screen.getByLabelText('Hora'), { target: { value: '21:00' } })
    enviarFormulario()

    expect(
      await screen.findByText(
        'Fecha u hora fuera del horario de atención (09:00 a 20:00).',
      ),
    ).toBeTruthy()
    expect(api.post).not.toHaveBeenCalled()
  })
})
