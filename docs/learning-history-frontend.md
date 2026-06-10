# Learning History Endpoint

Frontend guide for calling the dashboard learning history endpoint.

## Endpoint

```http
GET /api/v1/learning-paths/history
Authorization: Bearer <access_token>
```

This endpoint requires an authenticated active user. It returns the current user's learning history for the dashboard: aggregate stats across all of their learning paths, their most recently updated paths with progress, and a feed of recently read modules.

## Query Parameters

| Parameter | Type | Default | Range | Notes |
| --- | --- | --- | --- | --- |
| `recent_paths_limit` | `number` | `5` | 1–50 | Max paths returned in `recent_paths`. |
| `recent_activity_limit` | `number` | `10` | 1–50 | Max events returned in `recent_activity`. |

## Success Response

Status: `200 OK`

```json
{
  "stats": {
    "total_paths": 4,
    "completed_paths": 1,
    "in_progress_paths": 2,
    "total_modules": 18,
    "read_modules": 9,
    "minutes_read": 117
  },
  "recent_paths": [
    {
      "id": 42,
      "title": "Practical RAG for Technical Professionals",
      "topic": "teach me RAG",
      "progress_percent": 50,
      "is_completed": false,
      "updated_at": "2026-06-09T10:15:00Z",
      "summary": "A focused learning path for understanding retrieval augmented generation.",
      "total_modules": 2,
      "read_modules": 1,
      "estimated_minutes": 27,
      "next_module_id": 88,
      "created_at": "2026-06-08T09:00:00Z"
    }
  ],
  "recent_activity": [
    {
      "learning_path_id": 42,
      "learning_path_title": "Practical RAG for Technical Professionals",
      "module_id": 87,
      "module_title": "Retrieval Foundations",
      "module_order": 1,
      "read_at": "2026-06-09T10:15:00Z"
    }
  ]
}
```

### Field Notes

- `stats` covers all of the user's learning paths, not just the ones in `recent_paths`.
- `in_progress_paths` counts paths with at least one read module that are not completed. Untouched paths are `total_paths - completed_paths - in_progress_paths`.
- `minutes_read` sums `estimated_minutes` of every module the user has marked read.
- `recent_paths` is ordered by most recently updated first and uses the same shape as `GET /api/v1/learning-paths/`.
- `recent_activity` is ordered by most recently read first.

## TypeScript Types

```ts
export type LearningHistoryStats = {
  total_paths: number;
  completed_paths: number;
  in_progress_paths: number;
  total_modules: number;
  read_modules: number;
  minutes_read: number;
};

export type LearningPathSummary = {
  id: number;
  title: string;
  topic: string;
  progress_percent: number;
  is_completed: boolean;
  updated_at: string;
  summary: string;
  total_modules: number;
  read_modules: number;
  estimated_minutes: number;
  next_module_id: number | null;
  created_at: string;
};

export type LearningHistoryActivity = {
  learning_path_id: number;
  learning_path_title: string;
  module_id: number;
  module_title: string;
  module_order: number;
  read_at: string;
};

export type LearningHistory = {
  stats: LearningHistoryStats;
  recent_paths: LearningPathSummary[];
  recent_activity: LearningHistoryActivity[];
};
```

## Fetch Example

```ts
export async function getLearningHistory(
  apiBaseUrl: string,
  accessToken: string,
): Promise<LearningHistory> {
  const response = await fetch(`${apiBaseUrl}/api/v1/learning-paths/history`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `Learning history failed: ${response.status}`);
  }

  return response.json() as Promise<LearningHistory>;
}
```

## Error Responses

| Status | Meaning | Typical UI handling |
| --- | --- | --- |
| `401 Unauthorized` | Missing or invalid access token. | Send user to login or refresh auth token. |
| `403 Forbidden` | User exists but is inactive. | Show account access error. |
| `422 Unprocessable Entity` | Query parameter out of range. | Use defaults; treat as a frontend bug. |

## Frontend Notes

- A brand-new user gets `200 OK` with zeroed `stats` and empty arrays, not an error. Use that to show an empty dashboard state.
- Link `recent_paths` items to the learning path detail view via `GET /api/v1/learning-paths/{id}`; `next_module_id` is the module to resume from.
- Link `recent_activity` items to their path via `learning_path_id`.
- All timestamps are ISO 8601 with timezone; format client-side.
