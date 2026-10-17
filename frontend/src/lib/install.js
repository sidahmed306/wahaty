// Installation de l'application sur l'écran d'accueil, sans App Store ni Play Store (PWA).
// - Android / Chrome / Edge : le navigateur propose l'installation (événement « beforeinstallprompt ») :
//   on le garde pour l'ouvrir quand l'utilisateur appuie sur notre bouton.
// - iPhone / iPad (Safari) : pas d'installation automatique : on explique « Partager → Sur l'écran d'accueil ».

let deferredPrompt = null
const listeners = new Set()

function notify() {
  listeners.forEach((listener) => listener())
}

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault()
    deferredPrompt = event
    notify()
  })
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null
    notify()
  })
}

export function onInstallChange(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function canPromptInstall() {
  return deferredPrompt !== null
}

/** Ouvre la fenêtre d'installation du navigateur ; renvoie true si l'utilisateur accepte. */
export async function promptInstall() {
  if (!deferredPrompt) return false
  const event = deferredPrompt
  deferredPrompt = null
  notify()
  await event.prompt()
  const choice = await event.userChoice
  return choice?.outcome === 'accepted'
}

/** L'application est-elle déjà ouverte depuis l'écran d'accueil ? */
export function isInstalled() {
  return Boolean(
    window.matchMedia?.('(display-mode: standalone)')?.matches || window.navigator.standalone,
  )
}

/** « ios », « android » ou « other » (ordinateur…), d'après le navigateur. */
export function platform(userAgent = window.navigator.userAgent) {
  if (/iphone|ipad|ipod/i.test(userAgent) || (/macintosh/i.test(userAgent) && 'ontouchend' in document))
    return 'ios'
  if (/android/i.test(userAgent)) return 'android'
  return 'other'
}
