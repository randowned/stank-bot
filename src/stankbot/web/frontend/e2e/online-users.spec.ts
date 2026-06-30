import { test, expect, adminUser } from './fixtures';

test.describe('Online users badge', () => {
	test('admin sees online badge with count', async ({ page, mockLogin }) => {
		await mockLogin(adminUser);
		await expect(page.locator('[data-testid="online-badge"]')).toBeVisible();
		await expect(page.locator('[data-testid="online-badge-count"]')).toContainText(/online/);
	});

	test('non-admin sees live-badge instead of online-badge', async ({ page, mockLogin }) => {
		await mockLogin();
		await expect(page.locator('[data-testid="online-badge"]')).not.toBeVisible();
		await expect(page.locator('[data-testid="live-badge"]')).toBeVisible();
	});
});
