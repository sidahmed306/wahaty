import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { asList } from '../../api/client'
import { AngledLine, SectionTitle } from '../../components/ui'
import { localized } from '../../lib/format'
import { useFetch } from '../../lib/useFetch'
import { ListingCard } from './Market'

export default function Home() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const varieties = useFetch('/api/varieties/', null, { auth: false })
  const listings = useFetch('/api/market/listings/', { page_size: 3 }, { auth: false })
  const benefits = t('home.benefits', { returnObjects: true })
  const uses = t('home.uses', { returnObjects: true })

  return (
    <>
      <section className="hero">
        <div className="container content">
          <img className="logo-mark" src="/logo-mark.webp" alt="" />
          <h1 lang="ar">إرث النخيل</h1>
          <p className="subtitle">{t('home.subtitle')}</p>
          <div className="btn-row">
            <Link className="btn btn-sand" to="/varietes">
              {t('home.seeVarieties')}
            </Link>
            <Link className="btn btn-outline" to="/marche">
              {t('home.seeMarket')}
            </Link>
          </div>
        </div>
      </section>

      <section className="section container">
        <div className="grid-2">
          <div>
            <SectionTitle kicker="TRC" title={t('home.aboutTitle')} />
            <p style={{ fontSize: '1.1rem' }}>{t('home.about')}</p>
            <p className="muted">{t('home.about2')}</p>
          </div>
          <div className="band-sand">
            <h2>{t('home.joinTitle')}</h2>
            <p>{t('home.joinText')}</p>
            <div className="btn-row">
              <Link className="btn btn-primary" to="/inscription">
                {t('nav.register')}
              </Link>
              <Link className="btn btn-ghost" style={{ color: '#fff', borderColor: '#fff' }} to="/connexion">
                {t('nav.login')}
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="section container">
        <SectionTitle kicker="Variétés · أنواع" title={t('home.varietiesTitle')} />
        <div className="grid">
          {asList(varieties.data)
            .slice(0, 6)
            .map((v) => (
              <Link key={v.id} to={`/varietes/${v.slug}`} className="variety-card">
                <img className="photo" src={v.photo || '/logo-mark.webp'} alt="" loading="lazy" />
                <div className="body">
                  <h3>{localized(v, 'name', lang)}</h3>
                </div>
              </Link>
            ))}
        </div>
        <div className="mt">
          <Link className="btn btn-outline" to="/varietes">
            {t('home.allVarieties')}
          </Link>
        </div>
      </section>

      <section className="section container">
        <div className="band-green grid-2">
          <div>
            <h2>{t('home.benefitsTitle')}</h2>
            <p>{t('home.benefitsIntro')}</p>
            <ul>{Array.isArray(benefits) && benefits.map((b) => <li key={b}>{b}</li>)}</ul>
          </div>
          <div>
            <h2>{t('home.usesTitle')}</h2>
            <ul>{Array.isArray(uses) && uses.map((u) => <li key={u}>{u}</li>)}</ul>
          </div>
        </div>
      </section>

      {asList(listings.data).length > 0 && (
        <section className="section container">
          <SectionTitle kicker="Marché · سوق" title={t('home.latestListings')} />
          <div className="grid">
            {asList(listings.data).map((listing) => (
              <ListingCard key={listing.id} listing={listing} />
            ))}
          </div>
          <AngledLine />
        </section>
      )}
    </>
  )
}
