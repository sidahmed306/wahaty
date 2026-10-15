import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { api, ApiError, asList, setLogoutHandler, tokens } from '../api/client'
import i18n from '../i18n'
import ar from '../i18n/ar'
import fr from '../i18n/fr'
import {
  formatDate,
  formatDateTime,
  formatKg,
  formatMoney,
  formatNumber,
  formatPhone,
  localized,
  monthName,
  monthsInSeason,
  today,
} from '../lib/format'
import { mockApi } from './utils'

const PLURAL = /_(zero|one|two|few|many|other)$/

function keys(obj, prefix = '') {
  return Object.entries(obj).flatMap(([key, value]) =>
    value && typeof value === 'object' && !Array.isArray(value)
      ? keys(value, `${prefix}${key}.`)
      : [`${prefix}${key.replace(PLURAL, '')}`],
  )
}

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === 'test' ? [] : sourceFiles(path)
    return /\.(js|jsx)$/.test(name) ? [path] : []
  })
}

describe('traductions', () => {
  it('chaque texte existe en arabe et en français', () => {
    const arKeys = new Set(keys(ar))
    const frKeys = new Set(keys(fr))
    expect([...arKeys].filter((k) => !frKeys.has(k))).toEqual([])
    expect([...frKeys].filter((k) => !arKeys.has(k))).toEqual([])
  })

  it('chaque clé utilisée dans le code existe', () => {
    const all = new Set(keys(ar))
    const used = new Set()
    for (const file of sourceFiles(join(process.cwd(), 'src'))) {
      for (const match of readFileSync(file, 'utf8').matchAll(/\bt\('([a-zA-Z]+\.[a-zA-Z_.]+)'/g)) used.add(match[1])
    }
    expect(used.size).toBeGreaterThan(100)
    expect([...used].filter((k) => !all.has(k))).toEqual([])
  })

  it('arabe de droite à gauche, français de gauche à droite', async () => {
    await i18n.changeLanguage('fr')
    expect(document.documentElement.dir).toBe('ltr')
    expect(document.documentElement.lang).toBe('fr')
    expect(window.localStorage.getItem('trc.lang')).toBe('fr')
    await i18n.changeLanguage('ar')
    expect(document.documentElement.dir).toBe('rtl')
  })

  it('pluriels arabes', async () => {
    expect(i18n.t('orders.daysLate', { count: 1 })).toBe('تأخير يوم واحد')
    expect(i18n.t('orders.daysLate', { count: 2 })).toBe('تأخير يومين')
    expect(i18n.t('orders.daysLate', { count: 5 })).toBe('تأخير 5 أيام')
    await i18n.changeLanguage('fr')
    expect(i18n.t('orders.daysLate', { count: 3 })).toBe('3 jours de retard')
  })
})

describe('affichage des nombres et dates', () => {
  it('montants, kilos, nombres', () => {
    expect(formatMoney('1234.50', 'ar')).toBe('1,234.5 MRU')
    expect(formatMoney('1234.50', 'fr')).toMatch(/^1\s234,5 MRU$/)
    expect(formatMoney(null)).toBe('—')
    expect(formatKg('12', 'ar')).toBe('12 كغ')
    expect(formatKg('12', 'fr')).toBe('12 kg')
    expect(formatKg('')).toBe('—')
    expect(formatNumber('abc')).toBe('abc')
    expect(formatNumber(undefined)).toBe('—')
  })

  it('dates en arabe et en français', () => {
    expect(formatDate('2026-10-15', 'ar')).toBe('15 أكتوبر 2026')
    expect(formatDate('2026-07-01T10:00:00Z', 'fr')).toBe('1 juillet 2026')
    expect(formatDate(null)).toBe('—')
    expect(formatDate('demain')).toBe('demain')
    expect(formatDateTime('2026-10-15T08:05:00', 'fr')).toBe('15 octobre 2026 08:05')
    expect(formatDateTime('???')).toBe('???')
    expect(formatDateTime(null)).toBe('—')
    expect(monthName(6, 'ar')).toBe('يونيو')
    expect(today()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('saisons, noms bilingues, téléphones', () => {
    expect(monthsInSeason(6, 8)).toEqual([6, 7, 8])
    expect(monthsInSeason(11, 2)).toEqual([1, 2, 11, 12])
    expect(monthsInSeason(null, 2)).toEqual([])
    const v = { name_ar: 'سكاني', name_fr: 'Sekani' }
    expect(localized(v, 'name', 'ar')).toBe('سكاني')
    expect(localized({ name_ar: 'سكاني', name_fr: '' }, 'name', 'fr')).toBe('سكاني')
    expect(localized(null, 'name')).toBe('')
    expect(formatPhone('+22247826859')).toBe('+222 47 82 68 59')
    expect(formatPhone('123')).toBe('123')
    expect(formatPhone('')).toBe('—')
  })
})

describe('client de l’API', () => {
  it('messages d’erreur par champ et généraux', () => {
    const err = new ApiError(400, { phone: ['Numéro invalide.'], password: ['Trop court.', 'Trop simple.'] })
    expect(err.fields).toEqual({ phone: 'Numéro invalide.', password: 'Trop court. Trop simple.' })
    expect(err.general).toBe('')
    expect(err.message).toBe('Numéro invalide.')
    expect(new ApiError(403, { detail: 'Interdit.' }).general).toBe('Interdit.')
    expect(new ApiError(400, ['Erreur.']).general).toBe('Erreur.')
    expect(new ApiError(400, 'texte').general).toBe('texte')
    expect(new ApiError(500, null).general).toBe('')
    expect(new ApiError(500, null).message).toBe('HTTP 500')
    expect(new ApiError(400, { non_field_errors: ['Global.'], n: 3 }).fields).toEqual({ n: '3' })
  })

  it('envoie la langue et le jeton, puis renvoie le JSON', async () => {
    tokens.set({ access: 'A1', refresh: 'R1' })
    const { calls } = mockApi({ 'GET /api/farms/': [{ id: 1 }] })
    const data = await api('/api/farms/', { params: { owner: 3, empty: '' } })
    expect(data).toEqual([{ id: 1 }])
    expect(calls[0].headers.Authorization).toBe('Bearer A1')
    expect(calls[0].headers['Accept-Language']).toBe('ar')
    expect(calls[0].query).toEqual({ owner: '3' })
  })

  it('renouvelle le jeton expiré une fois puis réessaie', async () => {
    tokens.set({ access: 'OLD', refresh: 'R1' })
    let first = true
    const { calls } = mockApi({
      'GET /api/auth/me/': () => {
        if (first) {
          first = false
          return [401, { detail: 'expired' }]
        }
        return { id: 1 }
      },
      'POST /api/auth/refresh/': { access: 'NEW', refresh: 'R2' },
    })
    expect(await api('/api/auth/me/')).toEqual({ id: 1 })
    expect(tokens.access).toBe('NEW')
    expect(tokens.refresh).toBe('R2')
    expect(calls.at(-1).headers.Authorization).toBe('Bearer NEW')
  })

  it('déconnecte si le renouvellement échoue', async () => {
    tokens.set({ access: 'OLD', refresh: 'R1' })
    const onLogout = vi.fn()
    setLogoutHandler(onLogout)
    mockApi({
      'GET /api/auth/me/': [401, { detail: 'expired' }],
      'POST /api/auth/refresh/': [401, { detail: 'blacklisted' }],
    })
    await expect(api('/api/auth/me/')).rejects.toBeInstanceOf(ApiError)
    expect(tokens.access).toBeNull()
    expect(onLogout).toHaveBeenCalled()
  })

  it('envoi de fichier, réponse vide, texte, PDF et liste paginée', async () => {
    mockApi({ 'DELETE /api/x/1/': [204, null] })
    expect(await api('/api/x/1/', { method: 'DELETE', auth: false })).toBeNull()

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url, options) => {
        expect(options.headers['Content-Type']).toBeUndefined() // FormData : le navigateur choisit
        return new Response('ok', { status: 200, headers: { 'Content-Type': 'text/plain' } })
      }),
    )
    expect(await api('/api/upload/', { method: 'POST', body: new FormData() })).toBe('ok')

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('%PDF', { status: 200, headers: { 'Content-Type': 'application/pdf' } })),
    )
    expect((await api('/api/invoices/1/pdf/')).size).toBe(4)
    const raw = await api('/api/invoices/1/pdf/', { raw: true })
    expect(raw.ok).toBe(true)

    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 200 })))
    expect(await api('/api/empty/')).toBeNull()

    expect(asList({ results: [1, 2] })).toEqual([1, 2])
    expect(asList([3])).toEqual([3])
    expect(asList(null)).toEqual([])
  })

  it('stockage indisponible : aucune erreur', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(tokens.access).toBeNull()
  })
})
