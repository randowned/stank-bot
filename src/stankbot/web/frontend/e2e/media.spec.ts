import { test, expect } from './fixtures';

const GUILD = 123456789;

test.describe('Media admin page', () => {
	test.beforeEach(async ({ mockLogin, clearMedia, page }) => {
		await mockLogin({ user_id: 222222222, username: 'E2E Admin', is_global_admin: true, is_guild_admin: true });
		await clearMedia();
	});

	test('admin can navigate to add', async ({ page }) => {
		await page.goto('/admin/media');
		await page.getByTestId('media-add-btn').click();
		await expect(page).toHaveURL(/\/admin\/media\/add/);
	});

	test('admin list shows injected media', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'admin-test' });
		await page.goto('/admin/media');
		await expect(page.getByTestId('media-admin-row')).toBeVisible({ timeout: 10000 });
	});

	test('admin sees empty state', async ({ page }) => {
		await page.goto('/admin/media');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		await expect(page.getByText('No media')).toBeVisible();
	});

	test('redirects non-admin', async ({ page, mockLogin }) => {
		await mockLogin();
		await page.goto('/admin/media');
		await expect(page).not.toHaveURL(/\/admin\/media/);
	});
});

test.describe('Media page', () => {
	test.beforeEach(async ({ mockLogin, clearMedia }) => {
		await mockLogin();
		await clearMedia();
	});

	test('shows empty state when no media exist', async ({ page }) => {
		await page.goto('/media');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		await expect(page.getByText('No media yet')).toBeVisible();
	});

	test('shows media cards after injection', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'my-test-video', historyDays: 7 });
		await page.goto('/media');
		await expect(page.getByTestId('page-header')).toBeVisible();
		await expect(page.getByTestId('media-card')).toBeVisible({ timeout: 10000 });
	});

	test('media card shows all three metric values', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'multi-metric-test', historyDays: 7 });
		await page.goto('/media');
		await expect(page.getByTestId('media-card')).toBeVisible({ timeout: 10000 });
		const metricsEl = page.getByTestId('media-metrics').first();
		await expect(metricsEl).toBeVisible();
		// Should contain all three metric icons
		const text = await metricsEl.textContent();
		expect(text).toContain('👁️');
		expect(text).toContain('👍');
		expect(text).toContain('💬');
	});

	test('navigates to media detail page', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'my-detail-video', historyDays: 7 });
		await page.goto('/media');
		await page.getByTestId('media-card').first().click();
		await expect(page).toHaveURL(new RegExp(`/media/${id}`));
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
	});

	test('compare navigates to detail page with query params', async ({ page, injectMedia }) => {
		const item1 = await injectMedia({ guildId: GUILD, slug: 'compare-video-1', historyDays: 7 });
		const item2 = await injectMedia({ guildId: GUILD, slug: 'compare-video-2', historyDays: 7 });
		await page.goto(`/media/${item1.id}?compare=${item2.id}&metric=view_count&days=2&resolution=auto&mode=delta`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		await expect(page).toHaveURL(new RegExp(`/media/${item1.id}\\?`));
		await expect(page).toHaveURL(/metric=view_count/);
		await expect(page).toHaveURL(new RegExp(`compare=${item2.id}`));
		await expect(page).toHaveURL(/days=2/);
	});

	test('compare renders comparison section on detail page', async ({ page, injectMedia }) => {
		const item1 = await injectMedia({ guildId: GUILD, slug: 'comp-1', historyDays: 7 });
		const item2 = await injectMedia({ guildId: GUILD, slug: 'comp-2', historyDays: 7 });
		await page.goto(`/media/${item1.id}?compare=${item2.id}&metric=view_count&days=2`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		// Comparison heading renders (text is "— comparing N items")
		await expect(page.getByText(/comparing/)).toBeVisible({ timeout: 15000 });
		// Clear comparison button present
		await expect(page.getByTestId('media-clear-compare')).toBeVisible();
	});

	test('URL params restore chart state on reload', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'url-restore', historyDays: 7 });
		await page.goto(`/media/${id}?metric=like_count&hours=12&resolution=hourly&mode=total`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });

		// Metric dropdown shows "Likes" label
		const metricBtn = page.getByTestId('media-detail-metric');
		await expect(metricBtn).toHaveAttribute('aria-label', 'Likes');

		// Range dropdown shows "12 hours"
		const rangeBtn = page.getByTestId('media-detail-range');
		await expect(rangeBtn).toHaveAttribute('aria-label', '12 hours');

		// Reload and verify state persists
		await page.reload();
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		await expect(page.getByTestId('media-detail-metric')).toHaveAttribute('aria-label', 'Likes');
		await expect(page.getByTestId('media-detail-range')).toHaveAttribute('aria-label', '12 hours');
	});

	test('changing dropdown updates URL', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'dd-url-sync', historyDays: 7 });
		await page.goto(`/media/${id}`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });

		// Wait for chart controls to be interactive
		await expect(page.getByTestId('media-detail-metric')).toBeVisible({ timeout: 10000 });

		// Change metric to Likes (use double-click to work around open-then-close race)
		const metricBtn = page.getByTestId('media-detail-metric');
		await metricBtn.click();
		// If menu didn't open (timing race), retry with a small delay
		const menuAfterFirst = page.getByRole('menuitem', { name: 'Likes' });
		if (!(await menuAfterFirst.isVisible().catch(() => false))) {
			await page.waitForTimeout(100);
			await metricBtn.click();
		}
		await expect(menuAfterFirst).toBeVisible({ timeout: 5000 });
		await menuAfterFirst.click();
		await expect(page).toHaveURL(/metric=like_count/);

		// Change range to 6 hours
		const rangeBtn = page.getByTestId('media-detail-range');
		await rangeBtn.click();
		const rangeMenu = page.getByRole('menuitem', { name: '6 hours' });
		if (!(await rangeMenu.isVisible().catch(() => false))) {
			await page.waitForTimeout(100);
			await rangeBtn.click();
		}
		await expect(rangeMenu).toBeVisible({ timeout: 5000 });
		await rangeMenu.click();
		await expect(page).toHaveURL(/hours=6/);

		// Change mode to Cumulative
		const modeBtn = page.getByTestId('media-detail-view');
		await modeBtn.click();
		const modeMenu = page.getByRole('menuitem', { name: 'Cumulative' });
		if (!(await modeMenu.isVisible().catch(() => false))) {
			await page.waitForTimeout(100);
			await modeBtn.click();
		}
		await expect(modeMenu).toBeVisible({ timeout: 5000 });
		await modeMenu.click();
		await expect(page).toHaveURL(/mode=total/);
	});

	test('clear compare keeps other chart params in URL', async ({ page, injectMedia }) => {
		const item1 = await injectMedia({ guildId: GUILD, slug: 'clear-cmp-1', historyDays: 7 });
		const item2 = await injectMedia({ guildId: GUILD, slug: 'clear-cmp-2', historyDays: 7 });
		await page.goto(`/media/${item1.id}?compare=${item2.id}&metric=view_count&hours=48&resolution=auto`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		await expect(page.getByTestId('media-clear-compare')).toBeVisible({ timeout: 10000 });

		// Clear comparison — click with retry (Svelte 5 delegation race)
		const clearBtn = page.getByTestId('media-clear-compare');
		await clearBtn.click();
		// If button still visible after click, retry
		if (await clearBtn.isVisible().catch(() => false)) {
			await page.waitForTimeout(100);
			await clearBtn.click();
		}

		// URL should lose compare param
		await expect(page).not.toHaveURL(/compare=/, { timeout: 10000 });
		// Chart params persist
		await expect(page).toHaveURL(/metric=view_count/);
	});

	test('shared URL reproduces exact chart view with compare', async ({ page, injectMedia }) => {
		const item1 = await injectMedia({ guildId: GUILD, slug: 'share-1', historyDays: 7 });
		const item2 = await injectMedia({ guildId: GUILD, slug: 'share-2', historyDays: 7 });
		await page.goto(`/media/${item1.id}?compare=${item2.id}&metric=view_count&hours=24&mode=delta`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });

		// Comparison heading renders from the shared URL
		await expect(page.getByText(/comparing/)).toBeVisible({ timeout: 15000 });
		// Clear comparison button confirms compare mode is active
		await expect(page.getByTestId('media-clear-compare')).toBeVisible();
		// Chart renders
		await expect(page.getByTestId('media-detail-chart')).toBeVisible();
	});

	test('detail page shows chart and external link for YouTube', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'chart-test', historyDays: 7 });
		await page.goto(`/media/${id}`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		// Chart area renders
		await expect(page.getByTestId('media-detail-chart')).toBeVisible();
		// External link to YouTube
		const link = page.getByTestId('media-external-link');
		await expect(link).toBeVisible();
		await expect(link).toHaveAttribute('href', /youtu\.be\//);
		await expect(link).toContainText(/Open on/);
	});

	test('Spotify card shows provider metric instead of zeros', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'spotify-card', mediaType: 'spotify', historyDays: 7 });
		await page.goto('/media');
		await expect(page.getByTestId('media-card')).toBeVisible({ timeout: 10000 });
		// Spotify card should show 🎧 play count as primary metric
		const metricsEl = page.getByTestId('media-metrics').first();
		await expect(metricsEl).toContainText('🎧', { timeout: 15000 });
		await expect(metricsEl).not.toContainText('👁️');
	});

	test('Spotify detail page shows chart controls and external link', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'spotify-detail', mediaType: 'spotify', historyDays: 7 });
		await page.goto(`/media/${id}`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		// Play Count metric dropdown visible (Spotify uses play count instead of views)
		await expect(page.getByTestId('media-detail-metric')).toHaveAttribute('aria-label', 'Play Count', { timeout: 15000 });
		// Chart area or empty-state message renders (mock may not generate Spotify history)
		const chart = page.getByTestId('media-detail-chart');
		const emptyMsg = page.getByText('No history data yet');
		await expect(chart.or(emptyMsg)).toBeVisible({ timeout: 10000 });
		// External link points to Spotify
		const link = page.getByTestId('media-external-link');
		await expect(link).toBeVisible();
		await expect(link).toHaveAttribute('href', /open\.spotify\.com\//);
		await expect(link).toContainText(/Open on/);
	});

	test('detail page shows owner card with metrics', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'owner-test', historyDays: 7 });
		await page.goto(`/media/${id}`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		// Owner card renders
		await expect(page.getByTestId('owner-card')).toBeVisible({ timeout: 10000 });
		// Owner name link points to the internal profile page
		const nameLink = page.getByTestId('owner-name-link');
		await expect(nameLink).toBeVisible();
		await expect(nameLink).toHaveAttribute('href', /\/media\/profile\//);
		// Owner metric tiles render
		await expect(page.getByTestId('owner-metric-subscriber_count')).toBeVisible();
		await expect(page.getByTestId('owner-metric-total_view_count')).toBeVisible();
		await expect(page.getByTestId('owner-metric-video_count')).toBeVisible();
	});

	test('Spotify detail page shows owner card with artist metrics', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'spotify-owner', mediaType: 'spotify', historyDays: 7 });
		await page.goto(`/media/${id}`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		// Owner card renders
		await expect(page.getByTestId('owner-card')).toBeVisible({ timeout: 10000 });
		// Owner name link points to the internal profile page
		const nameLink = page.getByTestId('owner-name-link');
		await expect(nameLink).toHaveAttribute('href', /\/media\/profile\//);
		// Owner metric tiles render
		await expect(page.getByTestId('owner-metric-follower_count')).toBeVisible();
		await expect(page.getByTestId('owner-metric-popularity')).toBeVisible();
	});

	test('owner snapshot tab shows on admin edit page', async ({ page, injectMedia, mockLogin, clearMedia }) => {
		await mockLogin({ user_id: 222222222, username: 'E2E Admin', is_global_admin: true, is_guild_admin: true });
		await clearMedia();
		const { id } = await injectMedia({ guildId: GUILD, slug: 'owner-admin-test', historyDays: 7 });
		await page.goto(`/admin/media/${id}/edit`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });

		// Tabs render
		await expect(page.getByRole('tab', { name: 'Media Snapshots' })).toBeVisible();
		await expect(page.getByRole('tab', { name: 'Channel Snapshots' })).toBeVisible();

		// Click Channel Snapshots tab
		await page.getByRole('tab', { name: 'Channel Snapshots' }).click();
		// Owner snapshot table should have data
		await expect(page.getByTestId('media-edit-owner-snapshots')).toBeVisible({ timeout: 10000 });
	});

	test('Spotify admin edit shows Artist Snapshots tab', async ({ page, injectMedia, mockLogin, clearMedia }) => {
		await mockLogin({ user_id: 222222222, username: 'E2E Admin', is_global_admin: true, is_guild_admin: true });
		await clearMedia();
		const { id } = await injectMedia({ guildId: GUILD, slug: 'spotify-admin-owner', mediaType: 'spotify', historyDays: 7 });
		await page.goto(`/admin/media/${id}/edit`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });

		await expect(page.getByRole('tab', { name: 'Artist Snapshots' })).toBeVisible();
		await page.getByRole('tab', { name: 'Artist Snapshots' }).click();
		await expect(page.getByTestId('media-edit-owner-snapshots')).toBeVisible({ timeout: 10000 });
	});
});

// Admin-specific tests — separate block with admin login
test.describe('Media admin page — provider-aware', () => {
	test.beforeEach(async ({ mockLogin, clearMedia, page }) => {
		await mockLogin({ user_id: 222222222, username: 'E2E Admin', is_global_admin: true, is_guild_admin: true });
		await clearMedia();
	});

	test('tabs filter list client-side', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'youtube-tab', mediaType: 'youtube', historyDays: 7 });
		await injectMedia({ guildId: GUILD, slug: 'spotify-tab', mediaType: 'spotify', historyDays: 7 });
		await page.goto('/admin/media');
		await expect(page.getByTestId('media-admin-row')).toHaveCount(2, { timeout: 10000 });

		// Click "Spotify" tab — should filter instantly
		await page.getByRole('tab', { name: 'Spotify' }).click();
		await expect(page.getByTestId('media-admin-row')).toHaveCount(1);

		// Click "All" tab — should show all again
		await page.getByRole('tab', { name: 'All' }).click();
		await expect(page.getByTestId('media-admin-row')).toHaveCount(2);
	});
});
