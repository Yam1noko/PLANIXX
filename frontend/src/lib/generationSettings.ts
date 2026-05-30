import { GENERATION_SETTINGS_STORAGE_KEY } from '../app/constants'
import type { GenerationSettingsForm } from '../app/types'

const DEFAULT_GENERATION_SETTINGS: GenerationSettingsForm = {
  minBreakMinutes: '0',
  maxDailyPlannedMinutes: '480',
}

export function createDefaultGenerationSettings(): GenerationSettingsForm {
  return { ...DEFAULT_GENERATION_SETTINGS }
}

export function readStoredGenerationSettings(): GenerationSettingsForm {
  try {
    const rawValue = window.localStorage.getItem(GENERATION_SETTINGS_STORAGE_KEY)
    if (!rawValue) {
      return createDefaultGenerationSettings()
    }

    const parsed = JSON.parse(rawValue) as Partial<GenerationSettingsForm>
    return {
      minBreakMinutes:
        typeof parsed.minBreakMinutes === 'string'
          ? parsed.minBreakMinutes
          : DEFAULT_GENERATION_SETTINGS.minBreakMinutes,
      maxDailyPlannedMinutes:
        typeof parsed.maxDailyPlannedMinutes === 'string'
          ? parsed.maxDailyPlannedMinutes
          : DEFAULT_GENERATION_SETTINGS.maxDailyPlannedMinutes,
    }
  } catch {
    return createDefaultGenerationSettings()
  }
}

export function writeStoredGenerationSettings(settings: GenerationSettingsForm) {
  window.localStorage.setItem(
    GENERATION_SETTINGS_STORAGE_KEY,
    JSON.stringify(settings),
  )
}
