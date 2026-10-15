import { Suspense, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { api, ApiError, apiUrl } from '../../api/client'
import { useAuth } from '../../auth/AuthProvider'
import Field from '../../components/Field'
import { BellIcon } from '../../components/Icons'
import ResourcePage from '../../components/ResourcePage'
import { ErrorAlert, Loader, Stat } from '../../components/ui'
import { formatDateTime, formatKg, formatMoney, formatNumber, localized } from '../../lib/format'
import { useFetch } from '../../lib/useFetch'
import * as R from './resources'

/** Menu de l'espace : seulement les rubriques des rôles de la personne connectée. */
export function spaceMenu(user, t) {
  const roles = user?.roles || []
  const has = (role) => roles.includes(role)
  const groups = [
    {
      title: t('space.general'),
      links: [
        ['', t('space.dashboard')],
        ['notifications', t('space.notifications')],
        ['profil', t('space.profile')],
      ],
    },
  ]
  if (has('farmer') || has('field_agent'))
    groups.push({
      title: has('field_agent') ? t('roles.field_agent') : t('roles.farmer'),
      links: [
        ...(has('field_agent') ? [['agriculteurs', t('space.farmers')]] : []),
        ['fermes', t('space.farms')],
        ['palmiers', t('space.palms')],
        ['recoltes', t('space.harvests')],
        ['ventes', t('space.sales')],
        ['depenses', t('space.expenses')],
        ['bilan', t('space.summary')],
      ],
    })
  if (has('seller'))
    groups.push({
      title: t('roles.seller'),
      links: [
        ['commandes', t('space.orders')],
        ['clients', t('space.customers')],
        ['paiements-clients', t('space.customerPayments')],
        ['factures', t('space.invoices')],
        ['produits', t('space.products')],
        ['mouvements', t('space.movements')],
        ['fournisseurs', t('space.suppliers')],
        ['achats', t('space.purchases')],
        ['paiements-fournisseurs', t('space.supplierPayments')],
        ...(has('farmer') ? [] : [['depenses', t('space.expenses')], ['bilan', t('space.summary')]]),
      ],
    })
  if (has('farmer') || has('seller'))
    groups.push({ title: t('nav.market'), links: [['annonces', t('space.listings')]] })
  if (has('direction'))
    groups.push({
      title: t('roles.direction'),
      links: [
        ['direction', t('space.directionDashboard')],
        ['comptes', t('space.users')],
        ['validation-annonces', t('space.review')],
        ['journal', t('space.audit')],
        ['reglages', t('space.settings')],
        ['catalogue', t('space.catalogue')],
      ],
    })
  return groups
}

export function SpaceLayout() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const nav = useRef(null)
  const { pathname } = useLocation()
  // Téléphone : le menu défile de côté ; on montre la rubrique ouverte.
  useEffect(() => {
    nav.current?.querySelector('a.active')?.scrollIntoView?.({ block: 'nearest', inline: 'center' })
  }, [pathname])
  return (
    <div className="container space">
      <nav className="space-nav" aria-label={t('space.menu')} ref={nav}>
        {spaceMenu(user, t).map((group) => (
          <div key={group.title} style={{ display: 'contents' }}>
            <span className="group">{group.title}</span>
            {group.links.map(([to, label]) => (
              <NavLink key={to} to={to === '' ? '/espace' : `/espace/${to}`} end={to === ''}>
                {label}
              </NavLink>
            ))}
          </div>
        ))}
        <button type="button" className="btn btn-ghost btn-sm" onClick={logout} style={{ flex: '0 0 auto' }}>
          {t('nav.logout')}
        </button>
      </nav>
      <div>
        <Suspense fallback={<Loader />}>
          <Outlet />
        </Suspense>
      </div>
    </div>
  )
}

export const Resource = ({ name }) => <ResourcePage key={name} config={R[name]} />

// ---------------------------------------------------------------- Tableaux de bord

function MoneyStats({ money, t, lang }) {
  if (!money) return null
  return (
    <div className="grid">
      <Stat label={t('dashboard.sales')} value={formatMoney(money.sales_total, lang)} />
      <Stat label={t('dashboard.expenses')} value={formatMoney(money.expenses_total, lang)} tone="sand" />
      <Stat
        label={t('dashboard.profit')}
        value={formatMoney(money.profit, lang)}
        tone={Number(money.profit) < 0 ? 'alert' : 'brown'}
      />
    </div>
  )
}

function PalmStats({ data, t, lang }) {
  if (!data) return null
  return (
    <>
      <div className="grid">
        <Stat label={t('dashboard.farms')} value={formatNumber(data.farms, lang)} />
        <Stat label={t('dashboard.palms')} value={formatNumber(data.palms?.total, lang)} />
        <Stat label={t('farms.productive')} value={formatNumber(data.palms?.productive, lang)} tone="sand" />
        <Stat label={t('farms.young')} value={formatNumber(data.palms?.young, lang)} tone="brown" />
      </div>
      {data.production_by_season?.length > 0 && (
        <div className="table-wrap mt">
          <table className="simple">
            <thead>
              <tr>
                <th>{t('harvests.season')}</th>
                <th>{t('dashboard.production')}</th>
              </tr>
            </thead>
            <tbody>
              {data.production_by_season.map((row) => (
                <tr key={row.season}>
                  <td className="num">{row.season}</td>
                  <td className="num">{formatKg(row.total_kg, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function SellerStats({ data, t, lang }) {
  return (
    <div className="grid">
      <Stat label={t('dashboard.customers')} value={formatNumber(data.customers, lang)} />
      <Stat
        label={t('dashboard.lateOrders')}
        value={formatNumber(data.orders.late, lang)}
        tone={data.orders.late ? 'alert' : ''}
      />
      <Stat label={t('dashboard.customersOwe')} value={formatMoney(data.amounts_due.customers_owe, lang)} tone="sand" />
      <Stat label={t('dashboard.suppliersOwed')} value={formatMoney(data.amounts_due.suppliers_owed, lang)} tone="brown" />
      <Stat label={t('dashboard.stockValue')} value={formatMoney(data.stock.stock_value, lang)} />
      <Stat label={t('dashboard.lowStock')} value={formatNumber(data.stock.low_stock, lang)} tone={data.stock.low_stock ? 'alert' : ''} />
    </div>
  )
}

function OrderStatusTable({ orders, t, lang }) {
  return (
    <div className="table-wrap">
      <table className="simple">
        <tbody>
          {Object.entries(orders.by_status).map(([status, count]) => (
            <tr key={status}>
              <td>{t(`orderStatus.${status}`)}</td>
              <td className="num">{formatNumber(count, lang)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PeriodPicker({ period, onChange, t }) {
  return (
    <div className="filters">
      <Field label={t('common.from')} type="date" value={period.date_from} onChange={(v) => onChange({ ...period, date_from: v })} />
      <Field label={t('common.to')} type="date" value={period.date_to} onChange={(v) => onChange({ ...period, date_to: v })} />
    </div>
  )
}

export function MyDashboard() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { user } = useAuth()
  const [period, setPeriod] = useState({ date_from: '', date_to: '' })
  const { data, loading, error } = useFetch('/api/dashboard/me/', period)

  return (
    <div className="stack">
      <div className="page-head">
        <h1>
          {t('dashboard.hello')} {user?.full_name}
        </h1>
        {data?.unread_notifications > 0 && (
          <Link className="btn btn-outline btn-sm" to="/espace/notifications">
            <BellIcon width={18} height={18} /> {t('dashboard.unread', { count: data.unread_notifications })}
          </Link>
        )}
      </div>
      <PeriodPicker period={period} onChange={setPeriod} t={t} />
      <ErrorAlert error={error} />
      {loading && !data && <Loader />}
      {data?.farmer && (
        <section className="stack">
          <h2>{t('roles.farmer')}</h2>
          <PalmStats data={data.farmer} t={t} lang={lang} />
          <MoneyStats money={data.farmer.money} t={t} lang={lang} />
        </section>
      )}
      {data?.seller && (
        <section className="stack">
          <h2>{t('roles.seller')}</h2>
          <SellerStats data={data.seller} t={t} lang={lang} />
          <MoneyStats money={data.seller.money} t={t} lang={lang} />
          <OrderStatusTable orders={data.seller.orders} t={t} lang={lang} />
        </section>
      )}
      {data?.field_agent && (
        <section className="stack">
          <h2>{t('roles.field_agent')}</h2>
          <div className="grid">
            <Stat label={t('dashboard.myFarmers')} value={formatNumber(data.field_agent.farmers, lang)} />
            <Stat label={t('dashboard.claimed')} value={formatNumber(data.field_agent.farmers_claimed, lang)} tone="sand" />
            <Stat label={t('dashboard.pendingAccounts')} value={formatNumber(data.field_agent.farmers_pending, lang)} tone="brown" />
          </div>
          <PalmStats data={data.field_agent} t={t} lang={lang} />
        </section>
      )}
      {data && !data.farmer && !data.seller && !data.field_agent && user?.roles?.includes('direction') && (
        <Link className="btn btn-primary" to="/espace/direction">
          {t('space.directionDashboard')}
        </Link>
      )}
    </div>
  )
}

export function DirectionDashboard() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [period, setPeriod] = useState({ date_from: '', date_to: '' })
  const { data, loading, error } = useFetch('/api/dashboard/direction/', period)

  return (
    <div className="stack">
      <h1>{t('space.directionDashboard')}</h1>
      <PeriodPicker period={period} onChange={setPeriod} t={t} />
      <ErrorAlert error={error} />
      {loading && !data && <Loader />}
      {data && (
        <>
          <h2>{t('dashboard.accounts')}</h2>
          <div className="grid">
            <Stat label={t('roles.farmer')} value={formatNumber(data.accounts.farmers, lang)} />
            <Stat label={t('roles.seller')} value={formatNumber(data.accounts.sellers, lang)} />
            <Stat label={t('roles.field_agent')} value={formatNumber(data.accounts.field_agents, lang)} />
            <Stat label={t('accountStatus.pending')} value={formatNumber(data.accounts.pending, lang)} tone={data.accounts.pending ? 'alert' : 'sand'} />
            <Stat label={t('accountStatus.suspended')} value={formatNumber(data.accounts.suspended, lang)} tone="brown" />
          </div>
          <h2>{t('dashboard.palmsAndProduction')}</h2>
          <PalmStats data={data} t={t} lang={lang} />
          {data.palms_by_variety?.length > 0 && (
            <div className="table-wrap">
              <table className="simple">
                <thead>
                  <tr>
                    <th>{t('fields.variety')}</th>
                    <th>{t('farms.productive')}</th>
                    <th>{t('farms.young')}</th>
                    <th>{t('farms.totalPalms')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.palms_by_variety.map((row) => (
                    <tr key={row.variety}>
                      <td>{lang === 'ar' ? row.variety_ar : row.variety}</td>
                      <td className="num">{formatNumber(row.productive, lang)}</td>
                      <td className="num">{formatNumber(row.young, lang)}</td>
                      <td className="num">{formatNumber(row.total, lang)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <h2>{t('dashboard.money')}</h2>
          <MoneyStats money={data.money} t={t} lang={lang} />
          <h2>{t('dashboard.amountsDue')}</h2>
          <div className="grid">
            <Stat label={t('dashboard.customersOwe')} value={formatMoney(data.amounts_due.customers_owe, lang)} tone="sand" />
            <Stat label={t('dashboard.customerAdvances')} value={formatMoney(data.amounts_due.customer_advances, lang)} />
            <Stat label={t('dashboard.suppliersOwed')} value={formatMoney(data.amounts_due.suppliers_owed, lang)} tone="brown" />
          </div>
          <h2>{t('dashboard.ordersAndStock')}</h2>
          <div className="grid">
            <Stat label={t('dashboard.lateOrders')} value={formatNumber(data.orders.late, lang)} tone={data.orders.late ? 'alert' : ''} />
            <Stat label={t('dashboard.stockValue')} value={formatMoney(data.stock.stock_value, lang)} />
            <Stat label={t('dashboard.lowStock')} value={formatNumber(data.stock.low_stock, lang)} tone={data.stock.low_stock ? 'alert' : ''} />
            <Stat label={t('dashboard.listingsPublished')} value={formatNumber(data.market.published, lang)} />
            <Stat label={t('dashboard.listingsPending')} value={formatNumber(data.market.pending, lang)} tone={data.market.pending ? 'alert' : 'sand'} />
          </div>
          <OrderStatusTable orders={data.orders} t={t} lang={lang} />
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- Bilan (ventes − dépenses)

export function FinanceSummary() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [period, setPeriod] = useState({ date_from: '', date_to: '' })
  const { data, loading, error } = useFetch('/api/finance/summary/', period)
  return (
    <div className="stack">
      <h1>{t('space.summary')}</h1>
      <PeriodPicker period={period} onChange={setPeriod} t={t} />
      <ErrorAlert error={error} />
      {loading && !data && <Loader />}
      {data && (
        <>
          <MoneyStats money={data} t={t} lang={lang} />
          {data.expenses_by_category.length > 0 && (
            <div className="table-wrap">
              <table className="simple">
                <thead>
                  <tr>
                    <th>{t('fields.category')}</th>
                    <th>{t('fields.total')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.expenses_by_category.map((row) => (
                    <tr key={row.category.id}>
                      <td>{localized(row.category, 'name', lang)}</td>
                      <td className="num">{formatMoney(row.total, lang)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data.by_month.length > 0 && (
            <div className="table-wrap">
              <table className="simple">
                <thead>
                  <tr>
                    <th>{t('summary.month')}</th>
                    <th>{t('dashboard.sales')}</th>
                    <th>{t('dashboard.expenses')}</th>
                    <th>{t('dashboard.profit')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_month.map((row) => (
                    <tr key={row.month}>
                      <td className="num">{row.month}</td>
                      <td className="num">{formatMoney(row.sales, lang)}</td>
                      <td className="num">{formatMoney(row.expenses, lang)}</td>
                      <td className="num">{formatMoney(row.profit, lang)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- Notifications

export function Notifications() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { data, loading, error, reload } = useFetch('/api/notifications/')
  const list = Array.isArray(data) ? data : data?.results || []

  const markAll = async () => {
    await api('/api/notifications/read-all/', { method: 'POST' })
    reload()
  }
  const markOne = async (id) => {
    await api(`/api/notifications/${id}/read/`, { method: 'POST' })
    reload()
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h1>{t('space.notifications')}</h1>
        {list.some((n) => !n.read_at) && (
          <button type="button" className="btn btn-outline btn-sm" onClick={markAll}>
            {t('notifications.readAll')}
          </button>
        )}
      </div>
      <ErrorAlert error={error} />
      {loading && !data ? (
        <Loader />
      ) : list.length === 0 ? (
        <div className="empty">{t('notifications.empty')}</div>
      ) : (
        <div className="rows">
          {list.map((n) => (
            <article key={n.id} className={`row-card notif ${n.read_at ? '' : 'unread'}`}>
              <BellIcon />
              <div style={{ flex: 1 }}>
                <div>{lang === 'ar' ? n.message_ar : n.message_fr}</div>
                <div className="small muted">{formatDateTime(n.created_at, lang)}</div>
              </div>
              {!n.read_at && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => markOne(n.id)}>
                  {t('notifications.markRead')}
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- Mon profil

export function Profile() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { user, setUser } = useAuth()
  const oases = useFetch('/api/oases/', null, { auth: false })
  const [form, setForm] = useState(() => ({
    full_name: user.full_name,
    preferred_language: user.preferred_language || lang,
    business_name: user.profile?.business_name || '',
    whatsapp: user.profile?.whatsapp || '',
    address: user.profile?.address || '',
    oasis: user.profile?.oasis ?? '',
  }))
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const me = await api('/api/auth/me/', {
        method: 'PATCH',
        body: {
          full_name: form.full_name,
          preferred_language: form.preferred_language,
          profile: {
            business_name: form.business_name,
            whatsapp: form.whatsapp,
            address: form.address,
            oasis: form.oasis === '' ? null : Number(form.oasis),
          },
        },
      })
      setUser(me)
      setMessage(t('common.saved'))
      if (me.preferred_language && me.preferred_language !== i18n.language) i18n.changeLanguage(me.preferred_language)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const uploadPhoto = async (file) => {
    if (!file) return
    const body = new FormData()
    body.append('photo', file)
    setError(null)
    try {
      const result = await api('/api/auth/me/photo/', { method: 'PUT', body })
      setUser({ ...user, profile: { ...user.profile, photo: result.photo } })
      setMessage(t('common.saved'))
    } catch (err) {
      setError(err)
    }
  }

  const fields = error instanceof ApiError ? { ...error.fields, ...(error.data?.profile || {}) } : {}
  const flat = (v) => (Array.isArray(v) ? v.join(' ') : v)

  return (
    <form className="stack" onSubmit={save} noValidate>
      <h1>{t('space.profile')}</h1>
      {message && <div className="alert success">{message}</div>}
      {error && !Object.keys(fields).length && <ErrorAlert error={error} />}
      <div className="panel" style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <img
          src={user.profile?.photo || '/logo-mark.webp'}
          alt=""
          style={{ width: 88, height: 88, borderRadius: '50%', objectFit: 'cover', background: '#f6ead8' }}
        />
        <div>
          <div className="row-title">{user.full_name}</div>
          <div className="num muted">{user.phone}</div>
          <div className="small">{user.roles.map((r) => t(`roles.${r}`)).join(' + ')}</div>
          <label className="btn btn-ghost btn-sm mt">
            {t('profile.changePhoto')}
            <input type="file" accept="image/*" hidden onChange={(e) => uploadPhoto(e.target.files?.[0])} />
          </label>
        </div>
      </div>
      <div className="form-grid">
        <Field label={t('fields.fullName')} value={form.full_name} onChange={set('full_name')} error={flat(fields.full_name)} required />
        <Field
          label={t('fields.language')}
          type="select"
          value={form.preferred_language}
          onChange={set('preferred_language')}
          options={[
            { value: 'ar', label: 'العربية' },
            { value: 'fr', label: 'Français' },
          ]}
        />
        <Field label={t('profile.business')} value={form.business_name} onChange={set('business_name')} error={flat(fields.business_name)} />
        <Field label={t('fields.whatsapp')} type="tel" value={form.whatsapp} onChange={set('whatsapp')} error={flat(fields.whatsapp)} />
        <Field label={t('fields.address')} value={form.address} onChange={set('address')} error={flat(fields.address)} />
        <Field
          label={t('fields.oasis')}
          type="select"
          value={String(form.oasis)}
          onChange={set('oasis')}
          options={[
            { value: '', label: '—' },
            ...(oases.data || []).map((o) => ({ value: String(o.id), label: localized(o, 'name', lang) })),
          ]}
        />
      </div>
      <div>
        <button className="btn btn-primary" disabled={busy}>
          {busy ? t('common.wait') : t('common.save')}
        </button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------- Photos d'une annonce

export function ListingPhotos({ listing, onChanged }) {
  const { t } = useTranslation()
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const upload = async (file) => {
    if (!file) return
    const body = new FormData()
    body.append('image', file)
    body.append('order', String(listing.photos.length))
    setBusy(true)
    setError(null)
    try {
      await api(`/api/market/my-listings/${listing.id}/photos/`, { method: 'POST', body })
      onChanged()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (photo) => {
    setError(null)
    try {
      await api(`/api/market/my-listings/${listing.id}/photos/${photo.id}/`, { method: 'DELETE' })
      onChanged()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <div className="stack">
      <strong>{t('listings.photos')}</strong>
      <div className="photos">
        {listing.photos.map((photo) => (
          <figure key={photo.id}>
            <img src={photo.image} alt="" />
            {listing.is_editable && (
              <button type="button" className="btn btn-danger btn-sm" onClick={() => remove(photo)}>
                {t('common.delete')}
              </button>
            )}
          </figure>
        ))}
      </div>
      {listing.is_editable && listing.photos.length < 5 && (
        <label className="btn btn-outline btn-sm" style={{ justifySelf: 'start' }}>
          {busy ? t('common.wait') : `+ ${t('listings.addPhoto')}`}
          <input type="file" accept="image/*" hidden disabled={busy} onChange={(e) => upload(e.target.files?.[0])} />
        </label>
      )}
      {!listing.is_editable && <div className="small muted">{t('listings.photosLocked')}</div>}
      <ErrorAlert error={error} />
    </div>
  )
}

R.myListings.detail = (row, ctx, onChanged) => <ListingPhotos listing={row} onChanged={onChanged} />

// ---------------------------------------------------------------- Direction : réglages et catalogue

export function PlatformSettings() {
  const { t } = useTranslation()
  const { data, error, loading, setData } = useFetch('/api/settings/')
  const [saveError, setSaveError] = useState(null)
  const [message, setMessage] = useState(null)

  if (loading && !data) return <Loader />
  if (!data) return <ErrorAlert error={error} />

  const set = (key) => (value) => setData((d) => ({ ...d, [key]: value }))
  const save = async (event) => {
    event.preventDefault()
    setSaveError(null)
    try {
      const { updated_at: _ignored, ...body } = data
      setData(await api('/api/settings/', { method: 'PATCH', body }))
      setMessage(t('common.saved'))
    } catch (err) {
      setSaveError(err)
    }
  }
  const fields = saveError?.fields || {}
  return (
    <form className="stack" onSubmit={save} noValidate>
      <h1>{t('space.settings')}</h1>
      <p className="muted">{t('settings.intro')}</p>
      {message && <div className="alert success">{message}</div>}
      <ErrorAlert error={saveError && !Object.keys(fields).length ? saveError : null} />
      <div className="form-grid">
        <Field label={t('settings.premium')} type="number" value={data.premium_threshold} onChange={set('premium_threshold')} error={fields.premium_threshold} />
        <Field label={t('settings.newDays')} type="number" value={data.new_customer_days} onChange={set('new_customer_days')} error={fields.new_customer_days} />
        <Field label={t('settings.loyalOrders')} type="number" value={data.loyal_min_orders} onChange={set('loyal_min_orders')} error={fields.loyal_min_orders} />
        <Field label={t('settings.loyalDays')} type="number" value={data.loyal_period_days} onChange={set('loyal_period_days')} error={fields.loyal_period_days} />
        <Field label={t('settings.inactiveDays')} type="number" value={data.inactive_days} onChange={set('inactive_days')} error={fields.inactive_days} />
      </div>
      <div>
        <button className="btn btn-primary">{t('common.save')}</button>
      </div>
    </form>
  )
}

export function Catalogue() {
  const { t } = useTranslation()
  const links = [
    ['oases/region', t('catalogue.regions')],
    ['oases/oasis', t('catalogue.oases')],
    ['oases/datevariety', t('catalogue.varieties')],
    ['oases/oasisphoto', t('catalogue.photos')],
    ['finance/expensecategory', t('catalogue.categories')],
  ]
  return (
    <div className="stack">
      <h1>{t('space.catalogue')}</h1>
      <p className="muted">{t('catalogue.intro')}</p>
      <div className="grid">
        {links.map(([path, label]) => (
          <a key={path} className="card" href={apiUrl(`/admin/${path}/`)} target="_blank" rel="noopener noreferrer">
            <strong>{label}</strong>
            <div className="small muted">{t('catalogue.open')}</div>
          </a>
        ))}
      </div>
    </div>
  )
}
