# ARMENTA OS — Auth Testing Playbook

Save this alongside `/app/memory/test_credentials.md`. The testing agent
should read this file before validating auth-gated flows.

---

## Two supported auth paths

1. **Custom JWT (username/password)** — existing flow. Token in
   `Authorization: Bearer <jwt>` header, stored in `localStorage` under
   `armenta_os_session_v1`.

2. **Emergent managed Google Sign-In** — new. `session_token` httpOnly cookie
   named `session_token`, stored server-side in `db.user_sessions`.

Both are accepted by `get_current_user` — the dependency tries the Bearer
header first, then falls back to the cookie.

---

## Step 1 · Seed a test session via Mongo (Google path)

```
mongosh --eval "
use('armenta_os');
var uid = 'test-user-' + Date.now();
var token = 'test_session_' + Date.now();
db.users.insertOne({
  id: uid, username: 'test@example.com', email: 'test@example.com',
  name: 'Test User', role: 'admin', google_linked: true,
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  session_token: token, user_id: uid,
  expires_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
  created_at: new Date().toISOString()
});
print('session_token: ' + token);
print('user_id: ' + uid);
"
```

## Step 2 · Backend smoke

```
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# JWT flow (unchanged)
TOKEN=$(curl -s -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"identifier":"admin","password":"armenta123"}' | jq -r .token)
curl -s "$API/api/auth/me" -H "Authorization: Bearer $TOKEN"

# Cookie flow with the seeded session_token
curl -s "$API/api/auth/me" -H "Cookie: session_token=<PASTE_TOKEN>"

# Missing/invalid credentials
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/auth/me"                        # 401
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/auth/me" -H "Cookie: session_token=bogus"  # 401
```

## Step 3 · Google flow browser test (Playwright)

The exact OAuth handshake with `auth.emergentagent.com` cannot be replayed
without the real Google account. Instead, simulate the return leg by seeding
a `user_sessions` row (Step 1) and pre-loading the cookie:

```python
await context.add_cookies([{
    "name": "session_token",
    "value": "<PASTE_TOKEN>",
    "domain": "armenta-hub.preview.emergentagent.com",
    "path": "/",
    "httpOnly": True,
    "secure": True,
    "sameSite": "None",
}])
await page.goto("https://armenta-hub.preview.emergentagent.com/control")
# Should render dashboard without redirect to /login
```

Also verify the `#session_id=...` fragment path by visiting:
`/control#session_id=<ID>` after a real Google login via the "Continuar con
Google" button. Frontend calls `POST /api/auth/session` with header
`X-Session-ID`, receives a `Set-Cookie: session_token=...` and the URL hash
is scrubbed via `history.replaceState`.

## Step 4 · Logout parity

- JWT logout: `POST /api/auth/logout` with Bearer → responds `{ok:true}`;
  client drops localStorage entry.
- Google logout: `POST /api/auth/logout` with cookie → deletes the row in
  `db.user_sessions`, sets `Set-Cookie: session_token=; Max-Age=0`.

## Step 5 · Cleanup

```
mongosh --eval "
use('armenta_os');
db.users.deleteMany({email: /test@example/});
db.user_sessions.deleteMany({session_token: /^test_session_/});
"
```

## Success indicators

- ✅ `GET /api/auth/me` returns the same user object whether we authenticate
  by Bearer JWT or by `session_token` cookie.
- ✅ Frontend Login screen renders the "Continuar con Google" button below
  the username/password form.
- ✅ Landing at `/control#session_id=X` triggers `POST /api/auth/session`,
  scrubs the URL hash, and shows the dashboard.
- ✅ `POST /api/auth/logout` invalidates the cookie session in Mongo.

## Failure indicators

- ❌ `/api/auth/me` returns 401 while a valid `session_token` cookie is
  attached — likely a stale `expires_at` timezone bug.
- ❌ CORS preflight fails — origin must match `FRONTEND_URL` and
  `allow_credentials=True` (wildcard is rejected by browsers with cookies).
- ❌ "Continuar con Google" navigates to `auth.emergentagent.com` but the
  return hits `/control#session_id=` with no exchange — check that
  `AuthContext` runs the callback BEFORE `/auth/me` bootstrap.
