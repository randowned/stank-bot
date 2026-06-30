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

	test('/auth returns full response shape for admin user', async ({ mockLogin, page }) => {
		await mockLogin(adminUser);
		const res = await page.request.get('/auth');
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
});
