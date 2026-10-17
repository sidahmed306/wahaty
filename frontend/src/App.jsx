import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router'
import { useAuth } from './auth/AuthProvider'
import Layout from './components/Layout'
import { Loader } from './components/ui'
import { Claim, Login, Register } from './pages/auth/AuthPages'
import Home from './pages/public/Home'
import Install from './pages/public/Install'
import Market, { ListingDetail } from './pages/public/Market'
import Oases, { OasisDetail } from './pages/public/Oases'
import Varieties, { VarietyDetail } from './pages/public/Varieties'

// L'espace connecté est chargé seulement quand on y entre : le site public reste léger.
const space = () => import('./pages/space/SpacePages')
const page = (name) => lazy(() => space().then((m) => ({ default: m[name] })))
const SpaceLayout = page('SpaceLayout')
const MyDashboard = page('MyDashboard')
const DirectionDashboard = page('DirectionDashboard')
const FinanceSummary = page('FinanceSummary')
const Notifications = page('Notifications')
const PlatformSettings = page('PlatformSettings')
const Profile = page('Profile')
const Catalogue = page('Catalogue')
const ResourceLazy = page('Resource')
const Resource = (props) => <ResourceLazy {...props} />

/** Page réservée aux personnes connectées (et, si précisé, à certains rôles). */
export function RequireAuth({ roles, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Loader />
  if (!user) return <Navigate to="/connexion" replace state={{ from: location.pathname }} />
  if (roles && !roles.some((role) => user.roles.includes(role))) return <Navigate to="/espace" replace />
  return children
}

export function NotFound() {
  const { t } = useTranslation()
  return (
    <section className="container section" style={{ textAlign: 'center' }}>
      <img src="/logo-mark.webp" alt="" style={{ width: 90, margin: '0 auto' }} />
      <h1>{t('errors.notFoundTitle')}</h1>
      <p className="muted">{t('errors.notFound')}</p>
      <Link className="btn btn-primary" to="/">
        {t('nav.home')}
      </Link>
    </section>
  )
}

const FARM = ['farmer', 'field_agent', 'direction']
const SELL = ['seller', 'direction']
const MONEY = ['farmer', 'seller', 'field_agent', 'direction']
const DIR = ['direction']

const guarded = (roles, element) => <RequireAuth roles={roles}>{element}</RequireAuth>

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="varietes" element={<Varieties />} />
        <Route path="varietes/:slug" element={<VarietyDetail />} />
        <Route path="oasis" element={<Oases />} />
        <Route path="oasis/:slug" element={<OasisDetail />} />
        <Route path="marche" element={<Market />} />
        <Route path="marche/:id" element={<ListingDetail />} />
        <Route path="installer" element={<Install />} />
        <Route path="connexion" element={<Login />} />
        <Route path="inscription" element={<Register />} />
        <Route path="reprise" element={<Claim />} />
        <Route
          path="espace"
          element={
            <RequireAuth>
              <Suspense fallback={<Loader />}>
                <SpaceLayout />
              </Suspense>
            </RequireAuth>
          }
        >
          <Route index element={<MyDashboard />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="profil" element={<Profile />} />
          <Route path="agriculteurs" element={guarded(['field_agent'], <Resource name="agentFarmers" />)} />
          <Route path="fermes" element={guarded(FARM, <Resource name="farms" />)} />
          <Route path="palmiers" element={guarded(FARM, <Resource name="palmGroups" />)} />
          <Route path="recoltes" element={guarded(FARM, <Resource name="harvests" />)} />
          <Route path="ventes" element={guarded(FARM, <Resource name="sales" />)} />
          <Route path="depenses" element={guarded(MONEY, <Resource name="expenses" />)} />
          <Route path="bilan" element={guarded(MONEY, <FinanceSummary />)} />
          <Route path="commandes" element={guarded(SELL, <Resource name="orders" />)} />
          <Route path="clients" element={guarded(SELL, <Resource name="customers" />)} />
          <Route path="paiements-clients" element={guarded(SELL, <Resource name="customerPayments" />)} />
          <Route path="factures" element={guarded(SELL, <Resource name="invoices" />)} />
          <Route path="produits" element={guarded(SELL, <Resource name="products" />)} />
          <Route path="mouvements" element={guarded(SELL, <Resource name="stockMovements" />)} />
          <Route path="fournisseurs" element={guarded(SELL, <Resource name="suppliers" />)} />
          <Route path="achats" element={guarded(SELL, <Resource name="purchases" />)} />
          <Route path="paiements-fournisseurs" element={guarded(SELL, <Resource name="supplierPayments" />)} />
          <Route path="annonces" element={guarded(['farmer', 'seller'], <Resource name="myListings" />)} />
          <Route path="direction" element={guarded(DIR, <DirectionDashboard />)} />
          <Route path="comptes" element={guarded(DIR, <Resource name="users" />)} />
          <Route path="validation-annonces" element={guarded(DIR, <Resource name="review" />)} />
          <Route path="journal" element={guarded(DIR, <Resource name="audit" />)} />
          <Route path="reglages" element={guarded(DIR, <PlatformSettings />)} />
          <Route path="catalogue" element={guarded(DIR, <Catalogue />)} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
