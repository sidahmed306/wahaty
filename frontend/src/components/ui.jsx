import { useTranslation } from 'react-i18next'

/** Ligne fine avec un coin biseauté, reprise des flyers. */
export function AngledLine() {
  return (
    <svg className="angled-line" viewBox="0 0 400 14" preserveAspectRatio="none" aria-hidden="true">
      <path
        d="M0 13 H90 L102 1 H400"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

export function SectionTitle({ kicker, title, children }) {
  return (
    <div className="section-title">
      {kicker && <div className="kicker">{kicker}</div>}
      <h2>{title}</h2>
      {children}
      <AngledLine />
    </div>
  )
}

export function Loader() {
  const { t } = useTranslation()
  return (
    <div className="loader" role="status">
      <span />
      <span className="visually-hidden">{t('common.loading')}</span>
    </div>
  )
}

export function Empty({ children }) {
  const { t } = useTranslation()
  return (
    <div className="empty">
      <img src="/logo-mark.webp" alt="" />
      {children || t('common.empty')}
    </div>
  )
}

export function ErrorAlert({ error }) {
  const { t } = useTranslation()
  if (!error) return null
  const message =
    typeof error === 'string'
      ? error
      : error.status === 0 || error.name === 'TypeError'
        ? t('errors.network')
        : error.general || (error.fields && Object.values(error.fields)[0]) || t('errors.generic')
  return (
    <div className="alert" role="alert">
      {message}
    </div>
  )
}

const BADGE_COLORS = {
  approved: 'green',
  published: 'green',
  delivered: 'green',
  issued: 'green',
  loyal: 'green',
  premium: 'green',
  pending: 'orange',
  received: 'orange',
  confirmed: 'orange',
  prepared: 'orange',
  out_for_delivery: 'orange',
  new: 'orange',
  draft: 'grey',
  sold: 'grey',
  occasional: 'grey',
  inactive: 'grey',
  suspended: 'red',
  rejected: 'red',
  cancelled: 'red',
  late: 'red',
}

export function StatusBadge({ value, group }) {
  const { t } = useTranslation()
  if (!value) return null
  return <span className={`badge ${BADGE_COLORS[value] || ''}`}>{t(`${group}.${value}`)}</span>
}

export function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone || ''}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  )
}
