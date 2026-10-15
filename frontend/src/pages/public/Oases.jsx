import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { asList } from '../../api/client'
import { PinIcon } from '../../components/Icons'
import { AngledLine, Empty, ErrorAlert, Loader, SectionTitle } from '../../components/ui'
import { localized } from '../../lib/format'
import { useFetch } from '../../lib/useFetch'

export default function Oases() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [region, setRegion] = useState('')
  const regions = useFetch('/api/regions/', null, { auth: false })
  const { data, loading, error } = useFetch('/api/oases/', { region }, { auth: false })
  const list = asList(data)

  return (
    <section className="section container">
      <SectionTitle kicker="Oasis · واحات" title={t('oases.title')}>
        <p className="muted">{t('oases.intro')}</p>
      </SectionTitle>
      <div className="btn-row" style={{ marginBottom: 20 }} role="group" aria-label={t('oases.region')}>
        <button
          type="button"
          className={`btn btn-sm ${region === '' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => setRegion('')}
        >
          {t('common.all')}
        </button>
        {asList(regions.data).map((r) => (
          <button
            key={r.id}
            type="button"
            className={`btn btn-sm ${region === r.slug ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setRegion(r.slug)}
          >
            {localized(r, 'name', lang)}
          </button>
        ))}
      </div>
      <ErrorAlert error={error} />
      {loading && !data ? (
        <Loader />
      ) : list.length === 0 ? (
        <Empty>{t('oases.empty')}</Empty>
      ) : (
        <div className="grid">
          {list.map((o) => (
            <Link key={o.id} to={`/oasis/${o.slug}`} className="variety-card">
              <img
                className="photo"
                style={{ aspectRatio: '4 / 3' }}
                src={o.photos?.[0]?.image || '/oasis.webp'}
                alt=""
                loading="lazy"
              />
              <div className="body">
                <h3>{localized(o, 'name', lang)}</h3>
                <div className="muted small">
                  <PinIcon width={16} height={16} /> {localized(o.region_detail, 'name', lang)}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}

export function OasisDetail() {
  const { slug } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { data: o, loading, error } = useFetch(`/api/oases/${slug}/`, null, { auth: false })

  if (loading) return <Loader />
  if (error || !o)
    return (
      <div className="container section">
        <ErrorAlert error={error?.status === 404 ? t('errors.notFound') : error} />
      </div>
    )

  const hasMap = o.latitude && o.longitude
  return (
    <section className="section container">
      <Link to="/oasis" className="small">
        ← {t('oases.back')}
      </Link>
      <h1 className="mt">{localized(o, 'name', lang)}</h1>
      <div className="muted">
        <PinIcon width={16} height={16} /> {localized(o.region_detail, 'name', lang)}
      </div>
      <AngledLine />
      {o.photos?.length > 0 ? (
        <div className="gallery mt">
          {o.photos.map((p) => (
            <figure key={p.id} style={{ margin: 0 }}>
              <img src={p.image} alt={localized(p, 'caption', lang)} loading="lazy" />
              {localized(p, 'caption', lang) && (
                <figcaption className="small muted">{localized(p, 'caption', lang)}</figcaption>
              )}
            </figure>
          ))}
        </div>
      ) : (
        <img src="/oasis.webp" alt="" className="mt" style={{ borderRadius: 18, width: '100%' }} />
      )}
      <p className="mt" style={{ fontSize: '1.1rem' }}>
        {localized(o, 'description', lang)}
      </p>
      {hasMap && (
        <a
          className="btn btn-outline"
          target="_blank"
          rel="noopener noreferrer"
          href={`https://www.openstreetmap.org/?mlat=${o.latitude}&mlon=${o.longitude}#map=13/${o.latitude}/${o.longitude}`}
        >
          <PinIcon /> {t('oases.map')}
        </a>
      )}
      {o.varieties_detail?.length > 0 && (
        <div className="mt">
          <h2>{t('oases.varieties')}</h2>
          <div className="btn-row">
            {o.varieties_detail.map((v) => (
              <Link key={v.id} className="btn btn-ghost btn-sm" to={`/varietes/${v.slug}`}>
                {localized(v, 'name', lang)}
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
