import { test, expect } from './fixtures';
import { Packr } from 'msgpackr';

test.describe('Version update notification', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin();
	});

	test('shows update toast when client version mismatches server', async ({ page }) => {
		const apiResp = await page.request.get('/api/version');
		const { version: serverVersion } = await apiResp.json();
		expect(serverVersion).toBeTruthy();

		await page.evaluate(
			(v) => localStorage.setItem('stankbot:version', v),
			`${serverVersion}.old`
		);
		await page.reload();

		await expect(page.locator('[data-testid="live-badge"]')).toHaveAttribute(
			'title', /Receiving live updates/, { timeout: 15000 }
		);

		const toast = page.locator('[data-testid="update-toast"]');
		await expect(toast).toBeVisible({ timeout: 10000 });
		await expect(toast).toContainText('Updated available');

		const reloadBtn = page.locator('[data-testid="update-reload-btn"]');
		await expect(reloadBtn).toBeVisible();
		await expect(reloadBtn).toHaveText('Reload');
	});

	test('does not show update toast when versions match', async ({ page }) => {
		const apiResp = await page.request.get('/api/version');
		const { version: serverVersion } = await apiResp.json();
		await page.evaluate(
			(v) => localStorage.setItem('stankbot:version', v),
			serverVersion
		);
		await page.reload();

		await expect(page.locator('[data-testid="live-badge"]')).toHaveAttribute(
			'title', /Receiving live updates/, { timeout: 15000 }
		);
		await expect(page.locator('[data-testid="update-toast"]')).not.toBeVisible();
	});

	test('WS message type 109 (VERSION_MISMATCH) on version mismatch', async ({ page }) => {
		const apiResp = await page.request.get('/api/version');
		const { version: serverVersion } = await apiResp.json();

		await page.request.post('/api/mock/version', { data: { version: '99.0.0' } });

		const frameBuffers: Buffer[] = [];
		page.on('websocket', (ws) => {
			ws.on('framereceived', (frame) => {
				if (frame.payload instanceof Buffer) frameBuffers.push(frame.payload);
			});
		});

		await page.evaluate(
			(v) => localStorage.setItem('stankbot:version', v),
			`${serverVersion}.old`
		);
		await page.reload();

		const toast = page.locator('[data-testid="update-toast"]');
		await expect(toast).toBeVisible({ timeout: 10000 });

		const packr = new Packr({ useRecords: false });
		const mismatchFrames = frameBuffers
			.map((buf) => {
				try { return packr.unpack(new Uint8Array(buf)); } catch { return null; }
			})
			.filter((msg): msg is { t: number; d: Record<string, unknown> } =>
				msg !== null && typeof msg.t === 'number' && msg.t === 109
			);
		expect(mismatchFrames.length).toBeGreaterThan(0);

		const mismatch = mismatchFrames[0].d as { server_version: string; client_version: string };
		expect(mismatch.server_version).toBe('99.0.0');
	});
});
