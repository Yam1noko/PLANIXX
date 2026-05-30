import type {
  CategoryTimePreferenceFormEntry,
  DurationMultiplierFormEntry,
  ProfileForm,
  TimeOfDayScores,
  UserProfile,
} from '../../app/types'

function buildEntryId(prefix: string, category = '') {
  const normalizedCategory = category.trim().toLowerCase().replace(/\s+/g, '-')
  const randomPart = Math.random().toString(36).slice(2, 8)
  return `${prefix}-${normalizedCategory || 'new'}-${randomPart}`
}

export function createCategoryTimePreferenceEntry(
  category = '',
): CategoryTimePreferenceFormEntry {
  return {
    id: buildEntryId('category-time', category),
    category,
    morning: '0',
    afternoon: '0',
    evening: '0',
    night: '0',
  }
}

export function createDurationMultiplierEntry(category = ''): DurationMultiplierFormEntry {
  return {
    id: buildEntryId('duration-multiplier', category),
    category,
    multiplier: '1',
  }
}

export function createEmptyProfileForm(): ProfileForm {
  return {
    productivityMorning: '0',
    productivityAfternoon: '0',
    productivityEvening: '0',
    productivityNight: '0',
    categoryTimePreferences: [],
    durationMultipliers: [],
    comfortableDailyMinutes: '0',
    maxDailyPlannedMinutes: '0',
    preferredBreakMinutes: '0',
    preferredFocusBlockMinutes: '0',
    maxFocusBlockMinutes: '0',
    minBreakAfterFocusMinutes: '0',
    completionRate: '0',
    rescheduleRate: '0',
    likesCompactSchedule: false,
  }
}

export function profileToForm(profile: UserProfile): ProfileForm {
  return {
    productivityMorning: String(profile.productivity.morning),
    productivityAfternoon: String(profile.productivity.afternoon),
    productivityEvening: String(profile.productivity.evening),
    productivityNight: String(profile.productivity.night),
    categoryTimePreferences: Object.entries(profile.category_time_preferences ?? {})
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([category, scores]) => ({
        id: buildEntryId('category-time', category),
        category,
        morning: String(scores.morning),
        afternoon: String(scores.afternoon),
        evening: String(scores.evening),
        night: String(scores.night),
      })),
    durationMultipliers: Object.entries(profile.duration_multipliers ?? {})
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([category, multiplier]) => ({
        id: buildEntryId('duration-multiplier', category),
        category,
        multiplier: String(multiplier),
      })),
    comfortableDailyMinutes: String(profile.load.comfortable_daily_minutes),
    maxDailyPlannedMinutes: String(profile.load.max_daily_planned_minutes),
    preferredBreakMinutes: String(profile.load.preferred_break_minutes),
    preferredFocusBlockMinutes: String(profile.load.preferred_focus_block_minutes),
    maxFocusBlockMinutes: String(profile.load.max_focus_block_minutes),
    minBreakAfterFocusMinutes: String(profile.load.min_break_after_focus_minutes),
    completionRate: String(profile.behavior.completion_rate),
    rescheduleRate: String(profile.behavior.reschedule_rate),
    likesCompactSchedule: profile.behavior.likes_compact_schedule,
  }
}

function parseFiniteNumber(value: string, label: string) {
  const parsed = Number(value)

  if (!Number.isFinite(parsed)) {
    throw new Error(`Некорректное значение поля "${label}".`)
  }

  return parsed
}

function normalizeCategoryName(category: string, label: string) {
  const normalized = category.trim()

  if (!normalized) {
    throw new Error(`Поле "${label}" не может быть пустым.`)
  }

  return normalized
}

function buildCategoryTimePreferences(
  entries: CategoryTimePreferenceFormEntry[],
): Record<string, TimeOfDayScores> {
  const result: Record<string, TimeOfDayScores> = {}

  entries.forEach((entry, index) => {
    const category = normalizeCategoryName(
      entry.category,
      `category_time_preferences[${index}].category`,
    )

    if (category in result) {
      throw new Error(`Категория "${category}" в category_time_preferences дублируется.`)
    }

    result[category] = {
      morning: parseFiniteNumber(entry.morning, `${category}.morning`),
      afternoon: parseFiniteNumber(entry.afternoon, `${category}.afternoon`),
      evening: parseFiniteNumber(entry.evening, `${category}.evening`),
      night: parseFiniteNumber(entry.night, `${category}.night`),
    }
  })

  return result
}

function buildDurationMultipliers(
  entries: DurationMultiplierFormEntry[],
): Record<string, number> {
  const result: Record<string, number> = {}

  entries.forEach((entry, index) => {
    const category = normalizeCategoryName(
      entry.category,
      `duration_multipliers[${index}].category`,
    )

    if (category in result) {
      throw new Error(`Категория "${category}" в duration_multipliers дублируется.`)
    }

    result[category] = parseFiniteNumber(
      entry.multiplier,
      `duration_multipliers.${category}`,
    )
  })

  return result
}

export function buildProfilePayload(userId: string, form: ProfileForm): UserProfile {
  return {
    user_id: userId,
    productivity: {
      morning: parseFiniteNumber(form.productivityMorning, 'productivity.morning'),
      afternoon: parseFiniteNumber(form.productivityAfternoon, 'productivity.afternoon'),
      evening: parseFiniteNumber(form.productivityEvening, 'productivity.evening'),
      night: parseFiniteNumber(form.productivityNight, 'productivity.night'),
    },
    category_time_preferences: buildCategoryTimePreferences(
      form.categoryTimePreferences,
    ),
    duration_multipliers: buildDurationMultipliers(form.durationMultipliers),
    load: {
      comfortable_daily_minutes: parseFiniteNumber(
        form.comfortableDailyMinutes,
        'load.comfortable_daily_minutes',
      ),
      max_daily_planned_minutes: parseFiniteNumber(
        form.maxDailyPlannedMinutes,
        'load.max_daily_planned_minutes',
      ),
      preferred_break_minutes: parseFiniteNumber(
        form.preferredBreakMinutes,
        'load.preferred_break_minutes',
      ),
      preferred_focus_block_minutes: parseFiniteNumber(
        form.preferredFocusBlockMinutes,
        'load.preferred_focus_block_minutes',
      ),
      max_focus_block_minutes: parseFiniteNumber(
        form.maxFocusBlockMinutes,
        'load.max_focus_block_minutes',
      ),
      min_break_after_focus_minutes: parseFiniteNumber(
        form.minBreakAfterFocusMinutes,
        'load.min_break_after_focus_minutes',
      ),
    },
    behavior: {
      completion_rate: parseFiniteNumber(
        form.completionRate,
        'behavior.completion_rate',
      ),
      reschedule_rate: parseFiniteNumber(
        form.rescheduleRate,
        'behavior.reschedule_rate',
      ),
      likes_compact_schedule: form.likesCompactSchedule,
    },
  }
}
