import type { FormEvent } from 'react'

import type { GenerationSettingsForm } from '../../app/types'

type SettingsScreenProps = {
  isSavingSettings: boolean
  settingsError: string | null
  settingsForm: GenerationSettingsForm
  onBackToCalendar: () => void
  onSaveSettings: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
  onSettingsFieldChange: <K extends keyof GenerationSettingsForm>(
    field: K,
    value: GenerationSettingsForm[K],
  ) => void
}

export function SettingsScreen({
  isSavingSettings,
  settingsError,
  settingsForm,
  onBackToCalendar,
  onSaveSettings,
  onSettingsFieldChange,
}: SettingsScreenProps) {
  return (
    <>
      <div className="schedule-card-header">
        <div>
          <span className="eyebrow">Settings</span>
          <h3>Настройки генерации расписания</h3>
          <p>Эти параметры используются при вызове генерации на главном экране.</p>
        </div>
      </div>

      <form className="profile-form" onSubmit={onSaveSettings}>
        {settingsError ? <p className="form-error">{settingsError}</p> : null}

        <section className="profile-section">
          <div className="profile-section-heading">
            <h4>Generation</h4>
            <p>Параметры запроса `schedule-from-stored-data`.</p>
          </div>

          <div className="profile-grid two">
            <label>
              <span>Минимальный перерыв между задачами</span>
              <input
                type="number"
                min="0"
                step="1"
                value={settingsForm.minBreakMinutes}
                onChange={(event) =>
                  onSettingsFieldChange('minBreakMinutes', event.target.value)
                }
              />
            </label>

            <label>
              <span>Максимальное количество запланированных минут</span>
              <input
                type="number"
                min="0"
                step="1"
                value={settingsForm.maxDailyPlannedMinutes}
                onChange={(event) =>
                  onSettingsFieldChange('maxDailyPlannedMinutes', event.target.value)
                }
              />
            </label>
          </div>
        </section>

        <div className="profile-actions">
          <button type="button" className="ghost-button" onClick={onBackToCalendar}>
            К расписанию
          </button>
          <button type="submit" className="primary-button" disabled={isSavingSettings}>
            {isSavingSettings ? 'Сохраняем...' : 'Сохранить настройки'}
          </button>
        </div>
      </form>
    </>
  )
}
