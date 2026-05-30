export type AuthMode = 'register' | 'login'

export type AppScreen =
  | 'calendar'
  | 'profile'
  | 'settings'
  | 'tasks'
  | 'availability'
  | 'busy'

export type ScheduleStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

export type ProfileStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

export type TasksStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

export type AvailabilityStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

export type BusyStatus = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

export type CalendarViewDays = 1 | 3 | 7

export type User = {
  id: string
  username: string
  email: string
  timezone: string
  locale: string
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export type Session = {
  access_token: string
  token_type: string
  expires_in: number
  refresh_expires_in: number
  user: User
}

export type ScheduleTask = {
  task_id?: string
  status?: TaskLifecycleStatus
  title?: string
  task_title?: string
  name?: string
  start_at?: string
  end_at?: string
  variant_id?: number | null
  split_part_index?: number | null
  split_part_count?: number | null
  category?: string | null
  description?: string | null
  task?: {
    title?: string
    category?: string | null
    description?: string | null
  } | null
}

export type Schedule = {
  id: string
  user_id: string
  planning_start: string
  planning_end: string
  slot_minutes: number
  status: string
  is_current: boolean
  selected_variant_id: number | null
  source_request: Record<string, unknown> | null
  profile_context: Record<string, unknown> | null
  schedule_metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
  scheduled_tasks: ScheduleTask[]
}

export type RegisterForm = {
  username: string
  email: string
  password: string
}

export type LoginForm = {
  identifier: string
  password: string
}

export type ZonedDateParts = {
  year: number
  month: number
  day: number
  hour: number
  minute: number
}

export type CalendarDay = {
  key: string
  stamp: number
  weekdayLabel: string
  dateLabel: string
  fullLabel: string
}

export type CalendarSegment = {
  key: string
  dayKey: string
  title: string
  description: string
  category: string
  taskId: string
  status?: TaskLifecycleStatus
  startAt: string
  endAt: string
  startMinutes: number
  endMinutes: number
  durationLabel: string
}

export type PositionedCalendarSegment = CalendarSegment & {
  columnIndex: number
  columnCount: number
}

export type TimeOfDayScores = {
  morning: number
  afternoon: number
  evening: number
  night: number
}

export type UserProfile = {
  user_id: string
  productivity: TimeOfDayScores
  category_time_preferences: Record<string, TimeOfDayScores>
  duration_multipliers: Record<string, number>
  load: {
    comfortable_daily_minutes: number
    max_daily_planned_minutes: number
    preferred_break_minutes: number
    preferred_focus_block_minutes: number
    max_focus_block_minutes: number
    min_break_after_focus_minutes: number
  }
  behavior: {
    completion_rate: number
    reschedule_rate: number
    likes_compact_schedule: boolean
  }
}

export type CategoryTimePreferenceFormEntry = {
  id: string
  category: string
  morning: string
  afternoon: string
  evening: string
  night: string
}

export type DurationMultiplierFormEntry = {
  id: string
  category: string
  multiplier: string
}

export type ProfileForm = {
  productivityMorning: string
  productivityAfternoon: string
  productivityEvening: string
  productivityNight: string
  categoryTimePreferences: CategoryTimePreferenceFormEntry[]
  durationMultipliers: DurationMultiplierFormEntry[]
  comfortableDailyMinutes: string
  maxDailyPlannedMinutes: string
  preferredBreakMinutes: string
  preferredFocusBlockMinutes: string
  maxFocusBlockMinutes: string
  minBreakAfterFocusMinutes: string
  completionRate: string
  rescheduleRate: string
  likesCompactSchedule: boolean
}

export type StoredPlanningRunRequest = {
  planning_start: string
  planning_end: string
  slot_minutes: number
  task_statuses: string[]
  settings: {
    mode: 'quick' | 'full'
    min_break_minutes: number
    max_daily_planned_minutes: number
    max_schedule_variants: number
    use_warm_start: boolean
    replan_from_current_schedule: boolean
  }
}

export type BestScheduleResponse = {
  variant_id: number | null
  scheduled_tasks: ScheduleTask[]
  unscheduled_tasks?: Array<Record<string, unknown>>
}

export type GenerationSettingsForm = {
  minBreakMinutes: string
  maxDailyPlannedMinutes: string
}

export type TaskEnergyRequired = 'low' | 'medium' | 'high'

export type TaskLifecycleStatus = 'active' | 'completed' | 'cancelled' | 'archived'

export type TaskWindow = {
  start: string
  end: string
}

export type AvailabilityRecurrenceRule =
  | 'weekly'
  | 'biweekly'
  | 'daily'
  | `custom:${number}`

export type AvailabilityWindow = {
  id?: string
  window_id?: string
  user_id?: string
  start: string
  end: string
  is_recurring?: boolean
  recurrence_rule?: AvailabilityRecurrenceRule | null
  source?: string | null
  created_at?: string
  updated_at?: string
}

export type BusyInterval = {
  id?: string
  interval_id?: string
  user_id?: string
  title?: string | null
  start: string
  end: string
  source?: string | null
  external_event_id?: string | null
  payload?: Record<string, unknown> | null
  created_at?: string
  updated_at?: string
}

export type BusyForm = {
  title: string
  start: string
  end: string
}

export type CalendarOverlayBlock = {
  key: string
  dayKey: string
  startMinutes: number
  endMinutes: number
  kind: 'availability' | 'busy'
  title: string
  startAt?: string
  endAt?: string
}

export type UserTask = {
  id?: string
  task_id?: string
  title: string
  description?: string | null
  duration_minutes: number
  priority: number
  category?: string | null
  energy_required: TaskEnergyRequired
  status: TaskLifecycleStatus
  deadline?: string | null
  earliest_start?: string | null
  latest_end?: string | null
  fixed_start?: string | null
  is_mandatory: boolean
  is_fixed: boolean
  allow_splitting: boolean
  min_split_part_minutes?: number | null
  preferred_windows?: TaskWindow[]
  allowed_windows?: TaskWindow[]
  constraints?: Record<string, unknown>
  llm_metadata?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export type TaskWindowFormEntry = {
  id: string
  start: string
  end: string
}

export type TaskForm = {
  title: string
  description: string
  durationMinutes: string
  priority: string
  category: string
  energyRequired: TaskEnergyRequired
  status: TaskLifecycleStatus
  deadline: string
  earliestStart: string
  latestEnd: string
  fixedStart: string
  isMandatory: boolean
  isFixed: boolean
  allowSplitting: boolean
  minSplitPartMinutes: string
  preferredWindows: TaskWindowFormEntry[]
  allowedWindows: TaskWindowFormEntry[]
}
