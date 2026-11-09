// A5 — mensajes de error de la reserva en Agendar.
//
// Reglas de presentación (no tocan el backend ni el formato de la API):
// - se conserva el detalle específico que envía el backend (400:
//   superposición, disponibilidad, servicio/profesional inactivo, fecha
//   u horario inválido, intervalos de 15 minutos…);
// - se sustituye sólo cuando es técnico o no hay detalle útil: 401 (el
//   detail crudo es interno), 5xx, error de conexión y fallos sin
//   mensaje;
// - nunca se muestran trazas, nombres de clases ni datos internos.

// Mensajes del backend que son útiles en el fondo pero poco claros para
// la clienta: se traducen. Todos los demás se muestran tal cual.
const MENSAJES_AMIGABLES = [
  [
    /deben formar un conjunto único/,
    'Ese horario acaba de tomarse. Elegí otro horario o fecha.',
  ],
  [
    /formato no válido|wrong format/i,
    'La fecha o el horario enviado no es válido. Volvé a elegirlos.',
  ],
]

export function mensajeDeReserva(err) {
  const estado = err?.status
  if (estado === 401) {
    return 'Tu sesión expiró. Iniciá sesión nuevamente para poder reservar.'
  }
  if (estado === 0) {
    return 'No se pudo conectar con el servidor. Verificá tu conexión.'
  }
  if (typeof estado === 'number' && estado >= 500) {
    return 'El servidor tuvo un problema al procesar la reserva. Intentá nuevamente en unos minutos.'
  }

  const detalle = typeof err?.message === 'string' ? err.message.trim() : ''
  if (detalle) {
    const amigable = MENSAJES_AMIGABLES.find(([patron]) => patron.test(detalle))
    return amigable ? amigable[1] : detalle
  }

  if (estado === 403) return 'No tenés permiso para reservar turnos.'
  if (estado === 404) {
    return 'El servicio o la profesional ya no están disponibles. Volvé a empezar la reserva.'
  }
  return 'No se pudo registrar la reserva. Volvé a elegir la fecha y el horario.'
}
