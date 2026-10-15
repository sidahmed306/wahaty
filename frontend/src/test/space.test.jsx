import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../App'
import i18n from '../i18n'
import { spaceMenu } from '../pages/space/SpacePages'
import { farmer, loginAs, mockApi, renderAt } from './utils'

const seller = { ...farmer, id: 8, full_name: 'Mariem Seller', roles: ['seller'] }
const agent = { ...farmer, id: 9, full_name: 'Agent Ely', roles: ['field_agent'] }
const direction = { ...farmer, id: 1, full_name: 'Direction TRC', roles: ['direction'] }

const varieties = [{ id: 3, slug: 'sekani', name_ar: 'سكاني', name_fr: 'Sekani' }]
const oases = [{ id: 1, slug: 'atar', name_ar: 'أطار', name_fr: 'Atar' }]
const sale = {
  id: 21,
  owner: 7,
  farm: null,
  variety: 3,
  variety_detail: varieties[0],
  sale_date: '2026-10-10',
  quantity_kg: '10.00',
  unit_price: '300.00',
  total_amount: '3000.00',
  buyer_name: 'Ahmed',
  notes: '',
}

const card = (text) => screen.getByText(text).closest('article')

describe('menu de l’espace selon les rôles', () => {
  const t = (k) => k
  const links = (user) => spaceMenu(user, t).flatMap((g) => g.links.map(([to]) => to))

  it('chacun ne voit que ses rubriques', () => {
    expect(links(farmer)).toContain('fermes')
    expect(links(farmer)).toContain('annonces')
    expect(links(farmer)).not.toContain('commandes')
    expect(links(seller)).toContain('commandes')
    expect(links(seller)).toContain('depenses')
    expect(links(seller)).not.toContain('fermes')
    expect(links(agent)).toContain('agriculteurs')
    expect(links(agent)).not.toContain('annonces')
    expect(links(direction)).toContain('journal')
    expect(links({ ...farmer, roles: ['farmer', 'seller'] }).filter((l) => l === 'depenses')).toHaveLength(1)
  })

  it('un agriculteur ne peut pas ouvrir les commandes', async () => {
    mockApi({ ...loginAs(farmer), 'GET /api/dashboard/me/': { roles: ['farmer'], unread_notifications: 0 } })
    renderAt(<App />, { path: '/espace/commandes' })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/espace$/))
  })
})

describe('ventes de l’agriculteur (page générique)', () => {
  it('liste, ajout, modification, suppression', async () => {
    let list = [sale]
    const { calls } = mockApi({
      ...loginAs(farmer),
      'GET /api/sales/': () => list,
      'GET /api/varieties/': varieties,
      'GET /api/farms/': [],
      'POST /api/sales/': (body) => {
        list = [...list, { ...sale, id: 22, ...body, variety_detail: null, total_amount: '900.00' }]
        return [201, list.at(-1)]
      },
      'PATCH /api/sales/21/': (body) => ({ ...sale, ...body }),
      'DELETE /api/sales/21/': [204, null],
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/ventes' })
    expect(await screen.findByText('3,000 MRU')).toBeInTheDocument()
    expect(screen.getByText('Ahmed')).toBeInTheDocument()

    // Ajout : les champs vides facultatifs partent à null, les textes vides restent ''.
    await user.click(screen.getByRole('button', { name: '+ بيع جديد' }))
    await user.type(screen.getByLabelText(/^الكمية \(كغ\)/), '3')
    await user.type(screen.getByLabelText(/^سعر الكيلو/), '300')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    expect(await screen.findByText('تم الحفظ.')).toBeInTheDocument()
    const post = calls.find((c) => c.method === 'POST' && c.path === '/api/sales/')
    expect(post.body).toMatchObject({ variety: null, farm: null, quantity_kg: '3', unit_price: '300', buyer_name: '', notes: '' })
    expect(post.body.sale_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(post.body).not.toHaveProperty('owner') // pas un agent
    await user.click(screen.getByRole('button', { name: 'إغلاق' }))

    // Modification
    await user.click(within(card('3,000 MRU')).getByRole('button', { name: 'تعديل' }))
    const buyer = screen.getByLabelText('المشتري')
    await user.clear(buyer)
    await user.type(buyer, 'Brahim')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(calls.find((c) => c.method === 'PATCH').body.buyer_name).toBe('Brahim')

    // Suppression avec confirmation
    await user.click(within(card('3,000 MRU')).getByRole('button', { name: 'حذف' }))
    expect(screen.getByText('هل تريد حقًا حذف هذا العنصر؟')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'تأكيد' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
  })

  it('erreurs du serveur affichées sous les champs', async () => {
    mockApi({
      ...loginAs(farmer),
      'GET /api/sales/': [],
      'GET /api/varieties/': varieties,
      'GET /api/farms/': [],
      'POST /api/sales/': [400, { quantity_kg: ['Assurez-vous que cette valeur est supérieure ou égale à 0.01.'], owner: ['x'] }],
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/ventes' })
    expect(await screen.findByText('لا يوجد شيء حاليًا.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '+ بيع جديد' }))
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    expect(await screen.findByText(/supérieure ou égale à 0.01/)).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('x') // erreur d'un champ non affiché
    await user.click(screen.getByRole('button', { name: 'إلغاء' }))
    expect(screen.queryByRole('button', { name: 'حفظ' })).not.toBeInTheDocument()
  })
})

describe('agent de terrain', () => {
  it('inscrit un agriculteur et voit le code de reprise une fois', async () => {
    const farmers = [{ id: 30, phone: '+22247000030', full_name: 'Salem', status: 'pending', claimed_at: null, date_joined: '2026-10-01T00:00:00Z', can_edit: true }]
    const { calls } = mockApi({
      ...loginAs(agent),
      'GET /api/agent/farmers/': farmers,
      'GET /api/oases/': oases,
      'POST /api/agent/farmers/': [201, { ...farmers[0], id: 31, claim_code: 'K7P2M9QX', claim_code_expires_at: '2026-10-22T10:00:00Z' }],
      'POST /api/agent/farmers/30/claim-code/': { claim_code: 'ZZ99YY88', claim_code_expires_at: '2026-10-23T10:00:00Z' },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/agriculteurs' })
    expect(await screen.findByText('Salem')).toBeInTheDocument()
    expect(screen.getByText('يمكنني الإدخال')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '+ تسجيل مزارع' }))
    await user.type(screen.getByLabelText(/الاسم الكامل/), 'Moussa')
    await user.type(screen.getByLabelText(/^الهاتف/), '47000031')
    await user.selectOptions(screen.getByLabelText(/^الواحة/), '1')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    expect(await screen.findByText(/K7P2M9QX/)).toBeInTheDocument()
    expect(screen.getByText(/22 أكتوبر 2026/)).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST').body).toEqual({
      full_name: 'Moussa',
      phone: '47000031',
      oasis: '1',
      preferred_language: 'ar',
    })
    await user.click(screen.getByRole('button', { name: 'رمز جديد' }))
    await user.click(screen.getByRole('button', { name: 'تأكيد' }))
    expect(await screen.findByText(/ZZ99YY88/)).toBeInTheDocument()
  })

  it('choisit l’agriculteur pour qui il saisit une ferme', async () => {
    const { calls } = mockApi({
      ...loginAs(agent),
      'GET /api/farms/': [{ id: 5, name: 'Ferme Nord', owner: 30, owner_name: 'Salem', oasis_detail: oases[0], total_palms: 12, productive_palms: 10, young_palms: 2, area_hectares: null }],
      'GET /api/oases/': oases,
      'GET /api/agent/farmers/': [{ id: 30, full_name: 'Salem' }],
      'POST /api/farms/': [201, { id: 6 }],
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/fermes' })
    expect(await screen.findByText('Ferme Nord')).toBeInTheDocument()
    expect(within(card('Ferme Nord')).getByText('Salem')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '+ مزرعة جديدة' }))
    await user.selectOptions(await screen.findByLabelText(/^المزارع/), '30')
    await user.type(screen.getByLabelText(/^الاسم/), 'Ferme Sud')
    await user.selectOptions(screen.getByLabelText(/^الواحة/), '1')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST').body).toMatchObject({ owner: '30', name: 'Ferme Sud', oasis: '1', area_hectares: null })
  })
})

describe('vendeur : commandes, factures, annonces', () => {
  const product = { id: 40, name: 'Sekani 1 kg', unit: 'kg', sale_price: '500.00', stock: '20.00', is_low_stock: true, low_stock_threshold: '25.00' }
  const order = {
    id: 50,
    number: 'CMD-0001',
    customer: 60,
    customer_name: 'Khadija',
    status: 'received',
    order_date: '2026-10-10',
    expected_delivery_date: '2026-10-12',
    is_late: true,
    days_late: 3,
    lines: [{ id: 1, product: 40, product_name: 'Sekani 1 kg', quantity: '2.00', unit_price: '500.00', line_total: '1000.00' }],
    subtotal: '1000.00',
    delivery_fee: '0.00',
    discount: '0.00',
    total_amount: '1000.00',
    cancel_reason: '',
    history: [{ from_status: '', to_status: 'received', changed_at: '2026-10-10T09:00:00Z', changed_by_name: 'Mariem' }],
  }

  it('crée une commande avec lignes (prix proposé), la confirme, l’annule', async () => {
    const { calls } = mockApi({
      ...loginAs(seller),
      'GET /api/orders/': [order],
      'GET /api/customers/': [{ id: 60, name: 'Khadija' }],
      'GET /api/products/': [product],
      'POST /api/orders/': [201, { ...order, id: 51 }],
      'POST /api/orders/50/status/': { ...order, status: 'confirmed' },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/commandes' })
    expect(await screen.findByText('CMD-0001 · Khadija')).toBeInTheDocument()
    expect(within(card('CMD-0001 · Khadija')).getByText('متأخرة')).toBeInTheDocument()
    expect(screen.getByText('تأخير 3 أيام')).toBeInTheDocument()

    await user.click(within(card('CMD-0001 · Khadija')).getByRole('button', { name: 'التفاصيل' }))
    expect(screen.getByRole('cell', { name: 'Sekani 1 kg' })).toBeInTheDocument()
    expect(screen.getByText(/\(Mariem\)/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '+ طلبية جديدة' }))
    await user.selectOptions(screen.getByLabelText(/^الزبون/), '60')
    await user.selectOptions(screen.getByLabelText(/^المنتج/), '40')
    expect(screen.getByLabelText(/^سعر الوحدة/)).toHaveValue(500)
    await user.type(screen.getByLabelText(/^الكمية$|^الكمية \*/), '3')
    await user.click(screen.getByRole('button', { name: '+ إضافة سطر' }))
    await user.click(screen.getAllByRole('button', { name: 'إزالة' })[1])
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/api/orders/')).toBe(true))
    expect(calls.find((c) => c.path === '/api/orders/' && c.method === 'POST').body.items).toEqual([
      { product: 40, quantity: '3', unit_price: '500.00' },
    ])

    await user.click(within(card('CMD-0001 · Khadija')).getByRole('button', { name: 'تأكيد الطلبية' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/orders/50/status/')).toBe(true))
    expect(calls.find((c) => c.path === '/api/orders/50/status/').body).toEqual({ status: 'confirmed' })

    await user.click(within(card('CMD-0001 · Khadija')).getByRole('button', { name: 'إلغاء الطلبية' }))
    const confirm = screen.getByRole('button', { name: 'تأكيد' })
    expect(confirm).toBeDisabled() // motif obligatoire
    await user.type(screen.getByLabelText(/سبب الإلغاء/), 'Client absent')
    await user.click(confirm)
    await waitFor(() =>
      expect(calls.filter((c) => c.path === '/api/orders/50/status/').at(-1).body).toEqual({
        status: 'cancelled',
        cancel_reason: 'Client absent',
      }),
    )
  })

  it('commande confirmée : facture, refus du serveur affiché, filtres', async () => {
    const confirmed = { ...order, status: 'confirmed', is_late: false, cancel_reason: '' }
    const { calls } = mockApi({
      ...loginAs(seller),
      'GET /api/orders/': [confirmed],
      'GET /api/customers/': [],
      'GET /api/products/': [],
      'POST /api/invoices/': [201, { id: 70, number: 'FAC-2026-0001' }],
      'POST /api/orders/50/status/': [400, { detail: 'Stock insuffisant pour « Sekani 1 kg ».' }],
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/commandes' })
    await screen.findByText('CMD-0001 · Khadija')
    await user.click(screen.getByRole('button', { name: 'إنشاء الفاتورة' }))
    expect(await screen.findByText('تم إنشاء الفاتورة FAC-2026-0001.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'تم التحضير' }))
    expect(await screen.findByText(/Stock insuffisant/)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('الحالة'), 'confirmed')
    await waitFor(() => expect(calls.some((c) => c.path === '/api/orders/' && c.query.status === 'confirmed')).toBe(true))
  })

  it('factures : PDF et annulation', async () => {
    const invoice = {
      id: 70,
      number: 'FAC-2026-0001',
      order: 50,
      order_number: 'CMD-0001',
      issue_date: '2026-10-11',
      customer_snapshot: { name: 'Khadija' },
      total_amount: '1000.00',
      status: 'issued',
      cancel_reason: '',
    }
    const { calls } = mockApi({
      ...loginAs(seller),
      'GET /api/invoices/': [invoice],
      'GET /api/orders/': [],
      'GET /api/invoices/70/pdf/': 'pdf',
      'POST /api/invoices/70/cancel/': { ...invoice, status: 'cancelled' },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/factures' })
    expect(await screen.findByText('FAC-2026-0001 · Khadija')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'فتح PDF' }))
    expect(await screen.findByText('فُتح ملف PDF في نافذة جديدة.')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/api/invoices/70/pdf/').headers.Authorization).toBe('Bearer access-token')
    await user.click(screen.getByRole('button', { name: 'إلغاء الفاتورة' }))
    await user.type(screen.getByLabelText(/سبب الإلغاء/), 'Erreur de prix')
    await user.click(screen.getByRole('button', { name: 'تأكيد' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/invoices/70/cancel/')).toBe(true))
  })

  it('PDF refusé par le serveur', async () => {
    mockApi({
      ...loginAs(seller),
      'GET /api/invoices/': [{ id: 71, number: 'FAC-2026-0002', customer_snapshot: {}, status: 'cancelled', total_amount: '1.00' }],
      'GET /api/orders/': [],
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/factures' })
    await user.click(await screen.findByRole('button', { name: 'فتح PDF' }))
    expect(await screen.findByText('حدث خطأ. حاول مرة أخرى.')).toBeInTheDocument()
  })

  it('produits : stock bas signalé', async () => {
    mockApi({ ...loginAs(seller), 'GET /api/products/': [product], 'GET /api/varieties/': varieties })
    renderAt(<App />, { path: '/espace/produits' })
    expect(await screen.findByText('مخزون منخفض')).toBeInTheDocument()
    expect(card('Sekani 1 kg')).toHaveTextContent('20 كغ')
  })

  it('annonces : photos, envoi pour validation', async () => {
    const draft = {
      id: 80,
      title: 'Sekani frais',
      status: 'draft',
      is_editable: true,
      variety_detail: varieties[0],
      oasis_detail: oases[0],
      price_per_kg: '450.00',
      quantity_kg: '50.00',
      photos: [{ id: 1, image: '/media/l/1.jpg' }],
      rejection_reason: '',
    }
    const { calls } = mockApi({
      ...loginAs({ ...seller, roles: ['farmer', 'seller'] }),
      'GET /api/market/my-listings/': [draft],
      'GET /api/varieties/': varieties,
      'GET /api/oases/': oases,
      'POST /api/market/my-listings/80/photos/': [201, { id: 2 }],
      'DELETE /api/market/my-listings/80/photos/1/': [204, null],
      'POST /api/market/my-listings/80/submit/': { ...draft, status: 'pending' },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/annonces' })
    expect(await screen.findByText('Sekani frais')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'التفاصيل' }))
    const file = new File(['img'], 'datte.jpg', { type: 'image/jpeg' })
    await user.upload(screen.getByLabelText(/إضافة صورة/), file)
    await waitFor(() => expect(calls.some((c) => c.path === '/api/market/my-listings/80/photos/')).toBe(true))
    const upload = calls.find((c) => c.path === '/api/market/my-listings/80/photos/')
    expect(upload.body.get('image').name).toBe('datte.jpg')
    await user.click(card('Sekani frais').querySelector('figure button'))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
    await user.click(screen.getByRole('button', { name: 'إرسال للمصادقة' }))
    expect(await screen.findByText('أُرسل الإعلان إلى الإدارة.')).toBeInTheDocument()
  })
})

describe('Direction', () => {
  it('tableau de bord Direction', async () => {
    mockApi({
      ...loginAs(direction),
      'GET /api/dashboard/direction/': {
        accounts: { farmers: 4, sellers: 2, field_agents: 1, pending: 1, suspended: 1 },
        farms: 3,
        palms: { productive: 180, young: 30, total: 210 },
        palms_by_variety: [{ variety: 'Sekani', variety_ar: 'سكاني', productive: 180, young: 30, total: 210 }],
        production_by_season: [],
        market: { published: 2, pending: 1 },
        orders: { by_status: { received: 1, delivered: 2 }, late: 1 },
        stock: { products: 3, low_stock: 1, stock_value: '16000.00' },
        amounts_due: { customers_owe: '3000.00', customer_advances: '500.00', suppliers_owed: '10000.00' },
        money: { sales_total: '39000.00', expenses_total: '2700.00', profit: '36300.00' },
      },
    })
    renderAt(<App />, { path: '/espace/direction' })
    expect(await screen.findByText('36,300 MRU')).toBeInTheDocument()
    expect(screen.getByText('16,000 MRU')).toBeInTheDocument()
    expect(screen.getByText('10,000 MRU')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'سكاني' })).toBeInTheDocument()
  })

  it('valide et suspend des comptes', async () => {
    const pending = { id: 12, full_name: 'Nouveau', phone: '+22247000012', roles: ['farmer'], status: 'pending', date_joined: '2026-10-14T00:00:00Z', last_login: null }
    const active = { ...pending, id: 13, full_name: 'Actif', status: 'approved' }
    const { calls } = mockApi({
      ...loginAs(direction),
      'GET /api/users/': [pending, active, { ...direction, status: 'approved', date_joined: null }],
      'POST /api/users/12/approve/': { ...pending, status: 'approved' },
      'POST /api/users/13/suspend/': { ...active, status: 'suspended' },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/comptes' })
    await user.click(within(await screen.findByText('Nouveau').then((el) => el.closest('article'))).getByRole('button', { name: 'مصادقة' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/users/12/approve/')).toBe(true))
    await user.click(within(card('Actif')).getByRole('button', { name: 'إيقاف' }))
    await user.click(screen.getByRole('button', { name: 'تأكيد' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/users/13/suspend/')).toBe(true))
    // Pas de bouton sur son propre compte.
    expect(within(card('Direction TRC')).queryByRole('button', { name: 'إيقاف' })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('بحث'), 'Act')
    await waitFor(() => expect(calls.at(-1).query.search).toBe('Act'))
  })

  it('refuse une annonce avec un motif', async () => {
    const listing = { id: 90, title: 'Annonce douteuse', status: 'pending', seller_name: 'X', variety_detail: varieties[0], oasis_detail: oases[0], price_per_kg: '1.00', quantity_kg: '1.00', photos: [{ id: 3, image: '/m.jpg' }], description: 'desc' }
    const { calls } = mockApi({
      ...loginAs(direction),
      'GET /api/market/review/': [listing],
      'POST /api/market/review/90/reject/': { ...listing, status: 'rejected' },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/validation-annonces' })
    await user.click(await screen.findByRole('button', { name: 'التفاصيل' }))
    expect(screen.getByText('desc')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'رفض' }))
    await user.type(screen.getByLabelText(/سبب الرفض/), 'Photos floues')
    await user.click(screen.getByRole('button', { name: 'تأكيد' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/api/market/review/90/reject/')?.body).toEqual({ reason: 'Photos floues' }))
  })

  it('journal : détail des changements', async () => {
    mockApi({
      ...loginAs(direction),
      'GET /api/audit/': {
        count: 1,
        results: [{ id: 1, created_at: '2026-10-15T10:00:00Z', user_name: null, acting_for_name: 'Salem', action: 'status_change', object_type: 'orders.Order', object_repr: 'Commande CMD-0001', changes: { status: ['received', 'confirmed'], note: 'x' }, ip_address: '41.188.10.20' }],
      },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/journal' })
    expect(await screen.findByText('Commande CMD-0001')).toBeInTheDocument()
    expect(screen.getByText('النظام')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'التفاصيل' }))
    expect(screen.getByRole('cell', { name: '"confirmed"' })).toBeInTheDocument()
  })

  it('réglages du classement des clients', async () => {
    const { calls } = mockApi({
      ...loginAs(direction),
      'GET /api/settings/': { premium_threshold: '100000.00', new_customer_days: 30, loyal_min_orders: 3, loyal_period_days: 180, inactive_days: 90, updated_at: 'x' },
      'PATCH /api/settings/': (body) => (body.premium_threshold === '-1' ? [400, { premium_threshold: ['Trop petit.'] }] : { ...body, updated_at: 'y' }),
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/reglages' })
    const threshold = await screen.findByLabelText('حدّ الزبون المميّز (أوقية)')
    await user.clear(threshold)
    await user.type(threshold, '-1')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    expect(await screen.findByText('Trop petit.')).toBeInTheDocument()
    await user.clear(threshold)
    await user.type(threshold, '150000')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    expect(await screen.findByText('تم الحفظ.')).toBeInTheDocument()
    expect(calls.at(-1).body).not.toHaveProperty('updated_at')
  })

  it('catalogue : liens vers l’administration', async () => {
    mockApi(loginAs(direction))
    renderAt(<App />, { path: '/espace/catalogue' })
    expect((await screen.findByText('الواحات', { selector: 'strong' })).closest('a')).toHaveAttribute('href', '/admin/oases/oasis/')
  })
})

describe('pages communes', () => {
  it('notifications : lire une, lire toutes', async () => {
    let unread = true
    const { calls } = mockApi({
      ...loginAs(farmer),
      'GET /api/notifications/': () => [
        { id: 1, message_ar: 'الطلبية متأخرة', message_fr: 'Commande en retard', read_at: unread ? null : 'x', created_at: '2026-10-15T08:00:00Z' },
        { id: 2, message_ar: 'مخزون منخفض', message_fr: 'Stock bas', read_at: unread ? null : 'x', created_at: '2026-10-15T08:00:00Z' },
      ],
      'POST /api/notifications/1/read/': {},
      'POST /api/notifications/read-all/': () => {
        unread = false
        return { marked: 2 }
      },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/notifications' })
    expect(await screen.findByText('الطلبية متأخرة')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'تعليم كمقروء' })[0])
    await waitFor(() => expect(calls.some((c) => c.path === '/api/notifications/1/read/')).toBe(true))
    await user.click(screen.getByRole('button', { name: 'تعليم الكل كمقروء' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'تعليم الكل كمقروء' })).not.toBeInTheDocument())
  })

  it('notifications vides', async () => {
    mockApi({ ...loginAs(farmer), 'GET /api/notifications/': [] })
    renderAt(<App />, { path: '/espace/notifications' })
    expect(await screen.findByText('لا توجد إشعارات.')).toBeInTheDocument()
  })

  it('profil : enregistrer, changer de langue, photo', async () => {
    const { calls } = mockApi({
      ...loginAs(farmer),
      'GET /api/oases/': oases,
      'PATCH /api/auth/me/': (body) =>
        body.profile.whatsapp === 'bad' ? [400, { profile: { whatsapp: ['Numéro invalide.'] } }] : { ...farmer, ...body, profile: { ...farmer.profile, ...body.profile } },
      'PUT /api/auth/me/photo/': { photo: '/media/profiles/p.jpg' },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/profil' })
    const whatsapp = await screen.findByLabelText('واتساب')
    await user.type(whatsapp, 'bad')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    expect(await screen.findByText('Numéro invalide.')).toBeInTheDocument()
    await user.clear(whatsapp)
    await user.selectOptions(screen.getByLabelText('اللغة'), 'fr')
    await user.selectOptions(screen.getByLabelText('الواحة'), '1')
    await user.click(screen.getByRole('button', { name: 'حفظ' }))
    expect(await screen.findByText('تم الحفظ.')).toBeInTheDocument()
    expect(document.documentElement.dir).toBe('ltr')
    expect(calls.filter((c) => c.method === 'PATCH').at(-1).body.profile.oasis).toBe(1)
    await user.upload(screen.getByLabelText(/Changer la photo/), new File(['x'], 'moi.png', { type: 'image/png' }))
    await waitFor(() => expect(document.querySelector('img[src="/media/profiles/p.jpg"]')).not.toBeNull())
    await i18n.changeLanguage('ar')
  })

  it('bilan : totaux, catégories, mois', async () => {
    const { calls } = mockApi({
      ...loginAs(farmer),
      'GET /api/finance/summary/': {
        sales_total: '35000.00',
        expenses_total: '2700.00',
        profit: '-100.00',
        expenses_by_category: [{ category: { id: 1, name_ar: 'سقي', name_fr: 'Irrigation' }, total: '2700.00' }],
        by_month: [{ month: '2026-10', sales: '35000.00', expenses: '2700.00', profit: '32300.00' }],
      },
    })
    const user = userEvent.setup()
    renderAt(<App />, { path: '/espace/bilan' })
    expect(await screen.findByText('سقي')).toBeInTheDocument()
    expect(screen.getByText('2026-10')).toBeInTheDocument()
    await user.type(screen.getByLabelText('من'), '2026-01-01')
    await waitFor(() => expect(calls.at(-1).query.date_from).toBe('2026-01-01'))
  })

  it('tableau de bord vendeur et agent', async () => {
    mockApi({
      ...loginAs({ ...farmer, roles: ['seller', 'field_agent'] }),
      'GET /api/dashboard/me/': {
        unread_notifications: 0,
        seller: {
          customers: 5,
          orders: { by_status: { received: 1 }, late: 0 },
          stock: { stock_value: '16000.00', low_stock: 0 },
          amounts_due: { customers_owe: '3000.00', suppliers_owed: '0.00' },
          money: { sales_total: '4000.00', expenses_total: '0.00', profit: '4000.00' },
        },
        field_agent: { farmers: 3, farmers_claimed: 1, farmers_pending: 1, farms: 2, palms: { total: 50, productive: 40, young: 10 }, production_by_season: [] },
      },
    })
    renderAt(<App />, { path: '/espace' })
    expect(await screen.findByText('16,000 MRU')).toBeInTheDocument()
    expect(screen.getByText('المزارعون المسجّلون')).toBeInTheDocument()
  })

  it('tableau de bord d’un compte Direction seul', async () => {
    mockApi({ ...loginAs(direction), 'GET /api/dashboard/me/': { unread_notifications: 0 } })
    renderAt(<App />, { path: '/espace' })
    expect(await screen.findByRole('link', { name: 'لوحة الإدارة' , hidden: false })).toBeInTheDocument()
  })
})
