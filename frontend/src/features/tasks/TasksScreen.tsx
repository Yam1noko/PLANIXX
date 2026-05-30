import type { FormEvent } from 'react'

import type { TaskForm, TasksStatus, TaskWindowFormEntry, UserTask } from '../../app/types'
import { formatDateTime } from '../calendar/utils'
import { TaskEditorForm } from './TaskEditorForm'
import { getTaskId } from './utils'

type TasksScreenProps = {
  editingTaskId: string | null
  isCompletingTaskId: string | null
  isDeletingTaskId: string | null
  isSavingTask: boolean
  taskForm: TaskForm
  tasks: UserTask[]
  tasksError: string | null
  tasksStatus: TasksStatus
  timeZone: string
  onAddAllowedWindow: () => void
  onAddPreferredWindow: () => void
  onBackToCalendar: () => void
  onOpenAiTaskModal: () => void
  onCompleteTask: (taskId: string) => void | Promise<void>
  onDeleteTask: (taskId: string) => void | Promise<void>
  onEditTask: (task: UserTask) => void
  onResetTaskForm: () => void
  onRemoveAllowedWindow: (entryId: string) => void
  onRemovePreferredWindow: (entryId: string) => void
  onSaveTask: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
  onTaskFieldChange: <K extends keyof TaskForm>(field: K, value: TaskForm[K]) => void
  onTaskWindowChange: (
    collection: 'preferredWindows' | 'allowedWindows',
    entryId: string,
    field: keyof Omit<TaskWindowFormEntry, 'id'>,
    value: string,
  ) => void
}

export function TasksScreen({
  editingTaskId,
  isCompletingTaskId,
  isDeletingTaskId,
  isSavingTask,
  taskForm,
  tasks,
  tasksError,
  tasksStatus,
  timeZone,
  onAddAllowedWindow,
  onAddPreferredWindow,
  onBackToCalendar,
  onOpenAiTaskModal,
  onCompleteTask,
  onDeleteTask,
  onEditTask,
  onResetTaskForm,
  onRemoveAllowedWindow,
  onRemovePreferredWindow,
  onSaveTask,
  onTaskFieldChange,
  onTaskWindowChange,
}: TasksScreenProps) {
  return (
    <div className="tasks-screen">
      <div className="schedule-card-header">
        <div>
          <span className="eyebrow">Tasks</span>
          <h3>Список задач</h3>
          <p>Создание, редактирование и удаление задач пользователя.</p>
        </div>

        <div className="schedule-meta">
          <span>{tasks.length} задач</span>
          <span>{editingTaskId ? 'Режим: редактирование' : 'Режим: создание'}</span>
        </div>
      </div>

      {tasksError ? <p className="form-error">{tasksError}</p> : null}

      <div className="tasks-content">
        <div className="tasks-layout">
          <section className="tasks-list-panel">
            <div className="tasks-panel-header">
              <h4>Текущие задачи</h4>
              <button type="button" className="ghost-button" onClick={onResetTaskForm}>
                Новая задача
              </button>
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
            </div>

            {tasksStatus === 'loading' ? (
              <div className="schedule-empty">
                <p>Загружаю задачи...</p>
              </div>
            ) : null}

            {tasksStatus === 'empty' ? (
              <div className="schedule-empty">
                <p>Задач пока нет.</p>
              </div>
            ) : null}

            {tasksStatus === 'ready' ? (
              <div className="tasks-list-scroll">
                <div className="tasks-list">
                  {tasks.map((task) => {
                    const taskId = getTaskId(task)
                    const isCompleted = task.status === 'completed'
                    const isCompletionPending = isCompletingTaskId === taskId
                    const canComplete = task.status === 'active'

                    return (
                      <article
                        className={`task-card ${
                          editingTaskId === taskId ? 'is-active' : ''
                        } ${isCompleted ? 'is-completed' : ''}`}
                        key={taskId}
                      >
                        <button
                          type="button"
                          className="task-card-button"
                          onClick={() => onEditTask(task)}
                        >
                          <div className="task-card-header">
                            <div>
                              <h5>{task.title}</h5>
                              <p>{task.description || 'Без описания'}</p>
                            </div>
                            <span className={`task-status-chip is-${task.status}`}>
                              {task.status}
                            </span>
                          </div>

                          <div className="task-card-meta">
                            <span>{task.duration_minutes} мин</span>
                            <span>priority {task.priority}</span>
                            <span>{task.energy_required}</span>
                            {task.category ? <span>{task.category}</span> : null}
                          </div>

                          <div className="task-card-dates">
                            {task.deadline ? (
                              <span>Deadline: {formatDateTime(task.deadline, timeZone)}</span>
                            ) : null}
                            {task.fixed_start ? (
                              <span>Fixed: {formatDateTime(task.fixed_start, timeZone)}</span>
                            ) : null}
                          </div>
                        </button>

                        <button
                          type="button"
                          className={`task-card-complete-button ${
                            isCompleted ? 'is-checked' : ''
                          }`}
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
                          onClick={() => {
                            void onCompleteTask(taskId)
                          }}
                          disabled={!canComplete || isCompletionPending}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path
                              d="M9.55 16.4 5.7 12.55l-1.4 1.4 5.25 5.25L19.7 9.05l-1.4-1.4-8.75 8.75Z"
                              fill="currentColor"
                            />
                          </svg>
                        </button>

                        <button
                          type="button"
                          className="task-card-delete-icon"
                          aria-label="Удалить задачу"
                          title={isDeletingTaskId === taskId ? 'Удаляем...' : 'Удалить задачу'}
                          onClick={() => {
                            void onDeleteTask(taskId)
                          }}
                          disabled={isDeletingTaskId === taskId}
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

          <div className="tasks-form-panel">
            <div className="tasks-panel-header">
              <h4>{editingTaskId ? 'Редактирование задачи' : 'Новая задача'}</h4>
              <button type="button" className="ghost-button" onClick={onBackToCalendar}>
                К расписанию
              </button>
            </div>

            <div className="tasks-form-scroll">
              <TaskEditorForm
                editingTaskId={editingTaskId}
                isSavingTask={isSavingTask}
                secondaryActionLabel="Сбросить форму"
                taskForm={taskForm}
                onAddAllowedWindow={onAddAllowedWindow}
                onAddPreferredWindow={onAddPreferredWindow}
                onRemoveAllowedWindow={onRemoveAllowedWindow}
                onRemovePreferredWindow={onRemovePreferredWindow}
                onSaveTask={onSaveTask}
                onSecondaryAction={onResetTaskForm}
                onTaskFieldChange={onTaskFieldChange}
                onTaskWindowChange={onTaskWindowChange}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
