import { useEffect, useState } from 'react'

import type {
  AvailabilityWindow,
  BusyInterval,
  CalendarViewDays,
  Schedule,
  ScheduleStatus,
  TaskLifecycleStatus,
} from '../../app/types'
import {
  buildAvailabilityOverlayBlocks,
  buildBusyOverlayBlocks,
  buildCalendarDays,
  buildCalendarSegments,
  DAY_MS,
  formatDateTime,
  formatTimeRange,
  getCurrentZonedMinutes,
  getStartOfWeekStamp,
  getTodayStamp,
  getVisibleRangeLabel,
  HOUR_ROW_HEIGHT,
  layoutDaySegments,
} from './utils'

type CalendarScreenProps = {
  calendarOffset: number
  calendarViewDays: CalendarViewDays
  isCompletingTaskId: string | null
  onOpenAiTaskModal: () => void
  onOpenQuickCreateTask: () => void
  onCompleteTask: (taskId: string) => void | Promise<void>
  onOpenScheduledTask: (taskId: string) => void | Promise<void>
  availabilityWindows: AvailabilityWindow[]
  busyIntervals: BusyInterval[]
  schedule: Schedule | null
  scheduleError: string | null
  scheduleStatus: ScheduleStatus
  taskStatusesById: Record<string, TaskLifecycleStatus>
  timeZone: string
  username: string
  onCalendarOffsetChange: (updater: (current: number) => number) => void
  onCalendarViewChange: (view: CalendarViewDays) => void
}

export function CalendarScreen({
  calendarOffset,
  calendarViewDays,
  isCompletingTaskId,
  onOpenAiTaskModal,
  onOpenQuickCreateTask,
  onCompleteTask,
  onOpenScheduledTask,
  availabilityWindows,
  busyIntervals,
  schedule,
  scheduleError,
  scheduleStatus,
  taskStatusesById,
  timeZone,
  username,
  onCalendarOffsetChange,
  onCalendarViewChange,
}: CalendarScreenProps) {
  const [nowTick, setNowTick] = useState(() => Date.now())

  useEffect(() => {
    const timerId = window.setInterval(() => {
      setNowTick(Date.now())
    }, 60_000)

    return () => window.clearInterval(timerId)
  }, [])

  const sortedTasks = [...(schedule?.scheduled_tasks ?? [])]
    .map((task) => {
      const taskId = task.task_id
      const nextStatus = taskId ? taskStatusesById[taskId] : undefined

      return nextStatus ? { ...task, status: nextStatus } : task
    })
    .sort((left, right) => {
      const leftTime = left.start_at ? new Date(left.start_at).getTime() : 0
      const rightTime = right.start_at ? new Date(right.start_at).getTime() : 0
      return leftTime - rightTime
    })

  const calendarSegments = buildCalendarSegments(sortedTasks, timeZone)
  const todayStamp = getTodayStamp(timeZone)
  const rangeShift = calendarViewDays === 7 ? 7 : calendarViewDays
  const rangeStartStamp =
    calendarViewDays === 7
      ? getStartOfWeekStamp(todayStamp) + calendarOffset * DAY_MS * rangeShift
      : todayStamp + calendarOffset * DAY_MS * rangeShift
  const visibleDays = buildCalendarDays(rangeStartStamp, calendarViewDays)
  const visibleRangeLabel = getVisibleRangeLabel(visibleDays)
  const availabilityOverlays = buildAvailabilityOverlayBlocks(
    availabilityWindows,
    visibleDays,
    timeZone,
  )
  const busyOverlays = buildBusyOverlayBlocks(busyIntervals, visibleDays, timeZone)

  const visibleStartHour = 0
  const visibleHourCount = 24
  const calendarBodyHeight = visibleHourCount * HOUR_ROW_HEIGHT
  const currentDayStamp = getTodayStamp(timeZone)
  const currentMinutes = getCurrentZonedMinutes(timeZone)
  const currentTimeTop = Math.min(
    Math.max(((currentMinutes - visibleStartHour * 60) / 60) * HOUR_ROW_HEIGHT, 0),
    calendarBodyHeight,
  )
  const hourLabels = Array.from(
    { length: visibleHourCount + 1 },
    (_, index) => visibleStartHour + index,
  )

  const positionedSegmentsByDay = Object.fromEntries(
    visibleDays.map((day) => [
      day.key,
      layoutDaySegments(
        calendarSegments.filter((segment) => segment.dayKey === day.key),
      ),
    ]),
  )
  const availabilityOverlaysByDay = Object.fromEntries(
    visibleDays.map((day) => [
      day.key,
      availabilityOverlays.filter((overlay) => overlay.dayKey === day.key),
    ]),
  )
  const busyOverlaysByDay = Object.fromEntries(
    visibleDays.map((day) => [
      day.key,
      busyOverlays.filter((overlay) => overlay.dayKey === day.key),
    ]),
  )

  return (
    <div className="calendar-screen">
      <div className="schedule-card-header">
        <div>
          <span className="eyebrow">Calendar</span>
          <h3>Слоты задач в календаре</h3>
        </div>

        <div className="calendar-header-actions">
          {schedule ? (
            <div className="schedule-meta">
              <span>{schedule.slot_minutes} мин слот</span>
              <span>{sortedTasks.length} задач</span>
              <span>Статус: {schedule.status}</span>
            </div>
          ) : null}

          <button
            type="button"
            className="ai-task-launch-button"
            onClick={onOpenAiTaskModal}
          >
            <span className="ai-task-launch-pill">AI</span>
            <span className="ai-task-launch-copy">
              <strong>Добавить задачу через ИИ</strong>
              <small>Опишите задачу свободным текстом</small>
            </span>
          </button>

          <button
            type="button"
            className="quick-create-button"
            onClick={onOpenQuickCreateTask}
            aria-label="Создать задачу"
            title="Создать задачу"
          >
            <span className="quick-create-icon" aria-hidden="true"></span>
          </button>
        </div>
      </div>

      {scheduleStatus === 'loading' ? (
        <div className="schedule-empty">
          <p>Загружаю текущее расписание...</p>
        </div>
      ) : null}

      {scheduleStatus === 'error' ? (
        <div className="schedule-empty">
          <p>{scheduleError ?? 'Ошибка загрузки расписания.'}</p>
        </div>
      ) : null}

      {scheduleStatus === 'empty' ? (
        <div className="schedule-empty">
          <p>У пользователя пока нет сохраненного current schedule.</p>
        </div>
      ) : null}

      {schedule && scheduleStatus === 'ready' ? (
        <div className="calendar-content">
          <div className="schedule-range">
            <div>
              <span>Обновлено</span>
              <strong>{formatDateTime(schedule.updated_at, timeZone)}</strong>
            </div>
            <div>
              <span>Таймзона</span>
              <strong>{timeZone}</strong>
            </div>
            <div>
              <span>Пользователь</span>
              <strong>{username}</strong>
            </div>
          </div>

          <div className="calendar-toolbar">
            <div className="calendar-view-switcher" role="tablist" aria-label="Calendar views">
              <button
                type="button"
                className={calendarViewDays === 1 ? 'is-active' : ''}
                onClick={() => onCalendarViewChange(1)}
              >
                1 день
              </button>
              <button
                type="button"
                className={calendarViewDays === 3 ? 'is-active' : ''}
                onClick={() => onCalendarViewChange(3)}
              >
                3 дня
              </button>
              <button
                type="button"
                className={calendarViewDays === 7 ? 'is-active' : ''}
                onClick={() => onCalendarViewChange(7)}
              >
                Неделя
              </button>
            </div>

            <div className="calendar-navigation">
              <button
                type="button"
                className="ghost-button nav-button"
                onClick={() => onCalendarOffsetChange((current) => current - 1)}
              >
                Назад
              </button>
              <div className="calendar-range-chip">{visibleRangeLabel}</div>
              <button
                type="button"
                className="ghost-button nav-button"
                onClick={() => onCalendarOffsetChange((current) => current + 1)}
              >
                Вперед
              </button>
            </div>
          </div>

          {visibleDays.length > 0 ? (
            <div className="calendar-shell">
              <div
                className={`calendar-grid ${
                  calendarViewDays === 7 ? 'is-week-view' : ''
                } ${calendarViewDays === 3 ? 'is-three-day-view' : ''} ${
                  calendarViewDays === 1 ? 'is-day-view' : ''
                }`}
                style={{
                  gridTemplateColumns: `${
                    calendarViewDays === 7 ? '4.25rem' : '5.5rem'
                  } repeat(${visibleDays.length}, minmax(0, 1fr))`,
                }}
              >
                <div className="calendar-corner"></div>

                {visibleDays.map((day) => (
                  <div className="calendar-day-header" key={`header-${day.key}`}>
                    <span>{day.weekdayLabel}</span>
                    <strong>{day.dateLabel}</strong>
                  </div>
                ))}

                <div className="calendar-time-column">
                  {hourLabels.map((hour) => (
                    <div
                      className="calendar-time-slot"
                      key={`time-${hour}`}
                      style={{ height: `${HOUR_ROW_HEIGHT}px` }}
                    >
                      <span>{`${String(hour).padStart(2, '0')}:00`}</span>
                    </div>
                  ))}
                </div>

                {visibleDays.map((day) => (
                  <div
                    className="calendar-day-column"
                    key={day.key}
                    style={{ height: `${calendarBodyHeight}px` }}
                  >
                    {(availabilityOverlaysByDay[day.key] ?? []).map((overlay) => {
                      const top =
                        ((overlay.startMinutes - visibleStartHour * 60) / 60) *
                        HOUR_ROW_HEIGHT
                      const height = Math.max(
                        ((overlay.endMinutes - overlay.startMinutes) / 60) *
                          HOUR_ROW_HEIGHT,
                        6,
                      )

                      return (
                        <div
                          className="calendar-overlay calendar-overlay--availability"
                          key={overlay.key}
                          style={{
                            top: `${top}px`,
                            height: `${height}px`,
                          }}
                          aria-hidden="true"
                          title={overlay.title}
                        />
                      )
                    })}

                    {(busyOverlaysByDay[day.key] ?? []).map((overlay) => {
                      const top =
                        ((overlay.startMinutes - visibleStartHour * 60) / 60) *
                        HOUR_ROW_HEIGHT
                      const height = Math.max(
                        ((overlay.endMinutes - overlay.startMinutes) / 60) *
                          HOUR_ROW_HEIGHT,
                        6,
                      )

                      return (
                        <div
                          className="calendar-overlay calendar-overlay--busy"
                          key={overlay.key}
                          style={{
                            top: `${top}px`,
                            height: `${height}px`,
                          }}
                          role="note"
                          tabIndex={0}
                        >
                          <span className="calendar-overlay-label">
                            {overlay.title}
                          </span>
                          <div className="calendar-overlay-popup">
                            <span className="calendar-overlay-popup-time">
                              {formatTimeRange(overlay.startAt, overlay.endAt, timeZone)}
                            </span>
                            <strong className="calendar-overlay-popup-title">
                              {overlay.title}
                            </strong>
                            <div className="calendar-overlay-popup-meta">
                              <span>
                                Начало: {formatDateTime(overlay.startAt, timeZone)}
                              </span>
                              <span>
                                Конец: {formatDateTime(overlay.endAt, timeZone)}
                              </span>
                            </div>
                          </div>
                        </div>
                      )
                    })}

                    {Array.from({ length: visibleHourCount + 1 }, (_, index) => (
                      <div
                        className="calendar-hour-line"
                        key={`${day.key}-line-${index}`}
                        style={{ top: `${index * HOUR_ROW_HEIGHT}px` }}
                      ></div>
                    ))}

                    {day.stamp === currentDayStamp ? (
                      <div
                        className="calendar-now-line"
                        style={{ top: `${currentTimeTop}px` }}
                        aria-hidden="true"
                        key={`${day.key}-now-${nowTick}`}
                      >
                        <span className="calendar-now-dot"></span>
                        <span className="calendar-now-label">Сейчас</span>
                      </div>
                    ) : null}

                    {(positionedSegmentsByDay[day.key] ?? []).map((segment) => {
                      const top =
                        ((segment.startMinutes - visibleStartHour * 60) / 60) *
                        HOUR_ROW_HEIGHT
                      const height = Math.max(
                        ((segment.endMinutes - segment.startMinutes) / 60) *
                          HOUR_ROW_HEIGHT,
                        36,
                      )
                      const width = `calc(${100 / segment.columnCount}% - 0.5rem)`
                      const left = `calc(${(100 / segment.columnCount) * segment.columnIndex}% + 0.25rem)`

                      const isCompleted = segment.status === 'completed'
                      const isCompletionPending = isCompletingTaskId === segment.taskId
                      const canComplete =
                        segment.status !== 'completed' &&
                        segment.status !== 'cancelled' &&
                        segment.status !== 'archived'

                      return (
                        <div
                          className={`calendar-event ${isCompleted ? 'is-completed' : ''}`}
                          key={segment.key}
                          style={{
                            top: `${top}px`,
                            height: `${height}px`,
                            width,
                            left,
                          }}
                        >
                          <button
                            type="button"
                            className="calendar-event-button"
                            onClick={() => {
                              void onOpenScheduledTask(segment.taskId)
                            }}
                          >
                            <div className="calendar-event-preview">
                              <span className="calendar-event-time">
                                {formatTimeRange(segment.startAt, segment.endAt, timeZone)}
                              </span>
                              <strong className="calendar-event-title">{segment.title}</strong>
                            </div>

                            <div className="calendar-event-popup">
                              <span className="calendar-event-popup-time">
                                {formatTimeRange(segment.startAt, segment.endAt, timeZone)}
                              </span>
                              <strong className="calendar-event-popup-title">
                                {segment.title}
                              </strong>
                              {segment.description ? (
                                <p className="calendar-event-description">
                                  {segment.description}
                                </p>
                              ) : null}
                              <div className="calendar-event-popup-meta">
                                <span>{segment.durationLabel}</span>
                                <span>{segment.category}</span>
                                {segment.status ? (
                                  <span className={`task-status-chip is-${segment.status}`}>
                                    {segment.status}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          </button>

                          <button
                            type="button"
                            className={`calendar-complete-button ${
                              isCompleted ? 'is-checked' : ''
                            }`}
                            onClick={(event) => {
                              event.stopPropagation()
                              void onCompleteTask(segment.taskId)
                            }}
                            aria-label={
                              isCompleted
                                ? 'Задача уже выполнена'
                                : 'Отметить задачу как выполненную'
                            }
                            title={
                              isCompleted
                                ? 'Задача уже выполнена'
                                : isCompletionPending
                                  ? 'Отмечаем выполнение...'
                                  : canComplete
                                    ? 'Отметить как выполненную'
                                    : 'Эту задачу нельзя отметить как выполненную'
                            }
                            disabled={!canComplete || isCompletionPending}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                              <path
                                d="M9.55 16.4 5.7 12.55l-1.4 1.4 5.25 5.25L19.7 9.05l-1.4-1.4-8.75 8.75Z"
                                fill="currentColor"
                              />
                            </svg>
                          </button>
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="schedule-empty">
              <p>Не удалось построить календарный диапазон для текущего расписания.</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
