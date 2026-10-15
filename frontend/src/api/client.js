// Appels à l'API Django. Les jetons de connexion (JWT) sont gardés dans le navigateur ;
// quand le jeton court expire, on en demande un nouveau une seule fois puis on réessaie.

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const ACCESS = 'trc.access'
const REFRESH = 'trc.refresh'

let language = 'ar'
let onLogout = () => {}
let refreshing = null

export class ApiError extends Error {
  constructor(status, data) {
    super(firstMessage(data) || `HTTP ${status}`)
    this.status = status
    this.data = data
  }

  /** Erreurs par champ : { phone: "…", password: "…" } */
  get fields() {
    const out = {}
    if (this.data && typeof this.data === 'object' && !Array.isArray(this.data)) {
      for (const [key, value] of Object.entries(this.data)) {
        if (key !== 'detail' && key !== 'non_field_errors') out[key] = flatten(value).join(' ')
      }
    }
    return out
  }

  /** Message général (detail, non_field_errors ou liste simple). */
  get general() {
    const data = this.data
    if (!data) return ''
    if (typeof data === 'string') return data
    if (Array.isArray(data)) return flatten(data).join(' ')
    return flatten(data.detail ?? data.non_field_errors ?? []).join(' ')
  }
}

function flatten(value) {
  if (value == null) return []
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(flatten)
  if (typeof value === 'object') return Object.values(value).flatMap(flatten)
  return [String(value)]
}

function firstMessage(data) {
  return flatten(data)[0] || ''
}

function safeStorage(action) {
  try {
    return action(window.localStorage)
  } catch {
    return null
  }
}

export const tokens = {
  get access() {
    return safeStorage((s) => s.getItem(ACCESS))
  },
  get refresh() {
    return safeStorage((s) => s.getItem(REFRESH))
  },
  set({ access, refresh }) {
    safeStorage((s) => {
      if (access) s.setItem(ACCESS, access)
      if (refresh) s.setItem(REFRESH, refresh)
    })
  },
  clear() {
    safeStorage((s) => {
      s.removeItem(ACCESS)
      s.removeItem(REFRESH)
    })
  },
}

export function setApiLanguage(lang) {
  language = lang
}

export function setLogoutHandler(handler) {
  onLogout = handler
}

export function apiUrl(path) {
  return path.startsWith('http') ? path : `${API_URL}${path}`
}

function buildQuery(params) {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.append(key, value)
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

async function refreshAccess() {
  const refresh = tokens.refresh
  if (!refresh) return false
  refreshing ??= fetch(apiUrl('/api/auth/refresh/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept-Language': language },
    body: JSON.stringify({ refresh }),
  })
    .then(async (response) => {
      if (!response.ok) return false
      tokens.set(await response.json())
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

async function parse(response) {
  if (response.status === 204 || response.status === 205) return null
  const type = response.headers.get('Content-Type') || ''
  if (type.includes('application/json')) return response.json()
  if (type.includes('application/pdf')) return response.blob()
  const text = await response.text()
  return text || null
}

/**
 * Appel générique.
 * options : method, body (objet → JSON, FormData → envoi de fichier), params, auth (true par défaut)
 */
export async function api(path, { method = 'GET', body, params, auth = true, raw = false } = {}) {
  const send = () => {
    const headers = { Accept: 'application/json', 'Accept-Language': language }
    let payload = body
    if (body !== undefined && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
      payload = JSON.stringify(body)
    }
    const access = auth ? tokens.access : null
    if (access) headers.Authorization = `Bearer ${access}`
    return fetch(apiUrl(path) + buildQuery(params), { method, headers, body: payload })
  }

  let response = await send()
  if (response.status === 401 && auth && tokens.access) {
    if (await refreshAccess()) {
      response = await send()
    } else {
      tokens.clear()
      onLogout()
    }
  }
  if (raw && response.ok) return response
  const data = await parse(response)
  if (!response.ok) throw new ApiError(response.status, data)
  return data
}

/** Liste complète : accepte une réponse simple (tableau) ou paginée ({results}). */
export function asList(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}
