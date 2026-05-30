import type { FormEvent } from 'react'

import type { AuthMode, LoginForm, RegisterForm } from '../../app/types'

type AuthScreenProps = {
  authMode: AuthMode
  authError: string | null
  isSubmitting: boolean
  loginForm: LoginForm
  registerForm: RegisterForm
  onAuthModeChange: (mode: AuthMode) => void
  onLoginFormChange: (field: keyof LoginForm, value: string) => void
  onLoginSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
  onRegisterFormChange: (field: keyof RegisterForm, value: string) => void
  onRegisterSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
}

export function AuthScreen({
  authMode,
  authError,
  isSubmitting,
  loginForm,
  registerForm,
  onAuthModeChange,
  onLoginFormChange,
  onLoginSubmit,
  onRegisterFormChange,
  onRegisterSubmit,
}: AuthScreenProps) {
  return (
    <>
      <section className="hero-panel">
        <div className="hero-copy">
          <span className="eyebrow">PlanixAI</span>
          <h1>Регистрация, вход и текущее расписание в одном экране</h1>
          <p className="hero-text">
            Фронтенд хранит только `access_token` и `user.id`, а обновление
            access token делает через `HttpOnly` refresh cookie на `127.0.0.1:8000`.
          </p>
        </div>

        <div className="hero-card">
          <p>Что уже подключено</p>
          <ul>
            <li>Регистрация через `/api/auth/register`</li>
            <li>Авторизация через `/api/auth/login`</li>
            <li>Refresh через `/api/auth/refresh`</li>
            <li>Отдельный экран календаря и профиля</li>
          </ul>
        </div>
      </section>

      <section className="auth-layout">
        <div className="auth-card">
          <div className="auth-switcher" role="tablist" aria-label="Auth mode">
            <button
              type="button"
              className={authMode === 'register' ? 'is-active' : ''}
              onClick={() => onAuthModeChange('register')}
            >
              Регистрация
            </button>
            <button
              type="button"
              className={authMode === 'login' ? 'is-active' : ''}
              onClick={() => onAuthModeChange('login')}
            >
              Вход
            </button>
          </div>

          {authMode === 'register' ? (
            <form className="auth-form" onSubmit={onRegisterSubmit}>
              <label>
                <span>Username</span>
                <input
                  type="text"
                  placeholder="ivan.petrov"
                  minLength={3}
                  maxLength={32}
                  value={registerForm.username}
                  onChange={(event) =>
                    onRegisterFormChange('username', event.target.value)
                  }
                  required
                />
              </label>

              <label>
                <span>Email</span>
                <input
                  type="email"
                  placeholder="ivan.petrov@example.com"
                  value={registerForm.email}
                  onChange={(event) => onRegisterFormChange('email', event.target.value)}
                  required
                />
              </label>

              <label>
                <span>Пароль</span>
                <input
                  type="password"
                  placeholder="StrongPassw0rd!"
                  minLength={12}
                  value={registerForm.password}
                  onChange={(event) =>
                    onRegisterFormChange('password', event.target.value)
                  }
                  required
                />
              </label>

              {authError ? <p className="form-error">{authError}</p> : null}

              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Создаем аккаунт...' : 'Зарегистрироваться'}
              </button>
            </form>
          ) : (
            <form className="auth-form" onSubmit={onLoginSubmit}>
              <label>
                <span>Username или Email</span>
                <input
                  type="text"
                  placeholder="ivan.petrov"
                  value={loginForm.identifier}
                  onChange={(event) => onLoginFormChange('identifier', event.target.value)}
                  required
                />
              </label>

              <label>
                <span>Пароль</span>
                <input
                  type="password"
                  placeholder="StrongPassw0rd!"
                  value={loginForm.password}
                  onChange={(event) => onLoginFormChange('password', event.target.value)}
                  required
                />
              </label>

              {authError ? <p className="form-error">{authError}</p> : null}

              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Входим...' : 'Войти'}
              </button>
            </form>
          )}
        </div>
      </section>
    </>
  )
}
