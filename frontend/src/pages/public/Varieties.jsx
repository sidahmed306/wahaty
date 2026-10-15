import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { asList } from '../../api/client'
import { AngledLine, Empty, ErrorAlert, Loader, SectionTitle } from '../../components/ui'
import { localized, monthName, monthsInSeason } from '../../lib/format'
import { useFetch } from '../../lib/useFetch'

export function SeasonBar({ start, end }) {
  const { t, i18n } = useTranslation()
  const months = monthsInSeason(start, end)
  return (
    <div>
      <div>
        {t('varieties.season')} : {monthName(start, i18n.language)} → {monthName(end, i18n.language)}
      </div>
      <div className="month-bar" aria-hidden="true">
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} className={months.includes(i + 1) ? 'on' : ''} />
        ))}
      </div>
    </div>
  )
}

export default function Varieties() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [search, setSearch] = useState('')
  const [inSeason, setInSeason] = useState(false)
  const params = { search, in_season: inSeason ? new Date().getMonth() + 1 : '' }
  const { data, loading, error } = useFetch('/api/varieties/', params, { auth: false })
  const list = asList(data)

  return (
    <section className="section container">
      <SectionTitle kicker="Variétés · أنواع التمر" title={t('varieties.title')}>
        <p className="muted">{t('varieties.intro')}</p>
      </SectionTitle>
      <div className="filters">
        <div className="field">
          <label htmlFor="v-search">{t('common.search')}</label>
          <input id="v-search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="checks" style={{ alignSelf: 'end' }}>
          <label>
            <input type="checkbox" checked={inSeason} onChange={(e) => setInSeason(e.target.checked)} />
            {t('varieties.inSeasonNow')}
          </label>
        </div>
      </div>
      <ErrorAlert error={error} />
      {loading && !data ? (
        <Loader />
      ) : list.length === 0 ? (
        <Empty />
      ) : (
        <div className="variety-list">
          {list.map((v) => (
            <div key={v.id}>
              <Link to={`/varietes/${v.slug}`} className="variety-row">
                <img className="photo" src={v.photo || '/logo-mark.webp'} alt="" loading="lazy" />
                <div>
                  <h3>{localized(v, 'name', lang)}</h3>
                  <p>{localized(v, 'description', lang)}</p>
                </div>
              </Link>
              <AngledLine />
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function VarietyDetail() {
  const { slug } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { data: v, loading, error } = useFetch(`/api/varieties/${slug}/`, null, { auth: false })

  if (loading) return <Loader />
  if (error || !v)
    return (
      <div className="container section">
        <ErrorAlert error={error?.status === 404 ? t('errors.notFound') : error} />
      </div>
    )

  return (
    <section className="section container">
      <Link to="/varietes" className="small">
        ← {t('varieties.back')}
      </Link>
      <div className="detail-hero mt">
        <img src={v.photo || '/logo-mark.webp'} alt={localized(v, 'name', lang)} />
        <div>
          <h1>{localized(v, 'name', lang)}</h1>
          <div className="muted latin small">{lang === 'ar' ? v.name_fr : v.name_ar}</div>
          <AngledLine />
          <p style={{ fontSize: '1.1rem', color: '#3c5a40' }}>{localized(v, 'description', lang)}</p>
          <div className="facts">
            {v.texture && (
              <div>
                <span>{t('varieties.texture')}</span>
                <strong>{t(`texture.${v.texture}`)}</strong>
              </div>
            )}
          </div>
          <SeasonBar start={v.ripening_start_month} end={v.ripening_end_month} />
          {v.oases?.length > 0 && (
            <div className="mt">
              <h3>{t('varieties.foundIn')}</h3>
              <div className="btn-row">
                {v.oases.map((o) => (
                  <Link key={o.id} className="btn btn-ghost btn-sm" to={`/oasis/${o.slug}`}>
                    {localized(o, 'name', lang)}
                  </Link>
                ))}
              </div>
            </div>
          )}
          <div className="mt">
            <Link className="btn btn-primary" to={`/marche?variety=${v.slug}`}>
              {t('varieties.buy')}
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}
