import type { FormEvent } from 'react'

import type {
  CategoryTimePreferenceFormEntry,
  DurationMultiplierFormEntry,
  ProfileForm,
  ProfileStatus,
  Session,
} from '../../app/types'

type ProfileScreenProps = {
  isSavingProfile: boolean
  localTimeZone: string
  profileError: string | null
  profileForm: ProfileForm
  profileStatus: ProfileStatus
  session: Session
  onBackToCalendar: () => void
  onCreateDefaultProfile: () => void | Promise<void>
  onProfileFieldChange: <K extends keyof ProfileForm>(
    field: K,
    value: ProfileForm[K],
  ) => void
  onAddCategoryTimePreference: () => void
  onAddDurationMultiplier: () => void
  onCategoryTimePreferenceChange: (
    entryId: string,
    field: keyof Omit<CategoryTimePreferenceFormEntry, 'id'>,
    value: string,
  ) => void
  onDurationMultiplierChange: (
    entryId: string,
    field: keyof Omit<DurationMultiplierFormEntry, 'id'>,
    value: string,
  ) => void
  onRemoveCategoryTimePreference: (entryId: string) => void
  onRemoveDurationMultiplier: (entryId: string) => void
  onSaveProfile: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
}

export function ProfileScreen({
  isSavingProfile,
  localTimeZone,
  profileError,
  profileForm,
  profileStatus,
  session,
  onBackToCalendar,
  onCreateDefaultProfile,
  onProfileFieldChange,
  onAddCategoryTimePreference,
  onAddDurationMultiplier,
  onCategoryTimePreferenceChange,
  onDurationMultiplierChange,
  onRemoveCategoryTimePreference,
  onRemoveDurationMultiplier,
  onSaveProfile,
}: ProfileScreenProps) {
  return (
    <>
      <div className="schedule-card-header">
        <div>
          <span className="eyebrow">Profile</span>
          <h3>Данные профиля и настройки</h3>
        </div>

        <div className="schedule-meta">
          <span>{session.user.email}</span>
          <span>{localTimeZone}</span>
        </div>
      </div>

      {profileStatus === 'loading' ? (
        <div className="schedule-empty">
          <p>Загружаю профиль...</p>
        </div>
      ) : null}

      {profileStatus === 'error' && !profileError ? (
        <div className="schedule-empty">
          <p>Ошибка загрузки профиля.</p>
        </div>
      ) : null}

      {profileStatus === 'empty' ? (
        <div className="profile-empty-state">
          <p>Профиль пока не создан.</p>
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              void onCreateDefaultProfile()
            }}
          >
            Создать профиль по умолчанию
          </button>
        </div>
      ) : null}

      {profileStatus === 'ready' || profileStatus === 'error' ? (
        <form className="profile-form" onSubmit={onSaveProfile}>
          {profileError ? <p className="form-error">{profileError}</p> : null}

          <section className="profile-section">
            <div className="profile-section-heading">
              <h4>Productivity</h4>
              <p>Веса продуктивности по частям дня.</p>
            </div>
            <div className="profile-grid four">
              <label>
                <span>Morning</span>
                <input
                  type="number"
                  step="0.01"
                  value={profileForm.productivityMorning}
                  onChange={(event) =>
                    onProfileFieldChange('productivityMorning', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Afternoon</span>
                <input
                  type="number"
                  step="0.01"
                  value={profileForm.productivityAfternoon}
                  onChange={(event) =>
                    onProfileFieldChange('productivityAfternoon', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Evening</span>
                <input
                  type="number"
                  step="0.01"
                  value={profileForm.productivityEvening}
                  onChange={(event) =>
                    onProfileFieldChange('productivityEvening', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Night</span>
                <input
                  type="number"
                  step="0.01"
                  value={profileForm.productivityNight}
                  onChange={(event) =>
                    onProfileFieldChange('productivityNight', event.target.value)
                  }
                />
              </label>
            </div>
          </section>

          <section className="profile-section">
            <div className="profile-section-heading">
              <h4>Load</h4>
              <p>Ограничения и подход к нагрузке.</p>
            </div>
            <div className="profile-grid three">
              <label>
                <span>Comfortable daily minutes</span>
                <input
                  type="number"
                  value={profileForm.comfortableDailyMinutes}
                  onChange={(event) =>
                    onProfileFieldChange('comfortableDailyMinutes', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Max daily planned minutes</span>
                <input
                  type="number"
                  value={profileForm.maxDailyPlannedMinutes}
                  onChange={(event) =>
                    onProfileFieldChange('maxDailyPlannedMinutes', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Preferred break minutes</span>
                <input
                  type="number"
                  value={profileForm.preferredBreakMinutes}
                  onChange={(event) =>
                    onProfileFieldChange('preferredBreakMinutes', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Preferred focus block minutes</span>
                <input
                  type="number"
                  value={profileForm.preferredFocusBlockMinutes}
                  onChange={(event) =>
                    onProfileFieldChange(
                      'preferredFocusBlockMinutes',
                      event.target.value,
                    )
                  }
                />
              </label>
              <label>
                <span>Max focus block minutes</span>
                <input
                  type="number"
                  value={profileForm.maxFocusBlockMinutes}
                  onChange={(event) =>
                    onProfileFieldChange('maxFocusBlockMinutes', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Min break after focus minutes</span>
                <input
                  type="number"
                  value={profileForm.minBreakAfterFocusMinutes}
                  onChange={(event) =>
                    onProfileFieldChange('minBreakAfterFocusMinutes', event.target.value)
                  }
                />
              </label>
            </div>
          </section>

          <section className="profile-section">
            <div className="profile-section-heading">
              <h4>Behavior</h4>
              <p>Поведенческие коэффициенты планирования.</p>
            </div>
            <div className="profile-grid three">
              <label>
                <span>Completion rate</span>
                <input
                  type="number"
                  step="0.01"
                  value={profileForm.completionRate}
                  onChange={(event) =>
                    onProfileFieldChange('completionRate', event.target.value)
                  }
                />
              </label>
              <label>
                <span>Reschedule rate</span>
                <input
                  type="number"
                  step="0.01"
                  value={profileForm.rescheduleRate}
                  onChange={(event) =>
                    onProfileFieldChange('rescheduleRate', event.target.value)
                  }
                />
              </label>
              <label className="profile-toggle-field">
                <span>Likes compact schedule</span>
                <div className="profile-toggle-control">
                  <input
                    type="checkbox"
                    checked={profileForm.likesCompactSchedule}
                    onChange={(event) =>
                      onProfileFieldChange('likesCompactSchedule', event.target.checked)
                    }
                  />
                </div>
              </label>
            </div>
          </section>

          <section className="profile-section">
            <div className="profile-section-heading profile-section-heading-with-action">
              <div>
                <h4>Category time preferences</h4>
                <p>Настройки продуктивности по категориям без ручного JSON.</p>
              </div>
              <button
                type="button"
                className="ghost-button profile-inline-button"
                onClick={onAddCategoryTimePreference}
              >
                Добавить категорию
              </button>
            </div>

            {profileForm.categoryTimePreferences.length > 0 ? (
              <div className="profile-dynamic-list">
                {profileForm.categoryTimePreferences.map((entry) => (
                  <article className="profile-dynamic-card" key={entry.id}>
                    <div className="profile-dynamic-header">
                      <label>
                        <span>Category</span>
                        <input
                          type="text"
                          value={entry.category}
                          onChange={(event) =>
                            onCategoryTimePreferenceChange(
                              entry.id,
                              'category',
                              event.target.value,
                            )
                          }
                          placeholder="work"
                        />
                      </label>

                      <button
                        type="button"
                        className="ghost-button profile-remove-button"
                        onClick={() => onRemoveCategoryTimePreference(entry.id)}
                      >
                        Удалить
                      </button>
                    </div>

                    <div className="profile-grid four">
                      <label>
                        <span>Morning</span>
                        <input
                          type="number"
                          step="0.01"
                          value={entry.morning}
                          onChange={(event) =>
                            onCategoryTimePreferenceChange(
                              entry.id,
                              'morning',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <label>
                        <span>Afternoon</span>
                        <input
                          type="number"
                          step="0.01"
                          value={entry.afternoon}
                          onChange={(event) =>
                            onCategoryTimePreferenceChange(
                              entry.id,
                              'afternoon',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <label>
                        <span>Evening</span>
                        <input
                          type="number"
                          step="0.01"
                          value={entry.evening}
                          onChange={(event) =>
                            onCategoryTimePreferenceChange(
                              entry.id,
                              'evening',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                      <label>
                        <span>Night</span>
                        <input
                          type="number"
                          step="0.01"
                          value={entry.night}
                          onChange={(event) =>
                            onCategoryTimePreferenceChange(
                              entry.id,
                              'night',
                              event.target.value,
                            )
                          }
                        />
                      </label>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="profile-empty-state">
                <p>Категории для category_time_preferences пока не добавлены.</p>
              </div>
            )}
          </section>

          <section className="profile-section">
            <div className="profile-section-heading profile-section-heading-with-action">
              <div>
                <h4>Duration multipliers</h4>
                <p>Коэффициенты длительности по категориям в обычной форме.</p>
              </div>
              <button
                type="button"
                className="ghost-button profile-inline-button"
                onClick={onAddDurationMultiplier}
              >
                Добавить коэффициент
              </button>
            </div>

            {profileForm.durationMultipliers.length > 0 ? (
              <div className="profile-grid three">
                {profileForm.durationMultipliers.map((entry) => (
                  <article className="profile-dynamic-card" key={entry.id}>
                    <div className="profile-dynamic-header">
                      <label>
                        <span>Category</span>
                        <input
                          type="text"
                          value={entry.category}
                          onChange={(event) =>
                            onDurationMultiplierChange(
                              entry.id,
                              'category',
                              event.target.value,
                            )
                          }
                          placeholder="work"
                        />
                      </label>

                      <button
                        type="button"
                        className="ghost-button profile-remove-button"
                        onClick={() => onRemoveDurationMultiplier(entry.id)}
                      >
                        Удалить
                      </button>
                    </div>

                    <label>
                      <span>Multiplier</span>
                      <input
                        type="number"
                        step="0.01"
                        value={entry.multiplier}
                        onChange={(event) =>
                          onDurationMultiplierChange(
                            entry.id,
                            'multiplier',
                            event.target.value,
                          )
                        }
                      />
                    </label>
                  </article>
                ))}
              </div>
            ) : (
              <div className="profile-empty-state">
                <p>Коэффициенты для duration_multipliers пока не добавлены.</p>
              </div>
            )}
          </section>

          <div className="profile-actions">
            <button type="button" className="ghost-button" onClick={onBackToCalendar}>
              К расписанию
            </button>
            <button type="submit" className="primary-button" disabled={isSavingProfile}>
              {isSavingProfile ? 'Сохраняем...' : 'Сохранить профиль'}
            </button>
          </div>
        </form>
      ) : null}
    </>
  )
}
