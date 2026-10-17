// Panne du 15/10/2026 : les pages de gestion rechargeaient leurs listes en boucle, le navigateur
// restait occupé et les clics « restaient en recherche ». Ces tests empêchent son retour.

import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Profiler } from 'react'
import { expect, it } from 'vitest'
import App from '../App'
import { farmer, loginAs, mockApi, renderAt } from './utils'

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

it('les listes de choix ne sont chargées qu’une fois (pas de boucle)', async () => {
  const { calls } = mockApi({
    ...loginAs(farmer),
    'GET /api/sales/': [],
    'GET /api/varieties/': [],
    'GET /api/farms/': [],
  })
  renderAt(<App />, { path: '/espace/ventes' })
  await screen.findByRole('heading', { name: 'المبيعات المباشرة' })
  await wait(400)
  expect(calls.filter((c) => c.path === '/api/varieties/')).toHaveLength(1)
  expect(calls.filter((c) => c.path === '/api/farms/')).toHaveLength(1)
  expect(calls.filter((c) => c.path === '/api/sales/')).toHaveLength(1)
})

it('une page sans liste de choix ne se réaffiche pas sans fin', async () => {
  mockApi({ ...loginAs({ ...farmer, roles: ['direction'] }), 'GET /api/users/': [] })
  let renders = 0
  renderAt(
    <Profiler id="app" onRender={() => (renders += 1)}>
      <App />
    </Profiler>,
    { path: '/espace/comptes' },
  )
  await screen.findByRole('heading', { name: 'الحسابات' })
  const before = renders
  await wait(400)
  expect(renders - before).toBeLessThan(3)
})

it('Direction : on passe d’une rubrique à l’autre', async () => {
  mockApi({
    ...loginAs({ ...farmer, roles: ['direction'] }),
    'GET /api/users/': [],
    'GET /api/market/review/': [],
    'GET /api/audit/': { count: 0, results: [] },
    'GET /api/settings/': { premium_threshold: '1.00', new_customer_days: 30, loyal_min_orders: 3, loyal_period_days: 180, inactive_days: 90 },
  })
  const user = userEvent.setup()
  renderAt(<App />, { path: '/espace/comptes' })
  await screen.findByRole('heading', { name: 'الحسابات' })
  for (const [link, title] of [
    ['إعلانات للمصادقة', 'إعلانات للمصادقة'],
    ['السجل', 'سجل التدقيق'],
    ['الإعدادات', 'الإعدادات'],
    ['الحسابات', 'الحسابات'],
  ]) {
    await user.click(screen.getByRole('link', { name: link }))
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(title))
  }
})

it('serveur lent : un message explique l’attente, puis disparaît', async () => {
  const { act, render } = await import('@testing-library/react')
  const { api, SLOW_AFTER_MS } = await import('../api/client')
  const { WakeBanner } = await import('../components/Layout')
  const { vi } = await import('vitest')
  vi.useFakeTimers()
  let answer
  vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => (answer = resolve))))
  render(<WakeBanner />)
  const call = api('/api/health/', { auth: false })
  expect(screen.queryByRole('status')).toBeNull()
  await act(async () => vi.advanceTimersByTime(SLOW_AFTER_MS + 10))
  expect(screen.getByRole('status')).toHaveTextContent('الخادم يستيقظ')
  await act(async () => answer(new Response('{"status":"ok"}', { status: 200, headers: { 'Content-Type': 'application/json' } })))
  await call
  expect(screen.queryByRole('status')).toBeNull()
  vi.useRealTimers()
})

it('serveur sans réponse : arrêt au bout du délai avec un message clair', async () => {
  const { api, ApiError, TIMEOUT_MS } = await import('../api/client')
  const { vi } = await import('vitest')
  vi.useFakeTimers()
  vi.stubGlobal(
    'fetch',
    vi.fn((url, { signal }) => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('abort'))))),
  )
  const call = api('/api/health/', { auth: false })
  vi.advanceTimersByTime(TIMEOUT_MS + 10)
  const error = await call.catch((e) => e)
  expect(error).toBeInstanceOf(ApiError)
  expect(error.status).toBe(0) // affiché : « تعذّر الاتصال بالخادم… »
  vi.useRealTimers()
})
