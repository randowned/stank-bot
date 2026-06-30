import { test, expect, adminUser } from './fixtures';

test.describe('Admin template editor', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin(adminUser);
	});

	test('page loads with default templates and preview', async ({ page }) => {
		await page.goto('/admin/templates');
		await expect(page.getByRole('heading', { name: 'Templates' })).toBeVisible();
		await expect(page.getByTestId('template-select')).toBeVisible();
		await expect(page.getByTestId('template-preview')).toBeVisible({ timeout: 5000 });
	});

	test('edit → save → reload roundtrip persists template changes', async ({ page }) => {
		await page.goto('/admin/templates');
		await expect(page.getByTestId('template-preview')).toBeVisible({ timeout: 5000 });

		// Select chain break template, switch to Edit tab.
		await page.getByTestId('template-select').click();
		await page.getByRole('menuitem', { name: 'Chain break' }).click();
		await page.getByTestId('tab-edit').click();

		// Modify the title, save, reload, verify persists.
		const textarea = page.getByTestId('template-json');
		const original = JSON.parse(await textarea.inputValue());
		const modified = { ...original, title: 'E2E Template Test Title' };
		await textarea.evaluate(
			(el: HTMLTextAreaElement, val: string) => {
				el.value = val;
				el.dispatchEvent(new Event('input', { bubbles: true }));
			},
			JSON.stringify(modified)
		);
		await page.getByTestId('template-save').click();
		await expect(page.getByTestId('template-save-msg')).toHaveText('Saved.', { timeout: 5000 });

		await page.reload();
		await page.getByTestId('template-select').click();
		await page.getByRole('menuitem', { name: 'Chain break' }).click();
		await page.getByTestId('tab-edit').click();
		const reloaded = JSON.parse(await page.getByTestId('template-json').inputValue());
		expect(reloaded.title).toBe('E2E Template Test Title');

		// Restore default so other tests aren't polluted.
		await page.getByTestId('template-default').click();
		await page.getByTestId('template-save').click();
		await expect(page.getByTestId('template-save-msg')).toHaveText('Saved.', { timeout: 5000 });
	});
});
