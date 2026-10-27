import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import heroImg from '../assets/hero.jpg'
import manicuraImg from '../assets/galeria/Manicura-png.png'

import galeria1 from '../assets/galeria/trabajo1.jpg'
import galeria2 from '../assets/galeria/trabajo2.jpg'
import galeria3 from '../assets/galeria/trabajo3.jpg'
import galeria4 from '../assets/galeria/trabajo4.jpg'

import { api } from '../services/api.js'

const trabajosGaleria = [
  { id: 1, imagen: galeria1 },
  { id: 2, imagen: galeria2 },
  { id: 3, imagen: galeria3 },
  { id: 4, imagen: galeria4 },
]

function formatearDuracion(duracion) {
  if (!duracion) return 'Consultar'
  const [horas, minutos] = duracion.split(':')
  const h = parseInt(horas, 10)
  const m = parseInt(minutos, 10)
  if (m === 0) return `${h} hs`
  return `${h}:${String(m).padStart(2, '0')} hs`
}

function formatearPrecio(precio) {
  if (precio === null || precio === undefined || precio === '') return 'Consultar'
  const numero = Number(precio)
  if (Number.isNaN(numero)) return 'Consultar'
  return `$ ${numero.toLocaleString('es-AR')}`
}

function Home() {
  const [servicios, setServicios] = useState([])
  const [serviciosLoading, setServiciosLoading] = useState(true)
  const [serviciosError, setServiciosError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function cargarServicios() {
      setServiciosLoading(true)
      setServiciosError(null)
      try {
        const data = await api.get('/api/servicios/')
        if (!cancelled) {
          setServicios(Array.isArray(data.results) ? data.results : [])
        }
      } catch (err) {
        if (!cancelled) {
          setServicios([])
          setServiciosError(err.message || 'No se pudieron cargar los servicios.')
        }
      } finally {
        if (!cancelled) setServiciosLoading(false)
      }
    }

    cargarServicios()
    return () => {
      cancelled = true
    }
  }, [])
  return (
    <>
      {/* HERO SECTION */}
      <header id="inicio" className="hn-hero-section">
        <div className="container">
          <div className="row align-items-center g-5 text-center text-lg-start">
            <div className="col-12 col-lg-6">
              <p className="hn-hero-label mb-3">
                MANICURA & NAIL ART
              </p>
              <h1 className="hn-hero-title mb-3">
                Tu próxima
                <br />
                <span className="hn-hero-word-mask" role="img" aria-label="manicura">
                  <img
                    src={manicuraImg}
                    alt="manicura"
                    className="hn-hero-word"
                    width={2000}
                    height={2000}
                    aria-hidden="true"
                  />
                </span>
                <br />
                empieza acá
              </h1>
              <p className="lead text-muted mb-4 fs-6">
                Diseños únicos, calidad y detalles para que tus uñas hablen por vos.
              </p>
              <div className="d-flex flex-wrap gap-4 align-items-center justify-content-center justify-content-lg-start">
                <Link to="/agendar" className="btn btn-hn-dark">
                  Agendar turno
                </Link>
                <a href="#servicios" className="hn-hero-link">
                  Ver servicios
                </a>
              </div>
            </div>

            <div className="col-12 col-lg-6 text-center">
              <img
                src={heroImg}
                alt="Holy Nails - Muestra de manicura"
                className="hn-hero-img"
                width={1170}
                height={1552}
                fetchPriority="high"
              />
            </div>
          </div>
        </div>
      </header>

      {/* SERVICIOS SECTION */}
      <section id="servicios" className="py-5">
        <div className="container py-4">
          <div className="text-center mb-5">
            <h2 className="hn-section-title mb-2">Nuestros servicios</h2>
            <p className="text-muted small">
              Elegí el servicio que mejor se adapte a vos
            </p>
          </div>

          {serviciosLoading && (
            <div className="text-center py-4">
              <p className="text-muted small mb-0">Cargando servicios…</p>
            </div>
          )}

          {!serviciosLoading && serviciosError && (
            <div className="alert alert-warning py-2 small text-center" role="alert">
              {serviciosError}
            </div>
          )}

          {!serviciosLoading && !serviciosError && servicios.length === 0 && (
            <div className="text-center py-4">
              <p className="text-muted small mb-0">
                No hay servicios disponibles por el momento.
              </p>
            </div>
          )}

          {!serviciosLoading && !serviciosError && servicios.length > 0 && (
            <div className="row g-4">
              {servicios.map((s) => (
                <div className="col-12 col-md-6" key={s.id}>
                  <div className="hn-service-item">
                    <div className="hn-service-head">
                      <h3 className="h5 fw-bold mb-0">{s.nombre}</h3>
                      <span className="hn-service-price">
                        {formatearPrecio(s.precio)}
                      </span>
                    </div>
                    <p className="small text-muted mb-0">
                      Duración: {formatearDuracion(s.duracion)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* GALERIA SECTION */}
      <section id="galeria" className="py-5 bg-white border-top border-bottom">
        <div className="container py-4">
          <div className="text-center mb-5">
            <h2 className="hn-section-title mb-2">Algunos trabajos</h2>
          </div>

          <div className="row g-3 justify-content-center">
            {trabajosGaleria.map((t) => (
              <div className="col-6 col-lg-3" key={t.id}>
                <img
                  className="hn-gallery-img"
                  src={t.imagen}
                  alt={`Diseño ${t.id} de manicura Holy Nails`}
                  loading="lazy"
                />
              </div>
            ))}
          </div>

          <div className="text-center mt-4">
            <a
              href="https://instagram.com/holy.nails.demo"
              target="_blank"
              rel="noopener noreferrer"
              className="fw-semibold"
            >
              Ver más en Instagram
            </a>
          </div>
        </div>
      </section>

      {/* CONTACTO SECTION */}
      <section id="contacto" className="py-5">
        <div className="container">
          <div className="hn-contacto-section">
            <div className="row g-4 align-items-center text-center text-md-start">
              <div className="col-12 col-md-5">
                <h2 className="hn-section-title mb-2">Contacto</h2>
                <p className="mb-3">
                  Escribinos por WhatsApp y te ayudamos con tu pedido o dudas.
                </p>
                <a
                  href="https://wa.me/5492600000000"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-hn-dark d-inline-flex align-items-center gap-2"
                >
                  <svg
                    aria-hidden="true"
                    focusable="false"
                    viewBox="0 0 24 24"
                    width="17"
                    height="17"
                    fill="currentColor"
                  >
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
                  </svg>
                  Abrir WhatsApp
                </a>
              </div>

              <div className="col-12 col-md-7">
                <div className="hn-contacto-grid">
                  <div className="hn-contacto-item">
                    <p className="hn-contacto-label mb-1">WhatsApp</p>
                    <p className="hn-contacto-value mb-0">+54 9 260 000 0000</p>
                  </div>
                  <div className="hn-contacto-item">
                    <p className="hn-contacto-label mb-1">Instagram</p>
                    <p className="hn-contacto-value mb-0">@holy.nails.demo</p>
                  </div>
                  <div className="hn-contacto-item">
                    <p className="hn-contacto-label mb-1">Ubicación</p>
                    <p className="hn-contacto-value mb-0">
                      Av. Ejemplo 123, San Rafael, Mendoza
                    </p>
                  </div>
                  <div className="hn-contacto-item">
                    <p className="hn-contacto-label mb-1">Horarios</p>
                    <p className="hn-contacto-value mb-0">
                      Atención con turnos previos. Consultá disponibilidad.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}

export default Home
