import { test, expect } from './fixtures';

test.describe('Player profile page', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin();
		await newSession();
	});

	test('player profile loads after stank injection', async ({ page, injectStank }) => {
		const GUILD = 123456789;
		const USER = 7001;

		await injectStank(GUILD, USER, 'TestPlayer');
		await page.goto(`/player/${USER}`);

		await expect(page.getByText('TestPlayer')).toBeVisible({ timeout: 10000 });
		await expect(page.getByRole('heading', { name: 'Session' })).toBeVisible();
		await expect(page.getByText('All-time')).toBeVisible();
	});

	test('player profile shows SP and PP values', async ({ page, injectStank, injectBreak }) => {
		const GUILD = 123456789;
		const STANKER = 7002;
		const BREAKER = 7003;

		await injectStank(GUILD, STANKER, 'StankerUser');
		await injectBreak(GUILD, BREAKER, 'BreakerUser');

		await page.goto(`/player/${STANKER}`);
		await expect(page.getByText('StankerUser')).toBeVisible({ timeout: 10000 });
		await expect(page.getByText('SP').first()).toBeVisible();
	});

	test('player profile shows avatar, rank badge, and streak', async ({ page, injectStank }) => {
		const GUILD = 123456789;
		const USER = 7010;

		await injectStank(GUILD, USER, 'PlayerWithRank');
		await page.goto(`/player/${USER}`);

		await expect(page.getByText('PlayerWithRank')).toBeVisible({ timeout: 10000 });
		// Rank badge is visible as #1
		await expect(page.getByText('#1', { exact: true })).toBeVisible({ timeout: 5000 });
	});
});

test.describe('Session detail page', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin();
		await newSession();
	});

	test('session detail page loads with session data', async ({ page, injectStank }) => {
		const GUILD = 123456789;

		await injectStank(GUILD, 9001, 'SessionUser');

		await page.goto('/sessions');
		await expect(page.getByText('Session History')).toBeVisible({ timeout: 10000 });

		const sessionLink = page.locator('a[href*="/session/"]').first();
		await sessionLink.click();

		await expect(page.getByRole('heading', { name: 'Summary' })).toBeVisible({ timeout: 10000 });
	});

	test('session detail shows SP/PP totals', async ({ page, injectStank, injectBreak }) => {
		const GUILD = 123456789;
		const USER = 9010;

		await injectStank(GUILD, USER, 'SPTestUser');
		await injectBreak(GUILD, 9011, 'BreakerUser');

		await page.goto('/sessions');
		const sessionLink = page.locator('a[href*="/session/"]').first();
		await sessionLink.click();

		await expect(page.getByText('Total SP').first()).toBeVisible({ timeout: 10000 });
	});
});

test.describe('Sessions list page', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin();
		await newSession();
	});

	test('sessions list shows entries after activity', async ({ page, injectStank }) => {
		const GUILD = 123456789;

		await injectStank(GUILD, 10001, 'ListUser');
		await page.goto('/sessions');

		await expect(page.getByText('Session History')).toBeVisible({ timeout: 10000 });
		const sessionLinks = page.locator('a[href*="/session/"]');
		await expect(sessionLinks.first()).toBeVisible({ timeout: 10000 });
	});

	test('session list shows SP/PP and duration', async ({ page, injectStank }) => {
		const GUILD = 123456789;

		await injectStank(GUILD, 10101, 'StatsUser');
		await page.goto('/sessions');

		await expect(page.getByText('SP:').first()).toBeVisible({ timeout: 10000 });
		await expect(page.getByText('PP:').first()).toBeVisible({ timeout: 10000 });
	});
});

test.describe('Chain detail page', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin();
		await newSession();
	});

	test('chain page shows chain totals in subtitle', async ({ page, injectStank }) => {
		const GUILD = 123456789;

		const stank1 = await injectStank(GUILD, 5001, 'ChainStanker');
		const chainId = stank1.chain_id;

		await injectStank(GUILD, 5002, 'SecondStanker');

		await page.goto(`/chain/${chainId}`);

		await expect(page.getByText('ChainStanker').first()).toBeVisible({ timeout: 10000 });
		const rows = page.locator('[data-testid="rank-row"]');
		await expect(rows.first()).toBeVisible({ timeout: 10000 });
		const subtitle = rows.first().locator('.text-xs.text-muted');
		await expect(subtitle).toContainText('Stanks ·', { timeout: 5000 });
	});

	test('chain page shows timeline', async ({ page, injectStank }) => {
		const GUILD = 123456789;

		const stank1 = await injectStank(GUILD, 5003, 'TimelineUser');
		const chainId = stank1.chain_id;

		await injectStank(GUILD, 5004, 'SecondUser');

		await page.goto(`/chain/${chainId}`);

		const timeline = page.locator('[data-testid="chain-timeline"]');
		await expect(timeline).toBeVisible({ timeout: 10000 });
		const rows = page.locator('[data-testid="timeline-row"]');
		await expect(rows).toHaveCount(2);
		await expect(rows.first()).toContainText('Starter');
	});

	test('chain page shows status banner', async ({ page, injectStank }) => {
		const GUILD = 123456789;

		const stank1 = await injectStank(GUILD, 5005, 'BannerUser');
		const chainId = stank1.chain_id;

		await page.goto(`/chain/${chainId}`);

		await expect(page.getByText('Chain is alive')).toBeVisible({ timeout: 10000 });
	});
});
