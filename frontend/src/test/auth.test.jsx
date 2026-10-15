import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../App'
import { tokens } from '../api/client'
import { farmer, loginAs, mockApi, renderAt } from './utils'

const dashboard = {
  period: { date_from: '2026-01-01', date_to: '2026-10-15' },
  roles: ['farmer'],
  unread_notifications: 2,
  farmer: {
    farms: 1,
    palms: { productive: 180, young: 30, total: 210 },
    palms_by_variety: [],
    production_by_season: [{ season: 2026, total_kg: '1200.00' }],
    money: { direct_sales_total: '35000.00', orders_total: '0.00', sales_total: '35000.00', expenses_total: '2700.00', profit: '32300.00' },
  },
}

describe('connexion', () => {
  it('connexion réussie puis tableau de bord, déconnexion', async () => {
    const { calls } = mockApi({
      'POST /api/auth/login/': { access: 'A', refresh: 'R' },
      'GET /api/auth/me/': farmer,
      'GET /api/dashboard/me/': dashboard,
      'POST /api/auth/logout/': [205, null],
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/connexion' })
    await user.type(await screen.findByLabelText(/الهاتف/), '47000001')
    await user.type(screen.getByLabelText(/كلمة المرور/), 'Oasis-2026!')
    await user.click(screen.getByRole('button', { name: 'دخول' }))
    expect(await screen.findByText(/مرحبًا Sidi Mohamed/)).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/api/auth/login/').body).toEqual({ phone: '47000001', password: 'Oasis-2026!' })
    expect(tokens.access).toBe('A')
    expect(await screen.findByText('210')).toBeInTheDocument()
    expect(screen.getByText('إشعاران غير مقروءين')).toBeInTheDocument()
    expect(screen.getByText('1,200 كغ')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'تسجيل الخروج' }))
    await waitFor(() => expect(tokens.access).toBeNull())
    expect(calls.find((c) => c.path === '/api/auth/logout/').body).toEqual({ refresh: 'R' })
  })

  it('mauvais mot de passe, compte en attente, trop d’essais', async () => {
    let answer = [401, { detail: 'No active account' }]
    mockApi({ 'POST /api/auth/login/': () => answer })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/connexion' })
    await user.type(await screen.findByLabelText(/الهاتف/), '47000001')
    await user.type(screen.getByLabelText(/كلمة المرور/), 'x')
    await user.click(screen.getByRole('button', { name: 'دخول' }))
    expect(await screen.findByText('رقم الهاتف أو كلمة المرور غير صحيحة.')).toBeInTheDocument()
    answer = [403, { detail: 'Votre compte attend la validation de la Direction.' }]
    await user.click(screen.getByRole('button', { name: 'دخول' }))
    expect(await screen.findByText('Votre compte attend la validation de la Direction.')).toBeInTheDocument()
    answer = [429, { detail: 'throttled' }]
    await user.click(screen.getByRole('button', { name: 'دخول' }))
    expect(await screen.findByText('محاولات كثيرة. انتظر دقيقة ثم حاول مرة أخرى.')).toBeInTheDocument()
  })

  it('déjà connecté : la page de connexion renvoie vers l’espace', async () => {
    mockApi({ ...loginAs(farmer), 'GET /api/dashboard/me/': dashboard })
    renderAt(<App />, { path: '/connexion' })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/espace'))
  })

  it('jeton invalide : retour à l’état déconnecté', async () => {
    window.localStorage.setItem('trc.access', 'bad')
    mockApi({ 'GET /api/auth/me/': [403, { detail: 'suspendu' }] })
    renderAt(<App />, { path: '/espace' })
    expect(await screen.findByRole('heading', { name: 'تسجيل الدخول' })).toBeInTheDocument()
    expect(tokens.access).toBeNull()
  })
})

describe('inscription', () => {
  it('erreurs par champ puis succès', async () => {
    let answer = [400, { phone: ['Ce numéro est déjà utilisé.'], password: ['Mot de passe trop courant.'] }]
    const { calls } = mockApi({ 'POST /api/auth/register/': () => answer })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/inscription' })
    await user.type(await screen.findByLabelText(/الاسم الكامل/), 'Mariem')
    await user.type(screen.getByLabelText(/الهاتف/), '47000009')
    await user.type(screen.getByLabelText(/كلمة المرور/), 'password')
    await user.click(screen.getByLabelText('بائع'))
    await user.click(screen.getByRole('button', { name: 'إنشاء حسابي' }))
    expect(await screen.findByText('Ce numéro est déjà utilisé.')).toBeInTheDocument()
    expect(screen.getByText('Mot de passe trop courant.')).toBeInTheDocument()
    expect(calls[0].body).toEqual({
      full_name: 'Mariem',
      phone: '47000009',
      password: 'password',
      roles: ['farmer', 'seller'],
      preferred_language: 'ar',
    })
    answer = [201, { id: 5, status: 'pending' }]
    await user.click(screen.getByRole('button', { name: 'إنشاء حسابي' }))
    expect(await screen.findByText(/يجب أن تصادق عليه الإدارة/)).toBeInTheDocument()
  })

  it('erreur générale et trop d’essais', async () => {
    let answer = [400, { non_field_errors: ['Erreur globale.'] }]
    mockApi({ 'POST /api/auth/register/': () => answer })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/inscription' })
    await user.click(await screen.findByLabelText('مزارع')) // décoché
    await user.click(screen.getByRole('button', { name: 'إنشاء حسابي' }))
    expect(await screen.findByText('Erreur globale.')).toBeInTheDocument()
    answer = [429, {}]
    await user.click(screen.getByRole('button', { name: 'إنشاء حسابي' }))
    expect(await screen.findByText(/محاولات كثيرة/)).toBeInTheDocument()
  })
})

describe('reprise de compte (code de l’agent)', () => {
  it('code faux puis succès', async () => {
    let answer = [400, { detail: 'Code invalide ou expiré.' }]
    const { calls } = mockApi({ 'POST /api/auth/claim/': () => answer })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/reprise' })
    await user.type(await screen.findByLabelText(/الهاتف/), '47000003')
    await user.type(screen.getByLabelText(/رمز الاسترجاع/), 'AB12CD34')
    await user.type(screen.getByLabelText(/كلمة المرور الجديدة/), 'Palmier-2026')
    await user.click(screen.getByRole('button', { name: 'استرجاع حسابي' }))
    expect(await screen.findByText('Code invalide ou expiré.')).toBeInTheDocument()
    expect(calls[0].body).toEqual({ phone: '47000003', code: 'AB12CD34', password: 'Palmier-2026' })
    answer = [429, {}]
    await user.click(screen.getByRole('button', { name: 'استرجاع حسابي' }))
    expect(await screen.findByText(/محاولات كثيرة/)).toBeInTheDocument()
    answer = { detail: 'ok' }
    await user.click(screen.getByRole('button', { name: 'استرجاع حسابي' }))
    expect(await screen.findByText(/أصبح الحساب ملكك/)).toBeInTheDocument()
  })
})
