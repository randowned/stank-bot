import { test, expect, adminUser } from './fixtures';

test.describe('Admin dashboard', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin(adminUser);
	});

	test('admin page renders tiles when user is admin', async ({ page }) => {
		await page.goto('/admin');
		await expect(page.getByRole('heading', { name: 'Admin' })).toBeVisible();
		await expect(page.getByText('Settings', { exact: true }).first()).toBeVisible();
		await expect(page.getByText('Templates', { exact: true }).first()).toBeVisible();
		await expect(page.getByText('Audit log').first()).toBeVisible();
	});

	test('sidebar links navigate between admin pages', async ({ page }) => {
		await page.goto('/admin');
		await page.getByRole('link', { name: /Settings/ }).first().click();
		await expect(page).toHaveURL(/\/admin\/settings$/);
		await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
	});
});

test.describe('Admin templates preview', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin(adminUser);
	});

	test('template page loads keys and renders preview', async ({ page }) => {
		await page.goto('/admin/templates');
		await expect(page.getByRole('heading', { name: 'Templates' })).toBeVisible();
		await expect(page.getByTestId('template-select')).toBeVisible();
		await expect(page.getByTestId('template-preview')).toBeVisible({ timeout: 5000 });
	});
});
