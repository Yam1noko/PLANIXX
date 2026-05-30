import type { BusyForm, BusyInterval } from '../../app/types'

type ZonedDateParts = {
  year: number
  month: number
  day: number
  hour: number
  minute: number
}

function readPart(parts: Intl.DateTimeFormatPart[], type: string) {
  const value = parts.find((part) => part.type === type)?.value
  return value ? Number(value) : 0
}

function padNumber(value: number) {
  return String(value).padStart(2, '0')
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

function zonedInputToIso(value: string, timeZone: string) {
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

export function createEmptyBusyForm(): BusyForm {
  return {
    title: '',
    start: '',
    end: '',
  }
}

export function getBusyIntervalId(interval: BusyInterval) {
  return interval.id ?? interval.interval_id ?? ''
}

export function busyToForm(interval: BusyInterval, timeZone: string): BusyForm {
  return {
    title: interval.title ?? '',
    start: isoToZonedInput(interval.start, timeZone),
    end: isoToZonedInput(interval.end, timeZone),
  }
}

export function buildBusyPayload(form: BusyForm, timeZone: string) {
  const title = form.title.trim()

  if (!title) {
    throw new Error('Поле "title" не может быть пустым.')
  }

  if (!form.start || !form.end) {
    throw new Error('Поля "start" и "end" обязательны.')
  }

  const start = zonedInputToIso(form.start, timeZone)
  const end = zonedInputToIso(form.end, timeZone)

  if (new Date(end).getTime() <= new Date(start).getTime()) {
    throw new Error('"end" должен быть позже "start".')
  }

  return {
    title,
    start,
    end,
    source: 'manual' as const,
    external_event_id: null,
    payload: {},
  }
}
