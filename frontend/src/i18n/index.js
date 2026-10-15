import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { setApiLanguage } from '../api/client'
import ar from './ar'
import fr from './fr'

export const LANG_KEY = 'trc.lang'
export const LANGUAGES = ['ar', 'fr']

function savedLanguage() {
  try {
    const value = window.localStorage.getItem(LANG_KEY)
    return LANGUAGES.includes(value) ? value : 'ar'
  } catch {
    return 'ar'
  }
}

/** Arabe : de droite à gauche ; français : de gauche à droite. */
export function applyDocumentLanguage(lang) {
  document.documentElement.lang = lang
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
  setApiLanguage(lang)
}

i18n.on('languageChanged', (lang) => {
  applyDocumentLanguage(lang)
  try {
    window.localStorage.setItem(LANG_KEY, lang)
  } catch {
    // Navigateur sans stockage : la langue revient à l'arabe au prochain chargement.
  }
})

const initial = savedLanguage()
applyDocumentLanguage(initial)

i18n.use(initReactI18next).init({
  resources: { ar: { translation: ar }, fr: { translation: fr } },
  lng: initial,
  fallbackLng: 'ar',
  interpolation: { escapeValue: false },
  returnNull: false,
})

export default i18n
