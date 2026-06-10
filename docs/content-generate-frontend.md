# Content Generation Endpoint

Frontend guide for calling the persisted learning content generation endpoint.

## Endpoint

```http
POST /api/v1/content/generate
Authorization: Bearer <access_token>
Content-Type: application/json
```

This endpoint requires an authenticated active user. It generates a learning path from a topic, saves it to the database under the current user, and returns the saved learning path.

The returned `id` is the persisted `learning_paths.id`.

## Request

```json
{
  "topic": "teach me RAG"
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `topic` | `string` | Yes | Must be at least 1 character. Free-form learning request. |

## Success Response

Status: `200 OK`

```json
{
  "id": 42,
  "topic": "teach me RAG",
  "title": "Practical RAG for Technical Professionals",
  "summary": "A focused learning path for understanding retrieval augmented generation and building a practical RAG workflow.",
  "modules": [
    {
      "order": 1,
      "title": "Retrieval Foundations",
      "learning_objective": "Explain why retrieval improves generation quality.",
      "estimated_minutes": 12,
      "explanation": "Retrieval supplies relevant source context before the model generates an answer.",
      "key_points": [
        "Retrieval narrows the source material.",
        "Generation uses retrieved context to answer."
      ],
      "example": "Search product docs, then answer from the matching sections.",
      "practice_prompt": "List three sources your assistant should retrieve from.",
      "success_criteria": [
        "You can describe retrieval and generation separately.",
        "You can name a useful source corpus."
      ]
    }
  ]
}
```

## TypeScript Types

```ts
export type ContentModule = {
  order: number;
  title: string;
  learning_objective: string;
  estimated_minutes: number;
  explanation: string;
  key_points: string[];
  example: string;
  practice_prompt: string;
  success_criteria: string[];
};

export type ContentResponse = {
  id: number;
  topic: string;
  title: string;
  summary: string;
  modules: ContentModule[];
};
```

## Fetch Example

```ts
export async function generateContent(
  apiBaseUrl: string,
  accessToken: string,
  topic: string,
): Promise<ContentResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/content/generate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ topic }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail ?? `Content generation failed: ${response.status}`);
  }

  return response.json() as Promise<ContentResponse>;
}
```

## Error Responses

| Status | Meaning | Typical UI handling |
| --- | --- | --- |
| `401 Unauthorized` | Missing or invalid access token. | Send user to login or refresh auth token. |
| `403 Forbidden` | User exists but is inactive. | Show account access error. |
| `422 Unprocessable Entity` | Invalid request body, usually empty `topic`. | Show validation message near the input. |
| `503 Service Unavailable` | LLM service is not configured on backend. | Show temporary service unavailable message. |
| `502 Bad Gateway` | LLM returned invalid content shape. | Show retry option. |

## Frontend Notes

- Treat the response as already saved. Do not make a second save request.
- Store `id` if the UI needs to link to this generated learning path later.
- `modules` is ordered by `order`; render using that order.
- `key_points` and `success_criteria` are arrays intended for bullet lists.
- Generation may take longer than normal CRUD requests, so show a loading state.
- There is currently no separate read endpoint documented here for fetching a saved learning path by `id`.
