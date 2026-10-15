// Chaque page de gestion s'affiche avec une ligne d'exemple, ouvre son formulaire d'ajout
// et ses actions sans erreur, en arabe comme en français.

import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../App'
import i18n from '../i18n'
import { farmer, loginAs, mockApi, renderAt } from './utils'

const variety = { id: 3, slug: 'sekani', name_ar: 'سكاني', name_fr: 'Sekani' }
const oasis = { id: 1, slug: 'atar', name_ar: 'أطار', name_fr: 'Atar' }
const farm = { id: 5, name: 'Ferme Nord', owner: 7, owner_name: 'Sidi', oasis_detail: oasis }
const supplier = { id: 6, name: 'Coopérative Atar', phone: '+22247000006', purchases_total: '10000.00', paid_total: '0.00', balance: '10000.00' }
const customer = {
  id: 60,
  name: 'Khadija',
  phone: '+22247000060',
  segment: 'premium',
  orders_count: 4,
  total_purchased: '120000.00',
  paid_total: '120500.00',
  balance: '-500.00',
  last_order_date: '2026-10-01',
}
const product = { id: 40, name: 'Sekani 1 kg', unit: 'box', sale_price: null, stock: '3.00', is_low_stock: false }

const COMMON = {
  'GET /api/varieties/': [variety],
  'GET /api/oases/': [oasis],
  'GET /api/farms/': [farm],
  'GET /api/suppliers/': [supplier],
  'GET /api/customers/': [customer],
  'GET /api/products/': [product],
  'GET /api/orders/': [],
  'GET /api/purchases/': [{ id: 9, supplier: 6, supplier_name: 'Coopérative Atar', purchase_date: '2026-10-02', reference: 'B-12', total_amount: '10000.00', items: [{ id: 1, product_name: 'Sekani 1 kg', quantity: '20.00' }], cancelled_at: null }],
  'GET /api/expense-categories/': [
    { id: 1, name_ar: 'سقي', name_fr: 'Irrigation', applies_to: 'farmer' },
    { id: 2, name_ar: 'نقل', name_fr: 'Transport', applies_to: 'seller' },
  ],
  'GET /api/agent/farmers/': [],
}

const PAGES = [
  ['palmiers', 'GET /api/palm-groups/', { id: 1, farm: 5, variety: 3, variety_detail: variety, productive_count: 10, young_count: 2, total_count: 12 }, 'سكاني', 'Ferme Nord'],
  ['recoltes', 'GET /api/harvests/', { id: 1, farm: 5, variety: 3, variety_detail: variety, season: 2026, harvest_date: '2026-08-01', quantity_kg: '1200.00', notes: '' }, 'سكاني · 2026', '1,200 كغ'],
  ['depenses', 'GET /api/expenses/', { id: 1, category: 1, category_detail: { name_ar: 'سقي', name_fr: 'Irrigation' }, expense_date: '2026-10-01', amount: '2700.00', description: 'Pompe' }, '2,700 MRU', 'Pompe'],
  ['mouvements', 'GET /api/stock-movements/', { id: 1, product: 40, product_name: 'Sekani 1 kg', kind: 'loss', quantity: '1.00', movement_date: '2026-10-01T10:00:00Z', note: 'Abîmé' }, 'Sekani 1 kg', 'خسارة / تلف'],
  ['fournisseurs', 'GET /api/suppliers/', supplier, 'Coopérative Atar', '10,000 MRU'],
  ['achats', 'GET /api/purchases/', null, 'Coopérative Atar · 2 أكتوبر 2026', 'Sekani 1 kg × 20'],
  ['paiements-fournisseurs', 'GET /api/supplier-payments/', { id: 1, supplier: 6, payment_date: '2026-10-03', amount: '4000.00', method: 'bankily', reference: '' }, '4,000 MRU', 'بنكيلي'],
  ['clients', 'GET /api/customers/', null, 'Khadija', 'مميّز'],
  ['paiements-clients', 'GET /api/customer-payments/', { id: 1, customer: 60, customer_name: 'Khadija', payment_date: '2026-10-03', amount: '500.00', method: 'cash', reference: '' }, 'Khadija · 500 MRU', 'نقدًا'],
  ['produits', 'GET /api/products/', null, 'Sekani 1 kg', 'كرتونة'],
]

describe('toutes les pages de gestion', () => {
  it.each(PAGES)('%s : ligne, formulaire d’ajout', async (path, route, row, title, detail) => {
    const routes = { ...loginAs({ ...farmer, roles: ['farmer', 'seller'] }), ...COMMON }
    if (row) routes[route] = [row]
    mockApi(routes)
    const user = userEvent.setup()
    renderAt(<App />, { path: `/espace/${path}` })
    expect(await screen.findByText(title)).toBeInTheDocument()
    expect(screen.getByText(title).closest('article')).toHaveTextContent(detail)
    const add = screen.getAllByRole('button').find((b) => b.textContent.startsWith('+ '))
    await user.click(add)
    expect(await screen.findByRole('button', { name: 'حفظ' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'إلغاء' }))
  })

  it('achat : lignes au prix d’achat, annulation avec motif', async () => {
    const { calls } = mockApi({
      ...loginAs({ ...farmer, roles: ['seller'] }),
      ...COMMON,
      'POST /api/purchases/': [201, { id: 10 }],
      'POST /api/purchases/9/cancel/': { id: 9 },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/achats' })
    await screen.findByText('Coopérative Atar · 2 أكتوبر 2026')
    await user.click(screen.getByRole('button', { name: '+ شراء جديد' }))
    await user.selectOptions(screen.getByLabelText(/^المورّد/), '6')
    await user.selectOptions(screen.getByLabelText(/^المنتج/), '40')
    expect(screen.getByLabelText(/^سعر الشراء/)).toHaveValue(null) // pas de prix de vente proposé ici
    await user.type(screen.getByLabelText(/^الكمية/), '5')
    await user.type(screen.getByLabelText(/^سعر الشراء/), '350')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/api/purchases/')).toBe(true))
    expect(calls.find((c) => c.path === '/api/purchases/' && c.method === 'POST').body.lines).toEqual([
      { product: 40, quantity: '5', unit_cost: '350' },
    ])
    await user.click(screen.getByRole('button', { name: 'إلغاء الشراء' }))
    await user.type(screen.getByLabelText(/سبب الإلغاء/), 'Erreur')
    await user.click(screen.getByRole('button', { name: 'تأكيد' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/purchases/9/cancel/')).toBe(true))
  })

  it('dépense d’un vendeur : seulement ses catégories', async () => {
    mockApi({ ...loginAs({ ...farmer, roles: ['seller'] }), ...COMMON, 'GET /api/expenses/': [] })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/depenses' })
    await user.click(await screen.findByRole('button', { name: '+ مصروف جديد' }))
    const select = screen.getByLabelText(/^الفئة/)
    await waitFor(() => expect(select).toHaveTextContent('نقل'))
    expect(select).not.toHaveTextContent('سقي')
    expect(screen.queryByLabelText(/^المزرعة/)).not.toBeInTheDocument()
  })

  it('paiement client lié à une commande du même client', async () => {
    mockApi({
      ...loginAs({ ...farmer, roles: ['seller'] }),
      ...COMMON,
      'GET /api/customer-payments/': [],
      'GET /api/orders/': [
        { id: 1, number: 'CMD-0001', customer: 60, status: 'delivered', total_amount: '1000.00' },
        { id: 2, number: 'CMD-0002', customer: 61, status: 'delivered', total_amount: '1000.00' },
      ],
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/paiements-clients' })
    await user.click(await screen.findByRole('button', { name: '+ دفعة جديدة' }))
    await user.selectOptions(screen.getByLabelText(/^الزبون/), '60')
    const orderSelect = screen.getByLabelText(/عن الطلبية/)
    expect(orderSelect).toHaveTextContent('CMD-0001')
    expect(orderSelect).not.toHaveTextContent('CMD-0002')
  })

  it('la Direction lit sans pouvoir modifier', async () => {
    mockApi({
      ...loginAs({ ...farmer, roles: ['direction'] }),
      ...COMMON,
      'GET /api/sales/': [{ id: 1, owner_name: 'Sidi', sale_date: '2026-10-01', total_amount: '10.00', variety_detail: null }],
    })
    renderAt(<App />, { path: '/espace/ventes' })
    expect(await screen.findByText('10 MRU')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /بيع جديد/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'تعديل' })).not.toBeInTheDocument()
  })

  it('en français aussi', async () => {
    await i18n.changeLanguage('fr')
    mockApi({ ...loginAs({ ...farmer, roles: ['seller'] }), ...COMMON })
    renderAt(<App />, { path: '/espace/clients' })
    expect(await screen.findByText('Premium')).toBeInTheDocument()
    expect(screen.getByText(/Avance de/)).toBeInTheDocument()
  })
})
