import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

/** Charge une adresse de l'API et recharge quand l'adresse ou les filtres changent. */
export function useFetch(path, params, { auth = true, enabled = true } = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(Boolean(path) && enabled)
  const key = JSON.stringify(params || {})
  const latest = useRef(0)

  const load = useCallback(async () => {
    if (!path || !enabled) return
    const call = ++latest.current
    setLoading(true)
    setError(null)
    try {
      const result = await api(path, { params: JSON.parse(key), auth })
      if (call === latest.current) setData(result)
    } catch (err) {
      if (call === latest.current) setError(err)
    } finally {
      if (call === latest.current) setLoading(false)
    }
  }, [path, key, auth, enabled])

  useEffect(() => {
    load()
  }, [load])

  return { data, error, loading, reload: load, setData }
}
