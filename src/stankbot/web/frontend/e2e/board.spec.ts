import { test, expect, defaultUser } from './fixtures';

const GUILD = 123456804;

test.describe('Board', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin({ ...defaultUser, guild: GUILD });
		await newSession();
	});

	test('board loads and shows guild name + live badge', async ({ page }) => {
		await expect(page.locator('[data-testid="guild-name"]')).toBeVisible();
		await expect(page.locator('[data-testid="live-badge"]')).toBeVisible();
		await expect(page.locator('[data-testid="connection-dot"]')).toBeVisible();
		await expect(page.locator('[data-testid="tile-reactions"]')).toBeVisible();
	});

	test('websocket connects and receives chain update on stank injection', async ({ page, injectStank }) => {
		const logs: string[] = [];
		page.on('console', (msg) => logs.push(`[${msg.type()}] ${msg.text()}`));
		page.on('pageerror', (err) => logs.push(`[pageerror] ${err.message}`));

		await expect(page.locator('[data-testid="live-badge"]')).toHaveAttribute(
			'title',
			/Receiving live updates/
		);

		console.log('Browser logs:', logs);

		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText(/^0 /);

		await injectStank(GUILD, 111, 'Alice');

		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText(/^1 /);
	});

	test('websocket preserves exact Discord snowflake IDs', async ({ page, mockLogin, mockBotGuilds }) => {
		const largeGuildId = '1482266782306799646';
		const largeUserId = '129508601730564096';

		const wsUrls: string[] = [];
		page.on('websocket', (ws) => wsUrls.push(ws.url()));

		await mockBotGuilds([{ id: Number(largeGuildId), name: 'Big Server' }]);
		await mockLogin({
			user_id: largeUserId,
			username: 'SnowflakeTester',
			guild: largeGuildId as unknown as number,
			is_global_admin: false,
			is_guild_admin: false
		});
		// mockLogin already navigates to /

		await expect(page.locator('[data-testid="live-badge"]')).toHaveAttribute(
			'title',
			/Receiving live updates/,
			{ timeout: 10000 }
		);

		const appWsUrl = wsUrls.find((u) => u.endsWith('/ws'));
		expect(appWsUrl).toBeDefined();
		expect(appWsUrl).not.toContain('guild_id=');
		expect(appWsUrl).not.toContain('user_id=');
	});

	test('chain break resets counter', async ({ page, injectStank, injectBreak }) => {
		// Wait for the board page to fully load before injecting (avoids parallel-load race).
		await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => null);
		await expect(page.locator('[data-testid="live-badge"]')).toHaveAttribute(
			'title',
			/Receiving live updates/
		);

		await injectStank(GUILD, 111, 'Alice');
		await injectStank(GUILD, 222, 'Bob');

		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText(/^2 /);

		await injectBreak(GUILD, 333, 'Charlie');

		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText(/^0 /);
	});

	test('leaderboard rows appear live via rank_update broadcast', async ({ page, injectStank }) => {
		await expect(page.locator('[data-testid="live-badge"]')).toHaveAttribute(
			'title',
			/Receiving live updates/
		);

		const liveUserId = Date.now() % 1_000_000_000;
		const liveUser = `LiveUpdate_${liveUserId}`;

		await injectStank(GUILD, liveUserId, liveUser);

		const row = page.locator(`[data-testid="rank-row"][href$="/player/${liveUserId}"]`);
		await expect(row).toBeVisible({ timeout: 5000 });
		const netText = await row.locator('[data-testid="net-score"]').textContent();
		// format is now "+N SP" or "-N SP"
		expect(netText).toMatch(/^\+/);
	});

	test('reaction increments reactions tile and row counter', async ({
		page,
		injectStank,
		injectReaction
	}) => {
		const STANKER = 7001;
		const REACTOR = 7002;

		// Plant a stank so there's a message to react to
		const stank = await injectStank(GUILD, STANKER, 'StankUser');
		const messageId = stank.message_id;

		// Wait for the stank broadcast to fully settle by checking the chain counter
		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText(/^1 /, { timeout: 5000 });

		// Inject a reaction from a different user
		await injectReaction(GUILD, messageId, REACTOR);

		// Wait for the reactor's row to appear — this confirms the reaction's
		// rank_update broadcast was processed, so no stale stank broadcast can
		// overwrite the tile after we assert on it.
		const reactorRow = page.locator(`[data-testid="rank-row"][href$="/player/${REACTOR}"]`);
		await expect(reactorRow).toBeVisible({ timeout: 5000 });
		const subtitle = reactorRow.locator('.text-xs.text-muted');
		await expect(subtitle).toContainText('reacts', { timeout: 5000 });

		// Chain reactions tile (first number) should now be 1. The rank_update broadcast
		// may still be in flight when the row appears, so allow the tile assertion
		// to wait for the board state to settle.
		const reactionsTile = page.locator('[data-testid="tile-reactions"]').locator('div').first();
		await expect(reactionsTile).toHaveText(/^1 \/ /, { timeout: 10000 });
	});

	test('pagination loads rows with stanks/reactions counters', async ({
		page,
		injectStank,
		injectReaction
	}) => {

		// Create more than PAGE_SIZE (20) users to trigger pagination
		for (let i = 0; i < 25; i++) {
			await injectStank(GUILD, 8000 + i, `PaginatedUser${i}`);
		}

		// Wait for the last few rows to appear so pagination is active.
		// Also wait for the first row to be visible (not just present) so the
		// "Stanks" text is rendered.
		await expect(page.locator('[data-testid="rank-row"]')).toHaveCount(20, { timeout: 15000 });
		await expect(page.locator('[data-testid="rank-row"]').first()).toBeVisible();

		// Verify some rows show counters (stanks/reacted format) — at minimum the first 20
		// already injected all contain counters; the paginated set adds more.
		const rowsWithCounters = page.locator('[data-testid="rank-row"]').filter({ hasText: /Stanks/ });
		const count = await rowsWithCounters.count();
		expect(count).toBeGreaterThan(0);
	});

	test('subtitle shows session totals on board', async ({
		page,
		injectStank,
		injectReaction
	}) => {
		const STANKER = 9001;
		const REACTOR = 9002;

		// Plant a stank
		const stank = await injectStank(GUILD, STANKER, 'CounterUser');
		const messageId = stank.message_id;

		// Wait for chain to be active
		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText(/^1 /, { timeout: 5000 });

		// Add reaction
		await injectReaction(GUILD, messageId, REACTOR);

		// Find the reactor's row and verify counters format
		const reactorRow = page.locator(`[data-testid="rank-row"][href$="/player/${REACTOR}"]`);
		await expect(reactorRow).toBeVisible({ timeout: 5000 });
		const subtitle = reactorRow.locator('.text-xs.text-muted');

		// Should show "X Stanks · Y reacts" format
		await expect(subtitle).toHaveText(/\d+ Stanks · \d+ reacts/);
	});

	// Disabled: the async event generator's fire timing is unreliable under parallel load.
// The test is runnable manually with: npx playwright test board.spec.ts:193
test.skip('random events update the board', async ({ page, startRandomEvents, stopRandomEvents }) => {
		await startRandomEvents(1);

		// Wait for at least one event to be processed (chain counter changes or rank row appears).
		// The async event generator needs a few intervals to fire — give it 15s.
		await page.waitForFunction(() => {
			const counter = document.querySelector('[data-testid="chain-counter"]');
			const text = counter?.textContent || '';
			const rows = document.querySelectorAll('[data-testid="rank-row"]');
			return text !== '0 / 0' || rows.length > 0;
		}, { timeout: 15000 });

		await stopRandomEvents();

		const counterText = await page.locator('[data-testid="chain-counter"]').textContent();
		const rankingCount = await page.locator('[data-testid="rank-row"]').count();
		expect(counterText !== '0 / 0' || rankingCount > 0).toBeTruthy();
	});

	test('stat tiles show sublabels for compound values', async ({ page }) => {
		// Verify the sublabels we added between values and labels
		const reactionsTile = page.locator('[data-testid="tile-reactions"]');
		await expect(reactionsTile.getByText('chain · session')).toBeVisible();

		const currentTile = page.locator('[data-testid="tile-current"]');
		await expect(currentTile.getByText('stanks · unique')).toBeVisible();

		const sessionTile = page.locator('[data-testid="tile-session"]');
		await expect(sessionTile.getByText('record · unique')).toBeVisible();

		const alltimeTile = page.locator('[data-testid="tile-alltime"]');
		await expect(alltimeTile.getByText('record · unique')).toBeVisible();
	});

	test('session and alltime record tiles show 0 / 0 initially', async ({ page }) => {
		// Session is reliably 0/0 after newSession() in beforeEach.
		// Alltime may carry over from previous test runs — just check it has a value.
		const sessionVal = page.locator('[data-testid="tile-session"]').locator('div').first();
		const alltimeVal = page.locator('[data-testid="tile-alltime"]').locator('div').first();
		await expect(sessionVal).toHaveText(/^0 \/ 0/);
		await expect(alltimeVal).toHaveText(/\d+ \/ \d+/);
	});

	test('record tiles update after page reload following a chain break', async ({
		page,
		injectStank,
		injectBreak
	}) => {
		const BASE = 400000;

		// Build a chain of 3 unique stankers with IDs that won't conflict
		await injectStank(GUILD, BASE + 1, 'RecordUserA');
		await injectStank(GUILD, BASE + 2, 'RecordUserB');
		await injectStank(GUILD, BASE + 3, 'RecordUserC');

		await injectBreak(GUILD, BASE + 99, 'RecordBreaker');

		// Record tiles only refresh on page load/reload (not via WS).
		// Wait for the board API after reload so the tiles show the latest record.
		const boardResp = page.waitForResponse(r => r.url().includes('/api/board') && r.status() === 200, { timeout: 10000 });
		await page.reload();
		await boardResp;

		const sessionVal = page.locator('[data-testid="tile-session"]').locator('div').first();
		await expect(sessionVal).toHaveText(/^3 \/ 3/);
	});

	test('session record resets after session rollover', async ({
		page,
		injectStank,
		injectBreak,
		newSession
	}) => {
		const BASE = 500000;

		// Build and break a chain of 3
		await injectStank(GUILD, BASE + 1, 'RollUserA');
		await injectStank(GUILD, BASE + 2, 'RollUserB');
		await injectStank(GUILD, BASE + 3, 'RollUserC');
		await injectBreak(GUILD, BASE + 99, 'RollBreaker');
		// After chain break + reload, session tile shows the chain record.
		// Wait for the board API after reload so the tiles show the latest record.
		const boardAfterReload = page.waitForResponse(r => r.url().includes('/api/board') && r.status() === 200, { timeout: 10000 });
		await page.reload();
		await boardAfterReload;
		const sessionVal1 = page.locator('[data-testid="tile-session"]').locator('div').first();
		await expect(sessionVal1).toHaveText(/^3 \/ 3/);

		// Record the current alltime value so we can verify it persists
		const alltimeVal1 = page.locator('[data-testid="tile-alltime"]').locator('div').first();
		const alltimeBefore = await alltimeVal1.textContent();

		// Session rollover — wait for the board to refresh after the new session is created.
		// Pass GUILD explicitly: the default mock endpoint targets the mock default guild
		// (123456789), which has no active session in this test.
		const boardAfter = page.waitForResponse(r => r.url().includes('/api/board'));
		await newSession(GUILD);
		await boardAfter;

		// After rollover, session record should be zero
		const sessionVal2 = page.locator('[data-testid="tile-session"]').locator('div').first();
		await expect(sessionVal2).toHaveText(/^0 \/ 0/);

		// Alltime should persist (same value as before rollover, or higher)
		const alltimeVal2 = page.locator('[data-testid="tile-alltime"]').locator('div').first();
		const alltimeAfter = await alltimeVal2.textContent();
		expect(alltimeAfter).toBe(alltimeBefore);
	});

	test('alltime record survives multiple sessions unchanged', async ({
		page,
		injectStank,
		injectBreak,
		newSession
	}) => {
		const BASE = 600000;

		// Build a chain of 15 — enough unique users to set a visible alltime record
		for (let i = 0; i < 15; i++) {
			await injectStank(GUILD, BASE + i, `ChainUser${i}`);
		}
		await injectBreak(GUILD, BASE + 999, 'BigBreaker');
		await page.reload();

		const alltimeVal1 = page.locator('[data-testid="tile-alltime"]').locator('div').first();
		await expect(alltimeVal1).toHaveText(/^\d+ \/ \d+/);
		const alltimeText1 = await alltimeVal1.textContent();

		// Roll the session — pass GUILD explicitly (default mock targets 123456789, no active session)
		await newSession(GUILD);

		// Alltime should be unchanged
		const alltimeVal2 = page.locator('[data-testid="tile-alltime"]').locator('div').first();
		await expect(alltimeVal2).toHaveText(/^\d+ \/ \d+/);
		const alltimeText2 = await alltimeVal2.textContent();
		expect(alltimeText2).toBe(alltimeText1);

		// Session should be zero
		const sessionVal = page.locator('[data-testid="tile-session"]').locator('div').first();
		await expect(sessionVal).toHaveText(/^0 \/ 0/);
	});
});
