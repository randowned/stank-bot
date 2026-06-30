import { test, expect, adminUser } from './fixtures';

test.describe('User menu', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin();
	});

	test('user menu trigger is visible and opens dropdown with navigation', async ({ page }) => {
		await expect(page.locator('[data-testid="user-menu-trigger"]')).toBeVisible();
		await page.locator('[data-testid="user-menu-trigger"]').click();
		const menu = page.locator('[data-testid="dropdown-menu"]');
		await expect(menu).toBeVisible();
		await expect(menu.getByText('Dashboard')).toBeVisible();
		await expect(menu.getByText('Sessions')).toBeVisible();
		await expect(menu.getByText('My Profile')).toBeVisible();
		await expect(menu.getByText('Logout')).toBeVisible();
	});

	test('non-admin does not see guild switcher', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		await expect(page.locator('[data-testid="guild-switcher-toggle"]')).not.toBeVisible();
	});
});

test.describe('User menu — guild switcher (admin)', () => {
	test('admin sees guild switcher with bot guilds', async ({ page, mockLogin, mockBotGuilds }) => {
		await mockBotGuilds([
			{ id: 123456789, name: 'Alpha Server' },
			{ id: 987654321, name: 'Beta Server' }
		]);
		await mockLogin(adminUser);

		await page.locator('[data-testid="user-menu-trigger"]').click();
		await page.locator('[data-testid="guild-switcher-toggle"]').click();
		const items = page.locator('[data-testid="guild-switch-item"]');
		await expect(items).toHaveCount(2);
	});
});
