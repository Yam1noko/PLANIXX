import { useEffect, useMemo, useState } from 'react'

import type { AvailabilityStatus, AvailabilityWindow } from '../../app/types'
import type { AvailabilityRepeatMode } from './utils'
import {
  AVAILABILITY_SLOTS_PER_DAY,
  buildActiveAvailabilityCells,
  buildAvailabilityWeekDays,
  buildHourLabels,
  getAvailabilityRangeLabel,
  getTodayDayStamp,
  getWeekStartDayStamp,
} from './utils'

type AvailabilityScreenProps = {
  availabilityError: string | null
  availabilityStatus: AvailabilityStatus
  availabilityWindows: AvailabilityWindow[]
  isSavingAvailability: boolean
  timeZone: string
  onSaveAvailability: (
    weekStartStamp: number,
    cells: Set<string>,
    repeatMode: AvailabilityRepeatMode,
    repeatEveryWeeks: number,
  ) => void | Promise<void>
}

type DragMode = 'fill' | 'erase' | null

export function AvailabilityScreen({
  availabilityError,
  availabilityStatus,
  availabilityWindows,
  isSavingAvailability,
  timeZone,
  onSaveAvailability,
}: AvailabilityScreenProps) {
  const [weekOffset, setWeekOffset] = useState(0)
  const [isEditing, setIsEditing] = useState(false)
  const [repeatMode, setRepeatMode] = useState<AvailabilityRepeatMode>('none')
  const [repeatEveryWeeks, setRepeatEveryWeeks] = useState('2')
  const [draftCells, setDraftCells] = useState<Set<string>>(new Set())
  const [dragMode, setDragMode] = useState<DragMode>(null)

  const currentWeekStartStamp = useMemo(
    () => getWeekStartDayStamp(getTodayDayStamp(timeZone)),
    [timeZone],
  )
  const weekStartStamp = currentWeekStartStamp + weekOffset * 7 * 24 * 60 * 60 * 1000
  const days = useMemo(() => buildAvailabilityWeekDays(weekStartStamp), [weekStartStamp])
  const rangeLabel = useMemo(() => getAvailabilityRangeLabel(days), [days])
  const hourLabels = useMemo(() => buildHourLabels(), [])
  const persistedCells = useMemo(
    () => buildActiveAvailabilityCells(availabilityWindows, weekStartStamp, timeZone),
    [availabilityWindows, timeZone, weekStartStamp],
  )
  const visibleCells = isEditing ? draftCells : persistedCells
  const parsedRepeatWeeks = Number(repeatEveryWeeks)
  const isRepeatWeeksInvalid =
    repeatMode === 'custom' &&
    (!Number.isFinite(parsedRepeatWeeks) ||
      !Number.isInteger(parsedRepeatWeeks) ||
      parsedRepeatWeeks < 2)

  useEffect(() => {
    const handleMouseUp = () => {
      setDragMode(null)
    }

    window.addEventListener('mouseup', handleMouseUp)
    return () => window.removeEventListener('mouseup', handleMouseUp)
  }, [])

  function resetEditingState() {
    setDraftCells(new Set())
    setIsEditing(false)
    setDragMode(null)
  }

  function updateCell(cellKey: string, nextDragMode: Exclude<DragMode, null>) {
    setDraftCells((current) => {
      const next = new Set(current)

      if (nextDragMode === 'fill') {
        next.add(cellKey)
      } else {
        next.delete(cellKey)
      }

      return next
    })
  }

  function handleCellMouseDown(cellKey: string) {
    if (!isEditing) {
      return
    }

    const nextDragMode: Exclude<DragMode, null> = draftCells.has(cellKey)
      ? 'erase'
      : 'fill'

    setDragMode(nextDragMode)
    updateCell(cellKey, nextDragMode)
  }

  function handleCellMouseEnter(cellKey: string) {
    if (!isEditing || !dragMode) {
      return
    }

    updateCell(cellKey, dragMode)
  }

  async function handleSave() {
    if (isRepeatWeeksInvalid) {
      return
    }

    await onSaveAvailability(
      weekStartStamp,
      draftCells,
      repeatMode,
      parsedRepeatWeeks,
    )
  }

  return (
    <div className="availability-screen">
      <div className="schedule-card-header">
        <div>
          <span className="eyebrow">Availability</span>
          <h3>Свободные окна</h3>
        </div>

        <div className="availability-toolbar-meta">
          <span className="calendar-range-chip">{rangeLabel}</span>
          <span>{visibleCells.size * 15} мин отмечено</span>
        </div>
      </div>

      {availabilityError ? <p className="form-error">{availabilityError}</p> : null}

      <section className="availability-actions">
        <div className="calendar-navigation">
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setWeekOffset((current) => current - 1)
              resetEditingState()
            }}
          >
            Предыдущая неделя
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setWeekOffset(0)
              resetEditingState()
            }}
          >
            К текущей
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setWeekOffset((current) => current + 1)
              resetEditingState()
            }}
          >
            Следующая неделя
          </button>
        </div>

        <div className="availability-toolbar-controls">
          <button
            type="button"
            className={isEditing ? 'primary-button' : 'ghost-button'}
            onClick={() => {
              if (isEditing) {
                setIsEditing(false)
                setDragMode(null)
                return
              }

              setDraftCells(new Set(persistedCells))
              setIsEditing(true)
            }}
            disabled={availabilityStatus === 'loading' || isSavingAvailability}
          >
            {isEditing ? 'Режим разметки включен' : 'Разметить свободные окна'}
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => setDraftCells(new Set(persistedCells))}
            disabled={
              availabilityStatus === 'loading' ||
              isSavingAvailability ||
              !isEditing
            }
          >
            Сбросить изменения
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              void handleSave().catch(() => undefined)
            }}
            disabled={
              availabilityStatus === 'loading' ||
              isSavingAvailability ||
              isRepeatWeeksInvalid ||
              !isEditing
            }
          >
            {isSavingAvailability ? 'Сохраняем...' : 'Сохранить'}
          </button>
        </div>
      </section>

      <section className="profile-section availability-repeat-section">
        <div className="profile-section-heading">
          <h4>Повторение</h4>
        </div>

        <div className="availability-repeat-grid">
          <button
            type="button"
            className={`availability-repeat-card ${repeatMode === 'none' ? 'is-active' : ''}`}
            onClick={() => setRepeatMode('none')}
          >
            <strong>Без повтора</strong>
          </button>
          <button
            type="button"
            className={`availability-repeat-card ${repeatMode === 'weekly' ? 'is-active' : ''}`}
            onClick={() => setRepeatMode('weekly')}
          >
            <strong>Повторять каждую неделю</strong>
          </button>
          <label
            className={`availability-repeat-card availability-repeat-custom ${repeatMode === 'custom' ? 'is-active' : ''}`}
          >
            <strong>Повторять каждые m-ую неделю</strong>
            <div className="availability-repeat-inline">
              <input
                type="radio"
                name="availability-repeat-mode"
                checked={repeatMode === 'custom'}
                onChange={() => setRepeatMode('custom')}
              />
              <select
                value={repeatEveryWeeks}
                onChange={(event) => setRepeatEveryWeeks(event.target.value)}
                disabled={repeatMode !== 'custom'}
              >
                {Array.from({ length: 11 }, (_, index) => String(index + 2)).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
              <span>недель</span>
            </div>
          </label>
        </div>
      </section>

      {availabilityStatus === 'loading' ? (
        <div className="schedule-empty">
          <p>Загружаю свободные окна...</p>
        </div>
      ) : null}

      {(availabilityStatus === 'ready' || availabilityStatus === 'empty') && (
        <div className="availability-content">
          <div
            className={`availability-shell ${isEditing ? 'is-editing' : ''}`}
            onMouseLeave={() => setDragMode(null)}
          >
            <div
              className="availability-grid"
              style={{ gridTemplateColumns: `4.5rem repeat(${days.length}, minmax(0, 1fr))` }}
            >
              <div className="availability-corner" />

              {days.map((day) => (
                <div key={day.key} className="availability-day-header">
                  <span>{day.weekdayLabel}</span>
                  <strong>{day.dateLabel}</strong>
                </div>
              ))}

              <div className="availability-time-column" aria-hidden="true">
                {Array.from({ length: AVAILABILITY_SLOTS_PER_DAY }, (_, slotIndex) => (
                  <div
                    key={`time-${slotIndex}`}
                    className={`availability-time-slot ${slotIndex % 4 === 0 ? 'is-hour' : ''}`}
                  >
                    {slotIndex % 4 === 0 ? <span>{hourLabels[slotIndex / 4]}</span> : null}
                  </div>
                ))}
              </div>

              {days.map((day, dayIndex) => (
                <div key={day.key} className="availability-day-column">
                  {Array.from({ length: AVAILABILITY_SLOTS_PER_DAY }, (_, slotIndex) => {
                    const cellKey = `${dayIndex}:${slotIndex}`
                    const isActive = visibleCells.has(cellKey)

                    return (
                      <button
                        key={cellKey}
                        type="button"
                        className={`availability-cell ${isActive ? 'is-active' : ''} ${slotIndex % 4 === 0 ? 'is-hour' : ''}`}
                        onMouseDown={(event) => {
                          event.preventDefault()
                          handleCellMouseDown(cellKey)
                        }}
                        onMouseEnter={() => handleCellMouseEnter(cellKey)}
                        onDragStart={(event) => event.preventDefault()}
                        disabled={!isEditing}
                        aria-label={`${day.fullLabel}, слот ${slotIndex + 1}`}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
