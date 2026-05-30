import { SESSION_STORAGE_KEY } from '../app/constants'
import type { Session } from '../app/types'

export function readStoredSession(): Session | null {
  try {
    const rawValue = window.localStorage.getItem(SESSION_STORAGE_KEY)
    return rawValue ? (JSON.parse(rawValue) as Session) : null
  } catch {
    return null
  }
}

export function writeStoredSession(session: Session | null) {
  if (!session) {
    window.localStorage.removeItem(SESSION_STORAGE_KEY)
    return
  }

  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
}
