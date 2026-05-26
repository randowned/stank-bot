import { test, expect } from './fixtures';

const GUILD = 123456789;

test.describe('Profiles listing page', () => {
	test.beforeEach(async ({ mockLogin, clearMedia }) => {
		await mockLogin();
		await clearMedia();
	});

	test('shows empty state when no profiles exist', async ({ page }) => {
		await page.goto('/media/profiles');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		await expect(page.getByText('No profiles yet')).toBeVisible();
	});

	test('shows profile cards after injecting media', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-test', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });
		// Profile card should be visible
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
	});

	test('tabs filter profiles by provider', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'yt-profile', mediaType: 'youtube', historyDays: 7 });
		await injectMedia({ guildId: GUILD, slug: 'sp-profile', mediaType: 'spotify', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });

		// Both profile cards are visible
		await expect(page.getByTestId('profile-card')).toHaveCount(2, { timeout: 10000 });

		// Both providers are represented
		await expect(page.getByRole('tab', { name: 'YouTube' })).toBeVisible();
		await expect(page.getByRole('tab', { name: 'Spotify' })).toBeVisible();
	});

	test('profile card shows metrics and tracked count', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-metrics', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });

		const card = page.getByTestId('profile-card').first();
		// Should show channel name
		await expect(card).toContainText('Mock Channel');
		// Should show YouTube label
		await expect(card).toContainText('YouTube');
		// Should show subscriber metric
		await expect(card).toContainText('Subscribers');
		// Should show tracked videos
		await expect(card).toContainText('tracked');
	});

	test('clicking profile card navigates to detail page', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-nav', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });

		await page.getByTestId('profile-card').first().click();
		await expect(page).toHaveURL(/\/media\/profile\/\d+/);
		await expect(page.getByText('Mock Channel')).toBeVisible({ timeout: 10000 });
	});
});

test.describe('Profile detail page', () => {
	test.beforeEach(async ({ mockLogin, clearMedia }) => {
		await mockLogin();
		await clearMedia();
	});

	test('shows error state for invalid profile id', async ({ page }) => {
		await page.goto('/media/profile/99999');
		await expect(page.getByText('Profile not found')).toBeVisible({ timeout: 10000 });
	});

	test('shows cover photo hero with name and provider', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-hero', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-card').first().click();
		await expect(page).toHaveURL(/\/media\/profile\//);

		// Profile name renders
		await expect(page.getByText('Mock Channel')).toBeVisible({ timeout: 10000 });
		// Provider label renders
		await expect(page.getByTestId('profile-external-link')).toBeVisible();
		// External link points to YouTube
		await expect(page.getByTestId('profile-external-link')).toHaveAttribute('href', /youtube\.com\/channel\//);
		// Tracked count renders
		await expect(page.getByText(/tracked/)).toBeVisible();
	});

	test('shows StatTiles for owner metrics', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-tiles', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-card').first().click();

		// All YouTube owner metrics rendered
		await expect(page.getByTestId('profile-metric-subscriber_count')).toBeVisible({ timeout: 10000 });
		await expect(page.getByTestId('profile-metric-total_view_count')).toBeVisible();
		await expect(page.getByTestId('profile-metric-video_count')).toBeVisible();
	});

	test('shows chart with controls', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-chart', historyDays: 14 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-card').first().click();

		// Chart controls render
		await expect(page.getByTestId('profile-chart-metric')).toBeVisible({ timeout: 10000 });
		await expect(page.getByTestId('profile-chart-range')).toBeVisible();
		await expect(page.getByTestId('profile-chart-mode')).toBeVisible();
	});

	test('shows tracked media items grid', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-items', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-card').first().click();

		// Tracked Media heading renders
		await expect(page.getByText(/Tracked Media/)).toBeVisible({ timeout: 10000 });
		// Media item card renders
		await expect(page.getByTestId('profile-media-item')).toBeVisible();
	});

	test('clicking tracked media item navigates to media detail', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'profile-to-media', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-card').first().click();

		await expect(page.getByTestId('profile-media-item')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-media-item').first().getByRole('link').first().click();
		await expect(page).toHaveURL(new RegExp(`/media/${id}`));
	});

	test('back to profiles link navigates correctly', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'profile-back', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-card').first().click();

		await expect(page).toHaveURL(/\/media\/profile\//);
		await page.getByText('← Back to Profiles').click();
		await expect(page).toHaveURL('/media/profiles');
	});

	test('Spotify profile shows artist metrics', async ({ page, injectMedia }) => {
		await injectMedia({ guildId: GUILD, slug: 'sp-profile-detail', mediaType: 'spotify', historyDays: 7 });
		await page.goto('/media/profiles');
		await expect(page.getByTestId('profile-card')).toBeVisible({ timeout: 10000 });
		await page.getByTestId('profile-card').first().click();

		// Spotify artist metrics
		await expect(page.getByTestId('profile-metric-follower_count')).toBeVisible({ timeout: 10000 });
		await expect(page.getByTestId('profile-metric-popularity')).toBeVisible();
		await expect(page.getByText('Mock Artist')).toBeVisible();
		await expect(page.getByTestId('profile-external-link')).toHaveAttribute('href', /open\.spotify\.com\/artist\//);
	});
});

test.describe('Profile navigation from media page', () => {
	test.beforeEach(async ({ mockLogin, clearMedia }) => {
		await mockLogin();
		await clearMedia();
	});

	test('owner card on media detail links to profile page', async ({ page, injectMedia }) => {
		const { id } = await injectMedia({ guildId: GUILD, slug: 'owner-link-test', historyDays: 7 });
		await page.goto(`/media/${id}`);
		await expect(page.getByTestId('page-header')).toBeVisible({ timeout: 10000 });

		// Owner card renders with link to profile page
		const nameLink = page.getByTestId('owner-name-link');
		await expect(nameLink).toBeVisible();
		await expect(nameLink).toHaveAttribute('href', /\/media\/profile\//);

		// Click it and navigate to profile
		await nameLink.click();
		await expect(page).toHaveURL(/\/media\/profile\//);
		await expect(page.getByText('Mock Channel')).toBeVisible({ timeout: 10000 });
	});
});
