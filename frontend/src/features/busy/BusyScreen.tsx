import type { FormEvent } from 'react'

import type { BusyForm, BusyInterval, BusyStatus } from '../../app/types'
import { formatDateTime } from '../calendar/utils'
import { getBusyIntervalId } from './utils'

type BusyScreenProps = {
  busyError: string | null
  busyForm: BusyForm
  busyIntervals: BusyInterval[]
  busyStatus: BusyStatus
  editingBusyId: string | null
  isDeletingBusyId: string | null
  isSavingBusy: boolean
  timeZone: string
  onBackToCalendar: () => void
  onBusyFieldChange: <K extends keyof BusyForm>(field: K, value: BusyForm[K]) => void
  onDeleteBusy: (intervalId: string) => void | Promise<void>
  onEditBusy: (interval: BusyInterval) => void
  onResetBusyForm: () => void
  onSaveBusy: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
}

export function BusyScreen({
  busyError,
  busyForm,
  busyIntervals,
  busyStatus,
  editingBusyId,
  isDeletingBusyId,
  isSavingBusy,
  timeZone,
  onBackToCalendar,
  onBusyFieldChange,
  onDeleteBusy,
  onEditBusy,
  onResetBusyForm,
  onSaveBusy,
}: BusyScreenProps) {
  return (
    <div className="busy-screen">
      <div className="schedule-card-header">
        <div>
          <span className="eyebrow">Busy</span>
          <h3>Занятые окна</h3>
          <p>Создание, редактирование и удаление занятых интервалов с названием.</p>
        </div>

        <div className="schedule-meta">
          <span>{busyIntervals.length} интервалов</span>
          <span>{editingBusyId ? 'Режим: редактирование' : 'Режим: создание'}</span>
        </div>
      </div>

      {busyError ? <p className="form-error">{busyError}</p> : null}

      <div className="busy-content">
        <div className="tasks-layout">
          <section className="tasks-list-panel">
            <div className="tasks-panel-header">
              <h4>Текущие занятые окна</h4>
              <button type="button" className="ghost-button" onClick={onResetBusyForm}>
                Новый интервал
              </button>
            </div>

            {busyStatus === 'loading' ? (
              <div className="schedule-empty">
                <p>Загружаю занятые окна...</p>
              </div>
            ) : null}

            {busyStatus === 'empty' ? (
              <div className="schedule-empty">
                <p>Занятых окон пока нет.</p>
              </div>
            ) : null}

            {busyStatus === 'ready' ? (
              <div className="tasks-list-scroll">
                <div className="tasks-list">
                  {busyIntervals.map((interval) => {
                    const intervalId = getBusyIntervalId(interval)

                    return (
                      <article
                        className={`task-card busy-card ${editingBusyId === intervalId ? 'is-active' : ''}`}
                        key={intervalId}
                      >
                        <button
                          type="button"
                          className="task-card-button"
                          onClick={() => onEditBusy(interval)}
                        >
                          <div className="task-card-header">
                            <div>
                              <h5>{interval.title || 'Без названия'}</h5>
                              <p>{interval.source || 'manual'}</p>
                            </div>
                            <span className="task-status-chip is-cancelled">busy</span>
                          </div>

                          <div className="task-card-dates">
                            <span>Start: {formatDateTime(interval.start, timeZone)}</span>
                            <span>End: {formatDateTime(interval.end, timeZone)}</span>
                          </div>
                        </button>

                        <button
                          type="button"
                          className="task-card-delete-icon"
                          aria-label="Удалить интервал"
                          title={isDeletingBusyId === intervalId ? 'Удаляем...' : 'Удалить интервал'}
                          onClick={() => {
                            void onDeleteBusy(intervalId)
                          }}
                          disabled={isDeletingBusyId === intervalId}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path
                              d="M9 3.75h6l.55 1.5H19.5a.75.75 0 1 1 0 1.5h-.64l-.72 11.07a2.25 2.25 0 0 1-2.24 2.1H8.1a2.25 2.25 0 0 1-2.24-2.1L5.14 6.75H4.5a.75.75 0 0 1 0-1.5h3.95L9 3.75Zm-2.35 3 .71 10.97a.75.75 0 0 0 .74.7h7.8a.75.75 0 0 0 .74-.7l.71-10.97H6.65Zm3.1 2.25c.41 0 .75.34.75.75v5.5a.75.75 0 0 1-1.5 0v-5.5c0-.41.34-.75.75-.75Zm4.5 0c.41 0 .75.34.75.75v5.5a.75.75 0 0 1-1.5 0v-5.5c0-.41.34-.75.75-.75Z"
                              fill="currentColor"
                            />
                          </svg>
                        </button>
                      </article>
                    )
                  })}
                </div>
              </div>
            ) : null}
          </section>

          <section className="tasks-form-panel">
            <div className="tasks-panel-header">
              <h4>{editingBusyId ? 'Редактирование интервала' : 'Новый интервал'}</h4>
              <button type="button" className="ghost-button" onClick={onBackToCalendar}>
                К расписанию
              </button>
            </div>

            <div className="tasks-form-scroll">
              <form className="profile-form" onSubmit={onSaveBusy}>
                <section className="profile-section">
                  <div className="profile-section-heading">
                    <h4>Basic</h4>
                    <p>Основные свойства занятого интервала.</p>
                  </div>

                  <div className="profile-grid two">
                    <label className="profile-field">
                      <span>Title</span>
                      <input
                        type="text"
                        value={busyForm.title}
                        onChange={(event) => onBusyFieldChange('title', event.target.value)}
                        placeholder="Например, обед или встреча"
                      />
                    </label>
                  </div>
                </section>

                <section className="profile-section">
                  <div className="profile-section-heading">
                    <h4>Timing</h4>
                    <p>Локальное время пользователя, которое будет отправлено на сервер в UTC.</p>
                  </div>

                  <div className="profile-grid two">
                    <label className="profile-field">
                      <span>Start</span>
                      <input
                        type="datetime-local"
                        value={busyForm.start}
                        onChange={(event) => onBusyFieldChange('start', event.target.value)}
                      />
                    </label>

                    <label className="profile-field">
                      <span>End</span>
                      <input
                        type="datetime-local"
                        value={busyForm.end}
                        onChange={(event) => onBusyFieldChange('end', event.target.value)}
                      />
                    </label>
                  </div>
                </section>

                <div className="profile-actions">
                  <button type="button" className="ghost-button" onClick={onResetBusyForm}>
                    Сбросить форму
                  </button>
                  <button type="submit" className="primary-button" disabled={isSavingBusy}>
                    {isSavingBusy
                      ? 'Сохраняем...'
                      : editingBusyId
                        ? 'Сохранить изменения'
                        : 'Создать интервал'}
                  </button>
                </div>
              </form>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
