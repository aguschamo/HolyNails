import { useEffect, useRef, useState } from 'react'

import miPerfilImg from '../assets/galeria/mi-perfil.png'
import Avatar from '../components/Avatar.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const ETIQUETA_ROL = {
  cliente: 'Clienta',
  personal: 'Personal',
  admin: 'Administración',
}

// Mismos límites que el backend: el modelo User define max_length=30 y
// validate_telefono sólo admite números y símbolos habituales. El cliente
// evita envíos inválidos; la API sigue siendo la autoridad final.
const LIMITE_NOMBRE = 150
const LIMITE_TELEFONO = 30
const TELEFONO_PERMITIDO = /^[0-9\s()+.-]+$/

// B11.2: límites de la foto, idénticos a FotoPerfilSerializer.
const LIMITE_FOTO_BYTES = 2 * 1024 * 1024
const FORMATOS_FOTO = ['image/jpeg', 'image/png', 'image/webp']

// Perfil de usuario (B11.1 + B11.2): nombre y teléfono editables con
// PATCH /api/auth/profile/, y foto persistente con
// POST/DELETE /api/auth/profile/foto/ (multipart). La foto se sube al
// backend y se muestra desde la URL guardada: la vista previa local es
// sólo un paso intermedio antes de subir. El email y el rol se muestran
// como información (no se modifican desde este formulario). Ante un error
// de red o de validación, los campos y la foto anteriores se conservan.
function Perfil() {
  const { usuario, actualizarPerfil, subirFoto, eliminarFoto } = useAuth()

  const [nombre, setNombre] = useState(usuario.nombre ?? '')
  const [telefono, setTelefono] = useState(usuario.telefono ?? '')
  const [preview, setPreview] = useState(null)
  const [archivo, setArchivo] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [exito, setExito] = useState('')
  const [error, setError] = useState('')
  const [subiendoFoto, setSubiendoFoto] = useState(false)
  const [eliminandoFoto, setEliminandoFoto] = useState(false)
  const [exitoFoto, setExitoFoto] = useState('')
  const [errorFoto, setErrorFoto] = useState('')
  const inputFotoRef = useRef(null)

  // Limpieza de object URLs al desmontar (evita fugas de memoria) y al
  // reemplazar la vista previa.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview)
    }
  }, [preview])

  function liberarPreview() {
    if (preview) URL.revokeObjectURL(preview)
    setPreview(null)
  }

  function handlePhoto(e) {
    const seleccionado = e.target.files?.[0]
    if (!seleccionado) return

    // Validación temprana con los mismos mensajes que el backend: no se
    // gasta una petición en algo que el servidor va a rechazar.
    if (!FORMATOS_FOTO.includes(seleccionado.type)) {
      setErrorFoto('Formato no admitido. Usá una imagen JPEG, PNG o WebP.')
      if (inputFotoRef.current) inputFotoRef.current.value = ''
      return
    }
    if (seleccionado.size > LIMITE_FOTO_BYTES) {
      setErrorFoto('La imagen no puede superar los 2 MB.')
      if (inputFotoRef.current) inputFotoRef.current.value = ''
      return
    }

    // Se descarta la vista previa anterior y se muestra la nueva.
    liberarPreview()
    setArchivo(seleccionado)
    setPreview(URL.createObjectURL(seleccionado))
    setExitoFoto('')
    setErrorFoto('')
  }

  function cancelarFoto() {
    liberarPreview()
    setArchivo(null)
    setErrorFoto('')
    setExitoFoto('')
    if (inputFotoRef.current) inputFotoRef.current.value = ''
  }

  async function subirFotoSeleccionada() {
    // Evita subidas duplicadas mientras hay una petición en vuelo.
    if (subiendoFoto || !archivo) return
    setErrorFoto('')
    setExitoFoto('')
    setSubiendoFoto(true)
    try {
      const datos = new FormData()
      datos.append('foto', archivo)
      await subirFoto(datos)
      // Éxito: la foto persistida viene del backend, se suelta la vista
      // previa local y el encabezado/Navbar muestran la foto guardada.
      liberarPreview()
      setArchivo(null)
      if (inputFotoRef.current) inputFotoRef.current.value = ''
      setExitoFoto('Foto actualizada correctamente.')
    } catch (err) {
      // La foto anterior se conserva (el contexto no se tocó). La vista
      // previa queda para poder reintentar.
      setErrorFoto(err.message || 'No se pudo subir la foto.')
    } finally {
      setSubiendoFoto(false)
    }
  }

  async function borrarFoto() {
    if (eliminandoFoto || subiendoFoto) return
    setErrorFoto('')
    setExitoFoto('')
    setEliminandoFoto(true)
    try {
      await eliminarFoto()
      setExitoFoto('Foto eliminada.')
    } catch (err) {
      setErrorFoto(err.message || 'No se pudo eliminar la foto.')
    } finally {
      setEliminandoFoto(false)
    }
  }

  function alEditar(campo, valor) {
    if (campo === 'nombre') setNombre(valor)
    else setTelefono(valor)
    // Cualquier edición limpia los mensajes de la operación anterior.
    setExito('')
    setError('')
  }

  async function guardar(e) {
    e.preventDefault()
    // Evita envíos duplicados mientras hay un guardado en curso.
    if (guardando) return
    setExito('')
    setError('')

    const nombreLimpio = nombre.trim()
    const telefonoLimpio = telefono.trim()

    if (!nombreLimpio) {
      setError('Completá tu nombre y apellido.')
      return
    }
    if (nombreLimpio.length > LIMITE_NOMBRE) {
      setError(`El nombre no puede superar los ${LIMITE_NOMBRE} caracteres.`)
      return
    }
    if (telefonoLimpio && !TELEFONO_PERMITIDO.test(telefonoLimpio)) {
      setError('El teléfono sólo puede contener números, espacios y los símbolos + - ( ) .')
      return
    }
    if (telefonoLimpio.length > LIMITE_TELEFONO) {
      setError(`El teléfono no puede superar los ${LIMITE_TELEFONO} caracteres.`)
      return
    }

    setGuardando(true)
    try {
      await actualizarPerfil({ nombre: nombreLimpio, telefono: telefonoLimpio })
      // Sincroniza el estado local con los valores saneados; el encabezado
      // se actualiza porque el contexto ya tiene la respuesta del backend.
      setNombre(nombreLimpio)
      setTelefono(telefonoLimpio)
      setExito('Perfil actualizado correctamente.')
    } catch (err) {
      // Errores de validación (400) y de red llegan traducidos en
      // err.message. Los campos NO se resetean: no se pierden los cambios.
      setError(err.message || 'No se pudo guardar el perfil.')
    } finally {
      setGuardando(false)
    }
  }

  const hayFotoGuardada = Boolean(usuario.photo)

  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="row justify-content-center">
          <div className="col-12 col-md-8 col-lg-6">
            <div className="text-center mb-4">
              <h1 className="hn-section-title hn-page-title mb-1">
                <img
                  src={miPerfilImg}
                  alt="Mi perfil"
                  className="hn-page-title-img"
                />
              </h1>
              <p className="text-muted small mb-0">Tus datos de Holy Nails</p>
            </div>

            <div className="card hn-card">
              <div className="card-body p-4">
                <div className="d-flex align-items-center gap-3 mb-4">
                  <Avatar nombre={usuario.nombre} photo={preview || usuario.photo} size="lg" />
                  <div>
                    <h2 className="h5 fw-bold mb-1">
                      {usuario.nombre || 'Nombre sin completar'}
                    </h2>
                    <p className="small text-muted mb-1">{usuario.email}</p>
                    <span className="badge hn-badge-pink">
                      {ETIQUETA_ROL[usuario.role] || usuario.role}
                    </span>
                  </div>
                </div>

                <hr />

                <form onSubmit={guardar} noValidate>
                  {exito && (
                    <div className="alert alert-success py-2 small" role="status">
                      {exito}
                    </div>
                  )}
                  {error && (
                    <div className="alert alert-danger py-2 small" role="alert">
                      {error}
                    </div>
                  )}

                  <div className="mb-4">
                    <label htmlFor="perfilNombre" className="form-label">
                      Nombre y apellido
                    </label>
                    <input
                      id="perfilNombre"
                      type="text"
                      className="form-control"
                      value={nombre}
                      maxLength={LIMITE_NOMBRE}
                      onChange={(e) => alEditar('nombre', e.target.value)}
                      disabled={guardando}
                    />
                    <div className="form-text">
                      Tal como aparece en tus turnos.
                    </div>
                  </div>

                  <div className="mb-4">
                    <label htmlFor="perfilTelefono" className="form-label">
                      Teléfono de contacto
                    </label>
                    <input
                      id="perfilTelefono"
                      type="tel"
                      className="form-control"
                      value={telefono}
                      maxLength={LIMITE_TELEFONO}
                      placeholder="Ej: 11 5555-4321"
                      onChange={(e) => alEditar('telefono', e.target.value)}
                      disabled={guardando}
                    />
                    <div className="form-text">Opcional. Sólo números y símbolos + - ( ) .</div>
                  </div>

                  <button
                    type="submit"
                    className="btn btn-hn-dark w-100"
                    disabled={guardando}
                  >
                    {guardando ? 'Guardando…' : 'Guardar cambios'}
                  </button>
                </form>

                <hr />

                {/* B11.2 — foto de perfil persistente. Se gestiona con su
                    propio endpoint multipart, separada del formulario
                    JSON de nombre/teléfono. */}
                <div>
                  <h2 className="h6 fw-bold mb-2">Foto de perfil</h2>

                  {exitoFoto && (
                    <div className="alert alert-success py-2 small" role="status">
                      {exitoFoto}
                    </div>
                  )}
                  {errorFoto && (
                    <div className="alert alert-danger py-2 small" role="alert">
                      {errorFoto}
                    </div>
                  )}

                  <label htmlFor="perfilFoto" className="form-label">
                    Elegir imagen
                  </label>
                  <input
                    id="perfilFoto"
                    ref={inputFotoRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="form-control"
                    onChange={handlePhoto}
                    disabled={subiendoFoto || eliminandoFoto || guardando}
                  />
                  <div className="form-text mb-3">
                    JPEG, PNG o WebP de hasta 2 MB.
                    {hayFotoGuardada && !preview && ' Tu foto se guarda en tu cuenta.'}
                    {preview && ' Vista previa: todavía no se guardó.'}
                  </div>

                  <div className="d-flex flex-wrap gap-2">
                    {preview ? (
                      <>
                        <button
                          type="button"
                          className="btn btn-hn-dark btn-sm"
                          onClick={subirFotoSeleccionada}
                          disabled={subiendoFoto || eliminandoFoto}
                        >
                          {subiendoFoto ? 'Subiendo…' : 'Subir foto'}
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline-secondary btn-sm"
                          onClick={cancelarFoto}
                          disabled={subiendoFoto}
                        >
                          Cancelar
                        </button>
                      </>
                    ) : (
                      hayFotoGuardada && (
                        <button
                          type="button"
                          className="btn btn-outline-danger btn-sm"
                          onClick={borrarFoto}
                          disabled={eliminandoFoto || subiendoFoto}
                        >
                          {eliminandoFoto ? 'Eliminando…' : 'Eliminar foto'}
                        </button>
                      )
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default Perfil
