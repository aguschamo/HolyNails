import logo from '../assets/galeria/logo.png'

function Footer() {
  const anio = new Date().getFullYear()

  return (
    <footer className="hn-footer py-4 mt-auto">
      <div className="container">
        <div className="hn-footer-inner">
          <span
            className="hn-footer-logo"
            role="img"
            aria-label="Holy Nails"
            style={{
              WebkitMaskImage: `url(${logo})`,
              maskImage: `url(${logo})`,
              WebkitMaskSize: 'contain',
              maskSize: 'contain',
              WebkitMaskRepeat: 'no-repeat',
              maskRepeat: 'no-repeat',
              WebkitMaskPosition: 'center',
              maskPosition: 'center',
            }}
          />
          <p className="small mb-0">
            © {anio} Holy Nails. Todos los derechos reservados.
          </p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
