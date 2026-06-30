import { test, expect, defaultUser } from './fixtures';

const GUILD = 123456800;
let idCounter = 0;

function makeId(): number {
	idCounter++;
	return (GUILD * 10000) + (Date.now() % 10000) * 10 + idCounter;
}

test.describe('Achievement gallery on player profile', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin({ ...defaultUser, guild: GUILD });
	});

	test('shows achievements gallery with unlocked and locked badges', async ({
		page,
		injectStank
	}) => {
		const userId = makeId();
		await injectStank(GUILD, userId, 'AchievementPlayer');

		await page.goto(`/player/${userId}`);
		await page.waitForResponse(resp =>
			resp.url().includes('/api/player/') && resp.status() === 200,
			{ timeout: 10000 }
		);
		await expect(page.getByTestId('achievements-gallery')).toBeVisible();
		// injectStank auto-awards BOTH first_stank AND chain_starter (the user
		// is also the chain starter). Expect 2 unlocked.
		await expect(page.getByTestId('achievements-summary')).toContainText('2 of ');

		const firstStankBadge = page.locator('[data-testid="achievement-item"][data-achievement-key="first_stank"]');
		await expect(firstStankBadge).toHaveAttribute('data-unlocked', 'true');

		const chainStarterBadge = page.locator('[data-testid="achievement-item"][data-achievement-key="chain_starter"]');
		await expect(chainStarterBadge).toHaveAttribute('data-unlocked', 'true');

		const lockedBadge = page.locator('[data-testid="achievement-item"][data-achievement-key="fourth_place"]');
		await expect(lockedBadge).toHaveAttribute('data-unlocked', 'false');
	});

	test('repeatable badge shows ×N pill when count > 1', async ({
		page,
		injectStank,
		injectAchievement
	}) => {
		const userId = makeId();
		await injectStank(GUILD, userId, 'RepeatablePlayer');
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'fourth_place', count: 3 });

		await page.goto(`/player/${userId}`);
		await page.waitForResponse(resp =>
			resp.url().includes('/api/player/') && resp.status() === 200,
			{ timeout: 10000 }
		);
		await expect(page.getByTestId('achievements-gallery')).toBeVisible();

		const fourthBadge = page.getByTestId('achievement-item').filter({ hasText: 'Fourth Place' });
		await expect(fourthBadge).toBeVisible();
		const pill = fourthBadge.getByTestId('achievement-count-pill');
		await expect(pill).toBeVisible();
		await expect(pill).toHaveText('×3');
	});
});

test.describe('Achievement unlock toast via WebSocket', () => {
	test.beforeEach(async ({ mockLogin }) => {
		await mockLogin({ ...defaultUser, guild: GUILD });
	});

	test('achievement unlock toast fires via WebSocket broadcast', async ({
		page,
		injectAchievementBroadcast
	}) => {
		await expect(page.getByTestId('live-badge')).toHaveAttribute('title', /Receiving live updates/);

		await injectAchievementBroadcast({
			guildId: GUILD,
			userId: defaultUser.user_id,
			badge: {
				key: 'first_stank',
				name: 'First Stank',
				icon: '✨',
				description: 'Dropped your very first stank.'
			}
		});

		await expect(page.getByRole('alert').filter({ hasText: 'Achievement unlocked: First Stank!' })).toBeVisible({
			timeout: 5000
		});
	});
});
