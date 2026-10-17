import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { canPromptInstall, isInstalled, platform } from '../lib/install'
import Install from '../pages/public/Install'
import { mockApi, renderAt } from './utils'

describe('installer l’application (sans store)', () => {
  it('reconnaît iPhone, Android et ordinateur', () => {
    expect(platform('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)')).toBe('ios')
    expect(platform('Mozilla/5.0 (Linux; Android 14; SM-A145F)')).toBe('android')
    expect(platform('Mozilla/5.0 (X11; Linux x86_64)')).toBe('other')
    expect(isInstalled()).toBe(false)
  })

  it('Android : le bouton ouvre la fenêtre d’installation du navigateur', async () => {
    mockApi({})
    const prompt = vi.fn()
    const event = new Event('beforeinstallprompt')
    event.prompt = prompt
    event.userChoice = Promise.resolve({ outcome: 'accepted' })
    const user = userEvent.setup()
    renderAt(<Install />)
    expect(screen.queryByRole('button', { name: 'ثبّت التطبيق الآن' })).toBeNull()
    act(() => window.dispatchEvent(event))
    expect(canPromptInstall()).toBe(true)
    await user.click(screen.getByRole('button', { name: 'ثبّت التطبيق الآن' }))
    expect(prompt).toHaveBeenCalled()
    expect(await screen.findByText(/تم التثبيت/)).toBeInTheDocument()
    expect(canPromptInstall()).toBe(false)
  })

  it('explique les étapes iPhone et Android', () => {
    mockApi({})
    renderAt(<Install />)
    expect(screen.getByText('على آيفون (Safari)')).toBeInTheDocument()
    expect(screen.getByText('على أندرويد (Chrome)')).toBeInTheDocument()
    expect(screen.getAllByText(/الشاشة الرئيسية/).length).toBeGreaterThan(2)
  })

  it('déjà installée : message simple', () => {
    mockApi({})
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    renderAt(<Install />)
    expect(screen.getByText(/التطبيق مثبّت/)).toBeInTheDocument()
  })
})
