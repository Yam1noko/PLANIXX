import type { AvailabilityWindow, CalendarDay } from '../../app/types'
import { DAY_MS, buildCalendarDays } from '../calendar/utils'

export const AVAILABILITY_SLOT_MINUTES = 15
export const AVAILABILITY_SLOTS_PER_DAY = (24 * 60) / AVAILABILITY_SLOT_MINUTES

export type AvailabilityRepeatMode = 'none' | 'weekly' | 'custom'

export type AvailabilityWindowPayload = {
  start: string
  end: string
  is_recurring: boolean
  recurrence_rule: string | null
  source: 'manual'
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
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/)

  if (!match) {
    throw new Error(`Некорректная дата: "${value}".`)
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

  return new Date(timestamp).toISOString()
}

function getDayStampFromParts(parts: ZonedDateParts) {
  return Date.UTC(parts.year, parts.month - 1, parts.day)
}

function getMinutesOfDay(parts: ZonedDateParts) {
  return parts.hour * 60 + parts.minute
}

function getDayNumber(dayStamp: number) {
  return Math.floor(dayStamp / DAY_MS)
}

function formatLocalDate(dayStamp: number) {
  const date = new Date(dayStamp)
  return `${date.getUTCFullYear()}-${padNumber(date.getUTCMonth() + 1)}-${padNumber(date.getUTCDate())}`
}

function buildLocalDateTime(dayStamp: number, totalMinutes: number) {
  const date = formatLocalDate(dayStamp)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${date}T${padNumber(hours)}:${padNumber(minutes)}`
}

function getRecurrenceIntervalDays(
  window: AvailabilityWindow,
): number | null {
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

function getOccurrenceRangesForWeek(
  window: AvailabilityWindow,
  weekStartStamp: number,
  timeZone: string,
) {
  const startDate = new Date(window.start)
  const endDate = new Date(window.end)

  if (
    Number.isNaN(startDate.getTime()) ||
    Number.isNaN(endDate.getTime()) ||
    endDate <= startDate
  ) {
    return []
  }

  const startParts = getZonedDateParts(startDate, timeZone)
  const startDayStamp = getDayStampFromParts(startParts)
  const startMinutes = getMinutesOfDay(startParts)
  const durationMinutes = Math.round((endDate.getTime() - startDate.getTime()) / 60000)
  const intervalDays = getRecurrenceIntervalDays(window)

  const ranges: Array<{ start: number; end: number }> = []
  const weekStartDayNumber = getDayNumber(weekStartStamp)

  const pushOccurrence = (occurrenceStartDayStamp: number) => {
    const start =
      getDayNumber(occurrenceStartDayStamp) * 24 * 60 + startMinutes
    const end = start + durationMinutes
    const clipStart = Math.max(start, weekStartDayNumber * 24 * 60)
    const clipEnd = Math.min(end, (weekStartDayNumber + 7) * 24 * 60)

    if (clipEnd > clipStart) {
      ranges.push({ start: clipStart, end: clipEnd })
    }
  }

  if (!intervalDays) {
    pushOccurrence(startDayStamp)
    return ranges
  }

  for (let dayIndex = 0; dayIndex < 7; dayIndex += 1) {
    const targetDayStamp = weekStartStamp + dayIndex * DAY_MS
    const deltaDays = Math.round((targetDayStamp - startDayStamp) / DAY_MS)

    if (deltaDays < 0 || deltaDays % intervalDays !== 0) {
      continue
    }

    pushOccurrence(targetDayStamp)
  }

  return ranges
}

function addRangeCells(
  cells: Set<string>,
  rangeStart: number,
  rangeEnd: number,
  weekStartStamp: number,
) {
  const weekStartDayNumber = getDayNumber(weekStartStamp)
  let cursor = rangeStart

  while (cursor < rangeEnd) {
    const dayNumber = Math.floor(cursor / (24 * 60))
    const dayIndex = dayNumber - weekStartDayNumber
    const dayStartMinute = dayNumber * 24 * 60
    const segmentEnd = Math.min(rangeEnd, dayStartMinute + 24 * 60)
    const startMinutes = cursor - dayStartMinute
    const endMinutes = segmentEnd - dayStartMinute

    for (
      let slotIndex = Math.floor(startMinutes / AVAILABILITY_SLOT_MINUTES);
      slotIndex < Math.ceil(endMinutes / AVAILABILITY_SLOT_MINUTES);
      slotIndex += 1
    ) {
      cells.add(`${dayIndex}:${slotIndex}`)
    }

    cursor = segmentEnd
  }
}

export function getAvailabilityWindowId(window: AvailabilityWindow) {
  return window.id ?? window.window_id ?? ''
}

export function getTodayDayStamp(timeZone: string) {
  const parts = getZonedDateParts(new Date(), timeZone)
  return getDayStampFromParts(parts)
}

export function getWeekStartDayStamp(dayStamp: number) {
  const weekday = new Date(dayStamp).getUTCDay()
  const mondayOffset = (weekday + 6) % 7
  return dayStamp - mondayOffset * DAY_MS
}

export function buildAvailabilityWeekDays(weekStartStamp: number): CalendarDay[] {
  return buildCalendarDays(weekStartStamp, 7)
}

export function getAvailabilityRangeLabel(days: CalendarDay[]) {
  if (days.length === 0) {
    return 'Нет дат'
  }

  return `${days[0].dateLabel} - ${days[days.length - 1].dateLabel}`
}

export function buildActiveAvailabilityCells(
  windows: AvailabilityWindow[],
  weekStartStamp: number,
  timeZone: string,
) {
  const cells = new Set<string>()

  windows.forEach((window) => {
    getOccurrenceRangesForWeek(window, weekStartStamp, timeZone).forEach((range) => {
      addRangeCells(cells, range.start, range.end, weekStartStamp)
    })
  })

  return cells
}

export function windowTouchesWeek(
  window: AvailabilityWindow,
  weekStartStamp: number,
  timeZone: string,
) {
  return getOccurrenceRangesForWeek(window, weekStartStamp, timeZone).length > 0
}

export function buildAvailabilityPayloads(
  cells: Set<string>,
  weekStartStamp: number,
  timeZone: string,
  repeatMode: AvailabilityRepeatMode,
  repeatEveryWeeks: number,
) {
  const recurrenceRule =
    repeatMode === 'weekly'
      ? 'weekly'
      : repeatMode === 'custom'
        ? `custom:${repeatEveryWeeks * 7}`
        : null

  const payloads: AvailabilityWindowPayload[] = []

  for (let dayIndex = 0; dayIndex < 7; dayIndex += 1) {
    const slots: number[] = []

    for (let slotIndex = 0; slotIndex < AVAILABILITY_SLOTS_PER_DAY; slotIndex += 1) {
      if (cells.has(`${dayIndex}:${slotIndex}`)) {
        slots.push(slotIndex)
      }
    }

    if (slots.length === 0) {
      continue
    }

    let rangeStart = slots[0]
    let previousSlot = slots[0]

    const flushRange = (rangeEndExclusive: number) => {
      const dayStamp = weekStartStamp + dayIndex * DAY_MS
      const startMinutes = rangeStart * AVAILABILITY_SLOT_MINUTES
      const endMinutes = rangeEndExclusive * AVAILABILITY_SLOT_MINUTES

      payloads.push({
        start: zonedInputToIso(buildLocalDateTime(dayStamp, startMinutes), timeZone),
        end: zonedInputToIso(buildLocalDateTime(dayStamp, endMinutes), timeZone),
        is_recurring: recurrenceRule !== null,
        recurrence_rule: recurrenceRule,
        source: 'manual',
      })
    }

    for (let index = 1; index < slots.length; index += 1) {
      const currentSlot = slots[index]

      if (currentSlot === previousSlot + 1) {
        previousSlot = currentSlot
        continue
      }

      flushRange(previousSlot + 1)
      rangeStart = currentSlot
      previousSlot = currentSlot
    }

    flushRange(previousSlot + 1)
  }

  return payloads
}

export function buildHourLabels() {
  return Array.from({ length: 24 }, (_, hour) => `${padNumber(hour)}:00`)
}
