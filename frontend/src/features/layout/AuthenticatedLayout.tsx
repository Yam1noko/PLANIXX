import type { ReactNode } from 'react'

import type { AppScreen, Session } from '../../app/types'

type AuthenticatedLayoutProps = {
  appScreen: AppScreen
  children: ReactNode
  isGeneratingSchedule: boolean
  isRefreshingToken: boolean
  scheduleActionLabel: string | null
  session: Session
  onExtendSchedule: () => void | Promise<void>
  onGenerateSchedule: () => void | Promise<void>
  onOpenAvailability: () => void
  onOpenBusy: () => void
  onLogout: () => void | Promise<void>
  onOpenCalendar: () => void
  onOpenProfile: () => void
  onOpenSettings: () => void
  onOpenTasks: () => void
  onRefreshSchedule: () => void | Promise<void>
  onRefreshToken: () => void | Promise<void>
}

function getHeadingMeta(appScreen: AppScreen, username: string) {
  if (appScreen === 'profile') {
    return {
      eyebrow: 'User profile',
      title: 'Профиль пользователя',
      description: `Настройки планирования для ${username}`,
    }
  }

  if (appScreen === 'settings') {
    return {
      eyebrow: 'Settings',
      title: 'Настройки пользователя',
      description: `Параметры генерации расписания для ${username}`,
    }
  }

  if (appScreen === 'tasks') {
    return {
      eyebrow: 'Tasks',
      title: 'Список задач',
      description: `Управление задачами пользователя ${username}`,
    }
  }

  if (appScreen === 'availability') {
    return {
      eyebrow: 'Availability',
      title: 'Доступные окна',
      description: `Недельная разметка свободного времени для ${username}`,
    }
  }

  if (appScreen === 'busy') {
    return {
      eyebrow: 'Busy',
      title: 'Занятые окна',
      description: `Недельная разметка занятого времени для ${username}`,
    }
  }

  return {
    eyebrow: 'Current schedule',
    title: 'Календарь расписания',
    description: `Текущий план пользователя ${username}`,
  }
}

export function AuthenticatedLayout({
  appScreen,
  children,
  isGeneratingSchedule,
  isRefreshingToken,
  scheduleActionLabel,
  session,
  onExtendSchedule,
  onGenerateSchedule,
  onOpenAvailability,
  onOpenBusy,
  onLogout,
  onOpenCalendar,
  onOpenProfile,
  onOpenSettings,
  onOpenTasks,
  onRefreshSchedule,
  onRefreshToken,
}: AuthenticatedLayoutProps) {
  const heading = getHeadingMeta(appScreen, session.user.username)
  const isViewportFitScreen =
    appScreen === 'calendar' ||
    appScreen === 'availability' ||
    appScreen === 'busy' ||
    appScreen === 'tasks'

  return (
    <section
      className={`schedule-layout ${isViewportFitScreen ? 'is-viewport-layout' : ''}`}
    >
      <header className="schedule-toolbar">
        {appScreen === 'calendar' ? (
          <div></div>
        ) : (
          <div className="schedule-heading">
            <span className="eyebrow">{heading.eyebrow}</span>
            <h2>{heading.title}</h2>
            <p>{heading.description}</p>
          </div>
        )}

        <div className="toolbar-cluster">
          {appScreen === 'calendar' ? (
            <>
              <button
                type="button"
                className="primary-button"
                onClick={() => {
                  void onGenerateSchedule()
                }}
                disabled={isGeneratingSchedule}
              >
                {isGeneratingSchedule
                  ? scheduleActionLabel ?? 'Генерируем расписание...'
                  : 'Сгенерировать расписание'}
              </button>
              <button
                type="button"
                className="ghost-button"
                onClick={() => {
                  void onRefreshSchedule()
                }}
                disabled={isGeneratingSchedule}
              >
                Обновить расписание
              </button>
              <button
                type="button"
                className="ghost-button"
                onClick={() => {
                  void onExtendSchedule()
                }}
                disabled={isGeneratingSchedule}
              >
                Дополнить расписание
              </button>
            </>
          ) : (
            <button type="button" className="ghost-button" onClick={onOpenCalendar}>
              К расписанию
            </button>
          )}

          <div className="user-menu">
            <button
              type="button"
              className="user-menu-trigger"
              aria-label="Меню пользователя"
            >
              <svg className="user-menu-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Zm0 2c-3.33 0-6 1.79-6 4v1h12v-1c0-2.21-2.67-4-6-4Z"
                  fill="currentColor"
                />
              </svg>
            </button>

            <div className="user-menu-dropdown" role="menu" aria-label="Пользователь">
              <button
                type="button"
                className="user-menu-item"
                role="menuitem"
                onClick={onOpenProfile}
              >
                Профиль пользователя
              </button>
              <button
                type="button"
                className="user-menu-item"
                role="menuitem"
                onClick={onOpenAvailability}
              >
                Доступные окна
              </button>
              <button
                type="button"
                className="user-menu-item"
                role="menuitem"
                onClick={onOpenBusy}
              >
                Занятые окна
              </button>
              <button
                type="button"
                className="user-menu-item"
                role="menuitem"
                onClick={onOpenTasks}
              >
                Список задач
              </button>
              <button
                type="button"
                className="user-menu-item"
                role="menuitem"
                onClick={onOpenSettings}
              >
                Настройки
              </button>
              <button
                type="button"
                className="user-menu-item"
                role="menuitem"
                onClick={() => {
                  void onRefreshToken()
                }}
                disabled={isRefreshingToken}
              >
                {isRefreshingToken
                  ? 'Обновляем access token...'
                  : 'Обновить access token'}
              </button>
              <button
                type="button"
                className="user-menu-item is-danger"
                role="menuitem"
                onClick={onLogout}
              >
                Выход
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className={`schedule-card ${isViewportFitScreen ? 'is-viewport-card' : ''}`}>
        {children}
      </div>
    </section>
  )
}
