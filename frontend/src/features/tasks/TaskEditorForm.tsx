import type { FormEvent } from 'react'

import type { TaskForm, TaskWindowFormEntry } from '../../app/types'

type TaskEditorFormProps = {
  editingTaskId: string | null
  isSavingTask: boolean
  secondaryActionLabel: string
  taskForm: TaskForm
  onAddAllowedWindow: () => void
  onAddPreferredWindow: () => void
  onRemoveAllowedWindow: (entryId: string) => void
  onRemovePreferredWindow: (entryId: string) => void
  onSaveTask: (event: FormEvent<HTMLFormElement>) => void | Promise<void>
  onSecondaryAction: () => void
  onTaskFieldChange: <K extends keyof TaskForm>(field: K, value: TaskForm[K]) => void
  onTaskWindowChange: (
    collection: 'preferredWindows' | 'allowedWindows',
    entryId: string,
    field: keyof Omit<TaskWindowFormEntry, 'id'>,
    value: string,
  ) => void
}

function renderWindowSection(
  title: string,
  entries: TaskWindowFormEntry[],
  onAdd: () => void,
  onRemove: (entryId: string) => void,
  onChange: (
    entryId: string,
    field: keyof Omit<TaskWindowFormEntry, 'id'>,
    value: string,
  ) => void,
) {
  return (
    <section className="profile-section">
      <div className="profile-section-heading profile-section-heading-with-action">
        <div>
          <h4>{title}</h4>
          <p>Добавляй окна вручную через отдельные интервалы.</p>
        </div>
        <button type="button" className="ghost-button profile-inline-button" onClick={onAdd}>
          Добавить окно
        </button>
      </div>

      {entries.length > 0 ? (
        <div className="profile-dynamic-list">
          {entries.map((entry) => (
            <article className="profile-dynamic-card" key={entry.id}>
              <div className="task-window-row">
                <div className="profile-grid two task-window-grid">
                  <label>
                    <span>Start</span>
                    <input
                      type="datetime-local"
                      step={900}
                      value={entry.start}
                      onChange={(event) => onChange(entry.id, 'start', event.target.value)}
                    />
                  </label>
                  <label>
                    <span>End</span>
                    <input
                      type="datetime-local"
                      step={900}
                      value={entry.end}
                      onChange={(event) => onChange(entry.id, 'end', event.target.value)}
                    />
                  </label>
                </div>

                <button
                  type="button"
                  className="ghost-button profile-remove-button"
                  onClick={() => onRemove(entry.id)}
                >
                  Удалить
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="profile-empty-state">
          <p>Пока нет ни одного окна.</p>
        </div>
      )}
    </section>
  )
}

export function TaskEditorForm({
  editingTaskId,
  isSavingTask,
  secondaryActionLabel,
  taskForm,
  onAddAllowedWindow,
  onAddPreferredWindow,
  onRemoveAllowedWindow,
  onRemovePreferredWindow,
  onSaveTask,
  onSecondaryAction,
  onTaskFieldChange,
  onTaskWindowChange,
}: TaskEditorFormProps) {
  return (
    <form className="tasks-editor-form" onSubmit={onSaveTask}>
      <section className="profile-section">
        <div className="profile-section-heading">
          <h4>Basic</h4>
          <p>Основные свойства задачи.</p>
        </div>

        <div className="profile-grid two">
          <label>
            <span>Title</span>
            <input
              type="text"
              value={taskForm.title}
              onChange={(event) => onTaskFieldChange('title', event.target.value)}
              required
            />
          </label>
          <label>
            <span>Category</span>
            <input
              type="text"
              value={taskForm.category}
              onChange={(event) => onTaskFieldChange('category', event.target.value)}
            />
          </label>
        </div>

        <label className="task-full-width-field">
          <span>Description</span>
          <textarea
            rows={4}
            value={taskForm.description}
            onChange={(event) => onTaskFieldChange('description', event.target.value)}
          />
        </label>

        <div className="profile-grid four">
          <label>
            <span>Duration minutes</span>
            <input
              type="number"
              min="15"
              step="15"
              value={taskForm.durationMinutes}
              onChange={(event) => onTaskFieldChange('durationMinutes', event.target.value)}
            />
          </label>
          <label>
            <span>Priority</span>
            <input
              type="number"
              min="1"
              max="5"
              step="1"
              value={taskForm.priority}
              onChange={(event) => onTaskFieldChange('priority', event.target.value)}
            />
          </label>
          <label>
            <span>Energy required</span>
            <select
              value={taskForm.energyRequired}
              onChange={(event) =>
                onTaskFieldChange('energyRequired', event.target.value as TaskForm['energyRequired'])
              }
            >
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </select>
          </label>
          <label>
            <span>Status</span>
            <select
              value={taskForm.status}
              onChange={(event) =>
                onTaskFieldChange('status', event.target.value as TaskForm['status'])
              }
            >
              <option value="active">active</option>
              <option value="completed">completed</option>
              <option value="cancelled">cancelled</option>
              <option value="archived">archived</option>
            </select>
          </label>
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-heading">
          <h4>Timing</h4>
          <p>Ограничения по времени и дедлайн.</p>
        </div>

        <div className="profile-grid two">
          <label>
            <span>Deadline</span>
            <input
              type="datetime-local"
              step={900}
              value={taskForm.deadline}
              onChange={(event) => onTaskFieldChange('deadline', event.target.value)}
            />
          </label>
          <label>
            <span>Earliest start</span>
            <input
              type="datetime-local"
              step={900}
              value={taskForm.earliestStart}
              onChange={(event) => onTaskFieldChange('earliestStart', event.target.value)}
            />
          </label>
          <label>
            <span>Latest end</span>
            <input
              type="datetime-local"
              step={900}
              value={taskForm.latestEnd}
              onChange={(event) => onTaskFieldChange('latestEnd', event.target.value)}
            />
          </label>
          <label>
            <span>Fixed start</span>
            <input
              type="datetime-local"
              step={900}
              value={taskForm.fixedStart}
              onChange={(event) => onTaskFieldChange('fixedStart', event.target.value)}
              disabled={!taskForm.isFixed}
            />
          </label>
        </div>
      </section>

      <section className="profile-section">
        <div className="profile-section-heading">
          <h4>Flags</h4>
          <p>Признаки обязательности, фиксации и дробления.</p>
        </div>

        <div className="profile-grid three">
          <label className="profile-toggle-field">
            <span>Mandatory</span>
            <div className="profile-toggle-control">
              <input
                type="checkbox"
                checked={taskForm.isMandatory}
                onChange={(event) => onTaskFieldChange('isMandatory', event.target.checked)}
              />
            </div>
          </label>
          <label className="profile-toggle-field">
            <span>Fixed task</span>
            <div className="profile-toggle-control">
              <input
                type="checkbox"
                checked={taskForm.isFixed}
                onChange={(event) => onTaskFieldChange('isFixed', event.target.checked)}
              />
            </div>
          </label>
          <label className="profile-toggle-field">
            <span>Allow splitting</span>
            <div className="profile-toggle-control">
              <input
                type="checkbox"
                checked={taskForm.allowSplitting}
                disabled={taskForm.isFixed}
                onChange={(event) =>
                  onTaskFieldChange('allowSplitting', event.target.checked)
                }
              />
            </div>
          </label>
        </div>

        <div className="profile-grid one">
          <label>
            <span>Min split part minutes</span>
            <input
              type="number"
              min="15"
              step="15"
              value={taskForm.minSplitPartMinutes}
              disabled={!taskForm.allowSplitting || taskForm.isFixed}
              onChange={(event) =>
                onTaskFieldChange('minSplitPartMinutes', event.target.value)
              }
            />
          </label>
        </div>
      </section>

      {renderWindowSection(
        'Preferred windows',
        taskForm.preferredWindows,
        onAddPreferredWindow,
        onRemovePreferredWindow,
        (entryId, field, value) =>
          onTaskWindowChange('preferredWindows', entryId, field, value),
      )}

      {renderWindowSection(
        'Allowed windows',
        taskForm.allowedWindows,
        onAddAllowedWindow,
        onRemoveAllowedWindow,
        (entryId, field, value) =>
          onTaskWindowChange('allowedWindows', entryId, field, value),
      )}

      <div className="profile-actions">
        <button type="button" className="ghost-button" onClick={onSecondaryAction}>
          {secondaryActionLabel}
        </button>
        <button type="submit" className="primary-button" disabled={isSavingTask}>
          {isSavingTask
            ? 'Сохраняем...'
            : editingTaskId
              ? 'Сохранить изменения'
              : 'Создать задачу'}
        </button>
      </div>
    </form>
  )
}
