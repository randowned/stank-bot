import { test, expect, defaultUser } from './fixtures';

const GUILD = 123456810;

test.describe('Player profile page', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin({ ...defaultUser, guild: GUILD });
		await newSession();
	});

	test('player profile loads and shows SP/PP for stanker', async ({ page, injectStank, injectBreak }) => {
		const STANKER = 7002;
		const BREAKER = 7003;

		await injectStank(GUILD, STANKER, 'StankerUser');
		await injectBreak(GUILD, BREAKER, 'BreakerUser');

		await page.goto(`/player/${STANKER}`);
		await expect(page.getByText('StankerUser')).toBeVisible({ timeout: 10000 });
		await expect(page.getByText('SP').first()).toBeVisible();
	});
});

test.describe('Session detail page', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin({ ...defaultUser, guild: GUILD });
		await newSession();
	});

	test('session detail page loads after navigating from sessions list', async ({ page, injectStank }) => {
		await injectStank(GUILD, 9001, 'SessionUser');

		await page.goto('/sessions');
		await expect(page.getByText('Session History')).toBeVisible({ timeout: 10000 });

		const sessionLink = page.locator('a[href*="/session/"]').first();
		await sessionLink.click();

		await expect(page.getByRole('heading', { name: 'Summary' })).toBeVisible({ timeout: 10000 });
	});
});

test.describe('Chain detail page', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin({ ...defaultUser, guild: GUILD });
		await newSession();
	});

	test('chain page shows timeline with chain-starter row', async ({ page, injectStank }) => {
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
});
