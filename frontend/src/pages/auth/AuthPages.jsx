import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthProvider'
import Field from '../../components/Field'
import { AngledLine, ErrorAlert } from '../../components/ui'

function AuthCard({ title, children }) {
  return (
    <section className="container">
      <div className="auth-page card">
        <img src="/logo-mark.webp" alt="" style={{ width: 70, margin: '0 auto' }} />
        <h1 style={{ textAlign: 'center', fontSize: '1.6rem' }}>{title}</h1>
        <AngledLine />
        {children}
      </div>
    </section>
  )
}

export function Login() {
  const { t } = useTranslation()
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/espace" replace />

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(phone, password)
      navigate(location.state?.from || '/espace', { replace: true })
    } catch (err) {
      setError(err.status === 401 ? t('auth.wrongCredentials') : err.status === 429 ? t('errors.tooMany') : err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title={t('auth.loginTitle')}>
      <form className="form" onSubmit={submit} noValidate>
        <ErrorAlert error={error} />
        <Field
          label={t('fields.phone')}
          type="tel"
          value={phone}
          onChange={setPhone}
          autoComplete="username"
          help={t('auth.phoneHelp')}
          required
        />
        <Field
          label={t('fields.password')}
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          required
        />
        <button className="btn btn-primary" disabled={busy}>
          {busy ? t('common.wait') : t('auth.loginButton')}
        </button>
        <p className="small muted" style={{ textAlign: 'center' }}>
          {t('auth.noAccount')} <Link to="/inscription">{t('nav.register')}</Link>
          <br />
          {t('auth.haveCode')} <Link to="/reprise">{t('auth.claimLink')}</Link>
        </p>
      </form>
    </AuthCard>
  )
}

export function Register() {
  const { t, i18n } = useTranslation()
  const [form, setForm] = useState({ full_name: '', phone: '', password: '', roles: ['farmer'] })
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/api/auth/register/', {
        method: 'POST',
        auth: false,
        body: { ...form, preferred_language: i18n.language },
      })
      setDone(true)
    } catch (err) {
      setError(err.status === 429 ? t('errors.tooMany') : err)
    } finally {
      setBusy(false)
    }
  }

  if (done)
    return (
      <AuthCard title={t('auth.registerDoneTitle')}>
        <div className="alert success">{t('auth.registerDone')}</div>
        <Link className="btn btn-primary mt" to="/connexion">
          {t('nav.login')}
        </Link>
      </AuthCard>
    )

  const fields = error?.fields || {}
  return (
    <AuthCard title={t('auth.registerTitle')}>
      <form className="form" onSubmit={submit} noValidate>
        {error && !Object.keys(fields).length && <ErrorAlert error={error} />}
        <Field
          label={t('fields.fullName')}
          value={form.full_name}
          onChange={set('full_name')}
          error={fields.full_name}
          autoComplete="name"
          required
        />
        <Field
          label={t('fields.phone')}
          type="tel"
          value={form.phone}
          onChange={set('phone')}
          error={fields.phone}
          autoComplete="tel"
          help={t('auth.phoneHelp')}
          required
        />
        <Field
          label={t('fields.password')}
          type="password"
          value={form.password}
          onChange={set('password')}
          error={fields.password}
          autoComplete="new-password"
          help={t('auth.passwordHelp')}
          required
        />
        <Field
          label={t('auth.iAm')}
          type="checkboxes"
          value={form.roles}
          onChange={set('roles')}
          error={fields.roles}
          options={[
            { value: 'farmer', label: t('roles.farmer') },
            { value: 'seller', label: t('roles.seller') },
          ]}
        />
        <div className="alert info small">{t('auth.validationNote')}</div>
        <button className="btn btn-primary" disabled={busy}>
          {busy ? t('common.wait') : t('auth.registerButton')}
        </button>
        <p className="small muted" style={{ textAlign: 'center' }}>
          {t('auth.haveAccount')} <Link to="/connexion">{t('nav.login')}</Link>
        </p>
      </form>
    </AuthCard>
  )
}

export function Claim() {
  const { t } = useTranslation()
  const [form, setForm] = useState({ phone: '', code: '', password: '' })
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/api/auth/claim/', { method: 'POST', auth: false, body: form })
      setDone(true)
    } catch (err) {
      setError(err.status === 429 ? t('errors.tooMany') : err)
    } finally {
      setBusy(false)
    }
  }

  if (done)
    return (
      <AuthCard title={t('auth.claimTitle')}>
        <div className="alert success">{t('auth.claimDone')}</div>
        <Link className="btn btn-primary mt" to="/connexion">
          {t('nav.login')}
        </Link>
      </AuthCard>
    )

  const fields = error?.fields || {}
  return (
    <AuthCard title={t('auth.claimTitle')}>
      <p className="muted">{t('auth.claimIntro')}</p>
      <form className="form" onSubmit={submit} noValidate>
        {error && !Object.keys(fields).length && <ErrorAlert error={error} />}
        <Field label={t('fields.phone')} type="tel" value={form.phone} onChange={set('phone')} error={fields.phone} required />
        <Field
          label={t('auth.code')}
          value={form.code}
          onChange={set('code')}
          error={fields.code}
          autoComplete="one-time-code"
          style={{ textTransform: 'uppercase', direction: 'ltr' }}
          required
        />
        <Field
          label={t('auth.newPassword')}
          type="password"
          value={form.password}
          onChange={set('password')}
          error={fields.password}
          autoComplete="new-password"
          help={t('auth.passwordHelp')}
          required
        />
        <button className="btn btn-primary" disabled={busy}>
          {busy ? t('common.wait') : t('auth.claimButton')}
        </button>
      </form>
    </AuthCard>
  )
}
