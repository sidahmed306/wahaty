import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AngledLine } from '../../components/ui'
import { canPromptInstall, isInstalled, onInstallChange, platform, promptInstall } from '../../lib/install'

function Steps({ title, steps }) {
  return (
    <div className="panel">
      <h2 style={{ fontSize: '1.2rem' }}>{title}</h2>
      <ol className="install-steps">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </div>
  )
}

export default function Install() {
  const { t } = useTranslation()
  const [, refresh] = useState(0)
  const [result, setResult] = useState(null)
  useEffect(() => onInstallChange(() => refresh((n) => n + 1)), [])
  const device = platform()
  const ios = t('install.ios', { returnObjects: true })
  const android = t('install.android', { returnObjects: true })

  const install = async () => setResult((await promptInstall()) ? 'accepted' : 'dismissed')

  return (
    <section className="container section">
      <div className="auth-page" style={{ maxWidth: 560 }}>
        <div style={{ textAlign: 'center' }}>
          <img src="/icon-192.png" alt="" width="96" height="96" className="install-icon" />
          <h1 style={{ fontSize: '1.6rem', marginTop: 12 }}>{t('install.title')}</h1>
          <p className="muted">{t('install.intro')}</p>
        </div>
        <AngledLine />
        {isInstalled() ? (
          <div className="alert success">{t('install.already')}</div>
        ) : (
          <div className="stack">
            {canPromptInstall() && (
              <button type="button" className="btn btn-primary" onClick={install}>
                {t('install.button')}
              </button>
            )}
            {result === 'accepted' && <div className="alert success">{t('install.done')}</div>}
            {device === 'ios' ? (
              <Steps title={t('install.iosTitle')} steps={ios} />
            ) : device === 'android' ? (
              <Steps title={t('install.androidTitle')} steps={android} />
            ) : (
              <>
                <Steps title={t('install.androidTitle')} steps={android} />
                <Steps title={t('install.iosTitle')} steps={ios} />
              </>
            )}
            <p className="small muted">{t('install.free')}</p>
          </div>
        )}
      </div>
    </section>
  )
}
