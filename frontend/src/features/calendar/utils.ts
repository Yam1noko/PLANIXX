import type {
  AvailabilityWindow,
  BusyInterval,
  CalendarDay,
  CalendarOverlayBlock,
  CalendarSegment,
  PositionedCalendarSegment,
  ScheduleTask,
  ZonedDateParts,
} from '../../app/types'

export const DAY_MS = 24 * 60 * 60 * 1000
export const MINUTES_IN_DAY = 24 * 60
export const HOUR_ROW_HEIGHT = 72

export function formatDateTime(value: string | undefined, timeZone: string) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  }).format(date)
}

export function formatTimeRange(
  startAt: string | undefined,
  endAt: string | undefined,
  timeZone: string,
) {
  if (!startAt || !endAt) {
    return 'Время не указано'
  }

  const start = new Date(startAt)
  const end = new Date(endAt)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return `${startAt} - ${endAt}`
  }

  const formatter = new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  })

  return `${formatter.format(start)} - ${formatter.format(end)}`
}

export function formatDuration(startAt: string | undefined, endAt: string | undefined) {
  if (!startAt || !endAt) {
    return ''
  }

  const start = new Date(startAt)
  const end = new Date(endAt)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return ''
  }

  const totalMinutes = Math.max(
    0,
    Math.round((end.getTime() - start.getTime()) / 60000),
  )

  if (totalMinutes < 60) {
    return `${totalMinutes} мин`
  }

  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return minutes === 0 ? `${hours} ч` : `${hours} ч ${minutes} мин`
}

export function getTaskTitle(task: ScheduleTask, position: number) {
  return (
    task.title ??
    task.task_title ??
    task.task?.title ??
    task.name ??
    task.task_id ??
    `Задача ${position + 1}`
  )
}

export function getTaskCategory(task: ScheduleTask) {
  return task.category ?? task.task?.category ?? 'task'
}

export function getTaskDescription(task: ScheduleTask) {
  return task.description ?? task.task?.description ?? ''
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

function padNumber(value: number) {
  return String(value).padStart(2, '0')
}

function getZonedDayKey(date: Date, timeZone: string) {
  const parts = getZonedDateParts(date, timeZone)
  return `${parts.year}-${padNumber(parts.month)}-${padNumber(parts.day)}`
}

function getZonedDayStamp(date: Date, timeZone: string) {
  const parts = getZonedDateParts(date, timeZone)
  return Date.UTC(parts.year, parts.month - 1, parts.day)
}

function getZonedMinutes(date: Date, timeZone: string) {
  const parts = getZonedDateParts(date, timeZone)
  return parts.hour * 60 + parts.minute
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

function getLocalDateTimeValue(dayStamp: number, totalMinutes: number) {
  const date = new Date(dayStamp)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60

  return `${date.getUTCFullYear()}-${padNumber(date.getUTCMonth() + 1)}-${padNumber(date.getUTCDate())}T${padNumber(hours)}:${padNumber(minutes)}`
}

function zonedDateTimeToDate(value: string, timeZone: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/)

  if (!match) {
    return null
  }

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const hour = Number(match[4])
  const minute = Number(match[5])
  const naiveUtc = Date.UTC(year, month - 1, day, hour, minute)

  let timestamp = naiveUtc
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const offsetMinutes = getTimeZoneOffsetMinutes(new Date(timestamp), timeZone)
    const nextTimestamp = naiveUtc - offsetMinutes * 60000

    if (nextTimestamp === timestamp) {
      break
    }

    timestamp = nextTimestamp
  }

  return new Date(timestamp)
}

function getOverlayDateTime(dayStamp: number, totalMinutes: number, timeZone: string) {
  const date = zonedDateTimeToDate(getLocalDateTimeValue(dayStamp, totalMinutes), timeZone)
  return date ? date.toISOString() : undefined
}

function getRecurrenceIntervalDays(window: AvailabilityWindow) {
  const rule = window.recurrence_rule
  if (!window.is_recurring && !rule) {
    return null
  }

  if (!rule || rule === 'weekly') {
    return 7
  }

  if (rule === 'biweekly') {
    return 14
  }

  if (rule === 'daily') {
    return 1
  }

  if (rule.startsWith('custom:')) {
    const days = Number(rule.slice('custom:'.length))
    return Number.isFinite(days) && days > 0 ? days : null
  }

  return null
}

function pushOverlayRangeSegments(
  overlays: CalendarOverlayBlock[],
  {
    keyBase,
    kind,
    title,
    startDate,
    endDate,
  }: {
    keyBase: string
    kind: CalendarOverlayBlock['kind']
    title: string
    startDate: Date
    endDate: Date
  },
  visibleDayKeys: Set<string>,
  timeZone: string,
) {
  const startStamp = getZonedDayStamp(startDate, timeZone)
  const endStamp = getZonedDayStamp(endDate, timeZone)

  for (let stamp = startStamp; stamp <= endStamp; stamp += DAY_MS) {
    const dayKey = getZonedDayKey(new Date(stamp), 'UTC')
    if (!visibleDayKeys.has(dayKey)) {
      continue
    }

    const startMinutes = stamp === startStamp ? getZonedMinutes(startDate, timeZone) : 0
    const endMinutes = stamp === endStamp ? getZonedMinutes(endDate, timeZone) : MINUTES_IN_DAY

    if (endMinutes <= startMinutes) {
      continue
    }

    overlays.push({
      key: `${keyBase}-${dayKey}-${startMinutes}-${endMinutes}`,
      dayKey,
      startMinutes,
      endMinutes,
      kind,
      title,
      startAt: getOverlayDateTime(stamp, startMinutes, timeZone),
      endAt: getOverlayDateTime(stamp, endMinutes, timeZone),
    })
  }
}

export function getCurrentZonedMinutes(timeZone: string) {
  return getZonedMinutes(new Date(), timeZone)
}

export function buildCalendarDays(startStamp: number, dayCount: number) {
  const days: CalendarDay[] = []

  for (let index = 0; index < dayCount; index += 1) {
    const stamp = startStamp + index * DAY_MS
    const dayDate = new Date(stamp)

    days.push({
      key: getZonedDayKey(dayDate, 'UTC'),
      stamp,
      weekdayLabel: new Intl.DateTimeFormat('ru-RU', {
        weekday: 'short',
        timeZone: 'UTC',
      }).format(dayDate),
      dateLabel: new Intl.DateTimeFormat('ru-RU', {
        day: 'numeric',
        month: 'short',
        timeZone: 'UTC',
      }).format(dayDate),
      fullLabel: new Intl.DateTimeFormat('ru-RU', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        timeZone: 'UTC',
      }).format(dayDate),
    })
  }

  return days
}

export function getTodayStamp(timeZone: string) {
  return getZonedDayStamp(new Date(), timeZone)
}

export function getStartOfWeekStamp(dayStamp: number) {
  const weekday = new Date(dayStamp).getUTCDay()
  const mondayOffset = (weekday + 6) % 7
  return dayStamp - mondayOffset * DAY_MS
}

export function buildCalendarSegments(tasks: ScheduleTask[], timeZone: string) {
  const segments: CalendarSegment[] = []

  tasks.forEach((task, index) => {
    if (!task.start_at || !task.end_at) {
      return
    }

    const startDate = new Date(task.start_at)
    const endDate = new Date(task.end_at)

    if (
      Number.isNaN(startDate.getTime()) ||
      Number.isNaN(endDate.getTime()) ||
      endDate <= startDate
    ) {
      return
    }

    const startStamp = getZonedDayStamp(startDate, timeZone)
    const endStamp = getZonedDayStamp(endDate, timeZone)
    const title = getTaskTitle(task, index)
    const description = getTaskDescription(task)
    const category = getTaskCategory(task)
    const taskId = task.task_id ?? `task-${index + 1}`
    const durationLabel = formatDuration(task.start_at, task.end_at)

    for (let stamp = startStamp; stamp <= endStamp; stamp += DAY_MS) {
      const dayKey = getZonedDayKey(new Date(stamp), 'UTC')
      const startMinutes = stamp === startStamp ? getZonedMinutes(startDate, timeZone) : 0
      const endMinutes =
        stamp === endStamp ? getZonedMinutes(endDate, timeZone) : MINUTES_IN_DAY

      if (endMinutes <= startMinutes) {
        continue
      }

      segments.push({
        key: `${taskId}-${dayKey}-${startMinutes}-${endMinutes}`,
        dayKey,
        title,
        description,
        category,
        taskId,
        status: task.status,
        startAt: task.start_at,
        endAt: task.end_at,
        startMinutes,
        endMinutes,
        durationLabel,
      })
    }
  })

  return segments
}

export function buildAvailabilityOverlayBlocks(
  windows: AvailabilityWindow[],
  visibleDays: CalendarDay[],
  timeZone: string,
) {
  const overlays: CalendarOverlayBlock[] = []

  if (visibleDays.length === 0) {
    return overlays
  }

  const visibleDayKeys = new Set(visibleDays.map((day) => day.key))
  const firstVisibleStamp = visibleDays[0].stamp
  const lastVisibleStamp = visibleDays[visibleDays.length - 1].stamp

  windows.forEach((window, index) => {
    const startDate = new Date(window.start)
    const endDate = new Date(window.end)

    if (
      Number.isNaN(startDate.getTime()) ||
      Number.isNaN(endDate.getTime()) ||
      endDate <= startDate
    ) {
      return
    }

    const durationMs = endDate.getTime() - startDate.getTime()
    const startDayStamp = getZonedDayStamp(startDate, timeZone)
    const startMinutes = getZonedMinutes(startDate, timeZone)
    const durationDays = Math.max(1, Math.ceil(durationMs / DAY_MS))
    const recurrenceIntervalDays = getRecurrenceIntervalDays(window)
    const windowId = window.id ?? window.window_id ?? `availability-${index + 1}`

    if (!recurrenceIntervalDays) {
      pushOverlayRangeSegments(
        overlays,
        {
          keyBase: windowId,
          kind: 'availability',
          title: 'Доступное окно',
          startDate,
          endDate,
        },
        visibleDayKeys,
        timeZone,
      )
      return
    }

    for (
      let candidateDayStamp = firstVisibleStamp - durationDays * DAY_MS;
      candidateDayStamp <= lastVisibleStamp;
      candidateDayStamp += DAY_MS
    ) {
      const deltaDays = Math.round((candidateDayStamp - startDayStamp) / DAY_MS)
      if (deltaDays < 0 || deltaDays % recurrenceIntervalDays !== 0) {
        continue
      }

      const occurrenceStart = zonedDateTimeToDate(
        getLocalDateTimeValue(candidateDayStamp, startMinutes),
        timeZone,
      )
      if (!occurrenceStart) {
        continue
      }

      pushOverlayRangeSegments(
        overlays,
        {
          keyBase: `${windowId}-${candidateDayStamp}`,
          kind: 'availability',
          title: 'Доступное окно',
          startDate: occurrenceStart,
          endDate: new Date(occurrenceStart.getTime() + durationMs),
        },
        visibleDayKeys,
        timeZone,
      )
    }
  })

  return overlays
}

export function buildBusyOverlayBlocks(
  intervals: BusyInterval[],
  visibleDays: CalendarDay[],
  timeZone: string,
) {
  const overlays: CalendarOverlayBlock[] = []

  if (visibleDays.length === 0) {
    return overlays
  }

  const visibleDayKeys = new Set(visibleDays.map((day) => day.key))

  intervals.forEach((interval, index) => {
    const startDate = new Date(interval.start)
    const endDate = new Date(interval.end)

    if (
      Number.isNaN(startDate.getTime()) ||
      Number.isNaN(endDate.getTime()) ||
      endDate <= startDate
    ) {
      return
    }

    const intervalId = interval.id ?? interval.interval_id ?? `busy-${index + 1}`

    pushOverlayRangeSegments(
      overlays,
      {
        keyBase: intervalId,
        kind: 'busy',
        title: interval.title?.trim() || 'Busy interval',
        startDate,
        endDate,
      },
      visibleDayKeys,
      timeZone,
    )
  })

  return overlays
}

export function layoutDaySegments(segments: CalendarSegment[]) {
  const sortedSegments = [...segments].sort((left, right) => {
    if (left.startMinutes === right.startMinutes) {
      return left.endMinutes - right.endMinutes
    }

    return left.startMinutes - right.startMinutes
  })

  const columnEnds: number[] = []
  const positionedSegments: PositionedCalendarSegment[] = []

  sortedSegments.forEach((segment) => {
    let columnIndex = columnEnds.findIndex(
      (columnEnd) => columnEnd <= segment.startMinutes,
    )

    if (columnIndex === -1) {
      columnIndex = columnEnds.length
      columnEnds.push(segment.endMinutes)
    } else {
      columnEnds[columnIndex] = segment.endMinutes
    }

    positionedSegments.push({
      ...segment,
      columnIndex,
      columnCount: 1,
    })
  })

  const columnCount = Math.max(columnEnds.length, 1)

  return positionedSegments.map((segment) => ({
    ...segment,
    columnCount,
  }))
}

export function getVisibleRangeLabel(days: CalendarDay[]) {
  if (days.length === 0) {
    return 'Нет дат'
  }

  if (days.length === 1) {
    return days[0].fullLabel
  }

  return `${days[0].dateLabel} - ${days[days.length - 1].dateLabel}`
}
