import { test, expect, defaultUser } from './fixtures';

const GUILD = 123456805;

test.describe('Datetime serialization', () => {
	test.beforeEach(async ({ mockLogin, newSession }) => {
		await mockLogin({ ...defaultUser, guild: GUILD });
		await newSession();
	});

	test('all API datetime fields use +00:00 UTC offset', async ({ page, injectStank }) => {
		const STANKER = 6001;
		await injectStank(GUILD, STANKER, 'TimeTestUser');

		// Check chain API
		const chain = await injectStank(GUILD, 6002, 'TimeTestUser2');
		const chainRes = await page.request.get(`/api/chain/${chain.chain_id}`);
		const chainBody = await chainRes.json();
		expect(chainBody.started_at).toMatch(/\+00:00$/);
		for (const item of chainBody.timeline ?? []) {
			if (item.created_at) expect(item.created_at).toMatch(/\+00:00$/);
		}

		// Check player API
		const playerRes = await page.request.get(`/api/player/${STANKER}`);
		const playerBody = await playerRes.json();
		if (playerBody.last_stank_at) {
			expect(playerBody.last_stank_at).toMatch(/\+00:00$/);
		}
	});
});
