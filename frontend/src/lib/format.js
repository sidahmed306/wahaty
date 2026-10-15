// Affichage des montants, quantités et dates. Les montants arrivent de l'API en texte
// exact (« 1234.50 ») : on ne s'en sert que pour l'affichage, jamais pour calculer.

export const MONTHS = {
  ar: ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'],
  fr: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
}

function numberFormat(lang, digits) {
  return new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

export function formatNumber(value, lang = 'ar', digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (Number.isNaN(number)) return String(value)
  return numberFormat(lang, digits).format(number)
}

export function formatMoney(value, lang = 'ar') {
  if (value === null || value === undefined || value === '') return '—'
  return `${formatNumber(value, lang)} MRU`
}

export function formatKg(value, lang = 'ar') {
  if (value === null || value === undefined || value === '') return '—'
  return `${formatNumber(value, lang)} ${lang === 'fr' ? 'kg' : 'كغ'}`
}

export function formatDate(value, lang = 'ar') {
  if (!value) return '—'
  const [datePart] = String(value).split('T')
  const [year, month, day] = datePart.split('-').map(Number)
  if (!year || !month || !day) return String(value)
  return `${day} ${MONTHS[lang === 'fr' ? 'fr' : 'ar'][month - 1]} ${year}`
}

export function formatDateTime(value, lang = 'ar') {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  const day = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  return `${formatDate(day, lang)} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function monthName(month, lang = 'ar') {
  return MONTHS[lang === 'fr' ? 'fr' : 'ar'][month - 1] || ''
}

export function today() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** Texte dans la langue choisie, avec repli sur l'autre langue (champs name_ar / name_fr). */
export function localized(obj, field, lang = 'ar') {
  if (!obj) return ''
  const other = lang === 'fr' ? 'ar' : 'fr'
  return obj[`${field}_${lang}`] || obj[`${field}_${other}`] || ''
}

/** Numéro mauritanien lisible : +222 47 82 68 59 */
export function formatPhone(phone) {
  if (!phone) return '—'
  const digits = String(phone).replace(/\D/g, '')
  const local = digits.startsWith('222') && digits.length === 11 ? digits.slice(3) : digits
  if (local.length !== 8) return phone
  return `+222 ${local.slice(0, 2)} ${local.slice(2, 4)} ${local.slice(4, 6)} ${local.slice(6)}`
}

export function monthsInSeason(start, end) {
  const months = []
  if (!start || !end) return months
  for (let m = 1; m <= 12; m += 1) {
    const inside = start <= end ? m >= start && m <= end : m >= start || m <= end
    if (inside) months.push(m)
  }
  return months
}
