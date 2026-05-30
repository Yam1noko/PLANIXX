import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

import './App.css'
import type {
  AvailabilityStatus,
  AvailabilityWindow,
  AppScreen,
  AuthMode,
  BestScheduleResponse,
  BusyForm,
  BusyStatus,
  BusyInterval,
  CalendarViewDays,
  GenerationSettingsForm,
  LoginForm,
  ProfileForm,
  ProfileStatus,
  RegisterForm,
  Schedule,
  ScheduleStatus,
  Session,
  StoredPlanningRunRequest,
  TaskForm,
  TasksStatus,
  TaskWindowFormEntry,
  UserTask,
  UserProfile,
} from './app/types'
import { AvailabilityScreen } from './features/availability/AvailabilityScreen'
import { BusyScreen } from './features/busy/BusyScreen'
import {
  buildAvailabilityPayloads,
  getAvailabilityWindowId,
  windowTouchesWeek,
} from './features/availability/utils'
import type { AvailabilityRepeatMode } from './features/availability/utils'
import {
  buildBusyPayload,
  busyToForm,
  createEmptyBusyForm,
  getBusyIntervalId,
} from './features/busy/utils'
import { AuthScreen } from './features/auth/AuthScreen'
import { CalendarScreen } from './features/calendar/CalendarScreen'
import { AuthenticatedLayout } from './features/layout/AuthenticatedLayout'
import { ProfileScreen } from './features/profile/ProfileScreen'
import { SettingsScreen } from './features/settings/SettingsScreen'
import { TaskEditorForm } from './features/tasks/TaskEditorForm'
import { TasksScreen } from './features/tasks/TasksScreen'
import {
  buildProfilePayload,
  createCategoryTimePreferenceEntry,
  createDurationMultiplierEntry,
  createEmptyProfileForm,
  profileToForm,
} from './features/profile/utils'
import {
  buildTaskPayload,
  createEmptyTaskForm,
  createTaskWindowEntry,
  getTaskId,
  taskToForm,
} from './features/tasks/utils'
import { buildApiUrl, extractApiError } from './lib/api'
import {
  readStoredGenerationSettings,
  writeStoredGenerationSettings,
} from './lib/generationSettings'
import { readStoredSession, writeStoredSession } from './lib/session'

const SCHEDULE_FAILURE_REASON_KEYS = [
  'reason',
  'failure_reason',
  'failureReason',
  'error',
  'errors',
  'detail',
  'message',
  'msg',
  'description',
  'cause',
] as const

function extractFailureReasonValue(value: unknown, depth = 0): string | null {
  if (depth > 4 || value == null) {
    return null
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : null
  }

  if (Array.isArray(value)) {
    for (const entry of value) {
      const reason = extractFailureReasonValue(entry, depth + 1)
      if (reason) {
        return reason
      }
    }

    return null
  }

  if (typeof value !== 'object') {
    return null
  }

  const record = value as Record<string, unknown>

  for (const key of SCHEDULE_FAILURE_REASON_KEYS) {
    const reason = extractFailureReasonValue(record[key], depth + 1)
    if (reason) {
      return reason
    }
  }

  for (const nestedValue of Object.values(record)) {
    if (typeof nestedValue === 'object' && nestedValue != null) {
      const reason = extractFailureReasonValue(nestedValue, depth + 1)
      if (reason) {
        return reason
      }
    }
  }

  return null
}

function getScheduleFailureReason(schedule: Schedule) {
  return (
    extractFailureReasonValue(schedule.schedule_metadata) ??
    'Генерация расписания завершилась со статусом failed, но backend не вернул описание причины.'
  )
}

function App() {
  const [authMode, setAuthMode] = useState<AuthMode>('register')
  const [appScreen, setAppScreen] = useState<AppScreen>('calendar')
  const [session, setSession] = useState<Session | null>(() => readStoredSession())

  const [schedule, setSchedule] = useState<Schedule | null>(null)
  const [scheduleStatus, setScheduleStatus] = useState<ScheduleStatus>('idle')
  const [scheduleError, setScheduleError] = useState<string | null>(null)
  const [scheduleReloadKey, setScheduleReloadKey] = useState(0)
  const [scheduleFailureReason, setScheduleFailureReason] = useState<string | null>(
    null,
  )

  const [profileStatus, setProfileStatus] = useState<ProfileStatus>('idle')
  const [profileError, setProfileError] = useState<string | null>(null)
  const [profileReloadKey, setProfileReloadKey] = useState(0)
  const [profileForm, setProfileForm] = useState<ProfileForm>(() =>
    createEmptyProfileForm(),
  )
  const [settingsForm, setSettingsForm] = useState<GenerationSettingsForm>(() =>
    readStoredGenerationSettings(),
  )
  const [tasks, setTasks] = useState<UserTask[]>([])
  const [tasksStatus, setTasksStatus] = useState<TasksStatus>('idle')
  const [tasksError, setTasksError] = useState<string | null>(null)
  const [taskReloadKey, setTaskReloadKey] = useState(0)
  const [taskForm, setTaskForm] = useState<TaskForm>(() => createEmptyTaskForm())
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null)
  const [isQuickTaskModalOpen, setIsQuickTaskModalOpen] = useState(false)
  const [isAiTaskModalOpen, setIsAiTaskModalOpen] = useState(false)
  const [aiTaskText, setAiTaskText] = useState('')
  const [aiTaskError, setAiTaskError] = useState<string | null>(null)
  const [aiTaskSuccess, setAiTaskSuccess] = useState<string | null>(null)
  const [availabilityWindows, setAvailabilityWindows] = useState<AvailabilityWindow[]>([])
  const [busyIntervals, setBusyIntervals] = useState<BusyInterval[]>([])
  const [availabilityStatus, setAvailabilityStatus] =
    useState<AvailabilityStatus>('idle')
  const [availabilityError, setAvailabilityError] = useState<string | null>(null)
  const [availabilityReloadKey, setAvailabilityReloadKey] = useState(0)
  const [busyStatus, setBusyStatus] = useState<BusyStatus>('idle')
  const [busyError, setBusyError] = useState<string | null>(null)
  const [busyReloadKey, setBusyReloadKey] = useState(0)
  const [busyForm, setBusyForm] = useState<BusyForm>(() => createEmptyBusyForm())
  const [editingBusyId, setEditingBusyId] = useState<string | null>(null)

  const [registerForm, setRegisterForm] = useState<RegisterForm>({
    username: '',
    email: '',
    password: '',
  })
  const [loginForm, setLoginForm] = useState<LoginForm>({
    identifier: '',
    password: '',
  })

  const [calendarViewDays, setCalendarViewDays] = useState<CalendarViewDays>(3)
  const [calendarOffset, setCalendarOffset] = useState(0)

  const [authError, setAuthError] = useState<string | null>(null)
  const [isGeneratingSchedule, setIsGeneratingSchedule] = useState(false)
  const [scheduleActionLabel, setScheduleActionLabel] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRefreshingToken, setIsRefreshingToken] = useState(false)
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [isSavingSettings, setIsSavingSettings] = useState(false)
  const [isSavingTask, setIsSavingTask] = useState(false)
  const [isSubmittingAiTask, setIsSubmittingAiTask] = useState(false)
  const [isLoadingTaskDetails, setIsLoadingTaskDetails] = useState(false)
  const [isSavingAvailability, setIsSavingAvailability] = useState(false)
  const [isSavingBusy, setIsSavingBusy] = useState(false)
  const [isCompletingTaskId, setIsCompletingTaskId] = useState<string | null>(null)
  const [isDeletingTaskId, setIsDeletingTaskId] = useState<string | null>(null)
  const [isDeletingBusyId, setIsDeletingBusyId] = useState<string | null>(null)
  const [settingsError, setSettingsError] = useState<string | null>(null)

  const refreshPromiseRef = useRef<Promise<Session | null> | null>(null)
  const shownScheduleFailureRef = useRef<string | null>(null)

  const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  const browserLocale = navigator.language || 'ru-RU'
  const timeZone = browserTimeZone

  const applySession = useCallback((nextSession: Session | null) => {
    writeStoredSession(nextSession)
    setSession(nextSession)
  }, [])

  const clearClientSession = useCallback(
    (message: string | null = null) => {
      applySession(null)
      setAppScreen('calendar')
      setSchedule(null)
      setScheduleStatus('idle')
      setScheduleError(null)
      setScheduleFailureReason(null)
      shownScheduleFailureRef.current = null
      setTasks([])
      setTasksStatus('idle')
      setTasksError(null)
      setAvailabilityWindows([])
      setBusyIntervals([])
      setAvailabilityStatus('idle')
      setAvailabilityError(null)
      setBusyStatus('idle')
      setBusyError(null)
      setBusyForm(createEmptyBusyForm())
      setEditingBusyId(null)
      setTaskForm(createEmptyTaskForm())
      setEditingTaskId(null)
      setIsQuickTaskModalOpen(false)
      setIsAiTaskModalOpen(false)
      setAiTaskText('')
      setAiTaskError(null)
      setAiTaskSuccess(null)
      setIsSubmittingAiTask(false)
      setProfileStatus('idle')
      setProfileError(null)
      setProfileForm(createEmptyProfileForm())
      setSettingsError(null)
      setAuthError(message)
    },
    [applySession],
  )

  const setProfileField = useCallback(
    <K extends keyof ProfileForm>(field: K, value: ProfileForm[K]) => {
      setProfileForm((current) => ({
        ...current,
        [field]: value,
      }))
    },
    [],
  )

  const setTaskField = useCallback(
    <K extends keyof TaskForm>(field: K, value: TaskForm[K]) => {
      setTaskForm((current) => ({
        ...current,
        [field]: value,
      }))
    },
    [],
  )

  const setBusyField = useCallback(
    <K extends keyof BusyForm>(field: K, value: BusyForm[K]) => {
      setBusyForm((current) => ({
        ...current,
        [field]: value,
      }))
    },
    [],
  )

  const setTaskWindowField = useCallback(
    (
      collection: 'preferredWindows' | 'allowedWindows',
      entryId: string,
      field: keyof Omit<TaskWindowFormEntry, 'id'>,
      value: string,
    ) => {
      setTaskForm((current) => ({
        ...current,
        [collection]: current[collection].map((entry) =>
          entry.id === entryId ? { ...entry, [field]: value } : entry,
        ),
      }))
    },
    [],
  )

  const addTaskWindow = useCallback(
    (collection: 'preferredWindows' | 'allowedWindows') => {
      setTaskForm((current) => ({
        ...current,
        [collection]: [...current[collection], createTaskWindowEntry()],
      }))
    },
    [],
  )

  const removeTaskWindow = useCallback(
    (collection: 'preferredWindows' | 'allowedWindows', entryId: string) => {
      setTaskForm((current) => ({
        ...current,
        [collection]: current[collection].filter((entry) => entry.id !== entryId),
      }))
    },
    [],
  )

  const handleCategoryTimePreferenceChange = useCallback(
    (
      entryId: string,
      field: 'category' | 'morning' | 'afternoon' | 'evening' | 'night',
      value: string,
    ) => {
      setProfileForm((current) => ({
        ...current,
        categoryTimePreferences: current.categoryTimePreferences.map((entry) =>
          entry.id === entryId ? { ...entry, [field]: value } : entry,
        ),
      }))
    },
    [],
  )

  const handleDurationMultiplierChange = useCallback(
    (entryId: string, field: 'category' | 'multiplier', value: string) => {
      setProfileForm((current) => ({
        ...current,
        durationMultipliers: current.durationMultipliers.map((entry) =>
          entry.id === entryId ? { ...entry, [field]: value } : entry,
        ),
      }))
    },
    [],
  )

  const handleAddCategoryTimePreference = useCallback(() => {
    setProfileForm((current) => ({
      ...current,
      categoryTimePreferences: [
        ...current.categoryTimePreferences,
        createCategoryTimePreferenceEntry(),
      ],
    }))
  }, [])

  const handleAddDurationMultiplier = useCallback(() => {
    setProfileForm((current) => ({
      ...current,
      durationMultipliers: [
        ...current.durationMultipliers,
        createDurationMultiplierEntry(),
      ],
    }))
  }, [])

  const handleRemoveCategoryTimePreference = useCallback((entryId: string) => {
    setProfileForm((current) => ({
      ...current,
      categoryTimePreferences: current.categoryTimePreferences.filter(
        (entry) => entry.id !== entryId,
      ),
    }))
  }, [])

  const handleRemoveDurationMultiplier = useCallback((entryId: string) => {
    setProfileForm((current) => ({
      ...current,
      durationMultipliers: current.durationMultipliers.filter(
        (entry) => entry.id !== entryId,
      ),
    }))
  }, [])

  const setSettingsField = useCallback(
    <K extends keyof GenerationSettingsForm>(
      field: K,
      value: GenerationSettingsForm[K],
    ) => {
      setSettingsForm((current) => ({
        ...current,
        [field]: value,
      }))
    },
    [],
  )

  const parseNonNegativeInteger = useCallback((value: string, label: string) => {
    const parsed = Number(value)

    if (!Number.isFinite(parsed) || parsed < 0 || !Number.isInteger(parsed)) {
      throw new Error(`Поле "${label}" должно быть целым числом не меньше 0.`)
    }

    return parsed
  }, [])

  const buildScheduleGenerationRequest = useCallback((
    {
      useWarmStart,
      replanFromCurrentSchedule,
    }: {
      useWarmStart: boolean
      replanFromCurrentSchedule: boolean
    },
  ): StoredPlanningRunRequest => {
    const slotMinutes = 15
    const slotMs = slotMinutes * 60 * 1000
    const alignedStart = new Date(Math.ceil(Date.now() / slotMs) * slotMs)
    alignedStart.setUTCSeconds(0, 0)
    const minBreakMinutes = parseNonNegativeInteger(
      settingsForm.minBreakMinutes,
      'Минимальный перерыв между задачами',
    )
    const maxDailyPlannedMinutes = parseNonNegativeInteger(
      settingsForm.maxDailyPlannedMinutes,
      'Максимальное количество запланированных минут',
    )

    return {
      planning_start: alignedStart.toISOString(),
      planning_end: new Date(
        alignedStart.getTime() + 365 * 24 * 60 * 60 * 1000,
      ).toISOString(),
      slot_minutes: slotMinutes,
      task_statuses: ['active'],
      settings: {
        mode: 'full',
        min_break_minutes: minBreakMinutes,
        max_daily_planned_minutes: maxDailyPlannedMinutes,
        max_schedule_variants: 10,
        use_warm_start: useWarmStart,
        replan_from_current_schedule: replanFromCurrentSchedule,
      },
    }
  }, [parseNonNegativeInteger, settingsForm])

  const refreshAccessToken = useCallback(
    (currentSession: Session) => {
      if (refreshPromiseRef.current) {
        return refreshPromiseRef.current
      }

      setIsRefreshingToken(true)

      const refreshPromise = (async () => {
        const response = await fetch(buildApiUrl('/api/auth/refresh'), {
          method: 'POST',
          credentials: 'include',
        })

        if (response.status === 401) {
          return null
        }

        if (!response.ok) {
          throw new Error(await extractApiError(response))
        }

        const payload = (await response.json()) as Session
        const nextSession: Session = {
          ...currentSession,
          ...payload,
          user: payload.user ?? currentSession.user,
        }

        applySession(nextSession)
        return nextSession
      })()

      refreshPromiseRef.current = refreshPromise

      void refreshPromise.finally(() => {
        refreshPromiseRef.current = null
        setIsRefreshingToken(false)
      })

      return refreshPromise
    },
    [applySession],
  )

  const handleAccessTokenRefresh = useCallback(
    async (silent = false) => {
      if (!session) {
        return
      }

      try {
        const nextSession = await refreshAccessToken(session)

        if (!nextSession) {
          clearClientSession('Сессия истекла. Войдите заново.')
          return
        }

        if (!silent) {
          setScheduleError(null)
          setProfileError(null)
        }
      } catch (error: unknown) {
        if (!silent) {
          const message =
            error instanceof Error
              ? error.message
              : 'Не удалось обновить access token.'
          setScheduleError(message)
          setProfileError(message)
        }
      }
    },
    [clearClientSession, refreshAccessToken, session],
  )

  const fetchWithAuth = useCallback(
    async (currentSession: Session, path: string, init: RequestInit = {}) => {
      const sendRequest = (accessToken: string) => {
        const headers = new Headers(init.headers)
        headers.set('Authorization', `Bearer ${accessToken}`)

        return fetch(buildApiUrl(path), {
          ...init,
          headers,
        })
      }

      let response = await sendRequest(currentSession.access_token)
      if (response.status !== 401) {
        return { response, nextSession: currentSession }
      }

      const refreshedSession = await refreshAccessToken(currentSession)
      if (!refreshedSession) {
        return { response, nextSession: null }
      }

      response = await sendRequest(refreshedSession.access_token)
      if (response.status === 401) {
        return { response, nextSession: null }
      }

      return { response, nextSession: refreshedSession }
    },
    [refreshAccessToken],
  )

  useEffect(() => {
    if (!session) {
      return
    }

    const controller = new AbortController()

    const loadCurrentSchedule = async () => {
      setScheduleStatus('loading')
      setScheduleError(null)
      setAuthError(null)

      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/schedules/current`,
        {
          signal: controller.signal,
        },
      )

      if (controller.signal.aborted) {
        return
      }

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (response.status === 404) {
        setSchedule(null)
        setScheduleStatus('empty')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as Schedule
      setSchedule(payload)
      setScheduleStatus('ready')
      setCalendarOffset(0)
    }

    void loadCurrentSchedule().catch((error: unknown) => {
      if (controller.signal.aborted) {
        return
      }

      setSchedule(null)
      setScheduleStatus('error')
      setScheduleError(
        error instanceof Error ? error.message : 'Не удалось загрузить расписание.',
      )
    })

    return () => controller.abort()
  }, [clearClientSession, fetchWithAuth, scheduleReloadKey, session])

  useEffect(() => {
    if (!session || appScreen !== 'profile') {
      return
    }

    const controller = new AbortController()

    const loadProfile = async () => {
      setProfileStatus('loading')
      setProfileError(null)
      setAuthError(null)

      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/profile`,
        {
          signal: controller.signal,
        },
      )

      if (controller.signal.aborted) {
        return
      }

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (response.status === 404) {
        setProfileForm(createEmptyProfileForm())
        setProfileStatus('empty')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as UserProfile
      setProfileForm(profileToForm(payload))
      setProfileStatus('ready')
    }

    void loadProfile().catch((error: unknown) => {
      if (controller.signal.aborted) {
        return
      }

      setProfileStatus('error')
      setProfileError(
        error instanceof Error ? error.message : 'Не удалось загрузить профиль.',
      )
    })

    return () => controller.abort()
  }, [appScreen, clearClientSession, fetchWithAuth, profileReloadKey, session])

  useEffect(() => {
    if (!session || (appScreen !== 'tasks' && appScreen !== 'calendar')) {
      return
    }

    const controller = new AbortController()

    const loadTasks = async () => {
      setTasksStatus('loading')
      setTasksError(null)
      setAuthError(null)

      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/tasks`,
        {
          signal: controller.signal,
        },
      )

      if (controller.signal.aborted) {
        return
      }

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as UserTask[]
      setTasks(payload)
      setTasksStatus(payload.length > 0 ? 'ready' : 'empty')
    }

    void loadTasks().catch((error: unknown) => {
      if (controller.signal.aborted) {
        return
      }

      setTasks([])
      setTasksStatus('error')
      setTasksError(error instanceof Error ? error.message : 'Не удалось загрузить задачи.')
    })

    return () => controller.abort()
  }, [appScreen, clearClientSession, fetchWithAuth, session, taskReloadKey])

  useEffect(() => {
    if (!session || (appScreen !== 'availability' && appScreen !== 'calendar')) {
      return
    }

    const controller = new AbortController()

    const loadAvailabilityWindows = async () => {
      setAvailabilityStatus('loading')
      setAvailabilityError(null)
      setAuthError(null)

      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/availability-windows`,
        {
          signal: controller.signal,
        },
      )

      if (controller.signal.aborted) {
        return
      }

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as AvailabilityWindow[]
      setAvailabilityWindows(payload)
      setAvailabilityStatus(payload.length > 0 ? 'ready' : 'empty')
    }

    void loadAvailabilityWindows().catch((error: unknown) => {
      if (controller.signal.aborted) {
        return
      }

      setAvailabilityWindows([])
      setAvailabilityStatus('error')
      setAvailabilityError(
        error instanceof Error
          ? error.message
          : 'Не удалось загрузить доступные окна.',
      )
    })

    return () => controller.abort()
  }, [appScreen, availabilityReloadKey, clearClientSession, fetchWithAuth, session])

  useEffect(() => {
    if (!session || (appScreen !== 'calendar' && appScreen !== 'busy')) {
      return
    }

    const controller = new AbortController()
    const shouldTrackBusyState = appScreen === 'busy'

    const loadBusyIntervals = async () => {
      if (shouldTrackBusyState) {
        setBusyStatus('loading')
        setBusyError(null)
        setAuthError(null)
      }

      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/busy-intervals`,
        {
          signal: controller.signal,
        },
      )

      if (controller.signal.aborted) {
        return
      }

      if (!nextSession) {
        clearClientSession('РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’РѕР№РґРёС‚Рµ Р·Р°РЅРѕРІРѕ.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as BusyInterval[]
      setBusyIntervals(payload)
      if (shouldTrackBusyState) {
        setBusyStatus(payload.length > 0 ? 'ready' : 'empty')
      }
    }

    void loadBusyIntervals().catch((error: unknown) => {
      if (controller.signal.aborted) {
        return
      }

      setBusyIntervals([])
      if (shouldTrackBusyState) {
        setBusyStatus('error')
        setBusyError(
          error instanceof Error
            ? error.message
            : 'Не удалось загрузить занятые окна.',
        )
      }
    })

    return () => controller.abort()
  }, [appScreen, busyReloadKey, clearClientSession, fetchWithAuth, session])

  async function handleRegisterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    setAuthError(null)

    try {
      const response = await fetch(buildApiUrl('/api/auth/register'), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...registerForm,
          username: registerForm.username.trim().toLowerCase(),
          email: registerForm.email.trim(),
          timezone: browserTimeZone,
          locale: browserLocale,
        }),
      })

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as Session
      applySession(payload)
      setAppScreen('calendar')
      setSchedule(null)
      setScheduleStatus('idle')
      setScheduleError(null)
      setProfileStatus('idle')
      setProfileError(null)
      setCalendarOffset(0)
    } catch (error: unknown) {
      setAuthError(
        error instanceof Error ? error.message : 'Не удалось зарегистрироваться.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    setAuthError(null)

    try {
      const response = await fetch(buildApiUrl('/api/auth/login'), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          identifier: loginForm.identifier.trim(),
          password: loginForm.password,
        }),
      })

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as Session
      applySession(payload)
      setAppScreen('calendar')
      setSchedule(null)
      setScheduleStatus('idle')
      setScheduleError(null)
      setProfileStatus('idle')
      setProfileError(null)
      setCalendarOffset(0)
    } catch (error: unknown) {
      setAuthError(error instanceof Error ? error.message : 'Не удалось войти.')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleLogout() {
    const accessToken = session?.access_token

    try {
      await fetch(buildApiUrl('/api/auth/logout'), {
        method: 'POST',
        credentials: 'include',
        headers: accessToken
          ? {
              Authorization: `Bearer ${accessToken}`,
            }
          : undefined,
      })
    } catch {
      // Local cleanup should still happen even if backend logout fails.
    } finally {
      clearClientSession()
    }
  }

  async function handleCreateDefaultProfile() {
    if (!session) {
      return
    }

    setProfileError(null)
    setProfileStatus('loading')

    try {
      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/profile/default`,
        {
          method: 'POST',
        },
      )

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      setProfileReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setProfileStatus('error')
      setProfileError(
        error instanceof Error
          ? error.message
          : 'Не удалось создать профиль по умолчанию.',
      )
    }
  }

  async function handleSaveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!session) {
      return
    }

    setIsSavingProfile(true)
    setProfileError(null)

    try {
      const payload = buildProfilePayload(session.user.id, profileForm)
      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/profile`,
        {
          method: 'PUT',
          body: JSON.stringify(payload),
        },
      )

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      let savedProfile = payload
      const responseType = response.headers.get('content-type') ?? ''
      if (responseType.includes('application/json')) {
        savedProfile = (await response.json()) as UserProfile
      }

      setProfileForm(profileToForm(savedProfile))
      setProfileStatus('ready')
    } catch (error: unknown) {
      setProfileStatus('error')
      setProfileError(
        error instanceof Error ? error.message : 'Не удалось сохранить профиль.',
      )
    } finally {
      setIsSavingProfile(false)
    }
  }

  function applyBestSchedulePreview(
    currentSession: Session,
    planningRequest: StoredPlanningRunRequest,
    result: BestScheduleResponse,
  ) {
    const now = new Date().toISOString()

    setSchedule({
      id: `preview-${now}`,
      user_id: currentSession.user.id,
      planning_start: planningRequest.planning_start,
      planning_end: planningRequest.planning_end,
      slot_minutes: planningRequest.slot_minutes,
      status: 'success',
      is_current: true,
      selected_variant_id: result.variant_id,
      source_request: planningRequest,
      profile_context: null,
      schedule_metadata: {
        source: 'best-schedule-preview',
      },
      created_at: now,
      updated_at: now,
      scheduled_tasks: result.scheduled_tasks,
    })
    setScheduleStatus('ready')
    setCalendarOffset(0)
  }

  async function runBestSchedule(
    currentSession: Session,
    planningRequest: StoredPlanningRunRequest,
  ) {
    const { response, nextSession } = await fetchWithAuth(
      currentSession,
      `/api/users/${currentSession.user.id}/best-schedule-from-stored-data`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(planningRequest),
      },
    )

    if (!nextSession) {
      clearClientSession('Сессия истекла. Войдите заново.')
      return null
    }

    if (!response.ok) {
      throw new Error(await extractApiError(response))
    }

    const payload = (await response.json()) as BestScheduleResponse
    applyBestSchedulePreview(nextSession, planningRequest, payload)
    return nextSession
  }

  async function runScheduleAction({
    label,
    useWarmStart,
    replanFromCurrentSchedule,
  }: {
    label: string
    useWarmStart: boolean
    replanFromCurrentSchedule: boolean
  }) {
    if (!session) {
      return
    }

    setIsGeneratingSchedule(true)
    setScheduleActionLabel(label)
    setScheduleError(null)
    setSettingsError(null)
    setAuthError(null)

    try {
      const fullRequest = buildScheduleGenerationRequest({
        useWarmStart,
        replanFromCurrentSchedule,
      })
      const nextSession = await runBestSchedule(session, fullRequest)
      if (!nextSession) {
        return
      }
      setScheduleReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setScheduleStatus('error')
      setScheduleError(
        error instanceof Error
          ? error.message
          : 'Не удалось сгенерировать расписание.',
      )
    } finally {
      setIsGeneratingSchedule(false)
      setScheduleActionLabel(null)
    }
  }

  async function handleGenerateSchedule() {
    await runScheduleAction({
      label: 'Генерируем расписание...',
      useWarmStart: false,
      replanFromCurrentSchedule: false,
    })
  }

  async function handleRefreshSchedule() {
    await runScheduleAction({
      label: 'Обновляем расписание...',
      useWarmStart: true,
      replanFromCurrentSchedule: false,
    })
  }

  async function handleExtendSchedule() {
    await runScheduleAction({
      label: 'Дополняем расписание...',
      useWarmStart: false,
      replanFromCurrentSchedule: true,
    })
  }

      

  async function handleSaveTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!session) {
      return
    }

    setIsSavingTask(true)
    setTasksError(null)

    try {
      const payload = buildTaskPayload(taskForm, timeZone)
      const path = editingTaskId
        ? `/api/users/${session.user.id}/tasks/${editingTaskId}`
        : `/api/users/${session.user.id}/tasks`
      const method = editingTaskId ? 'PATCH' : 'POST'

      const { response, nextSession } = await fetchWithAuth(session, path, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      setTaskForm(createEmptyTaskForm())
      setEditingTaskId(null)
      setIsQuickTaskModalOpen(false)
      setTaskReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setTasksError(error instanceof Error ? error.message : 'Не удалось сохранить задачу.')
    } finally {
      setIsSavingTask(false)
    }
  }

  async function handleSubmitAiTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!session) {
      return
    }

    const text = aiTaskText.trim()

    if (!text) {
      setAiTaskError('Введите текст задачи перед отправкой.')
      setAiTaskSuccess(null)
      return
    }

    setIsSubmittingAiTask(true)
    setAiTaskError(null)
    setAiTaskSuccess(null)

    try {
      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/ai-task-drafts`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ text }),
        },
      )

      if (!nextSession) {
        clearClientSession('РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’РѕР№РґРёС‚Рµ Р·Р°РЅРѕРІРѕ.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      setAiTaskText('')
      setAiTaskSuccess('Текст задачи отправлен на сервер.')
    } catch (error: unknown) {
      setAiTaskError(
        error instanceof Error ? error.message : 'Не удалось отправить задачу через ИИ.',
      )
    } finally {
      setIsSubmittingAiTask(false)
    }
  }

  async function handleDeleteTask(taskId: string) {
    if (!session || !taskId) {
      return
    }

    setIsDeletingTaskId(taskId)
    setTasksError(null)

    try {
      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/tasks/${taskId}`,
        {
          method: 'DELETE',
        },
      )

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      if (editingTaskId === taskId) {
        setTaskForm(createEmptyTaskForm())
        setEditingTaskId(null)
      }

      setTaskReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setTasksError(error instanceof Error ? error.message : 'Не удалось удалить задачу.')
    } finally {
      setIsDeletingTaskId(null)
    }
  }

  const syncTaskStatusLocally = useCallback(
    (taskId: string, status: UserTask['status']) => {
      setTasks((current) =>
        current.map((task) => (getTaskId(task) === taskId ? { ...task, status } : task)),
      )
      setSchedule((current) =>
        current
          ? {
              ...current,
              scheduled_tasks: current.scheduled_tasks.map((task) =>
                task.task_id === taskId ? { ...task, status } : task,
              ),
            }
          : current,
      )

      if (editingTaskId === taskId) {
        setTaskForm((current) => ({
          ...current,
          status,
        }))
      }
    },
    [editingTaskId],
  )

  const handleCompleteTask = useCallback(
    async (taskId: string) => {
      if (!session || !taskId) {
        return
      }

      setIsCompletingTaskId(taskId)
      setTasksError(null)

      try {
        const { response, nextSession } = await fetchWithAuth(
          session,
          `/api/users/${session.user.id}/tasks/${taskId}`,
          {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              status: 'completed',
            }),
          },
        )

        if (!nextSession) {
          clearClientSession('РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’РѕР№РґРёС‚Рµ Р·Р°РЅРѕРІРѕ.')
          return
        }

        if (!response.ok) {
          throw new Error(await extractApiError(response))
        }

        syncTaskStatusLocally(taskId, 'completed')
        setTaskReloadKey((value) => value + 1)
      } catch (error: unknown) {
        setTasksError(
          error instanceof Error
            ? error.message
            : 'РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РјРµС‚РёС‚СЊ Р·Р°РґР°С‡Сѓ РєР°Рє РІС‹РїРѕР»РЅРµРЅРЅСѓСЋ.',
        )
      } finally {
        setIsCompletingTaskId(null)
      }
    },
    [clearClientSession, fetchWithAuth, session, syncTaskStatusLocally],
  )

  async function handleSaveAvailability(
    weekStartStamp: number,
    cells: Set<string>,
    repeatMode: AvailabilityRepeatMode,
    repeatEveryWeeks: number,
  ) {
    if (!session) {
      return
    }

    setIsSavingAvailability(true)
    setAvailabilityError(null)

    try {
      let activeSession: Session | null = session
      const windowsToDelete = availabilityWindows.filter((window) =>
        windowTouchesWeek(window, weekStartStamp, timeZone),
      )

      for (const window of windowsToDelete) {
        const windowId = getAvailabilityWindowId(window)
        if (!windowId || !activeSession) {
          continue
        }

        const { response, nextSession } = await fetchWithAuth(
          activeSession,
          `/api/users/${activeSession.user.id}/availability-windows/${windowId}`,
          {
            method: 'DELETE',
          },
        )

        if (!nextSession) {
          clearClientSession('Сессия истекла. Войдите заново.')
          return
        }

        activeSession = nextSession

        if (!response.ok) {
          throw new Error(await extractApiError(response))
        }
      }

      const payloads = buildAvailabilityPayloads(
        cells,
        weekStartStamp,
        timeZone,
        repeatMode,
        repeatEveryWeeks,
      )

      for (const payload of payloads) {
        if (!activeSession) {
          break
        }

        const { response, nextSession } = await fetchWithAuth(
          activeSession,
          `/api/users/${activeSession.user.id}/availability-windows`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          },
        )

        if (!nextSession) {
          clearClientSession('Сессия истекла. Войдите заново.')
          return
        }

        activeSession = nextSession

        if (!response.ok) {
          throw new Error(await extractApiError(response))
        }
      }

      setAvailabilityReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setAvailabilityStatus('error')
      setAvailabilityError(
        error instanceof Error
          ? error.message
          : 'Не удалось сохранить доступные окна.',
      )
      throw error
    } finally {
      setIsSavingAvailability(false)
    }
  }

  async function handleSaveBusy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!session) {
      return
    }

    setIsSavingBusy(true)
    setBusyError(null)

    try {
      const payload = buildBusyPayload(busyForm, timeZone)
      const path = editingBusyId
        ? `/api/users/${session.user.id}/busy-intervals/${editingBusyId}`
        : `/api/users/${session.user.id}/busy-intervals`
      const method = editingBusyId ? 'PATCH' : 'POST'

      const { response, nextSession } = await fetchWithAuth(session, path, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      setBusyForm(createEmptyBusyForm())
      setEditingBusyId(null)
      setBusyReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setBusyStatus('error')
      setBusyError(
        error instanceof Error ? error.message : 'Не удалось сохранить занятые окна.',
      )
      throw error
    } finally {
      setIsSavingBusy(false)
    }
  }

  async function handleSaveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSavingSettings(true)
    setSettingsError(null)

    try {
      const sanitizedSettings: GenerationSettingsForm = {
        minBreakMinutes: String(
          parseNonNegativeInteger(
            settingsForm.minBreakMinutes,
            'Минимальный перерыв между задачами',
          ),
        ),
        maxDailyPlannedMinutes: String(
          parseNonNegativeInteger(
            settingsForm.maxDailyPlannedMinutes,
            'Максимальное количество запланированных минут',
          ),
        ),
      }

      writeStoredGenerationSettings(sanitizedSettings)
      setSettingsForm(sanitizedSettings)
    } catch (error: unknown) {
      setSettingsError(
        error instanceof Error ? error.message : 'Не удалось сохранить настройки.',
      )
    } finally {
      setIsSavingSettings(false)
    }
  }

  const handleAuthModeChange = useCallback((mode: AuthMode) => {
    setAuthMode(mode)
    setAuthError(null)
  }, [])

  const handleRegisterFormChange = useCallback(
    (field: keyof RegisterForm, value: string) => {
      setRegisterForm((current) => ({
        ...current,
        [field]: value,
      }))
    },
    [],
  )

  const handleLoginFormChange = useCallback((field: keyof LoginForm, value: string) => {
    setLoginForm((current) => ({
      ...current,
      [field]: value,
    }))
  }, [])

  const handleOpenCalendar = useCallback(() => {
    setAppScreen('calendar')
  }, [])

  const handleOpenProfile = useCallback(() => {
    setAppScreen('profile')
    setProfileReloadKey((value) => value + 1)
  }, [])

  const handleOpenAvailability = useCallback(() => {
    setAppScreen('availability')
    setAvailabilityError(null)
    setAvailabilityReloadKey((value) => value + 1)
  }, [])

  const handleOpenBusy = useCallback(() => {
    setAppScreen('busy')
    setBusyError(null)
    setBusyForm(createEmptyBusyForm())
    setEditingBusyId(null)
    setBusyReloadKey((value) => value + 1)
  }, [])

  const handleResetBusyForm = useCallback(() => {
    setBusyForm(createEmptyBusyForm())
    setEditingBusyId(null)
    setBusyError(null)
  }, [])

  const handleEditBusy = useCallback((interval: BusyInterval) => {
    const intervalId = getBusyIntervalId(interval)
    setEditingBusyId(intervalId)
    setBusyForm(busyToForm(interval, timeZone))
    setBusyError(null)
  }, [timeZone])

  const handleDeleteBusy = useCallback(async (intervalId: string) => {
    if (!session || !intervalId) {
      return
    }

    setIsDeletingBusyId(intervalId)
    setBusyError(null)

    try {
      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/busy-intervals/${intervalId}`,
        {
          method: 'DELETE',
        },
      )

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      if (editingBusyId === intervalId) {
        setBusyForm(createEmptyBusyForm())
        setEditingBusyId(null)
      }

      setBusyReloadKey((value) => value + 1)
    } catch (error: unknown) {
      setBusyError(
        error instanceof Error ? error.message : 'Не удалось удалить занятый интервал.',
      )
    } finally {
      setIsDeletingBusyId(null)
    }
  }, [clearClientSession, editingBusyId, fetchWithAuth, session])

  const handleOpenTasks = useCallback(() => {
    setAppScreen('tasks')
    setTasksError(null)
    setTaskReloadKey((value) => value + 1)
  }, [])

  const handleOpenSettings = useCallback(() => {
    setAppScreen('settings')
    setSettingsError(null)
  }, [])

  const handleResetTaskForm = useCallback(() => {
    setTaskForm(createEmptyTaskForm())
    setEditingTaskId(null)
    setTasksError(null)
  }, [])

  const handleOpenQuickTaskModal = useCallback(() => {
    setTaskForm(createEmptyTaskForm())
    setEditingTaskId(null)
    setTasksError(null)
    setIsLoadingTaskDetails(false)
    setIsQuickTaskModalOpen(true)
  }, [])

  const handleCloseQuickTaskModal = useCallback(() => {
    setIsQuickTaskModalOpen(false)
    setTaskForm(createEmptyTaskForm())
    setEditingTaskId(null)
    setIsLoadingTaskDetails(false)
  }, [])

  const handleOpenAiTaskModal = useCallback(() => {
    setAiTaskText('')
    setAiTaskError(null)
    setAiTaskSuccess(null)
    setIsAiTaskModalOpen(true)
  }, [])

  const handleCloseAiTaskModal = useCallback(() => {
    setIsAiTaskModalOpen(false)
    setAiTaskText('')
    setAiTaskError(null)
    setAiTaskSuccess(null)
    setIsSubmittingAiTask(false)
  }, [])

  const handleCloseScheduleFailureModal = useCallback(() => {
    setScheduleFailureReason(null)
  }, [])

  const handleEditTask = useCallback((task: UserTask) => {
    const taskId = getTaskId(task)
    setEditingTaskId(taskId)
    setTaskForm(taskToForm(task, timeZone))
    setTasksError(null)
  }, [timeZone])

  const handleOpenScheduledTask = useCallback(async (taskId: string) => {
    if (!session || !taskId) {
      return
    }

    setTaskForm(createEmptyTaskForm())
    setEditingTaskId(null)
    setTasksError(null)
    setIsLoadingTaskDetails(true)
    setIsQuickTaskModalOpen(true)

    try {
      const { response, nextSession } = await fetchWithAuth(
        session,
        `/api/users/${session.user.id}/tasks/${taskId}`,
      )

      if (!nextSession) {
        clearClientSession('Сессия истекла. Войдите заново.')
        return
      }

      if (!response.ok) {
        throw new Error(await extractApiError(response))
      }

      const payload = (await response.json()) as UserTask
      setEditingTaskId(getTaskId(payload) || taskId)
      setTaskForm(taskToForm(payload, timeZone))
      setTasksError(null)
    } catch (error: unknown) {
      setTaskForm(createEmptyTaskForm())
      setEditingTaskId(null)
      setTasksError(
        error instanceof Error
          ? error.message
          : 'Не удалось загрузить данные задачи.',
      )
    } finally {
      setIsLoadingTaskDetails(false)
    }
  }, [clearClientSession, fetchWithAuth, session, timeZone])

  const handleCalendarViewChange = useCallback((view: CalendarViewDays) => {
    setCalendarViewDays(view)
    setCalendarOffset(0)
  }, [])

  const taskStatusesById: Record<string, UserTask['status']> = {}

  tasks.forEach((task) => {
    const taskId = getTaskId(task)
    if (taskId) {
      taskStatusesById[taskId] = task.status
    }
  })

  useEffect(() => {
    if (!schedule || scheduleStatus !== 'ready' || schedule.status !== 'failed') {
      return
    }

    const failureKey = `${schedule.id}:${schedule.updated_at}`

    if (shownScheduleFailureRef.current === failureKey) {
      return
    }

    shownScheduleFailureRef.current = failureKey
    setScheduleFailureReason(getScheduleFailureReason(schedule))
  }, [schedule, scheduleStatus])

  if (!session) {
    return (
      <main className="app-shell">
        <AuthScreen
          authMode={authMode}
          authError={authError}
          isSubmitting={isSubmitting}
          loginForm={loginForm}
          registerForm={registerForm}
          onAuthModeChange={handleAuthModeChange}
          onLoginFormChange={handleLoginFormChange}
          onLoginSubmit={handleLoginSubmit}
          onRegisterFormChange={handleRegisterFormChange}
          onRegisterSubmit={handleRegisterSubmit}
        />
      </main>
    )
  }

  return (
    <main className="app-shell">
      <AuthenticatedLayout
        appScreen={appScreen}
        isGeneratingSchedule={isGeneratingSchedule}
        isRefreshingToken={isRefreshingToken}
        scheduleActionLabel={scheduleActionLabel}
        session={session}
        onExtendSchedule={handleExtendSchedule}
        onGenerateSchedule={handleGenerateSchedule}
        onOpenAvailability={handleOpenAvailability}
        onOpenBusy={handleOpenBusy}
        onLogout={handleLogout}
        onOpenCalendar={handleOpenCalendar}
        onOpenProfile={handleOpenProfile}
        onOpenSettings={handleOpenSettings}
        onOpenTasks={handleOpenTasks}
        onRefreshSchedule={handleRefreshSchedule}
        onRefreshToken={() => handleAccessTokenRefresh()}
      >
        {appScreen === 'calendar' ? (
          <CalendarScreen
            availabilityWindows={availabilityWindows}
            busyIntervals={busyIntervals}
            calendarOffset={calendarOffset}
            calendarViewDays={calendarViewDays}
            isCompletingTaskId={isCompletingTaskId}
            onCompleteTask={handleCompleteTask}
            onOpenAiTaskModal={handleOpenAiTaskModal}
            onOpenQuickCreateTask={handleOpenQuickTaskModal}
            onOpenScheduledTask={handleOpenScheduledTask}
            schedule={schedule}
            scheduleError={scheduleError}
            scheduleStatus={scheduleStatus}
            taskStatusesById={taskStatusesById}
            timeZone={timeZone}
            username={session.user.username}
            onCalendarOffsetChange={setCalendarOffset}
            onCalendarViewChange={handleCalendarViewChange}
          />
        ) : appScreen === 'settings' ? (
          <SettingsScreen
            isSavingSettings={isSavingSettings}
            settingsError={settingsError}
            settingsForm={settingsForm}
            onBackToCalendar={handleOpenCalendar}
            onSaveSettings={handleSaveSettings}
            onSettingsFieldChange={setSettingsField}
          />
        ) : appScreen === 'availability' ? (
          <AvailabilityScreen
            availabilityError={availabilityError}
            availabilityStatus={availabilityStatus}
            availabilityWindows={availabilityWindows}
            isSavingAvailability={isSavingAvailability}
            timeZone={timeZone}
            onSaveAvailability={handleSaveAvailability}
          />
        ) : appScreen === 'busy' ? (
          <BusyScreen
            busyError={busyError}
            busyForm={busyForm}
            busyIntervals={busyIntervals}
            busyStatus={busyStatus}
            editingBusyId={editingBusyId}
            isDeletingBusyId={isDeletingBusyId}
            isSavingBusy={isSavingBusy}
            timeZone={timeZone}
            onBackToCalendar={handleOpenCalendar}
            onBusyFieldChange={setBusyField}
            onDeleteBusy={handleDeleteBusy}
            onEditBusy={handleEditBusy}
            onResetBusyForm={handleResetBusyForm}
            onSaveBusy={handleSaveBusy}
          />
        ) : appScreen === 'tasks' ? (
          <TasksScreen
            editingTaskId={editingTaskId}
            isCompletingTaskId={isCompletingTaskId}
            isDeletingTaskId={isDeletingTaskId}
            isSavingTask={isSavingTask}
            taskForm={taskForm}
            tasks={tasks}
            tasksError={tasksError}
            tasksStatus={tasksStatus}
            timeZone={timeZone}
            onAddAllowedWindow={() => addTaskWindow('allowedWindows')}
            onAddPreferredWindow={() => addTaskWindow('preferredWindows')}
            onBackToCalendar={handleOpenCalendar}
            onOpenAiTaskModal={handleOpenAiTaskModal}
            onCompleteTask={handleCompleteTask}
            onDeleteTask={handleDeleteTask}
            onEditTask={handleEditTask}
            onResetTaskForm={handleResetTaskForm}
            onRemoveAllowedWindow={(entryId) =>
              removeTaskWindow('allowedWindows', entryId)
            }
            onRemovePreferredWindow={(entryId) =>
              removeTaskWindow('preferredWindows', entryId)
            }
            onSaveTask={handleSaveTask}
            onTaskFieldChange={setTaskField}
            onTaskWindowChange={setTaskWindowField}
          />
        ) : (
          <ProfileScreen
            isSavingProfile={isSavingProfile}
            localTimeZone={timeZone}
            onAddCategoryTimePreference={handleAddCategoryTimePreference}
            onAddDurationMultiplier={handleAddDurationMultiplier}
            onCategoryTimePreferenceChange={handleCategoryTimePreferenceChange}
            onDurationMultiplierChange={handleDurationMultiplierChange}
            profileError={profileError}
            profileForm={profileForm}
            profileStatus={profileStatus}
            session={session}
            onBackToCalendar={handleOpenCalendar}
            onCreateDefaultProfile={handleCreateDefaultProfile}
            onProfileFieldChange={setProfileField}
            onRemoveCategoryTimePreference={handleRemoveCategoryTimePreference}
            onRemoveDurationMultiplier={handleRemoveDurationMultiplier}
            onSaveProfile={handleSaveProfile}
          />
        )}
      </AuthenticatedLayout>

      {appScreen === 'calendar' && isQuickTaskModalOpen ? (
        <div
          className="modal-overlay"
          role="presentation"
          onClick={handleCloseQuickTaskModal}
        >
          <section
            className="modal-dialog task-modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="quick-task-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="tasks-panel-header">
              <div>
                <span className="eyebrow">Quick Task</span>
                <h3 id="quick-task-modal-title">
                  {editingTaskId ? 'Редактировать задачу' : 'Создать задачу'}
                </h3>
              </div>
              <button
                type="button"
                className="ghost-button"
                onClick={handleCloseQuickTaskModal}
              >
                Закрыть
              </button>
            </div>

            <div className="task-modal-scroll">
              {tasksError ? <p className="form-error">{tasksError}</p> : null}

              {isLoadingTaskDetails ? (
                <div className="schedule-empty">
                  <p>Загружаю данные задачи...</p>
                </div>
              ) : (
                <TaskEditorForm
                  editingTaskId={editingTaskId}
                  isSavingTask={isSavingTask}
                  secondaryActionLabel="Закрыть"
                  taskForm={taskForm}
                  onAddAllowedWindow={() => addTaskWindow('allowedWindows')}
                  onAddPreferredWindow={() => addTaskWindow('preferredWindows')}
                  onRemoveAllowedWindow={(entryId) =>
                    removeTaskWindow('allowedWindows', entryId)
                  }
                  onRemovePreferredWindow={(entryId) =>
                    removeTaskWindow('preferredWindows', entryId)
                  }
                  onSaveTask={handleSaveTask}
                  onSecondaryAction={handleCloseQuickTaskModal}
                  onTaskFieldChange={setTaskField}
                  onTaskWindowChange={setTaskWindowField}
                />
              )}
            </div>
          </section>
        </div>
      ) : null}

      {isAiTaskModalOpen ? (
        <div
          className="modal-overlay"
          role="presentation"
          onClick={handleCloseAiTaskModal}
        >
          <section
            className="modal-dialog ai-task-modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-task-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="tasks-panel-header">
              <div>
                <span className="eyebrow">ИИ-помощник</span>
                <h3 id="ai-task-modal-title">Добавить задачу через ИИ</h3>
              </div>
              <button
                type="button"
                className="ghost-button"
                onClick={handleCloseAiTaskModal}
              >
                Закрыть
              </button>
            </div>

            <form className="ai-task-modal-form" onSubmit={handleSubmitAiTask}>
              <p className="modal-message">
                Опишите задачу в свободной форме. Фронтенд отправит текст на сервер как
                есть.
              </p>

              <label className="task-full-width-field ai-task-field">
                <span>Текст задачи</span>
                <textarea
                  rows={7}
                  value={aiTaskText}
                  onChange={(event) => {
                    setAiTaskText(event.target.value)
                    if (aiTaskError) {
                      setAiTaskError(null)
                    }
                    if (aiTaskSuccess) {
                      setAiTaskSuccess(null)
                    }
                  }}
                  placeholder="Подготовить текст для прайсинга, поправить onboarding-письмо, созвониться с Машей по документам подрядчика..."
                />
              </label>

              {aiTaskError ? <p className="form-error">{aiTaskError}</p> : null}
              {aiTaskSuccess ? <p className="ai-task-success">{aiTaskSuccess}</p> : null}

              <div className="ai-task-submit-row">
                <button
                  type="button"
                  className="ghost-button"
                  onClick={handleCloseAiTaskModal}
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="ai-task-submit-button"
                  disabled={isSubmittingAiTask}
                >
                  {isSubmittingAiTask ? 'Отправка...' : 'Отправить'}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {scheduleFailureReason ? (
        <div
          className="modal-overlay"
          role="presentation"
          onClick={handleCloseScheduleFailureModal}
        >
          <section
            className="modal-dialog info-modal-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="schedule-failure-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="tasks-panel-header">
              <div>
                <span className="eyebrow">Schedule failed</span>
                <h3 id="schedule-failure-modal-title">
                  Генерация расписания завершилась с ошибкой
                </h3>
              </div>
              <button
                type="button"
                className="ghost-button"
                onClick={handleCloseScheduleFailureModal}
              >
                Закрыть
              </button>
            </div>

            <p className="modal-message">{scheduleFailureReason}</p>
          </section>
        </div>
      ) : null}
    </main>
  )
}

export default App
