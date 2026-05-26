---
name: stank-e2e-workflow
description: Browser automation, UX review, frontend debugging, E2E test writing, mock endpoint catalog. Trigger when asked to review UX, debug the dashboard, write E2E tests, take screenshots, or inspect pages. Also trigger when `stank-frontend-patterns` fires and introduces new components/pages/test-ids.
allowed-tools: Bash(playwright-cli:*) Bash(npx:*) Bash(npm:*) Bash(python:*) Bash(curl:*)
---

# StankBot E2E workflow

Teaches agents how to drive the stank-bot dev environment for UX review, debugging, and test improvement. Uses two Playwright tools:

- **playwright-cli** (`@playwright/cli`) — token-efficient CLI commands for quick interactions. Use for everyday tasks.
- **playwright-mcp** (`@playwright/mcp`) — MCP server with rich introspection tools. Use for deep debugging when CLI hits limits. Tools include: `browser_navigate`, `browser_click`, `browser_snapshot`, `browser_take_screenshot`, `browser_console_messages`, `browser_network_requests`, `browser_evaluate`, `browser_wait_for`, `browser_press_key`, `browser_fill_form`.

## Dev environment quick-start

### Ports
| Port | Service |
|------|---------|
| 8000 | Python backend (FastAPI) |
| 5173 | Vite frontend dev server |

### Preferred: use `.mjs` scripts (cross-platform, reliable)

```bash
# One-command: starts backend + frontend, health-polls, opens headed browser, cleans up on Ctrl+C
node scripts/agent-browser.mjs

# Options:
node scripts/agent-browser.mjs --headless     # for background/CI
node scripts/agent-browser.mjs --persistent   # save browser state to disk
```

This script (`scripts/agent-browser.mjs`) is the canonical way to start the full dev environment. It handles:
- Stale process cleanup
- Backend startup + health-check polling
- Frontend startup + readiness polling
- Mock authentication
- Playwright browser launch (headed by default)
- Graceful cleanup on exit

### Alternative: manual startup (use ONLY if agent-browser.mjs isn't suitable)

**IMPORTANT: The Bash tool on this platform runs PowerShell, NOT bash. Avoid bash syntax.**

**PowerShell startup:**

```powershell
# Set env
$env:ENV = 'dev-mock'
$env:PYTHONPATH = 'src'

# Start backend
$bproc = Start-Process -FilePath python -ArgumentList '-m','stankbot' -PassThru -NoNewWindow `
  -RedirectStandardOutput '.stankbot_backend.log' -RedirectStandardError '.stankbot_backend_err.log'
$bproc.Id | Out-File -FilePath '.stankbot_backend.pid'

# Health-check (use curl.exe, not curl)
# Vite binds to localhost, not 127.0.0.1
curl.exe -s http://localhost:8000/healthz

# Start frontend (npm is a .cmd script, needs cmd /c wrapper)
$fproc = Start-Process -FilePath cmd -ArgumentList '/c','npm','run','dev' -PassThru -NoNewWindow `
  -WorkingDirectory 'src\stankbot\web\frontend' `
  -RedirectStandardOutput '.stankbot_frontend.log' -RedirectStandardError '.stankbot_frontend_err.log'
$fproc.Id | Out-File -FilePath '.stankbot_frontend.pid'

# Wait for frontend
curl.exe -s http://localhost:5173
```

**Stopping:**

```powershell
$bpid = Get-Content '.stankbot_backend.pid'; Stop-Process -Id $bpid -Force
$fpid = Get-Content '.stankbot_frontend.pid'; Stop-Process -Id $fpid -Force
```

**Linux/macOS startup (bash):**

```bash
export ENV=dev-mock
export PYTHONPATH="src"
python -m stankbot &
echo $! > /tmp/backend.pid
# Health-check
for i in $(seq 1 60); do
    curl -sf http://localhost:8000/healthz > /dev/null 2>&1 && break
    sleep 0.5
done
cd src/stankbot/web/frontend && npm run dev &
echo $! > /tmp/frontend.pid
```

### Shell pitfalls (Windows/PowerShell)

| Pitfall | Fix |
|---------|-----|
| `curl` is aliased to `Invoke-WebRequest` | Use `curl.exe` (real curl binary) |
| `$pid` is a reserved automatic variable | Use `$bpid`, `$fpid`, `$procId` instead |
| `Start-Process npm` fails ("not a valid Win32 application") | Use `-FilePath cmd -ArgumentList '/c','npm',...` |
| `curl.exe -d '{"key":"val"}'` mangles JSON | Write JSON to temp file: `Set-Content tmp.json '{"key":"val"}'; curl.exe -d @tmp.json` |
| Vite unreachable at `127.0.0.1:5173` | Use `localhost:5173` (Vite binds to localhost, not 127.0.0.1 on Windows) |
| `&&`, `2>&1`, `seq`, `$!` don't work | These are bash syntax; use PowerShell equivalents or .mjs scripts |
| Killing `python.exe`/`node.exe` by name | Kills VS Code, other projects — only kill by tracked PID |

**Critical rules:**
- Track PIDs, never kill by process name
- DB: `data/stankbot_dev.db` (SQLite, persists between runs)
- Mock endpoints only mounted in `ENV=dev-mock`; never call them in `ENV=dev` or `production`

## Authentication

When `ENV=dev-mock`, the `/auth/mock-login` endpoint bypasses Discord OAuth. All mock endpoints work cross-origin from the Vite dev server (port 5173).

### Mock login via curl

**PowerShell (curl.exe + temp file for JSON):**

```powershell
# Default user
Set-Content -Path $env:TEMP\stank_auth.json -Value '{"user_id":111111111,"username":"DevUser","guild":123456789}'
curl.exe -X POST http://localhost:8000/auth/mock-login -H "Content-Type: application/json" -d @$env:TEMP\stank_auth.json

# Admin user
Set-Content -Path $env:TEMP\stank_auth.json -Value '{"user_id":222222222,"username":"Admin","guild":123456789,"is_global_admin":true,"is_guild_admin":true}'
curl.exe -X POST http://localhost:8000/auth/mock-login -H "Content-Type: application/json" -d @$env:TEMP\stank_auth.json
```

**Linux/macOS (bash):**

```bash
curl -X POST http://localhost:8000/auth/mock-login \
  -H "Content-Type: application/json" \
  -d '{"user_id":111111111,"username":"DevUser","guild":123456789}'
```

### Mock login via playwright-cli

```bash
# Navigate to app
playwright-cli open http://localhost:5173

# POST mock login via eval
playwright-cli eval "
  async () => {
    const res = await fetch('/auth/mock-login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user_id:111111111,username:'Agent',guild:123456789})
    });
    return res.ok ? 'ok' : await res.text();
  }
"

# Clear frontend caches and reload
playwright-cli eval "
  () => {
    sessionStorage.removeItem('stankbot:auth');
    sessionStorage.removeItem('stankbot:guilds');
    return 'cleared';
  }
"
playwright-cli reload
```

### Mock login via MCP

Use `browser_navigate` to `http://localhost:5173`, then `browser_evaluate` to call `fetch('/auth/mock-login', ...)`, then `browser_evaluate` to clear sessionStorage, then `browser_navigate` again to reload.

### Pre-built user fixtures

| User | user_id | username | is_global_admin | is_guild_admin |
|------|---------|----------|-----------------|----------------|
| defaultUser | 111111111 | E2E Tester | false | false |
| adminUser | 222222222 | E2E Admin | true | true |
| guildAdminUser | 333333333 | E2E Guild Admin | false | true |

### Cache cleanup

After mock login, the frontend caches must be cleared:

```javascript
sessionStorage.removeItem('stankbot:auth');
sessionStorage.removeItem('stankbot:guilds');
```

### Version sync

To suppress the version-mismatch toast:

```javascript
fetch('/api/version').then(r => r.json()).then(({version}) => {
  localStorage.setItem('stankbot:version', version);
});
```

## Mock game state injection

All endpoints are `POST` with JSON body. Base URL: `http://localhost:8000`.

### Core game events

| Endpoint | Body | Returns | Notes |
|----------|------|---------|-------|
| `/api/mock/stank` | `{guild_id, user_id, display_name}` | `{message_id, chain_id, chain_length, sp_awarded}` | Advances the chain |
| `/api/mock/break` | `{guild_id?, user_id?, display_name?}` | — | Breaks active chain, awards finish bonus |
| `/api/mock/reaction` | `{guild_id, message_id, user_id}` | — | Awards SP to reactor (first-time only) |
| `/api/mock/noise` | — | — | Non-stank message, breaks chain |

### Session control

| Endpoint | Body | Notes |
|----------|------|-------|
| `/api/mock/session/start` | — | Starts a new session |
| `/api/mock/session/end` | — | Ends current session (does NOT clear event history) |

### Background events

| Endpoint | Body | Notes |
|----------|------|-------|
| `/api/mock/random/start` | `{interval?}` | Auto-generate stanks/breaks at interval seconds (default 2) |
| `/api/mock/random/stop` | — | Stop auto events |

### Media

| Endpoint | Body | Returns | Notes |
|----------|------|---------|-------|
| `/api/mock/media` | `{guild_id?, media_type?, name?, history_days?}` | `{id, name}` | Creates fake media item with generated history |
| `/api/mock/clear-media` | `{guild_id?}` | — | Deletes all media |

### Guild config

| Endpoint | Body | Notes |
|----------|------|-------|
| `/api/mock/bot-guilds` | `{guilds: [{id, name, icon?}]}` | Sets bot guilds for guild switcher |

All mock endpoints default to `guild_id=123456789` if not specified.

## Known data-testid selectors

All components use `data-testid` attributes. Use `getByTestId('name')` in Playwright locators.

### Dashboard (`/`)

| Test ID | Element | Notes |
|---------|---------|-------|
| `guild-name` | Guild name header | |
| `live-badge` | WS connection indicator | Title shows "Receiving live updates" |
| `connection-dot` | Dot inside live badge | Green = connected |
| `chain-counter` | Chain length counter | Format: "N stanks" |
| `tile-reactions` | Reactions stat tile | |
| `board-table` | Leaderboard table | |
| `rank-row` | Leaderboard row | `href$="/player/<id>"` |
| `net-score` | Net SP in rank row | Format: "+N SP" or "-N SP" |
| `welcome-login-btn` | Login button | On welcome/unauthenticated page |
| `user-menu-btn` | User menu trigger | Top-right avatar/button |

### Admin templates (`/admin/templates`)

| Test ID | Element | Notes |
|---------|---------|-------|
| `template-select` | Template key dropdown | `<select>` element |
| `template-preview` | Preview render area | Shows rendered embed |
| `template-json` | JSON editor textarea | Edit tab only |
| `tab-edit` | Edit tab button | Switches to JSON editor |
| `tab-preview` | Preview tab button | Switches to rendered view |
| `template-save` | Save button | Persists template |

### Admin settings (`/admin/settings`)

| Test ID | Element | Notes |
|---------|---------|-------|
| `guild-select` | Guild selector | Admin guild switcher |
| `settings-form` | Settings form container | |
| `settings-save` | Save settings button | |

### Common utilities

| Test ID | Element | Notes |
|---------|---------|-------|
| `toast` | Toast notification | Auto-dismiss after 3s |
| `modal-overlay` | Modal backdrop | Click to dismiss |
| `modal-close` | Modal close button | |
| `loading-spinner` | Loading indicator | |
| `error-state` | Error display | Has retry button |
| `empty-state` | Empty/zero-state | |

### Updating this table

When you add a new component with `data-testid`, append a row to the relevant section above. When you discover a selector not listed here during debugging, add it.

## Playwright CLI workflows

### UX review of a page

```bash
# 1. Ensure dev environment is running (see quick-start above)
# 2. Open browser (headed for visual review)
playwright-cli open http://localhost:5173 --headed

# 3. Authenticate
playwright-cli eval "
  async () => {
    const res = await fetch('/auth/mock-login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user_id:111111111,username:'Reviewer',guild:123456789})
    });
    sessionStorage.removeItem('stankbot:auth');
    sessionStorage.removeItem('stankbot:guilds');
    const v = await fetch('/api/version').then(r => r.json());
    localStorage.setItem('stankbot:version', v.version);
    return res.ok;
  }
"
playwright-cli reload

# 4. Wait for WS connection
playwright-cli eval "
  () => {
    const badge = document.querySelector('[data-testid=\"live-badge\"]');
    return badge ? badge.getAttribute('title') : 'not found';
  }
"

# 5. Take snapshot and screenshot
playwright-cli snapshot --filename=review/page-snapshot.yaml
playwright-cli screenshot --filename=review/page.png

# 6. Inspect specific elements
playwright-cli snapshot [data-testid="board-table"]
playwright-cli snapshot [data-testid="chain-counter"]

# 7. Interactive UX review (user annotates, you get annotated screenshot + notes)
playwright-cli show --annotate

# 8. Cleanup
playwright-cli close
```

### Debugging a broken flow

```bash
playwright-cli open http://localhost:5173 --headed

# Check JS errors
playwright-cli console error

# Check all console output
playwright-cli console

# Inspect network requests
playwright-cli requests

# Detail on a specific request
playwright-cli request 3

# Inject state and observe
playwright-cli eval "
  async () => {
    await fetch('/api/mock/stank', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({guild_id:123456789,user_id:999,display_name:'Debug'})
    });
    return 'injected';
  }
"
playwright-cli snapshot [data-testid="chain-counter"]
```

### Inspecting element attributes

```bash
# Get element id, class, or any attribute not in the snapshot
playwright-cli eval "el => el.id" [data-testid="chain-counter"]
playwright-cli eval "el => el.getAttribute('class')" [data-testid="chain-counter"]
playwright-cli eval "el => el.textContent" [data-testid="chain-counter"]
```

### Snapshot comparison (before/after)

```bash
playwright-cli --raw snapshot > before.yml
playwright-cli click [data-testid="tab-edit"]
playwright-cli --raw snapshot > after.yml
diff before.yml after.yml
```

### Interactive debugging

```bash
# Click an element
playwright-cli click [data-testid="chain-counter"]

# Fill a field
playwright-cli fill [data-testid="template-json"] '{"title":"Test"}'

# Press a key
playwright-cli press Enter

# Navigate
playwright-cli goto /admin/templates

# Resize for mobile viewport
playwright-cli resize 375 812
```

### Recording for later analysis

```bash
playwright-cli open http://localhost:5173 --headed
playwright-cli tracing-start
# ... perform interactions ...
playwright-cli tracing-stop
playwright-cli video-start debug.webm
# ... perform interactions ...
playwright-cli video-stop
playwright-cli close
```

### Generating Playwright locators from refs

```bash
playwright-cli snapshot
# Find the ref (e.g., e23) for the element you want
playwright-cli generate-locator e23
# Output: page.getByTestId('chain-counter')
```

### Highlighting elements

```bash
playwright-cli highlight [data-testid="chain-counter"]
playwright-cli highlight [data-testid="chain-counter"] --style="outline: 3px dashed red"
playwright-cli highlight --hide
```

## MCP workflows

MCP tools are available when the playwright MCP server is running (configured in opencode config). Use them for deeper inspection.

### Navigate + inspect

1. `browser_navigate` → `http://localhost:5173`
2. `browser_wait_for` → wait for page load
3. `browser_snapshot` → get accessibility tree
4. `browser_take_screenshot` → visual capture

### Authenticate via MCP

1. `browser_navigate` → `http://localhost:5173`
2. `browser_evaluate` → `fetch('/auth/mock-login', ...)` to log in
3. `browser_evaluate` → clear sessionStorage
4. `browser_navigate` → reload

### Fill forms

```json
{
  "fields": [
    {"target": "[data-testid='template-json']", "value": "{\"title\":\"test\"}"},
    {"target": "[data-testid='template-select']", "value": "board_embed"}
  ]
}
```

### Debug console + network

- `browser_console_messages` → `{level: "error"}` for JS errors
- `browser_network_requests` → `{static: false}` for API calls only
- `browser_network_request` → `{index: 3}` for full request/response details

### Run arbitrary Playwright code

`browser_run_code_unsafe` accepts a JavaScript function receiving `page`:

```javascript
async (page) => {
  await page.getByTestId('chain-counter').textContent();
  const frames = [];
  page.on('websocket', ws => {
    ws.on('framereceived', frame => {
      if (frame.payload instanceof Buffer) frames.push(frame.payload);
    });
  });
  await page.reload();
  await page.waitForTimeout(2000);
  return frames.length;
}
```

## Running E2E tests

### Full suite (auto-starts backend)

```bash
cd src/stankbot/web/frontend
npm run e2e
```

### Specific file or pattern

```bash
npm run e2e -- board.spec.ts
npm run e2e -- --grep "chain break"
```

### Direct Playwright (servers already running)

```bash
cd src/stankbot/web/frontend
npx playwright test --project=e2e
npx playwright test --project=e2e board.spec.ts
npx playwright test --project=e2e --grep "chain break"
```

### HTML report

```bash
npx playwright show-report
```

## Writing E2E tests

### Template for new test file

```typescript
import { test, expect } from './fixtures';

test.describe('FeatureName', () => {
    test.beforeEach(async ({ mockLogin, newSession }) => {
        await mockLogin();
        await newSession();
    });

    test('does something', async ({ page }) => {
        // Arrange
        await expect(page.locator('[data-testid="target"]')).toBeVisible();

        // Act
        // ...

        // Assert
        await expect(page.locator('[data-testid="result"]')).toHaveText('expected');
    });
});
```

### Rules

1. **Import from `./fixtures`** — use `test` and `expect` from `./fixtures.ts`, NOT from `@playwright/test` directly
2. **Use `data-testid` selectors** — `page.getByTestId('name')` or `page.locator('[data-testid="name"]')`
3. **Unique user IDs** — `Date.now() % 1_000_000_000` to avoid DB pollution across runs
4. **Start fresh** — `mockLogin()` + `newSession()` in `beforeEach` (breaks chain, ends session, reloads)
5. **Prefer fixtures** — use `injectStank()`, `injectBreak()`, etc. over manual API calls
6. **WS frame capture** — use `page.on('websocket', ws => ws.on('framereceived', ...))` — NOT `'frames'`

### Fixture reference

| Fixture | Signature | Notes |
|---------|-----------|-------|
| `mockLogin` | `(user?: MockUser) => Promise<void>` | Authenticates, reloads page, clears caches, syncs version |
| `mockBotGuilds` | `(guilds: BotGuild[]) => Promise<void>` | Sets bot guilds, clears sessionStorage guld cache |
| `newSession` | `() => Promise<void>` | Breaks chain, ends session, reloads |
| `injectStank` | `(guildId: number, userId: number, displayName: string) => Promise<{message_id, chain_id, chain_length, sp_awarded}>` | Triggers stank, asserts response OK |
| `injectBreak` | `(guildId: number, userId: number, displayName: string) => Promise<void>` | Triggers chain break |
| `injectReaction` | `(guildId: number, messageId: number, userId: number) => Promise<void>` | Injects reaction bonus |
| `startRandomEvents` | `(interval?: number) => Promise<void>` | Auto-generates events every N seconds (default 2) |
| `stopRandomEvents` | `() => Promise<void>` | Stops auto events |
| `injectMedia` | `(opts?: {guildId?, mediaType?, slug?, historyDays?}) => Promise<{id, name}>` | Creates fake media item |
| `clearMedia` | `(guildId?: number) => Promise<void>` | Deletes all media |

### MockUser shape

```typescript
interface MockUser {
  user_id: number;
  username: string;
  avatar?: string | null;
  guild?: number;
  is_global_admin?: boolean;
  is_guild_admin?: boolean;
}
```

### BotGuild shape

```typescript
interface BotGuild {
  id: number;
  name: string;
  icon?: string | null;
}
```

## WebSocket frame interception

When debugging WS messages or writing tests that assert on server-pushed data:

```typescript
const frames: Buffer[] = [];
page.on('websocket', (ws) => {
    ws.on('framereceived', (frame) => {
        if (frame.payload instanceof Buffer) frames.push(frame.payload);
    });
});
// Set up BEFORE page.reload() or page.goto()
```

For msgpack binary frames, decode with:

```typescript
import { unpack } from 'msgpackr';
const data = unpack(new Uint8Array(frame.payload));
```

## Pitfall catalog

| Pitfall | Cause | Fix |
|---------|-------|-----|
| SPA navigation doesn't reload stores | `+layout.ts` caches data | `mockLogin()` does `page.reload()`; otherwise manually reload |
| `StatTile` value missing in E2E | `testId` targets wrapper, not value | Use `valueTestId` prop (e.g., `valueTestId="chain-counter"`) |
| API calls fail with `ECONNREFUSED` | Backend not running | Vite proxies to `localhost:8000` — ensure backend is up |
| WS events not captured in Playwright | `'frames'` event unreliable | Use `'framereceived'` event (fires per-message) |
| `bind:this` resolves after `onMount` | Svelte 5 lifecycle quirk | Use `$effect` + `tick()` for bound element access |
| Hardcoded user IDs cause flaky SP/PP assertions | DB persists across runs | Use `Date.now() % 1_000_000_000` for unique IDs |
| Killing `python.exe` / `node.exe` kills editor/other projects | Process name ambiguous | Track PIDs: `echo $! > /tmp/backend.pid`; kill only by PID |
| Vite caches stale components | In-memory Vite compilation | Kill the Node dev server process and restart |
| Mock endpoints 404 | Wrong `ENV` | Mock endpoints only mount in `ENV=dev-mock` |
| MsgType enum constants out of sync | Frontend/backend drifted | See `stank-ws-protocol` skill — update both sides |
| Multiple WS connections | No dedup guard | `ws?.readyState === WebSocket.OPEN` before creating new |

## Session management (playwright-cli)

```bash
# Named session for stankbot (avoids conflict with other projects)
playwright-cli -s=stankbot open http://localhost:5173 --headed --persistent

# List all sessions
playwright-cli list

# Close stankbot session
playwright-cli -s=stankbot close

# Close all browsers
playwright-cli close-all

# Force kill all (emergency)
playwright-cli kill-all
```

## Keeping this skill current

You MUST update this file when any of the following changes:

| Trigger | What to update |
|---------|---------------|
| New Svelte component added with `data-testid` | Append to **Known data-testid selectors** table in the correct page section |
| New mock API endpoint added or existing changed | Update **Mock game state injection** tables |
| New E2E fixture added to `e2e/fixtures.ts` | Add to **Fixture reference** table |
| New pitfall discovered during debugging | Append to **Pitfall catalog** |
| Dev startup flow changes (ports, env vars) | Update **Dev environment quick-start** section |
| New page/route added | Add its selectors to the **Known data-testid selectors** tables |
| New E2E test pattern emerges | Add example to **Writing E2E tests** section |
| Playwright CLI/MCP gets new features | Update relevant workflow section |

**How to update:**
1. Read the source file to confirm the current state
2. Edit this file (`.opencode/skills/stank-e2e-workflow/SKILL.md`)
3. Keep the same format — tables for selectors/endpoints, code blocks for commands
4. No explanatory commentary — just the facts
5. Bump the `LAST_UPDATED` date below

<!-- LAST_UPDATED: 2026-05-26 | VERSION: 1.0.0 -->
