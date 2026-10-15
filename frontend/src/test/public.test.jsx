import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from '../App'
import Layout from '../components/Layout'
import i18n from '../i18n'
import Home from '../pages/public/Home'
import Market, { ListingDetail } from '../pages/public/Market'
import Oases, { OasisDetail } from '../pages/public/Oases'
import Varieties, { VarietyDetail } from '../pages/public/Varieties'
import { mockApi, renderAt } from './utils'

const sekani = {
  id: 3,
  slug: 'sekani',
  name_ar: 'سكاني',
  name_fr: 'Sekani',
  description_ar: 'صفراء بمذاق ملكي',
  description_fr: 'Datte jaune au goût royal',
  texture: 'soft',
  ripening_start_month: 6,
  ripening_end_month: 8,
  photo: 'https://res.cloudinary.com/demo/sekani.jpg',
  oases: [{ id: 1, slug: 'chinguetti', name_ar: 'شنقيط', name_fr: 'Chinguetti' }],
}
const honey = {
  ...sekani,
  id: 9,
  slug: 'miel-de-dattes',
  name_ar: 'عسل التمر',
  name_fr: 'Miel de dattes',
  description_ar: 'سائل حلو',
  photo: null,
  oases: [],
}

const region = { id: 1, slug: 'adrar', name_ar: 'آدرار', name_fr: 'Adrar' }
const oasis = {
  id: 1,
  slug: 'chinguetti',
  name_ar: 'شنقيط',
  name_fr: 'Chinguetti',
  description_ar: 'مدينة تاريخية',
  description_fr: 'Ville historique',
  region_detail: region,
  latitude: '20.46',
  longitude: '-12.36',
  photos: [{ id: 4, image: '/media/oases/c.jpg', caption_ar: 'المسجد', caption_fr: 'La mosquée' }],
  varieties_detail: [{ id: 3, slug: 'sekani', name_ar: 'سكاني', name_fr: 'Sekani' }],
}

const listing = {
  id: 11,
  title: 'سكاني ممتاز',
  description: 'تمر هذا الموسم',
  variety: { id: 3, slug: 'sekani', name_ar: 'سكاني', name_fr: 'Sekani' },
  oasis: { id: 1, slug: 'chinguetti', name_ar: 'شنقيط', name_fr: 'Chinguetti', region },
  price_per_kg: '450.00',
  quantity_kg: '120.00',
  seller_name: 'Ahmed',
  whatsapp_link: 'https://wa.me/22247000002?text=x',
  phone_link: 'tel:+22247000002',
  photos: [
    { id: 1, image: '/media/l/1.jpg' },
    { id: 2, image: '/media/l/2.jpg' },
  ],
  published_at: '2026-10-01T10:00:00Z',
}

describe('en-tête et pied de page', () => {
  it('logo, WhatsApp sur toutes les pages, changement de langue', async () => {
    mockApi({})
    const user = userEvent.setup()
    renderAt(<Layout />, { extraRoutes: <Route path="/x" element={<p>x</p>} /> })
    expect(screen.getByLabelText('TRC إرث النخيل')).toBeInTheDocument()
    const whatsapp = screen.getByLabelText(/WhatsApp 47 82 68 59/)
    expect(whatsapp).toHaveAttribute('href', expect.stringContaining('https://wa.me/22247826859?text='))
    expect(document.documentElement.dir).toBe('rtl')
    await user.click(screen.getByRole('button', { name: /Passer en français/ }))
    expect(document.documentElement.dir).toBe('ltr')
    expect(screen.getByRole('link', { name: 'Marché' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ouvrir le menu' }))
    expect(screen.getByRole('button', { name: 'Fermer le menu' })).toHaveAttribute('aria-expanded', 'true')
  })
})

describe('accueil', () => {
  it('variétés et dernières annonces', async () => {
    mockApi({ 'GET /api/varieties/': [sekani, honey], 'GET /api/market/listings/': { count: 1, results: [listing] } })
    renderAt(<Home />)
    expect(await screen.findByRole('heading', { name: 'سكاني' })).toBeInTheDocument()
    expect(screen.getByText('مصدر طبيعي للطاقة والنشاط')).toBeInTheDocument()
    expect(await screen.findByText('سكاني ممتاز')).toBeInTheDocument()
  })
})

describe('variétés', () => {
  it('liste comme le flyer, recherche et « en saison »', async () => {
    const { calls } = mockApi({ 'GET /api/varieties/': [sekani, honey] })
    const user = userEvent.setup()
    renderAt(<Varieties />)
    expect(await screen.findByText('صفراء بمذاق ملكي')).toBeInTheDocument()
    // Pas de photo : le logo remplace la photo.
    const honeyRow = screen.getByRole('link', { name: /عسل التمر/ })
    expect(honeyRow.querySelector('img')).toHaveAttribute('src', '/logo-mark.webp')
    await user.click(screen.getByLabelText('في موسمها هذا الشهر'))
    await waitFor(() => expect(calls.at(-1).query.in_season).toBe(String(new Date().getMonth() + 1)))
  })

  it('aucune variété', async () => {
    mockApi({ 'GET /api/varieties/': [] })
    renderAt(<Varieties />)
    expect(await screen.findByText('لا يوجد شيء حاليًا.')).toBeInTheDocument()
  })

  it('fiche détaillée bilingue avec saison', async () => {
    mockApi({ 'GET /api/varieties/sekani/': sekani })
    renderAt(<VarietyDetail />, { path: '/varietes/sekani', route: '/varietes/:slug' })
    expect(await screen.findByRole('heading', { name: 'سكاني' })).toBeInTheDocument()
    expect(screen.getByText('Sekani')).toBeInTheDocument()
    expect(screen.getByText('طري')).toBeInTheDocument()
    expect(screen.getByText(/يونيو → أغسطس/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'شنقيط' })).toHaveAttribute('href', '/oasis/chinguetti')
    expect(screen.getByRole('link', { name: 'عرض إعلانات هذا النوع' })).toHaveAttribute('href', '/marche?variety=sekani')
  })

  it('variété introuvable', async () => {
    mockApi({})
    renderAt(<VarietyDetail />, { path: '/varietes/x', route: '/varietes/:slug' })
    expect(await screen.findByText('هذه الصفحة غير موجودة.')).toBeInTheDocument()
  })
})

describe('oasis', () => {
  it('liste filtrée par région', async () => {
    const { calls } = mockApi({ 'GET /api/regions/': [region], 'GET /api/oases/': [oasis] })
    const user = userEvent.setup()
    renderAt(<Oases />)
    expect(await screen.findByRole('heading', { name: 'شنقيط' })).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'آدرار' }))
    await waitFor(() => expect(calls.at(-1).query.region).toBe('adrar'))
  })

  it('liste vide', async () => {
    mockApi({ 'GET /api/regions/': [], 'GET /api/oases/': [] })
    renderAt(<Oases />)
    expect(await screen.findByText('لا توجد واحات في هذه المنطقة حاليًا.')).toBeInTheDocument()
  })

  it('fiche : photos, carte, variétés', async () => {
    mockApi({ 'GET /api/oases/chinguetti/': oasis })
    renderAt(<OasisDetail />, { path: '/oasis/chinguetti', route: '/oasis/:slug' })
    expect(await screen.findByRole('heading', { name: 'شنقيط' })).toBeInTheDocument()
    expect(screen.getByAltText('المسجد')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /عرض على الخريطة/ })).toHaveAttribute(
      'href',
      expect.stringContaining('mlat=20.46'),
    )
    expect(screen.getByRole('link', { name: 'سكاني' })).toBeInTheDocument()
  })

  it('fiche sans photo ni GPS, et oasis introuvable', async () => {
    mockApi({ 'GET /api/oases/a/': { ...oasis, photos: [], latitude: null, varieties_detail: [] } })
    renderAt(<OasisDetail />, { path: '/oasis/a', route: '/oasis/:slug' })
    expect(await screen.findByRole('heading', { name: 'شنقيط' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /الخريطة/ })).not.toBeInTheDocument()
  })

  it('erreur réseau', async () => {
    mockApi({ 'GET /api/oases/b/': [500, { detail: 'Erreur serveur' }] })
    renderAt(<OasisDetail />, { path: '/oasis/b', route: '/oasis/:slug' })
    expect(await screen.findByText('Erreur serveur')).toBeInTheDocument()
  })
})

describe('marché', () => {
  const routes = {
    'GET /api/varieties/': [sekani],
    'GET /api/regions/': [region],
    'GET /api/market/listings/': { count: 45, results: [listing] },
  }

  it('annonces, filtres dans l’adresse, pages', async () => {
    const { calls } = mockApi(routes)
    const user = userEvent.setup()
    renderAt(<Market />, { path: '/marche?variety=sekani' })
    expect(await screen.findByText('سكاني ممتاز')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/api/market/listings/').query.variety).toBe('sekani')
    expect(screen.getByText('1 / 3')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'التالي' }))
    expect(screen.getByTestId('location')).toHaveTextContent('page=2')
    await user.selectOptions(screen.getByLabelText('الترتيب'), 'price_per_kg')
    expect(screen.getByTestId('location')).toHaveTextContent('ordering=price_per_kg')
    expect(screen.getByTestId('location')).not.toHaveTextContent('page=')
    await user.selectOptions(screen.getByLabelText('المنطقة'), 'adrar')
    await user.type(screen.getByLabelText('أعلى سعر (أوقية/كغ)'), '5')
    await user.type(screen.getByLabelText('بحث'), 'x')
    await user.click(screen.getByRole('button', { name: 'السابق' }))
    await user.selectOptions(screen.getByLabelText('النوع'), '')
    expect(screen.getByTestId('location')).not.toHaveTextContent('variety=')
  })

  it('aucune annonce', async () => {
    mockApi({ ...routes, 'GET /api/market/listings/': { count: 0, results: [] } })
    renderAt(<Market />)
    expect(await screen.findByText('لا توجد إعلانات تطابق بحثك.')).toBeInTheDocument()
  })

  it('fiche d’annonce : WhatsApp et téléphone du vendeur', async () => {
    mockApi({ 'GET /api/market/listings/11/': listing })
    renderAt(<ListingDetail />, { path: '/marche/11', route: '/marche/:id' })
    expect(await screen.findByRole('heading', { name: 'سكاني ممتاز' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /راسل عبر واتساب/ })).toHaveAttribute('href', listing.whatsapp_link)
    expect(screen.getByRole('link', { name: /اتصل/ })).toHaveAttribute('href', 'tel:+22247000002')
    expect(screen.getByText('Ahmed')).toBeInTheDocument()
  })

  it('annonce sans photo, puis annonce retirée', async () => {
    mockApi({ 'GET /api/market/listings/12/': { ...listing, id: 12, photos: [], description: '' } })
    renderAt(<ListingDetail />, { path: '/marche/12', route: '/marche/:id' })
    expect(await screen.findByAltText('سكاني ممتاز')).toHaveAttribute('src', '/logo-mark.webp')
  })

  it('annonce introuvable', async () => {
    mockApi({})
    renderAt(<ListingDetail />, { path: '/marche/99', route: '/marche/:id' })
    expect(await screen.findByText('هذه الصفحة غير موجودة.')).toBeInTheDocument()
  })
})

describe('application complète', () => {
  it('page inconnue', async () => {
    mockApi({})
    renderAt(<App />, { path: '/nimporte' })
    expect(await screen.findByRole('heading', { name: 'الصفحة غير موجودة' })).toBeInTheDocument()
  })

  it('l’espace demande la connexion', async () => {
    mockApi({})
    renderAt(<App />, { path: '/espace/ventes' })
    expect(await screen.findByRole('heading', { name: 'تسجيل الدخول' })).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/connexion')
  })

  it('en français', async () => {
    await i18n.changeLanguage('fr')
    mockApi({ 'GET /api/varieties/': [sekani] })
    renderAt(<App />, { path: '/varietes' })
    expect(await screen.findByText('Datte jaune au goût royal')).toBeInTheDocument()
  })
})
