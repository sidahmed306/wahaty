import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { vi } from 'vitest'
import { AuthProvider } from '../auth/AuthProvider'

/**
 * Faux serveur : routes = { 'GET /api/varieties/': data, 'POST /api/x/': (body, url) => [status, data] }
 * Une valeur simple répond 200 ; une fonction peut renvoyer [statut, données].
 */
export function mockApi(routes) {
  const calls = []
  const fetchMock = vi.fn(async (input, options = {}) => {
    const url = new URL(String(input), 'http://localhost')
    const method = options.method || 'GET'
    let body = options.body
    if (typeof body === 'string') body = JSON.parse(body)
    calls.push({ method, path: url.pathname, query: Object.fromEntries(url.searchParams), body, headers: options.headers || {} })
    const handler = routes[`${method} ${url.pathname}`]
    if (handler === undefined) return jsonResponse(404, { detail: 'Not found' })
    const result = typeof handler === 'function' ? handler(body, url) : handler
    const [status, data] = Array.isArray(result) && typeof result[0] === 'number' ? result : [200, result]
    return jsonResponse(status, data)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock }
}

export function jsonResponse(status, data) {
  return new Response(status === 204 ? null : JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

/** Affiche un élément dans un routeur en mémoire, avec la connexion (AuthProvider). */
export function renderAt(element, { path = '/', route = '*', extraRoutes = null } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path={route} element={element} />
          {extraRoutes}
        </Routes>
        <LocationProbe />
      </AuthProvider>
    </MemoryRouter>,
  )
}

export function loginAs(user) {
  window.localStorage.setItem('trc.access', 'access-token')
  window.localStorage.setItem('trc.refresh', 'refresh-token')
  return { 'GET /api/auth/me/': user }
}

export const farmer = {
  id: 7,
  phone: '+22247000001',
  full_name: 'Sidi Mohamed',
  roles: ['farmer'],
  preferred_language: 'ar',
  status: 'approved',
  profile: { oasis: null, photo: null, whatsapp: '', address: '', business_name: '' },
}
