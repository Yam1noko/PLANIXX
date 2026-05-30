# PlanixAI Backend API

This README documents the main frontend API.

Important scope:
- only DB-backed endpoints are documented here
- direct internal/service endpoints that bypass DB are intentionally omitted

Base prefix: `/api`

## 1. Main Product Flow

Normal frontend flow:

1. Register or login
2. Save `access_token` and `user.id`
3. Refresh token is stored by backend in `HttpOnly` cookie
4. Send Bearer token on protected requests
5. Fill user data in DB:
   - profile
   - tasks
   - availability windows
   - busy intervals
6. Run one of:
   - schedule preview from stored data
   - schedule generation from stored data
   - best schedule from stored data
   - manual schedule upload
7. Read current saved schedule

## 2. Authentication

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

For browser clients:
- send auth refresh/logout requests with `credentials: "include"`
- otherwise refresh cookie will not be sent

### Access token lifetime
- default: `15 minutes`

### Refresh behavior
- refresh token is stored in `HttpOnly` cookie
- refresh rotates cookie value on every refresh
- refresh response returns a new `access_token`
- old refresh token must not be reused

### How auth works in browser
Frontend stores:
- `access_token`
- `user.id`

Frontend does not store:
- `refresh_token`

Backend stores refresh token in:
- `HttpOnly` cookie

This means:
- JavaScript cannot read refresh token directly
- browser sends refresh cookie automatically on requests with `credentials: "include"`
- access token is still sent manually in `Authorization: Bearer <access_token>`

Typical browser flow:
1. User logs in or registers
2. Backend returns `access_token` in JSON
3. Backend sets refresh token as `HttpOnly` cookie
4. Frontend saves only `access_token`
5. Frontend uses `Authorization: Bearer <access_token>` on protected endpoints
6. When access token expires, frontend calls `POST /api/auth/refresh`
7. Browser sends refresh cookie automatically
8. Backend validates cookie, rotates refresh token, sets new cookie, returns new `access_token`
9. Frontend replaces old `access_token` with new one

Important frontend rule:
- call `refresh`, `logout`, and `logout-all` with `credentials: "include"`

Example:

```ts
await fetch("/api/auth/refresh", {
  method: "POST",
  credentials: "include"
});
```

### POST `/api/auth/register`
Create user and return token pair.

Request:

```json
{
  "username": "ivan.petrov",
  "email": "ivan.petrov@example.com",
  "password": "StrongPassw0rd!",
  "timezone": "UTC",
  "locale": "ru-RU"
}
```

Rules:
- `username`: 3-32 chars
- lowercase only
- allowed chars: `a-z`, `0-9`, `.`, `_`, `-`
- `password`: 12-128 chars, uppercase + lowercase + digit + special char required

Response:

```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_expires_in": 2592000,
  "user": {
    "id": "string",
    "username": "ivan.petrov",
    "email": "ivan.petrov@example.com",
    "timezone": "UTC",
    "locale": "ru-RU",
    "is_active": true,
    "created_at": "2026-05-05T10:00:00Z",
    "last_login_at": null
  }
}
```

### POST `/api/auth/login`
Login by `username` or `email`.

Request:

```json
{
  "identifier": "ivan.petrov",
  "password": "StrongPassw0rd!"
}
```

Response: same as `register`.

### POST `/api/auth/refresh`
Rotate refresh cookie and get new access token.

Request:
- no request body required
- backend reads refresh token from `HttpOnly` cookie

Response: same as `register`, but without refresh token in body.

### POST `/api/auth/logout`
Revoke current session.

Response:
- `204 No Content`

### POST `/api/auth/logout-all`
Revoke all sessions for current user.

Response:
- `204 No Content`

### GET `/api/auth/me`
Return current user.

## 3. Global Datetime Rules

Most validation errors are caused by invalid datetime values.

### Datetime format
Use ISO 8601 only.

Good:

```json
"2026-05-20T09:00:00Z"
```

Bad:

```json
"2026-05-20 09:00"
"20.05.2026 09:00"
```

Recommendation:
- always send UTC
- avoid random seconds
- avoid random milliseconds

### Supported `slot_minutes`
- `5`
- `10`
- `15`
- `30`
- `60`

### Alignment rule
Time values are validated relative to `planning_start`.

Example:

```json
{
  "planning_start": "2026-05-20T09:00:00Z",
  "slot_minutes": 15
}
```

Valid:
- `09:00`
- `09:15`
- `09:30`
- `09:45`

Invalid:
- `09:10`
- `09:07`
- `09:15:12`

Values that must align with `slot_minutes`:
- `planning_end`
- task `duration_minutes`
- task `fixed_start` if fixed
- busy interval `start`
- busy interval `end`
- manual schedule block `start_at`
- manual schedule block `end_at`

Recommended default:
- use `slot_minutes = 15`

## 4. Error Format

Common error shape:

```json
{
  "detail": "message"
}
```

Or:

```json
{
  "detail": [
    {}
  ]
}
```

Typical statuses:
- `400` business or internal validation error
- `401` auth required / invalid token
- `403` access to another user's resource
- `404` not found
- `409` conflict
- `422` request validation error

## 5. User Profile API

All endpoints below are protected.

`user_id` in URL must match token user.

### GET `/api/users/{user_id}/profile`
Return full profile.

### POST `/api/users/{user_id}/profile/default`
Create default profile.

### PUT `/api/users/{user_id}/profile`
Replace full profile.

Payload:

```json
{
  "user_id": "string",
  "productivity": {
    "morning": 0.9,
    "afternoon": 0.7,
    "evening": 0.5,
    "night": 0.2
  },
  "category_time_preferences": {
    "work": {
      "morning": 0.9,
      "afternoon": 0.8,
      "evening": 0.4,
      "night": 0.1
    }
  },
  "duration_multipliers": {
    "work": 1.1
  },
  "load": {
    "comfortable_daily_minutes": 300,
    "max_daily_planned_minutes": 480,
    "preferred_break_minutes": 15,
    "preferred_focus_block_minutes": 90,
    "max_focus_block_minutes": 120,
    "min_break_after_focus_minutes": 15
  },
  "behavior": {
    "completion_rate": 0.7,
    "reschedule_rate": 0.25,
    "likes_compact_schedule": false
  }
}
```

### PATCH `/api/users/{user_id}/profile`
Partial profile update.

Example:

```json
{
  "productivity": {
    "morning": 0.95,
    "evening": 0.35
  },
  "load": {
    "max_daily_planned_minutes": 420
  },
  "behavior": {
    "likes_compact_schedule": true
  }
}
```

### DELETE `/api/users/{user_id}/profile`
Delete profile.

### GET `/api/users/{user_id}/solver-preferences`
Return derived solver preferences.

## 6. User Planning Data API

These endpoints store planning data in DB.

### GET `/api/users/{user_id}/planning-context`
Return all planning inputs for the user:
- profile
- tasks
- availability windows
- busy intervals

### Task payload

```json
{
  "title": "Prepare presentation",
  "description": "Slides for client meeting",
  "duration_minutes": 60,
  "priority": 5,
  "category": "work",
  "energy_required": "high",
  "status": "active",
  "deadline": "2026-05-20T16:00:00Z",
  "earliest_start": "2026-05-20T09:00:00Z",
  "latest_end": "2026-05-20T16:00:00Z",
  "fixed_start": null,
  "is_mandatory": true,
  "is_fixed": false,
  "allow_splitting": true,
  "min_split_part_minutes": 30,
  "preferred_windows": [
    {
      "start": "2026-05-20T09:00:00Z",
      "end": "2026-05-20T12:00:00Z"
    }
  ],
  "allowed_windows": [
    {
      "start": "2026-05-20T09:00:00Z",
      "end": "2026-05-20T16:00:00Z"
    }
  ],
  "constraints": {},
  "llm_metadata": {}
}
```

Rules:
- `priority`: `1..5`
- `energy_required`: `low | medium | high`
- `status`: `active | completed | cancelled | archived`
- if `is_fixed = true`, `fixed_start` is required
- if `is_fixed = false`, `fixed_start` may be `null`
- if `allow_splitting = true`, `min_split_part_minutes` is required
- fixed tasks cannot be split
- `min_split_part_minutes` should be divisible by the `slot_minutes` used for generation

### Tasks endpoints

#### GET `/api/users/{user_id}/tasks`
Return user tasks.

Optional filter:

`/api/users/{user_id}/tasks?statuses=active&statuses=completed`

#### POST `/api/users/{user_id}/tasks`
Create task.

#### GET `/api/users/{user_id}/tasks/{task_id}`
Return one task.

#### PATCH `/api/users/{user_id}/tasks/{task_id}`
Update task partially.

Example:

```json
{
  "priority": 4,
  "duration_minutes": 45,
  "preferred_windows": [
    {
      "start": "2026-05-20T10:00:00Z",
      "end": "2026-05-20T11:30:00Z"
    }
  ]
}
```

#### DELETE `/api/users/{user_id}/tasks/{task_id}`
Delete task.

### Availability window payload

```json
{
  "start": "2026-05-20T09:00:00Z",
  "end": "2026-05-20T12:30:00Z",
  "is_recurring": false,
  "recurrence_rule": null,
  "source": "manual"
}
```

Rules:
- `title` is ignored for availability windows and is always stored as `null`
- if `is_recurring = true`, `recurrence_rule` is required
- supported `recurrence_rule` values:
  - `weekly` = every week on the same weekday as `start`
  - `biweekly` = every 2 weeks on the same weekday as `start`
  - `daily` = every day
  - `custom:<days>` = custom period in days, for example `custom:3`
- if `recurrence_rule` is provided, backend treats the window as recurring even if `is_recurring` was omitted
- recurring windows are expanded only inside the requested `planning_start..planning_end` range during schedule generation

### Availability windows endpoints

#### GET `/api/users/{user_id}/availability-windows`
Return windows.

#### POST `/api/users/{user_id}/availability-windows`
Create window.

#### PATCH `/api/users/{user_id}/availability-windows/{window_id}`
Update window.

#### DELETE `/api/users/{user_id}/availability-windows/{window_id}`
Delete window.

### Busy interval payload

```json
{
  "title": "Lunch",
  "start": "2026-05-20T12:30:00Z",
  "end": "2026-05-20T13:30:00Z",
  "source": "manual",
  "external_event_id": null,
  "payload": {}
}
```

Rules:
- `end > start`

### Busy intervals endpoints

#### GET `/api/users/{user_id}/busy-intervals`
Return intervals.

#### POST `/api/users/{user_id}/busy-intervals`
Create interval.

#### PATCH `/api/users/{user_id}/busy-intervals/{interval_id}`
Update interval.

#### DELETE `/api/users/{user_id}/busy-intervals/{interval_id}`
Delete interval.

## 7. Schedule Generation From Stored Data

These are the main schedule generation endpoints for frontend.

### StoredPlanningRunRequest

```json
{
  "planning_start": "2026-05-20T09:00:00Z",
  "planning_end": "2026-05-20T18:00:00Z",
  "slot_minutes": 15,
  "task_statuses": [
    "active"
  ],
  "settings": {
    "mode": "full",
    "min_break_minutes": 0,
    "max_daily_planned_minutes": 480,
    "max_schedule_variants": 5,
    "use_warm_start": false,
    "replan_from_current_schedule": false
  }
}
```

Important:
- task splitting is configured per task, not in `settings`
- `settings` only controls run-level options like max planned minutes and variant count
- `mode = "quick"` builds only one variant and uses a shorter solver time budget
- `use_warm_start = true` reuses placements from current schedule as solver hints when possible
- `replan_from_current_schedule = true` tries to preserve valid blocks from current schedule and replans around them

### POST `/api/users/{user_id}/schedule-preview-from-stored-data`
Build schedule from DB data and return preview only.

Response:

```json
{
  "planning_request": {},
  "planning_result": {}
}
```

### POST `/api/users/{user_id}/schedule-from-stored-data`
Build schedule from DB data and save it.

When saved:
- previous current schedule becomes `is_current = false`
- new schedule becomes `is_current = true`

### POST `/api/users/{user_id}/best-schedule-from-stored-data`
Run full pipeline:
- load DB data
- generate variants
- score variants
- return best variant

Response:

```json
{
  "variant_id": 1,
  "scheduled_tasks": [],
  "unscheduled_tasks": []
}
```

## 8. Current Schedule API

This API works with saved schedules in DB.

### Current schedule logic
Only one saved schedule per user should be current.

Field:
- `schedules.is_current`

Meaning:
- `true` = current active schedule
- saving a new schedule clears old current schedule

### GET `/api/users/{user_id}/schedules/current`
Return current saved schedule.

Important:
- `scheduled_tasks` in this response contain only the selected variant
- backend does not mix tasks from alternative variants into one timeline

Response shape:

```json
{
  "id": "string",
  "user_id": "string",
  "planning_start": "2026-05-20T09:00:00Z",
  "planning_end": "2026-05-20T18:00:00Z",
  "slot_minutes": 15,
  "status": "success",
  "is_current": true,
  "selected_variant_id": 1,
  "source_request": {},
  "profile_context": {},
  "schedule_metadata": {},
  "created_at": "2026-05-20T08:55:00Z",
  "updated_at": "2026-05-20T08:55:00Z",
  "scheduled_tasks": []
}
```

## 9. Manual Schedule Upload API

Use this when frontend already built the final schedule in UI and needs to save it.

### POST `/api/users/{user_id}/schedules`
Create new manual schedule and mark it as current.

### PUT `/api/users/{user_id}/schedules/current`
Replace current schedule by saving a new manual current schedule.

### Manual schedule payload

```json
{
  "planning_start": "2026-05-20T09:00:00Z",
  "planning_end": "2026-05-20T18:00:00Z",
  "slot_minutes": 15,
  "status": "success",
  "selected_variant_id": 1,
  "source_request": {
    "source": "frontend_manual"
  },
  "profile_context": null,
  "schedule_metadata": {
    "editor": "calendar_ui"
  },
  "scheduled_tasks": [
    {
      "task_id": "task-1",
      "start_at": "2026-05-20T09:00:00Z",
      "end_at": "2026-05-20T10:00:00Z",
      "variant_id": 1,
      "split_part_index": null,
      "split_part_count": null
    },
    {
      "task_id": "task-2",
      "start_at": "2026-05-20T10:15:00Z",
      "end_at": "2026-05-20T11:00:00Z",
      "variant_id": 1,
      "split_part_index": null,
      "split_part_count": null
    }
  ]
}
```

Validation rules:
- every `task_id` must already exist and belong to the user
- every block must stay inside `planning_start..planning_end`
- `start_at` and `end_at` must align with `slot_minutes`
- duration of block must align with `slot_minutes`
- blocks must not overlap
- if the same task appears multiple times, split metadata should be used

## 10. Current Backend Limitation

At the moment:
- `min_break_minutes` must be `0`

If you send another value, backend returns validation failure.

## 11. Recommended Frontend Flows

### Flow A. Normal product flow
1. `POST /api/auth/register`
2. `POST /api/auth/login`
3. `PATCH /api/users/{user_id}/profile`
4. `POST /api/users/{user_id}/tasks`
5. `POST /api/users/{user_id}/availability-windows`
6. `POST /api/users/{user_id}/busy-intervals`
7. `POST /api/users/{user_id}/schedule-preview-from-stored-data`
8. Then one of:
   - `POST /api/users/{user_id}/schedule-from-stored-data`
   - `POST /api/users/{user_id}/best-schedule-from-stored-data`
9. Read saved result:
   - `GET /api/users/{user_id}/schedules/current`

### Flow B. Manual calendar editor
1. Create user tasks in DB
2. Build visual schedule in frontend
3. Save final schedule:
   - `POST /api/users/{user_id}/schedules`
   - or `PUT /api/users/{user_id}/schedules/current`
4. Read current schedule:
   - `GET /api/users/{user_id}/schedules/current`

## 12. Practical Frontend Rules

- Do not send random seconds and milliseconds.
- Do not send durations not divisible by `slot_minutes`.
- If task may be split:

```json
{
  "allow_splitting": true,
  "min_split_part_minutes": 30
}
```

- If task must stay whole:

```json
{
  "allow_splitting": false,
  "min_split_part_minutes": null
}
```

- If task is not fixed:

```json
{
  "is_fixed": false,
  "fixed_start": null
}
```

- If task is fixed:

```json
{
  "is_fixed": true,
  "fixed_start": "2026-05-20T10:00:00Z"
}
```

- Prefer `slot_minutes = 15`.
- If you get alignment errors, check:
  - `planning_start`
  - `planning_end`
  - task duration
  - busy interval start/end
  - manual schedule block start/end
