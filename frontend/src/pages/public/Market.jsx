import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router'
import { asList } from '../../api/client'
import { PhoneIcon, PinIcon, WhatsAppIcon } from '../../components/Icons'
import { AngledLine, Empty, ErrorAlert, Loader, SectionTitle } from '../../components/ui'
import { formatDate, formatKg, formatMoney, localized } from '../../lib/format'
import { useFetch } from '../../lib/useFetch'

export function ListingCard({ listing, to }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  return (
    <Link to={to || `/marche/${listing.id}`} className="listing-card">
      <img
        className="cover"
        src={listing.photos?.[0]?.image || '/logo-mark.webp'}
        alt=""
        loading="lazy"
        style={listing.photos?.[0] ? undefined : { objectFit: 'contain', padding: 24 }}
      />
      <div className="body">
        <strong>{listing.title}</strong>
        <div className="small muted">
          {localized(listing.variety, 'name', lang)} · <PinIcon width={14} height={14} />{' '}
          {localized(listing.oasis, 'name', lang)}
        </div>
        <div>
          <span className="price">{formatMoney(listing.price_per_kg, lang)}</span>{' '}
          <span className="small muted">/ {t('market.perKg')}</span>
        </div>
        <div className="small">
          {t('market.available')} : <span className="num">{formatKg(listing.quantity_kg, lang)}</span>
        </div>
      </div>
    </Link>
  )
}

const FILTERS = ['variety', 'region', 'min_price', 'max_price', 'ordering', 'search', 'page']

export default function Market() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [searchParams, setSearchParams] = useSearchParams()
  const params = Object.fromEntries(FILTERS.map((k) => [k, searchParams.get(k) || '']))
  const page = Number(params.page || 1)
  const varieties = useFetch('/api/varieties/', null, { auth: false })
  const regions = useFetch('/api/regions/', null, { auth: false })
  const { data, loading, error } = useFetch('/api/market/listings/', params, { auth: false })

  const update = (key, value) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next, { replace: true })
  }

  const list = asList(data)
  const pages = data?.count ? Math.ceil(data.count / 20) : 1

  return (
    <section className="section container">
      <SectionTitle kicker="Marché · سوق التمور" title={t('market.title')}>
        <p className="muted">{t('market.intro')}</p>
      </SectionTitle>
      <form className="filters" onSubmit={(e) => e.preventDefault()} role="search">
        <div className="field">
          <label htmlFor="m-search">{t('common.search')}</label>
          <input
            id="m-search"
            defaultValue={params.search}
            onChange={(e) => update('search', e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="m-variety">{t('market.variety')}</label>
          <select id="m-variety" value={params.variety} onChange={(e) => update('variety', e.target.value)}>
            <option value="">{t('common.all')}</option>
            {asList(varieties.data).map((v) => (
              <option key={v.id} value={v.slug}>
                {localized(v, 'name', lang)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="m-region">{t('market.region')}</label>
          <select id="m-region" value={params.region} onChange={(e) => update('region', e.target.value)}>
            <option value="">{t('common.all')}</option>
            {asList(regions.data).map((r) => (
              <option key={r.id} value={r.slug}>
                {localized(r, 'name', lang)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="m-max">{t('market.maxPrice')}</label>
          <input
            id="m-max"
            type="number"
            min="0"
            inputMode="decimal"
            defaultValue={params.max_price}
            onChange={(e) => update('max_price', e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="m-order">{t('market.sort')}</label>
          <select id="m-order" value={params.ordering} onChange={(e) => update('ordering', e.target.value)}>
            <option value="">{t('market.sortRecent')}</option>
            <option value="price_per_kg">{t('market.sortPriceAsc')}</option>
            <option value="-price_per_kg">{t('market.sortPriceDesc')}</option>
            <option value="-quantity_kg">{t('market.sortQuantity')}</option>
          </select>
        </div>
      </form>
      <ErrorAlert error={error} />
      {loading && !data ? (
        <Loader />
      ) : list.length === 0 ? (
        <Empty>{t('market.empty')}</Empty>
      ) : (
        <>
          <div className="grid">
            {list.map((listing) => (
              <ListingCard key={listing.id} listing={listing} />
            ))}
          </div>
          {pages > 1 && (
            <nav className="pagination" aria-label={t('common.pages')}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={page <= 1}
                onClick={() => update('page', String(page - 1))}
              >
                {t('common.previous')}
              </button>
              <span className="num">
                {page} / {pages}
              </span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={page >= pages}
                onClick={() => update('page', String(page + 1))}
              >
                {t('common.next')}
              </button>
            </nav>
          )}
        </>
      )}
    </section>
  )
}

export function ListingDetail() {
  const { id } = useParams()
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { data: l, loading, error } = useFetch(`/api/market/listings/${id}/`, null, { auth: false })

  if (loading) return <Loader />
  if (error || !l)
    return (
      <div className="container section">
        <ErrorAlert error={error?.status === 404 ? t('errors.notFound') : error} />
      </div>
    )

  return (
    <section className="section container">
      <Link to="/marche" className="small">
        ← {t('market.back')}
      </Link>
      <div className="detail-hero mt">
        <div className="stack">
          <img
            src={l.photos?.[0]?.image || '/logo-mark.webp'}
            alt={l.title}
            style={l.photos?.[0] ? undefined : { objectFit: 'contain', padding: 40 }}
          />
          {l.photos?.length > 1 && (
            <div className="photos">
              {l.photos.slice(1).map((p) => (
                <img key={p.id} src={p.image} alt="" loading="lazy" />
              ))}
            </div>
          )}
        </div>
        <div>
          <h1>{l.title}</h1>
          <AngledLine />
          <div className="facts">
            <div>
              <span>{t('market.variety')}</span>
              <Link to={`/varietes/${l.variety.slug}`}>{localized(l.variety, 'name', lang)}</Link>
            </div>
            <div>
              <span>{t('market.oasis')}</span>
              <span>
                {localized(l.oasis, 'name', lang)} – {localized(l.oasis.region, 'name', lang)}
              </span>
            </div>
            <div>
              <span>{t('market.price')}</span>
              <strong className="price">{formatMoney(l.price_per_kg, lang)} / {t('market.perKg')}</strong>
            </div>
            <div>
              <span>{t('market.available')}</span>
              <strong className="num">{formatKg(l.quantity_kg, lang)}</strong>
            </div>
            <div>
              <span>{t('market.seller')}</span>
              <span>{l.seller_name}</span>
            </div>
            <div>
              <span>{t('market.publishedAt')}</span>
              <span>{formatDate(l.published_at, lang)}</span>
            </div>
          </div>
          {l.description && <p dir="auto">{l.description}</p>}
          <div className="btn-row">
            <a className="btn whatsapp-btn" href={l.whatsapp_link} target="_blank" rel="noopener noreferrer">
              <WhatsAppIcon /> {t('market.whatsapp')}
            </a>
            <a className="btn btn-outline" href={l.phone_link}>
              <PhoneIcon /> {t('market.call')}
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
