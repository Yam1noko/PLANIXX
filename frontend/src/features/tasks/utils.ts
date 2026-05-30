import type { TaskForm, TaskWindowFormEntry, UserTask } from '../../app/types'

function buildEntryId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}`
}

type ZonedDateParts = {
  year: number
  month: number
  day: number
  hour: number
  minute: number
}

function padNumber(value: number) {
  return String(value).padStart(2, '0')
}

function readPart(parts: Intl.DateTimeFormatPart[], type: string) {
  const value = parts.find((part) => part.type === type)?.value
  return value ? Number(value) : 0
}

function getZonedDateParts(date: Date, timeZone: string): ZonedDateParts {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })

  const parts = formatter.formatToParts(date)

  return {
    year: readPart(parts, 'year'),
    month: readPart(parts, 'month'),
    day: readPart(parts, 'day'),
    hour: readPart(parts, 'hour'),
    minute: readPart(parts, 'minute'),
  }
}

function isoToZonedInput(value: string | null | undefined, timeZone: string) {
  if (!value) {
    return ''
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  const parts = getZonedDateParts(date, timeZone)
  return `${parts.year}-${padNumber(parts.month)}-${padNumber(parts.day)}T${padNumber(parts.hour)}:${padNumber(parts.minute)}`
}

function parseDateTimeLocal(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/)

  if (!match) {
    throw new Error(`Некорректная дата: "${value}".`)
  }

  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
    hour: Number(match[4]),
    minute: Number(match[5]),
  }
}

function getTimeZoneOffsetMinutes(date: Date, timeZone: string) {
  const parts = getZonedDateParts(date, timeZone)
  const zonedAsUtc = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
  )

  return Math.round((zonedAsUtc - date.getTime()) / 60000)
}

function zonedInputToIso(value: string, timeZone: string) {
  if (!value) {
    return null
  }

  const parts = parseDateTimeLocal(value)
  const naiveUtc = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
  )

  let timestamp = naiveUtc
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const offsetMinutes = getTimeZoneOffsetMinutes(new Date(timestamp), timeZone)
    const nextTimestamp = naiveUtc - offsetMinutes * 60000

    if (nextTimestamp === timestamp) {
      break
    }

    timestamp = nextTimestamp
  }

  return new Date(timestamp).toISOString()
}

export function createTaskWindowEntry(): TaskWindowFormEntry {
  return {
    id: buildEntryId('task-window'),
    start: '',
    end: '',
  }
}

export function createEmptyTaskForm(): TaskForm {
  return {
    title: '',
    description: '',
    durationMinutes: '60',
    priority: '3',
    category: '',
    energyRequired: 'medium',
    status: 'active',
    deadline: '',
    earliestStart: '',
    latestEnd: '',
    fixedStart: '',
    isMandatory: true,
    isFixed: false,
    allowSplitting: false,
    minSplitPartMinutes: '30',
    preferredWindows: [],
    allowedWindows: [],
  }
}

export function getTaskId(task: UserTask) {
  return task.id ?? task.task_id ?? ''
}

export function taskToForm(task: UserTask, timeZone: string): TaskForm {
  return {
    title: task.title,
    description: task.description ?? '',
    durationMinutes: String(task.duration_minutes),
    priority: String(task.priority),
    category: task.category ?? '',
    energyRequired: task.energy_required,
    status: task.status,
    deadline: isoToZonedInput(task.deadline, timeZone),
    earliestStart: isoToZonedInput(task.earliest_start, timeZone),
    latestEnd: isoToZonedInput(task.latest_end, timeZone),
    fixedStart: isoToZonedInput(task.fixed_start, timeZone),
    isMandatory: task.is_mandatory,
    isFixed: task.is_fixed,
    allowSplitting: task.allow_splitting,
    minSplitPartMinutes: String(task.min_split_part_minutes ?? 30),
    preferredWindows: (task.preferred_windows ?? []).map((window) => ({
      id: buildEntryId('preferred-window'),
      start: isoToZonedInput(window.start, timeZone),
      end: isoToZonedInput(window.end, timeZone),
    })),
    allowedWindows: (task.allowed_windows ?? []).map((window) => ({
      id: buildEntryId('allowed-window'),
      start: isoToZonedInput(window.start, timeZone),
      end: isoToZonedInput(window.end, timeZone),
    })),
  }
}

function parsePositiveInteger(value: string, label: string) {
  const parsed = Number(value)

  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`Поле "${label}" должно быть целым числом больше 0.`)
  }

  return parsed
}

function parsePriority(value: string) {
  const parsed = parsePositiveInteger(value, 'priority')

  if (parsed < 1 || parsed > 5) {
    throw new Error('Поле "priority" должно быть в диапазоне от 1 до 5.')
  }

  return parsed
}

function normalizeOptionalString(value: string) {
  const normalized = value.trim()
  return normalized.length > 0 ? normalized : null
}

function buildWindows(
  entries: TaskWindowFormEntry[],
  fieldName: string,
  timeZone: string,
) {
  return entries.map((entry, index) => {
    const start = zonedInputToIso(entry.start, timeZone)
    const end = zonedInputToIso(entry.end, timeZone)

    if (!start || !end) {
      throw new Error(`Окно "${fieldName}[${index}]" должно иметь start и end.`)
    }

    return { start, end }
  })
}

export function buildTaskPayload(form: TaskForm, timeZone: string) {
  const title = form.title.trim()
  if (!title) {
    throw new Error('Поле "title" не может быть пустым.')
  }

  const durationMinutes = parsePositiveInteger(form.durationMinutes, 'duration_minutes')
  const priority = parsePriority(form.priority)
  const minSplitPartMinutes = form.allowSplitting
    ? parsePositiveInteger(form.minSplitPartMinutes, 'min_split_part_minutes')
    : null

  if (durationMinutes % 15 !== 0) {
    throw new Error('Поле "duration_minutes" должно быть кратно 15.')
  }

  if (form.isFixed && !form.fixedStart) {
    throw new Error('Для fixed task требуется "fixed_start".')
  }

  if (form.isFixed && form.allowSplitting) {
    throw new Error('Fixed task не может иметь allow_splitting = true.')
  }

  if (form.allowSplitting && minSplitPartMinutes && minSplitPartMinutes % 15 !== 0) {
    throw new Error('Поле "min_split_part_minutes" должно быть кратно 15.')
  }

  return {
    title,
    description: normalizeOptionalString(form.description),
    duration_minutes: durationMinutes,
    priority,
    category: normalizeOptionalString(form.category),
    energy_required: form.energyRequired,
    status: form.status,
    deadline: zonedInputToIso(form.deadline, timeZone),
    earliest_start: zonedInputToIso(form.earliestStart, timeZone),
    latest_end: zonedInputToIso(form.latestEnd, timeZone),
    fixed_start: form.isFixed ? zonedInputToIso(form.fixedStart, timeZone) : null,
    is_mandatory: form.isMandatory,
    is_fixed: form.isFixed,
    allow_splitting: form.isFixed ? false : form.allowSplitting,
    min_split_part_minutes: form.isFixed ? null : minSplitPartMinutes,
    preferred_windows: buildWindows(form.preferredWindows, 'preferred_windows', timeZone),
    allowed_windows: buildWindows(form.allowedWindows, 'allowed_windows', timeZone),
    constraints: {},
    llm_metadata: {},
  }
}
