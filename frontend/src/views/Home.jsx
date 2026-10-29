import { Link } from 'react-router-dom'
import heroImg from '../assets/hero.jpg'

import galeria1 from '../assets/galeria/trabajo1.jpg'
import galeria2 from '../assets/galeria/trabajo2.jpg'
import galeria3 from '../assets/galeria/trabajo3.jpg'
import galeria4 from '../assets/galeria/trabajo4.jpg'

import { useServicios } from '../hooks/useServicios.js'

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
  const {
    servicios,
    loading: serviciosLoading,
    error: serviciosError,
  } = useServicios()
  return (
    <>
      {/* HERO SECTION */}
      <header id="inicio" className="hn-hero-section">
        <div className="container">
          <div className="row align-items-center g-5 text-center text-lg-start">
            <div className="col-12 col-lg-6">
              <span className="hn-badge-pink mb-3">
                MANICURA & NAIL ART
              </span>
              <h1 className="hn-hero-title mb-3">
                TU PRÓXIMA <br />
                <span className="gothic-accent">manicura</span> <br />
                EMPIEZA ACÁ ✨
              </h1>
              <p className="lead text-muted mb-4 fs-6">
                Diseños únicos, calidad y detalles para que tus uñas hablen por vos.
              </p>
              <div className="d-flex flex-wrap gap-3 justify-content-center justify-content-lg-start">
                <Link to="/agendar" className="btn btn-hn-dark">
                  RESERVAR TURNO ✨
                </Link>
              </div>
            </div>

            <div className="col-12 col-lg-6 text-center">
              <div className="hn-hero-img-wrapper">
                <img
                  src={heroImg}
                  alt="Holy Nails - Muestra de manicura"
                  className="hn-hero-img"
                  width={1170}
                  height={1552}
                  fetchPriority="high"
                />
                <span className="hn-hero-butterfly" role="img" aria-label="Mariposa">
                  🦋
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* SERVICIOS SECTION */}
      <section id="servicios" className="py-5">
        <div className="container py-4">
          <div className="text-center mb-5">
            <h2 className="hn-section-title mb-2">✦ NUESTROS SERVICIOS ✦</h2>
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
                <div className="col-12 col-md-4" key={s.id}>
                  <div className="card hn-card h-100 text-center p-4">
                    <div className="card-body d-flex flex-column align-items-center">
                      <div className="hn-card-icon" aria-hidden="true">
                        <span style={{ fontSize: '2.5rem' }}>💅</span>
                      </div>
                      <h3 className="h5 font-weight-bold fw-bold mt-2 mb-2">
                        {s.nombre}
                      </h3>
                      <p className="small text-muted mb-2">
                        ⏱️ Duración: <strong>{formatearDuracion(s.duracion)}</strong>
                      </p>
                      <p className="small text-dark fw-bold mb-3">
                        💰 {formatearPrecio(s.precio)}
                      </p>
                      <a href="#contacto" className="btn btn-hn-pink mt-auto">
                        VER MÁS
                      </a>
                    </div>
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
            <h2 className="hn-section-title mb-2">✦ ALGUNOS TRABAJOS ✦</h2>
            <p className="text-muted small">
              Especialistas en diseños cute & dark hechos a mano
            </p>
          </div>

          <div className="row g-3 justify-content-center">
            {trabajosGaleria.map((t) => (
              <div className="col-6 col-md-6 col-lg-3" key={t.id}>
                <div className="hn-gallery-card h-100">
                  <div className="hn-gallery-thumb">
                    <img
                      src={t.imagen}
                      alt={`Diseño ${t.id} de manicura Holy Nails`}
                      loading="lazy"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="text-center mt-5">
            <a
              href="https://instagram.com/holy.nails.demo"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-hn-outline"
            >
              VER MÁS EN INSTAGRAM 📷
            </a>
          </div>
        </div>
      </section>

      {/* CONTACTO SECTION */}
      <section id="contacto" className="py-5">
        <div className="container">
          <div className="hn-contacto-section text-center">
            <h2 className="hn-section-title mb-2">¿TENÉS UNA CONSULTA?</h2>
            <p className="text-muted mb-4">
              Escribinos por WhatsApp y te ayudamos con tu pedido o dudas.
            </p>

            <div className="row justify-content-center g-4 my-3 text-start">
              <div className="col-12 col-sm-6 col-lg-3">
                <div className="p-3 bg-white rounded-3 shadow-sm h-100">
                  <p className="fw-bold mb-2">💬 WhatsApp</p>
                  <p className="small text-muted mb-0">+54 9 260 000 0000</p>
                </div>
              </div>

              <div className="col-12 col-sm-6 col-lg-3">
                <div className="p-3 bg-white rounded-3 shadow-sm h-100">
                  <p className="fw-bold mb-2">📷 Instagram</p>
                  <p className="small text-muted mb-0">@holy.nails.demo</p>
                </div>
              </div>

              <div className="col-12 col-sm-6 col-lg-3">
                <div className="p-3 bg-white rounded-3 shadow-sm h-100">
                  <p className="fw-bold mb-2">📍 Ubicación</p>
                  <p className="small text-muted mb-0">
                    Av. Ejemplo 123, San Rafael, Mendoza
                  </p>
                </div>
              </div>

              <div className="col-12 col-sm-6 col-lg-3">
                <div className="p-3 bg-white rounded-3 shadow-sm h-100">
                  <p className="fw-bold mb-2">⏰ Horarios</p>
                  <p className="small text-muted mb-0">
                    Atención con turnos previos. Consultá disponibilidad.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4">
              <a
                href="https://wa.me/5492600000000"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-hn-whatsapp"
              >
                HABLAR POR WHATSAPP 💬
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* BANNER PRE-FOOTER */}
      <section className="py-4">
        <div className="container">
          <div className="hn-banner-cta text-center">
            <h3 className="hn-section-title mb-2">
              ¿LISTA PARA TU PRÓXIMO SET? ✨
            </h3>
            <p className="text-muted mb-4">
              Reservá tu turno de forma rápida y sencilla.
            </p>
            <Link to="/agendar" className="btn btn-hn-dark">
              RESERVAR TURNO ✨
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}

export default Home
