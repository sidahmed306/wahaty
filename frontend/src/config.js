// Contact général de la plateforme (affiché en bas de toutes les pages).
export const CONTACT_WHATSAPP = '22247826859'
export const CONTACT_DISPLAY = '47 82 68 59'

export function whatsappLink(number = CONTACT_WHATSAPP, text = '') {
  const digits = String(number).replace(/\D/g, '')
  return `https://wa.me/${digits}${text ? `?text=${encodeURIComponent(text)}` : ''}`
}
