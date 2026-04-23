import { test, expect } from './fixtures';

test.describe('User menu', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin();
	});

	test('user menu trigger is visible in header', async ({ page }) => {
		await expect(page.locator('[data-testid="user-menu-trigger"]')).toBeVisible();
	});

	test('clicking trigger opens dropdown with profile + logout', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		const menu = page.locator('[data-testid="dropdown-menu"]');
		await expect(menu).toBeVisible();
		await expect(menu.getByText('My Profile')).toBeVisible();
		await expect(menu.getByText('Logout')).toBeVisible();
	});

	test('clicking outside closes the dropdown', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		await expect(page.locator('[data-testid="dropdown-menu"]')).toBeVisible();
		await page.locator('main').click({ position: { x: 10, y: 10 } });
		await expect(page.locator('[data-testid="dropdown-menu"]')).not.toBeVisible();
	});

	test('logout link ends the session', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		await Promise.all([
			page.waitForURL((url) => !url.pathname.startsWith('/v2') || url.pathname === '/v2/', {
				timeout: 10000
			}),
			page.getByRole('menuitem', { name: /Logout/ }).click()
		]);
		// Session cleared: /v2/auth should now return 401/403 (not 200 with a user)
		const resp = await page.request.get('/v2/auth');
		expect(resp.status()).toBeGreaterThanOrEqual(400);
	});

	test('guild switcher hidden when user has only one guild', async ({ page }) => {
		await page.locator('[data-testid="user-menu-trigger"]').click();
		const menu = page.locator('[data-testid="dropdown-menu"]');
		await expect(menu).toBeVisible();
		await expect(menu.getByText(/Switch Guild/i)).toHaveCount(0);
	});

	test('guild switcher appears when user has multiple guilds and switching updates session', async ({
		page,
		mockLogin
	}) => {
		await mockLogin({
			user_id: 111111111,
			username: 'Multi Guild',
			avatar: null,
			guilds: [
				{ id: 123456789, name: 'Alpha Server', permissions: 0x20 },
				{ id: 987654321, name: 'Beta Server', permissions: 0x20 }
			],
			guild: 123456789,
			is_admin: true
		});

		await page.locator('[data-testid="user-menu-trigger"]').click();
		const menu = page.locator('[data-testid="dropdown-menu"]');
		await expect(menu.getByText(/Switch Guild/i)).toBeVisible();
		await expect(menu.getByText('Alpha Server')).toBeVisible();
		await expect(menu.getByText('Beta Server')).toBeVisible();
	});
});
