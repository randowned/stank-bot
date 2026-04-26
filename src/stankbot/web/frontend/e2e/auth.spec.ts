import { test, expect, adminUser } from './fixtures';

test.describe('Auth', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.post('/api/mock/bot-guilds', { data: { guilds: [] } });
	});
	test('shows welcome page for unauthenticated visitors', async ({ page }) => {
		await page.goto('/');
		await expect(page.getByText('MAPHRA Discord community')).toBeVisible();
		await expect(page.getByText('Continue with Discord')).toBeVisible();
	});

	test('auto-redirects to mock login in dev mode', async ({ page }) => {
		await page.goto('/auth/login');
		await expect(page.locator('[data-testid="guild-name"]')).toBeVisible();
	});

	test('mock login with custom user', async ({ mockLogin, page }) => {
		await mockLogin({ user_id: 999, username: 'CustomBot' });
		const authRes = await page.request.get('/auth');
		expect(authRes.ok()).toBeTruthy();
		const body = await authRes.json();
		expect(body.user.username).toBe('CustomBot');
	});

	test('/auth returns full response shape for non-admin user', async ({ mockLogin, mockBotGuilds, page }) => {
		await mockBotGuilds([{ id: 123456789, name: 'Alpha Server' }]);
		await mockLogin({
			user_id: 42,
			username: 'RegularUser',
			avatar: 'abc123',
			guild: 123456789,
			is_global_admin: false,
			is_guild_admin: false
		});

		const res = await page.request.get('/auth');
		expect(res.ok()).toBeTruthy();
		const body = await res.json();

		expect(body.user).toBeDefined();
		expect(body.user.id).toBe('42');
		expect(body.user.username).toBe('RegularUser');
		expect(body.user.avatar).toBe('abc123');
		expect(body.guild_id).toBe('123456789');
		expect(body.guild_name).toBe('Alpha Server');
		expect(body.is_admin).toBe(false);
		expect(body.is_global_admin).toBe(false);
	});

	test('/auth returns full response shape for admin user', async ({ mockLogin, page }) => {
		await mockLogin(adminUser);

		const res = await page.request.get('/auth');
		expect(res.ok()).toBeTruthy();
		const body = await res.json();

		expect(body.user.id).toBe(String(adminUser.user_id));
		expect(body.user.username).toBe(adminUser.username);
		expect(body.is_admin).toBe(true);
		expect(body.is_global_admin).toBe(true);
	});

	test('session persists across page reload', async ({ mockLogin, page }) => {
		await mockLogin({ user_id: 77, username: 'PersistentUser' });

		await page.reload();

		const res = await page.request.get('/auth');
		const body = await res.json();
		expect(body.user.username).toBe('PersistentUser');
		expect(body.user.id).toBe('77');
	});

	test('logout clears session', async ({ mockLogin, page }) => {
		await mockLogin();

		const before = await page.request.get('/auth');
		expect((await before.json()).user).not.toBeNull();

		await page.request.get('/auth/logout');

		const after = await page.request.get('/auth');
		expect(after.status()).toBe(200);
		expect(await after.json()).toBeNull();
	});

	test('guilds are fetched for global admin on layout load', async ({
		mockLogin,
		mockBotGuilds,
		page
	}) => {
		await mockBotGuilds([
			{ id: 123456789, name: 'Alpha Server' },
			{ id: 987654321, name: 'Beta Server' }
		]);
		await mockLogin(adminUser);

		// Verify the layout data contains guilds by checking the page content
		// The guild switcher in the user menu should show both guilds
		await page.locator('[data-testid="user-menu-trigger"]').click();
		await page.locator('[data-testid="guild-switcher-toggle"]').click();
		const items = page.locator('[data-testid="guild-switch-item"]');
		await expect(items).toHaveCount(2);
	});

	test('guilds are NOT fetched for non-admin on layout load', async ({
		mockLogin,
		mockBotGuilds,
		page
	}) => {
		await mockBotGuilds([{ id: 123456789, name: 'Alpha Server' }]);
		await mockLogin();

		// Non-admin should not see guild switcher
		await page.locator('[data-testid="user-menu-trigger"]').click();
		await expect(page.locator('[data-testid="guild-switcher-toggle"]')).not.toBeVisible();
	});
});
