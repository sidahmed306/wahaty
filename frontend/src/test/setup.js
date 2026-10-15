import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import i18n from '../i18n'

window.scrollTo = () => {}
window.open = vi.fn(() => null)
URL.createObjectURL = vi.fn(() => 'blob:pdf')

beforeEach(async () => {
  window.localStorage.clear()
  await i18n.changeLanguage('ar')
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
