# EEE OAU frontend

React application built with Vite.

## Run locally

1. Start the Django API server on `http://127.0.0.1:8000`.
2. Install frontend dependencies with `npm install`.
3. Run `npm run dev` from this directory.

Vite forwards `/api` requests to the Django server. To use a different backend
address, set `VITE_API_PROXY_TARGET` in a local `.env` file, for example:

```dotenv
VITE_API_PROXY_TARGET=http://127.0.0.1:8001
```

The browser API client uses Django session cookies and CSRF tokens. It does not
store credentials or session tokens in local storage. Login requires an
existing backend account; there is no public self-registration endpoint.

The shared API methods and backend contracts are described in [api.md](./api.md).
Only session authentication and password-reset requests are currently wired to
the visible application. Most portal pages still contain prototype data or
actions and should not be treated as live academic records.

## Checks

- `npm run lint`
- `npm run build`
