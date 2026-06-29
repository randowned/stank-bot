import { test, expect, defaultUser, adminUser } from './fixtures';

/**
 * Smoke tests — critical-path tests that run on every push (~30s).
 * Full E2E suite runs on PRs to main.
 *
 * Run: npx playwright test --project=smoke
 */

test.describe('Smoke: Auth', () => {
	test('mock login and reach dashboard', async ({ mockLogin, page }) => {
		await mockLogin({ ...defaultUser, guild: 123456789 });
		await expect(page.getByTestId('guild-name')).toBeVisible();
		await expect(page.getByTestId('live-badge')).toBeVisible();
	});

	test('admin login and reach admin page', async ({ mockLogin, page }) => {
		await mockLogin({ ...adminUser, guild: 123456789 });
		await page.goto('/admin');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 5000 });
	});
});

test.describe('Smoke: Core pages', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin({ ...defaultUser, guild: 123456789 });
	});

	test('leaderboard renders', async ({ page }) => {
		await expect(page.getByTestId('live-badge')).toBeVisible({ timeout: 5000 });
		await expect(page.getByTestId('chain-counter')).toBeVisible();
	});

	test('sessions page loads', async ({ page }) => {
		await page.goto('/sessions');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 5000 });
	});

	test('media page loads', async ({ page }) => {
		await page.goto('/media');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 5000 });
	});

	test('media profiles page loads', async ({ page }) => {
		await page.goto('/media/profiles');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 5000 });
	});

	test('WebSocket connect indicator visible', async ({ page }) => {
		await expect(page.getByTestId('connection-dot')).toBeVisible({ timeout: 5000 });
		await expect(page.getByTestId('live-badge')).toHaveAttribute('title', /Receiving live updates/, { timeout: 5000 });
	});

	test('guild switcher works', async ({ page, mockBotGuilds }) => {
		await mockBotGuilds([
			{ id: 123456789, name: 'Alpha Server' },
			{ id: 987654321, name: 'Beta Server' }
		]);
		const switcher = page.getByTestId('guild-switcher');
		await expect(switcher).toBeVisible({ timeout: 5000 });
	});
});
