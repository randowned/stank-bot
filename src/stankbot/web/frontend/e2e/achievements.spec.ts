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
		injectStank,
		injectAchievement
	}) => {
		const userId = makeId();
		await injectStank(GUILD, userId, 'AchievementPlayer');
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'first_stank', count: 1 });

		await page.goto(`/player/${userId}`);
		// Wait for the player API response before asserting visibility
		await page.waitForResponse(resp =>
			resp.url().includes('/api/player/') && resp.status() === 200,
			{ timeout: 10000 }
		);
		await expect(page.getByTestId('achievements-gallery')).toBeVisible();
		await expect(page.getByTestId('achievements-summary')).toContainText('1 of ');

		// The first_stank badge should be unlocked
		const unlockedBadge = page.locator('[data-testid="achievement-item"][data-achievement-key="first_stank"]');
		await expect(unlockedBadge).toBeVisible();
		await expect(unlockedBadge).toHaveAttribute('data-unlocked', 'true');

		// Other badges should be locked (opacity-50 class)
		const lockedBadge = page.locator('[data-testid="achievement-item"][data-achievement-key="chain_starter"]');
		await expect(lockedBadge).toBeVisible();
		await expect(lockedBadge).toHaveAttribute('data-unlocked', 'false');
	});

	test('repeatable badge shows ×N pill when count > 1', async ({
		page,
		injectStank,
		injectAchievement
	}) => {
		const userId = makeId();
		await injectStank(GUILD, userId, 'RepeatablePlayer');
		// Inject fourth_place with count=3
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'fourth_place', count: 3 });

		await page.goto(`/player/${userId}`);
		await page.waitForResponse(resp =>
			resp.url().includes('/api/player/') && resp.status() === 200,
			{ timeout: 10000 }
		);
		await expect(page.getByTestId('achievements-gallery')).toBeVisible();

		// The fourth_place badge should show ×3 pill
		const fourthBadge = page.getByTestId('achievement-item').filter({ hasText: 'Fourth Place' });
		await expect(fourthBadge).toBeVisible();
		const pill = fourthBadge.getByTestId('achievement-count-pill');
		await expect(pill).toBeVisible();
		await expect(pill).toHaveText('×3');
	});

	test('non-repeatable badge shows no count pill', async ({
		page,
		injectStank,
		injectAchievement
	}) => {
		const userId = makeId();
		await injectStank(GUILD, userId, 'NonRepeatPlayer');
		// Inject first_stank (non-repeatable) with count=1
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'first_stank', count: 1 });

		await page.goto(`/player/${userId}`);
		await page.waitForResponse(resp =>
			resp.url().includes('/api/player/') && resp.status() === 200,
			{ timeout: 10000 }
		);
		await expect(page.getByTestId('achievements-gallery')).toBeVisible();

		// The first_stank badge should NOT have a count pill
		const firstBadge = page.locator('[data-testid="achievement-item"][data-achievement-key="first_stank"]');
		await expect(firstBadge).toBeVisible();
		await expect(firstBadge.getByTestId('achievement-count-pill')).toHaveCount(0);
	});

	test('repeatable badge with count=1 shows no count pill', async ({
		page,
		injectStank,
		injectAchievement
	}) => {
		const userId = makeId();
		await injectStank(GUILD, userId, 'CountOnePlayer');
		// Inject fourth_place with count=1 (only earned once — no pill)
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'fourth_place', count: 1 });

		await page.goto(`/player/${userId}`);
		await page.waitForResponse(resp =>
			resp.url().includes('/api/player/') && resp.status() === 200,
			{ timeout: 10000 }
		);
		await expect(page.getByTestId('achievements-gallery')).toBeVisible();

		const fourthBadge = page.getByTestId('achievement-item').filter({ hasText: 'Fourth Place' });
		await expect(fourthBadge).toBeVisible();
		await expect(fourthBadge.getByTestId('achievement-count-pill')).toHaveCount(0);
	});

	test('achievement summary shows correct unlock ratio', async ({
		page,
		injectStank,
		injectAchievement
	}) => {
		const userId = makeId();
		await injectStank(GUILD, userId, 'SummaryPlayer');
		// Unlock 3 achievements
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'first_stank', count: 1 });
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'chain_starter', count: 1 });
		await injectAchievement({ guildId: GUILD, userId, achievementKey: 'fourth_place', count: 2 });

		await page.goto(`/player/${userId}`);
		await page.waitForResponse(resp =>
			resp.url().includes('/api/player/') && resp.status() === 200,
			{ timeout: 10000 }
		);
		await expect(page.getByTestId('achievements-gallery')).toBeVisible();

		// Summary should say "3 of N unlocked"
		await expect(page.getByTestId('achievements-summary')).toContainText('3 of ');
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
		// Navigate to the board so the WebSocket is connected
		await expect(page.getByTestId('live-badge')).toBeVisible({ timeout: 10000 });
		await expect(page.getByTestId('live-badge')).toHaveAttribute('title', /Receiving live updates/);

		// Broadcast an achievement event
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

		// Toast should appear with the achievement message
		await expect(page.getByRole('alert').filter({ hasText: 'Achievement unlocked: First Stank!' })).toBeVisible({
			timeout: 5000
		});
	});

	test('achievement toast shows correct badge name', async ({
		page,
		injectAchievementBroadcast
	}) => {
		await expect(page.getByTestId('live-badge')).toBeVisible({ timeout: 10000 });
		await expect(page.getByTestId('live-badge')).toHaveAttribute('title', /Receiving live updates/);

		await injectAchievementBroadcast({
			guildId: GUILD,
			userId: defaultUser.user_id,
			badge: {
				key: 'fourth_place',
				name: 'Fourth Place',
				icon: '4️⃣',
				description: 'Finished 4th in SP earned during a session.'
			}
		});

		await expect(page.getByRole('alert').filter({ hasText: 'Achievement unlocked: Fourth Place!' })).toBeVisible({
			timeout: 5000
		});
	});
});
