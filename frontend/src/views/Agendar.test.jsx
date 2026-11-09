// @vitest-environment jsdom
// Pruebas de renderizado y contratos de API para Agendar.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import { api, ApiError } from "../services/api.js"
import Agendar from "./Agendar.jsx"
import { mensajeDeReserva } from "../services/mensajesReserva.js"

vi.mock("../services/api.js", () => {
  class ApiError extends Error {
    constructor(message, status, data) {
      super(message)
      this.name = "ApiError"
      this.status = status
      this.data = data
    }
  }
  return { api: { get: vi.fn(), post: vi.fn() }, ApiError }
})

const CATALOGO = [
  { id: 1, nombre: "Semipermanente", duracion: "01:00:00", precio: "5000.00" },
  { id: 7, nombre: "Kapping", duracion: "01:30:00", precio: "8000.00" },
]

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderAgendar() {
  return render(<MemoryRouter><Agendar /></MemoryRouter>)
}

async function renderConCatalogo(catalogo = CATALOGO) {
  api.get.mockResolvedValue({ count: catalogo.length, next: null, results: catalogo })
  const view = renderAgendar()
  const select = await screen.findByLabelText("Servicio")
  await waitFor(() => expect(select.disabled).toBe(false))
  return view
}

describe("Agendar — renderizado", () => {
  it("puebla el select con los servicios de la API usando el ID como valor", async () => {
    await renderConCatalogo()
    const opciones = screen.getAllByRole("option")
    expect(opciones).toHaveLength(3)
    expect(opciones[1].value).toBe("1")
    expect(opciones[1].textContent).toBe("Semipermanente")
    expect(opciones[2].value).toBe("7")
    expect(opciones[2].textContent).toBe("Kapping")
    expect(opciones.map((o) => o.value)).not.toContain("KAPPING")
  })

  it("estado vacío: sin servicios el select queda bloqueado", async () => {
    api.get.mockResolvedValue({ count: 0, next: null, results: [] })
    renderAgendar()
    expect(await screen.findByText("No hay servicios disponibles por el momento.")).toBeTruthy()
    expect(screen.getByLabelText("Servicio").disabled).toBe(true)
  })

  it("error de API al cargar el catálogo se muestra", async () => {
    api.get.mockRejectedValue(new Error("No se pudo conectar con el servidor."))
    renderAgendar()
    expect(await screen.findByText("No se pudo conectar con el servidor.")).toBeTruthy()
  })

  it("muestra el título de la sección y el paso de servicio", async () => {
    await renderConCatalogo()
    await waitFor(() => expect(screen.getByLabelText("Servicio")).toBeTruthy())
    expect(screen.getByAltText("Agendar turno")).toBeTruthy()
  })
})

describe("Agendar — contratos de API", () => {
  it("POST /api/turnos/ acepta fecha, hora, servicio y profesional como IDs numéricos", async () => {
    await renderConCatalogo()
    api.post.mockResolvedValue({
      id: 42, fecha: "2030-01-15", hora: "10:00", servicio: 7, profesional: 10, estado: "pendiente",
    })
    await api.post("/api/turnos/", {
      fecha: "2030-01-15", hora: "10:00", servicio: 7, profesional: 10,
    })
    expect(api.post).toHaveBeenCalledWith("/api/turnos/", {
      fecha: "2030-01-15", hora: "10:00", servicio: 7, profesional: 10,
    })
  })

  it("POST /api/turnos/ rechaza con 400 cuando el horario está ocupado", async () => {
    await renderConCatalogo()
    api.post.mockRejectedValueOnce(new ApiError("Este horario ya se encuentra ocupado. Por favor, elija otra fecha u hora.", 400))
    try {
      await api.post("/api/turnos/", { fecha: "2030-01-15", hora: "10:00", servicio: 7, profesional: 10 })
    } catch (err) {
      expect(err.status).toBe(400)
      expect(err.message).toContain("ya se encuentra ocupado")
    }
  })

  it("POST /api/turnos/ error de red devuelve status 0", async () => {
    await renderConCatalogo()
    api.post.mockRejectedValueOnce(new ApiError("No se pudo conectar con el servidor.", 0))
    try {
      await api.post("/api/turnos/", { fecha: "2030-01-15", hora: "10:00", servicio: 7, profesional: 10 })
    } catch (err) {
      expect(err.status).toBe(0)
      expect(err.message).toBe("No se pudo conectar con el servidor.")
    }
  })
})

describe("Agendar — mensajes de error de reserva (A5)", () => {
  // Mock de los tres endpoints del flujo: catálogo, profesionales y
  // horarios disponibles (estos últimos en forma de lista directa).
  function mockearFlujo() {
    api.get.mockImplementation((url) => {
      const u = String(url)
      if (u.includes("disponibles")) {
        return Promise.resolve([
          { fecha: "2030-01-15", hora: "10:00" },
          { fecha: "2030-01-15", hora: "10:15" },
        ])
      }
      if (u.includes("/api/profesionales/")) {
        return Promise.resolve({
          count: 1, next: null, previous: null,
          results: [{ id: 10, nombre: "Brenda", is_active: true }],
        })
      }
      if (u.includes("/api/servicios/")) {
        return Promise.resolve({ count: CATALOGO.length, next: null, results: CATALOGO })
      }
      return Promise.resolve({ count: 0, next: null, results: [] })
    })
  }

  // Recorre el flujo hasta el paso de horario, listo para reservar.
  async function abrirHastaHorario() {
    mockearFlujo()
    renderAgendar()
    const selectServicio = await screen.findByLabelText("Servicio")
    await waitFor(() => expect(selectServicio.disabled).toBe(false))
    fireEvent.change(selectServicio, { target: { value: "1" } })
    fireEvent.change(await screen.findByLabelText("Fecha"), { target: { value: "2030-01-15" } })
    // El efecto de profesionales avanza solo al paso «profesional».
    fireEvent.change(await screen.findByLabelText("Profesional"), { target: { value: "10" } })
    // El efecto de horarios avanza solo al paso «horario».
    await screen.findByLabelText("Horario disponible")
    fireEvent.change(screen.getByLabelText("Horario disponible"), {
      target: { value: "10:00" },
    })
  }

  it("conserva el mensaje específico del backend ante un 400 de superposición", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValue(
      new ApiError(
        "El profesional ya tiene un turno que se superpone con ese horario.",
        400,
        ["El profesional ya tiene un turno que se superpone con ese horario."],
      ),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(
      await screen.findByText(/un turno que se superpone con ese horario/),
    ).toBeTruthy()
    // El mensaje genérico que antes reemplazaba al detalle ya no aparece.
    expect(screen.queryByText(/El horario ya no está disponible/)).toBeNull()
  })

  it("muestra el mensaje de intervalos de 15 minutos del backend", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValue(
      new ApiError(
        "El horario de inicio debe respetar intervalos de 15 minutos (minutos 00, 15, 30 o 45).",
        400,
        ["El horario de inicio debe respetar intervalos de 15 minutos (minutos 00, 15, 30 o 45)."],
      ),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(await screen.findByText(/intervalos de 15 minutos/)).toBeTruthy()
  })

  it("muestra el detalle de servicio o profesional inactivo tal cual", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValue(
      new ApiError("El profesional seleccionado no está activo.", 400, {
        non_field_errors: ["El profesional seleccionado no está activo."],
      }),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(await screen.findByText("El profesional seleccionado no está activo.")).toBeTruthy()
  })

  it("traduce el error técnico de unicidad a un mensaje claro", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValue(
      new ApiError(
        "Los campos profesional, fecha y hora deben formar un conjunto único.",
        400,
        { non_field_errors: ["Los campos profesional, fecha y hora deben formar un conjunto único."] },
      ),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(await screen.findByText("Ese horario acaba de tomarse. Elegí otro horario o fecha.")).toBeTruthy()
    expect(screen.queryByText(/conjunto único/)).toBeNull()
  })

  it("un 401 muestra un mensaje de sesión claro sin tecnicismos", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValue(
      new ApiError("Given token not valid for any token type.", 401, {
        detail: "Given token not valid for any token type.",
      }),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(
      await screen.findByText("Tu sesión expiró. Iniciá sesión nuevamente para poder reservar."),
    ).toBeTruthy()
    expect(screen.queryByText(/Given token/)).toBeNull()
  })

  it("un 5xx muestra un mensaje claro sin el detalle técnico", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValue(
      new ApiError("Se produjo un error al procesar la solicitud.", 500, {
        detail: "Se produjo un error al procesar la solicitud.",
      }),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(
      await screen.findByText(/El servidor tuvo un problema al procesar la reserva/),
    ).toBeTruthy()
    expect(screen.queryByText(/Se produjo un error/)).toBeNull()
  })

  it("un error de conexión conserva el mensaje de conexión", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValue(
      new ApiError("No se pudo conectar con el servidor. Verificá tu conexión.", 0),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(
      await screen.findByText("No se pudo conectar con el servidor. Verificá tu conexión."),
    ).toBeTruthy()
  })

  it("permite reintentar la reserva después del error", async () => {
    await abrirHastaHorario()
    api.post.mockRejectedValueOnce(
      new ApiError("El profesional ya tiene un turno que se superpone con ese horario.", 400),
    )
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))
    expect(await screen.findByText(/se superpone/)).toBeTruthy()

    // Tras el 400 se limpió la selección: se elige de nuevo y se reintenta.
    fireEvent.change(await screen.findByLabelText("Horario disponible"), {
      target: { value: "10:00" },
    })
    api.post.mockResolvedValueOnce({
      id: 42, fecha: "2030-01-15", hora: "10:00", servicio: 1, profesional: 10, estado: "pendiente",
    })
    fireEvent.click(screen.getByRole("button", { name: "Reservar turno" }))

    expect(await screen.findByText("Reserva enviada")).toBeTruthy()
  })

  it("mensajeDeReserva: conserva el detalle útil y usa respuestas claras como fallback", () => {
    // Detalle específico del backend: se conserva tal cual.
    expect(mensajeDeReserva({ status: 400, message: "Debe seleccionar un servicio." }))
      .toBe("Debe seleccionar un servicio.")
    // Error sin status explícito pero con mensaje: también se conserva.
    expect(mensajeDeReserva({ message: "Mensaje heredado." })).toBe("Mensaje heredado.")
    // Sin mensaje: fallbacks por estado.
    expect(mensajeDeReserva({ status: 403 })).toBe("No tenés permiso para reservar turnos.")
    expect(mensajeDeReserva({ status: 404 }))
      .toBe("El servicio o la profesional ya no están disponibles. Volvé a empezar la reserva.")
    expect(mensajeDeReserva({ status: 400 }))
      .toBe("No se pudo registrar la reserva. Volvé a elegir la fecha y el horario.")
    // 401: nunca el detail crudo.
    expect(mensajeDeReserva({ status: 401, message: "Authentication credentials were not provided." }))
      .toBe("Tu sesión expiró. Iniciá sesión nuevamente para poder reservar.")
  })
})

describe("Agendar — paginación de profesionales (A2)", () => {
  it("recorre todas las páginas al elegir la fecha (PAGE_SIZE=10)", async () => {
    const pagina1 = Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      nombre: `Profesional ${i + 1}`,
      is_active: true,
    }))
    const pagina2 = [
      { id: 11, nombre: "Profesional Once", is_active: true },
      // Inactivo en la última página: el filtro activos se aplica al total.
      { id: 12, nombre: "Profesional Inactiva", is_active: false },
    ]
    api.get.mockImplementation((url) => {
      const u = String(url)
      // `next` es una URL absoluta: se busca por contenido, no por prefijo.
      if (u.includes("/api/servicios/")) {
        return Promise.resolve({ count: 1, next: null, previous: null, results: CATALOGO })
      }
      if (u.includes("/api/profesionales/") && u.includes("page=2")) {
        return Promise.resolve({ count: 12, next: null, previous: "http://testserver/api/profesionales/", results: pagina2 })
      }
      if (u.includes("/api/profesionales/")) {
        return Promise.resolve({ count: 12, next: "http://testserver/api/profesionales/?page=2", previous: null, results: pagina1 })
      }
      return Promise.resolve({ count: 0, next: null, previous: null, results: [] })
    })
    renderAgendar()

    const selectServicio = await screen.findByLabelText("Servicio")
    await waitFor(() => expect(selectServicio.disabled).toBe(false))
    fireEvent.change(selectServicio, { target: { value: "1" } })

    fireEvent.change(await screen.findByLabelText("Fecha"), { target: { value: "2030-01-15" } })

    const botonProfesional = await screen.findByRole("button", { name: "Elegir profesional" })
    await waitFor(() => expect(botonProfesional.disabled).toBe(false))
    fireEvent.click(botonProfesional)

    // El profesional de la segunda página aparece en el select…
    expect(await screen.findByText("Profesional Once")).toBeTruthy()
    await waitFor(() =>
      expect(api.get).toHaveBeenCalledWith("http://testserver/api/profesionales/?page=2"),
    )
    // …y el inactivo de esa misma página queda filtrado.
    expect(screen.queryByText("Profesional Inactiva")).toBeNull()
  })
})

