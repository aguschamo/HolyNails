import { useEffect, useRef } from 'react'

const SELECTOR_FOCOABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function AuthModal({ ariaLabel, closeLabel, onClose, children }) {
  const panelRef = useRef(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  })

  useEffect(() => {
    const opener = document.activeElement
    const panel = panelRef.current
    const overflowPrevio = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    panel?.focus()

    function manejarTecla(e) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCloseRef.current?.()
        return
      }
      if (e.key !== 'Tab' || !panel) return

      const focoables = Array.from(panel.querySelectorAll(SELECTOR_FOCOABLES)).filter(
        (el) => el.getClientRects().length > 0
      )
      if (focoables.length === 0) {
        e.preventDefault()
        panel.focus()
        return
      }

      const primero = focoables[0]
      const ultimo = focoables[focoables.length - 1]
      const activo = document.activeElement
      const dentro = panel.contains(activo)

      if (e.shiftKey) {
        if (!dentro || activo === panel || activo === primero) {
          e.preventDefault()
          ultimo.focus()
        }
      } else if (!dentro || activo === panel || activo === ultimo) {
        e.preventDefault()
        primero.focus()
      }
    }

    document.addEventListener('keydown', manejarTecla, true)

    return () => {
      document.removeEventListener('keydown', manejarTecla, true)
      document.body.style.overflow = overflowPrevio
      if (
        opener &&
        opener !== document.body &&
        opener.isConnected &&
        typeof opener.focus === 'function'
      ) {
        opener.focus()
      }
    }
  }, [])

  return (
    <div className="hn-auth-overlay">
      <div
        className="hn-auth-panel"
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        ref={panelRef}
        tabIndex={-1}
      >
        <button
          type="button"
          className="hn-auth-close"
          onClick={() => onCloseRef.current?.()}
          aria-label={closeLabel}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            viewBox="0 0 16 16"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />
          </svg>
        </button>
        {children}
      </div>
    </div>
  )
}

export default AuthModal
