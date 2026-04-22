import { test, expect } from './fixtures';

test.describe('Board', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin();
	});

	test('board loads and shows guild name', async ({ page }) => {
		await expect(page.locator('[data-testid="guild-name"]')).toBeVisible();
		await expect(page.locator('[data-testid="connection-dot"]')).toBeVisible();
	});

	test('websocket connects and receives chain update on stank injection', async ({ page, injectStank }) => {
		// Capture all browser console logs
		const logs: string[] = [];
		page.on('console', msg => logs.push(`[${msg.type()}] ${msg.text()}`));
		page.on('pageerror', err => logs.push(`[pageerror] ${err.message}`));

		// Wait for WS to be fully connected
		await expect(page.locator('[data-testid="connection-dot"]')).toHaveAttribute('title', 'Live');

		// Log connection status for debugging
		console.log('Browser logs:', logs);

		// Initially no active chain
		await expect(page.locator('[data-testid="chain-status"]')).toContainText('No active chain');

		await injectStank(123456789, 111, 'Alice');

		// After injection, chain should be active
		await expect(page.locator('[data-testid="chain-status"]')).toContainText('Live chain');
		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText('1');
	});

	test('chain break resets counter', async ({ page, injectStank, injectBreak }) => {
		// Wait for WS to be fully connected before injecting
		await expect(page.locator('[data-testid="connection-dot"]')).toHaveAttribute('title', 'Live');

		await injectStank(123456789, 111, 'Alice');
		await injectStank(123456789, 222, 'Bob');

		await expect(page.locator('[data-testid="chain-counter"]')).toHaveText('2');

		await injectBreak(123456789, 333, 'Charlie');

		await expect(page.locator('[data-testid="chain-status"]')).toContainText('No active chain');
	});

	test('random events update the board', async ({ page, startRandomEvents, stopRandomEvents }) => {
		await startRandomEvents(1);

		// Wait for random event to fire
		await page.waitForTimeout(3500);

		// Stop random events
		await stopRandomEvents();

		// Board should show some activity
		const chainText = await page.locator('[data-testid="chain-status"]').textContent();
		const rankingCount = await page.locator('[data-testid="rank-row"]').count();
		expect(chainText?.includes('Live chain') || rankingCount > 0).toBeTruthy();
	});
});
