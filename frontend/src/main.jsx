import '@fontsource-variable/alexandria'
import '@fontsource-variable/unbounded'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { registerSW } from 'virtual:pwa-register'
import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import './i18n'
import './lib/install' // écoute tout de suite la proposition d'installation du navigateur
import './styles/global.css'

// Application installée : dès qu'une nouvelle version est en ligne, la page se recharge seule.
registerSW({ immediate: true })

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
