import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { onSlowChange } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { CONTACT_DISPLAY, whatsappLink } from '../config'
import { CloseIcon, MenuIcon, PhoneIcon, WhatsAppIcon } from './Icons'

export function Brand() {
  return (
    <Link to="/" className="brand" aria-label="TRC إرث النخيل">
      <img src="/logo-mark.webp" alt="" width="44" height="40" />
      <span className="names">
        <span className="ar-name" lang="ar">
          إرث النخيل
        </span>
        <span className="trc">TRC</span>
      </span>
    </Link>
  )
}

export function LanguageSwitch() {
  const { t, i18n } = useTranslation()
  const next = i18n.language === 'ar' ? 'fr' : 'ar'
  return (
    <button
      type="button"
      className="lang-switch"
      onClick={() => i18n.changeLanguage(next)}
      aria-label={t('nav.switchLanguage')}
      lang={next}
    >
      {next === 'fr' ? 'FR' : 'ع'}
    </button>
  )
}

function Header() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()

  useEffect(() => setOpen(false), [location.pathname])

  const links = [
    ['/', t('nav.home'), true],
    ['/varietes', t('nav.varieties')],
    ['/oasis', t('nav.oases')],
    ['/marche', t('nav.market')],
  ]

  return (
    <header className="site-header">
      <div className="container bar">
        <Brand />
        <nav className={`main-nav ${open ? 'open' : ''}`} aria-label={t('nav.main')}>
          <ul>
            {links.map(([to, label, end]) => (
              <li key={to}>
                <NavLink to={to} end={end}>
                  {label}
                </NavLink>
              </li>
            ))}
            {user ? (
              <li>
                <NavLink to="/espace">{t('nav.mySpace')}</NavLink>
              </li>
            ) : (
              <>
                <li>
                  <NavLink to="/connexion">{t('nav.login')}</NavLink>
                </li>
                <li>
                  <NavLink to="/inscription">{t('nav.register')}</NavLink>
                </li>
              </>
            )}
          </ul>
        </nav>
        <LanguageSwitch />
        <button
          type="button"
          className="nav-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? t('nav.close') : t('nav.open')}
        >
          {open ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>
    </header>
  )
}

export function Footer() {
  const { t } = useTranslation()
  return (
    <footer className="site-footer">
      <div className="container inner">
        <div>
          <strong>TRC إرث النخيل</strong>
          <div className="muted">{t('footer.tagline')}</div>
        </div>
        <div className="btn-row">
          <a
            className="contact-pill"
            href={whatsappLink(undefined, t('footer.whatsappMessage'))}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`WhatsApp ${CONTACT_DISPLAY}`}
          >
            <WhatsAppIcon />
            <span className="num">{CONTACT_DISPLAY}</span>
          </a>
          <a className="contact-pill" href="tel:+22247826859" aria-label={t('footer.call')}>
            <PhoneIcon />
            <span>{t('footer.call')}</span>
          </a>
          <Link className="contact-pill" to="/installer">
            <img src="/favicon.png" alt="" width="22" height="22" style={{ borderRadius: 6 }} />
            <span>{t('install.short')}</span>
          </Link>
        </div>
        <div className="muted small">
          © {new Date().getFullYear()} TRC — {t('footer.rights')}
        </div>
      </div>
    </footer>
  )
}

/** Bandeau affiché quand le serveur tarde (serveur gratuit qui se réveille). */
export function WakeBanner() {
  const { t } = useTranslation()
  const [slow, setSlow] = useState(false)
  useEffect(() => onSlowChange(setSlow), [])
  if (!slow) return null
  return (
    <div className="wake-banner" role="status">
      <span className="loader-dot" aria-hidden="true" />
      {t('errors.waking')}
    </div>
  )
}

export default function Layout() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo?.(0, 0)
  }, [pathname])
  return (
    <>
      <a href="#main" className="visually-hidden">
        Skip
      </a>
      <Header />
      <main id="main">
        <Outlet />
      </main>
      <Footer />
      <WakeBanner />
    </>
  )
}
