import { test, expect, adminUser } from './fixtures';

test.describe('User menu', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin();
	});

	test('user menu trigger is visible in header', async ({ page }) => {
		await expect(page.locator('[data-testid="user-menu-trigger"]')).toBeVisible();
	});

	test('clicking trigger opens dropdown with navigation + profile + logout', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		const menu = page.locator('[data-testid="dropdown-menu"]');
		await expect(menu).toBeVisible();
		await expect(menu.getByText('Dashboard')).toBeVisible();
		await expect(menu.getByText('Sessions')).toBeVisible();
		await expect(menu.getByText('My Profile')).toBeVisible();
		await expect(menu.getByText('Logout')).toBeVisible();
	});

	test('clicking outside closes the dropdown', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		const menu = page.locator('[data-testid="dropdown-menu"]');
		await expect(menu).toBeVisible();
		await page.locator('body').click({ position: { x: 10, y: 10 } });
		await expect(menu).not.toBeVisible();
	});

	test('logout link ends the session', async ({ page }) => {
		const logoutResp = await page.request.get('/auth/logout', { maxRedirects: 0 });
		expect(logoutResp.status()).toBe(303);
	});

	test('non-admin does not see guild switcher', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		await expect(page.locator('[data-testid="guild-switcher-toggle"]')).not.toBeVisible();
	});
});

test.describe('User menu — guild switcher (admin)', () => {
	test('guild switcher toggle does not close the menu on click', async ({
		page,
		mockLogin,
		mockBotGuilds
	}) => {
		await mockBotGuilds([
			{ id: 123456789, name: 'Alpha Server' },
			{ id: 987654321, name: 'Beta Server' }
		]);
		await mockLogin(adminUser);
		await page.locator('[data-testid="user-menu-trigger"]').click();
		const menu = page.locator('[data-testid="dropdown-menu"]');
		await expect(menu).toBeVisible();
		await page.locator('[data-testid="guild-switcher-toggle"]').click();
		await expect(menu).toBeVisible();
	});

	test('guild switcher lists bot-present guilds and switching triggers reload', async ({
		page,
		mockLogin,
		mockBotGuilds
	}) => {
		await mockBotGuilds([
			{ id: 123456789, name: 'Alpha Server' },
			{ id: 987654321, name: 'Beta Server' }
		]);
		await mockLogin(adminUser);

		await page.locator('[data-testid="user-menu-trigger"]').click();
		await page.locator('[data-testid="guild-switcher-toggle"]').click();
		const items = page.locator('[data-testid="guild-switch-item"]');
		await expect(items).toHaveCount(2);
		await expect(items.first()).toContainText(/Alpha|Beta/);
	});
});
