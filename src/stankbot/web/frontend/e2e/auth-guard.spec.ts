import { test, expect, adminUser, guildAdminUser } from './fixtures';

test.describe('Auth guard — unauthenticated', () => {
	test('/auth returns 200 null when unauthenticated', async ({ page }) => {
		const res = await page.request.get('/auth');
		expect(res.status()).toBe(200);
		expect(await res.json()).toBeNull();
	});

	test('deep link /sessions redirects unauthenticated user to /', async ({ page }) => {
		await page.goto('/sessions');
		await expect(page).toHaveURL(/\/$/);
		await expect(page.getByText('MAPHRA Discord community')).toBeVisible();
	});
});

test.describe('Auth guard — non-admin user', () => {
	test('non-admin can access board', async ({ mockLogin, page }) => {
		await mockLogin();
		await expect(page.locator('[data-testid="guild-name"]')).toBeVisible();
	});

	test('non-admin is redirected from /admin to /', async ({ mockLogin, page }) => {
		await mockLogin();
		await page.goto('/admin');
		await expect(page).toHaveURL(/\/$/);
	});

	test('non-admin /api/admin/settings returns 403', async ({ mockLogin, page }) => {
		await mockLogin();
		const res = await page.request.get('/api/admin/settings');
		expect(res.status()).toBe(403);
	});
});

test.describe('Auth guard — admin user', () => {
	test('admin can access admin page', async ({ mockLogin, page }) => {
		await mockLogin(adminUser);
		await page.goto('/admin');
		await expect(page.getByRole('heading', { name: 'Admin' })).toBeVisible();
	});

	test('admin /api/admin/settings returns 200', async ({ mockLogin, page }) => {
		await mockLogin(adminUser);
		const res = await page.request.get('/api/admin/settings');
		expect(res.status()).toBe(200);
	});
});

test.describe('Auth guard — guild-only admin', () => {
	test('guild admin /api/admin/settings returns 200 (scoped to guild)', async ({ mockLogin, page }) => {
		await mockLogin(guildAdminUser);
		const res = await page.request.get('/api/admin/settings');
		expect(res.status()).toBe(200);
	});
});
