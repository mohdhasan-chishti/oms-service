# Error Handling Guide: ValueError vs HTTPException

This document defines how to raise and handle errors across OMS so contributors follow a consistent pattern.

Applies to code under:
- `application/app/validations/`
- `application/app/services/`
- `application/app/core/`
- `application/app/routes/`

## Principles
- Domain and validation logic must be framework-agnostic.
- Only the application/presentation boundary should convert domain errors to HTTP responses.
- Never let a 4xx be turned into a 500 by accident.

## Quick Rules (Cheat Sheet)

| Layer | Location | What to raise | Why | Example status mapped |
|---|---|---|---|---|
| Validators (domain) | `app/validations/` | `ValueError` (or custom domain exceptions) | Keep domain free of FastAPI | Mapped to 400 (Bad Request) in core |
| Services (domain) | `app/services/` | `ValueError` (or custom domain exceptions) | Same as above | Mapped to 400/404 depending on context |
| Core / Use-cases (application) | `app/core/` | Catch domain `ValueError` and re-raise `HTTPException` | Translate domain errors to HTTP | 400 for validation; 404 for not-found |
| Routes (presentation) | `app/routes/` | Let `HTTPException` bubble, catch only unexpected exceptions | Avoid converting 4xx into 500 | 500 only for unexpected errors |

## Current Implementation (Returns flow)

- Validators raise `ValueError` only:
  - File: `app/validations/returns.py`
  - Functions: `ReturnsValidator.validate_order_exists_and_status`, `validate_items_exist_and_quantities`, `validate_items_eligibility`, etc.

- Core maps domain errors to HTTP:
  - File: `app/core/order_return.py`
  - Function: `create_return_core()` wraps the whole domain flow in a single `try` block and:
    - re-raises `HTTPException` as-is
    - converts any `ValueError` to `HTTPException(status_code=400, detail=str(e))`

- Route lets HTTPException pass through:
  - File: `app/routes/app/returns.py`
  - Endpoint: `POST /create_return`
  - Re-raises `HTTPException` and converts only unexpected exceptions to `HTTPException(500, "Internal server error")`.

## Do and Don’t

- Do raise `ValueError` from validators/services with human-friendly messages.
- Do translate domain errors to `HTTPException` in the core layer (one place, not many).
- Do let routes re-raise `HTTPException` and return 500 only for unexpected exceptions.
- Don’t import or raise `HTTPException` in `app/validations/` or `app/services/`.
- Don’t swallow `HTTPException` in routes (avoid wrapping 400 into 500).
