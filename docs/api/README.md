# API

FastAPI generates interactive documentation at `/api/docs` and the OpenAPI
schema at `/api/openapi.json`. That is the authoritative reference; this file
covers the conventions behind it.

## Authentication

All endpoints except `/api/health` and the two public auth endpoints require
`Authorization: Bearer <token>`. Tokens are obtained from `/api/auth/login`
and expire after `ACCESS_TOKEN_EXPIRE_MINUTES`.

Logging out is the client discarding its token. Tokens are stateless and
self-expiring, so there is no server-side session to destroy; revoking a token
early would need a deny list, which FYP1 does not implement.

## Status codes

| Code | Meaning in this API |
|---|---|
| 200 | Success |
| 201 | Created |
| 401 | Missing, malformed or expired token; or wrong credentials |
| 404 | Not found, **or** owned by another user |
| 409 | Duplicate: email already registered, period label reused, record already entered |
| 422 | Request failed validation, including the accounting identity |

A resource belonging to another user returns 404 rather than 403, so the API
does not confirm which identifiers exist.

## Validation errors

Field-level failures use FastAPI's standard 422 shape. A cross-field failure
returns the reasons explicitly:

```json
{
  "detail": {
    "message": "Financial data failed validation.",
    "errors": ["Accounting identity does not hold: total assets differ from liabilities plus equity by 100,000.00."]
  }
}
```

## Not-applicable indicators

An indicator that cannot be calculated returns `value: null`, `score: null`,
`status: "not_applicable"` and a `note` explaining why. It is never returned as
zero, and it is never omitted — all ten are always present.
