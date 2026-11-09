// Formatos compartidos de la UI (catálogo público y panel admin).

// Duración del backend (DurationField, ej: "1:00:00" o "01:15:00"):
// "1 h 15 min" / "2 h 30 min"; solo minutos cuando es menor a una hora
// ("45 min") y solo horas cuando no tiene minutos ("2 h").
export function formatearDuracion(duracion) {
  if (!duracion) return 'Consultar'
  const [horas, minutos] = String(duracion).split(':')
  const h = parseInt(horas, 10)
  const m = parseInt(minutos, 10)
  if (Number.isNaN(h) || Number.isNaN(m)) return 'Consultar'
  if (h === 0) return `${m} min`
  if (m === 0) return `${h} h`
  return `${h} h ${m} min`
}

// Precio del backend (DecimalField, ej: "5000.00"): mismo formato que
// Home y Agendar, "$ " + miles con locale es-AR.
export function formatearPrecio(precio) {
  if (precio === null || precio === undefined || precio === '') return 'Consultar'
  const numero = Number(precio)
  if (Number.isNaN(numero)) return 'Consultar'
  return `$ ${numero.toLocaleString('es-AR')}`
}
