import { test as base, expect as baseExpect, type Page } from '@playwright/test';

export const expect = baseExpect;

export interface MockUser {
	user_id: number;
	username: string;
	avatar?: string | null;
	guilds?: Array<{ id: number; name: string; permissions: number }>;
	guild?: number;
	is_admin?: boolean;
}

const defaultUser: MockUser = {
	user_id: 111111111,
	username: 'E2E Tester',
	avatar: null,
	guilds: [{ id: 123456789, name: 'Test Server', permissions: 0x20 }],
	guild: 123456789,
	is_admin: true
};

export const test = base.extend<{
	mockLogin: (user?: MockUser) => Promise<void>;
	injectStank: (guildId: number, userId: number, displayName: string) => Promise<void>;
	injectBreak: (guildId: number, userId: number, displayName: string) => Promise<void>;
	startRandomEvents: (interval?: number) => Promise<void>;
	stopRandomEvents: () => Promise<void>;
}>({
	mockLogin: async ({ page }, use) => {
		await use(async (user = defaultUser) => {
			const response = await page.request.post('/auth/mock-login', { data: user });
			expect(response.ok()).toBeTruthy();
			await page.goto('/v2');
		});
	},

	injectStank: async ({ page }, use) => {
		await use(async (guildId, userId, displayName) => {
			const response = await page.request.post('/v2/api/mock/stank', {
				data: { guild_id: guildId, user_id: userId, display_name: displayName }
			});
			if (!response.ok()) {
				const body = await response.text().catch(() => 'unknown');
				console.error('injectStank failed:', response.status(), body);
			}
			expect(response.ok()).toBeTruthy();
		});
	},

	injectBreak: async ({ page }, use) => {
		await use(async (guildId, userId, displayName) => {
			const response = await page.request.post('/v2/api/mock/break', {
				data: { guild_id: guildId, user_id: userId, display_name: displayName }
			});
			if (!response.ok()) {
				const body = await response.text().catch(() => 'unknown');
				console.error('injectBreak failed:', response.status(), body);
			}
			expect(response.ok()).toBeTruthy();
		});
	},

	startRandomEvents: async ({ page }, use) => {
		await use(async (interval = 2) => {
			await page.request.post('/v2/api/mock/random/start', { data: { interval } });
		});
	},

	stopRandomEvents: async ({ page }, use) => {
		await use(async () => {
			await page.request.post('/v2/api/mock/random/stop');
		});
	}
});
