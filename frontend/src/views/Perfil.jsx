import { useEffect, useState } from 'react'

import Avatar from '../components/Avatar.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const ETIQUETA_ROL = {
  cliente: 'Clienta',
  admin: 'Administración',
}

function Perfil() {
  const { usuario } = useAuth()
  const [preview, setPreview] = useState(null)

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview)
    }
  }, [preview])

  function handlePhoto(e) {
    const archivo = e.target.files?.[0]
    if (!archivo) return
    setPreview(URL.createObjectURL(archivo))
  }

  return (
    <section className="hn-auth-bg py-5">
      <div className="container py-4">
        <div className="row justify-content-center">
          <div className="col-12 col-md-8 col-lg-6">
            <div className="text-center mb-4">
              <h1 className="hn-section-title mb-1">✦ MI PERFIL ✦</h1>
              <p className="text-muted small mb-0">Tus datos de Holy Nails</p>
            </div>

            <div className="card hn-card border-0 shadow-sm p-4">
              <div className="card-body">
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

                <div className="mb-4">
                  <label htmlFor="perfilNombre" className="form-label">
                    Nombre y apellido
                  </label>
                  <input
                    id="perfilNombre"
                    type="text"
                    className="form-control"
                    placeholder="Se puede completar en el TP8"
                    defaultValue={usuario.nombre ?? ''}
                    disabled
                  />
                  <div className="form-text">
                    La edición de datos se conectará con la API en el TP8.
                  </div>
                </div>

                <div>
                  <label htmlFor="perfilFoto" className="form-label">
                    Foto de perfil
                  </label>
                  <input
                    id="perfilFoto"
                    type="file"
                    accept="image/*"
                    className="form-control"
                    onChange={handlePhoto}
                  />
                  <div className="form-text">
                    Opcional. La vista previa es local; la subida real se
                    implementará junto a la API.
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