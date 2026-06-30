import { test as base, expect as baseExpect, type Page } from '@playwright/test';

export const expect = baseExpect;

// ---- Per-test DB reset to prevent cross-test data contamination ----
// With workers=1, spec files run sequentially in one worker. The shared
// SQLite mock DB accumulates data across tests within the same file,
// causing assertion failures (e.g. achievement count "2 of 10" instead of
// "1 of 10"). This resets the mock backend DB before every single test.

base.beforeEach(async ({ request }) => {
  try {
    await request.post('http://127.0.0.1:8000/api/mock/db/reset');
  } catch {
    // Backend may not be ready yet — first reset can race startup
  }
});

async function waitForBackend(page: Page, timeoutMs = 10000): Promise<void> {
	const started = Date.now();
	while (Date.now() - started < timeoutMs) {
		try {
			const resp = await page.request.get('/ping');
			if (resp.ok()) return;
		} catch {
			// backend not reachable yet
		}
		await new Promise((r) => setTimeout(r, 100));
	}
	throw new Error(
		`Backend not reachable at /ping after ${timeoutMs}ms. ` +
			'Is the backend running? Run `npm run e2e` to auto-start it.'
	);
}

export interface MockUser {
	user_id: number;
	username: string;
	avatar?: string | null;
	guild?: number;
	is_global_admin?: boolean;
	is_guild_admin?: boolean;
}

export const defaultUser: MockUser = {
	user_id: 111111111,
	username: 'E2E Tester',
	avatar: null,
	guild: 123456789,
	is_global_admin: false,
	is_guild_admin: false
};

export const adminUser: MockUser = {
	user_id: 222222222,
	username: 'E2E Admin',
	avatar: null,
	guild: 123456789,
	is_global_admin: true,
	is_guild_admin: true
};

export const guildAdminUser: MockUser = {
	user_id: 333333333,
	username: 'E2E Guild Admin',
	avatar: null,
	guild: 123456789,
	is_global_admin: false,
	is_guild_admin: true
};

export interface BotGuild {
	id: number;
	name: string;
	icon?: string | null;
}

export const test = base.extend<{
	mockLogin: (user?: MockUser) => Promise<void>;
	mockBotGuilds: (guilds: BotGuild[]) => Promise<void>;
	newSession: (guild?: number) => Promise<void>;
	resetDb: () => Promise<void>;
	injectStank: (guildId: number, userId: number, displayName: string) => Promise<void>;
	injectBreak: (guildId: number, userId: number, displayName: string) => Promise<void>;
	injectReaction: (guildId: number, messageId: number, userId: number) => Promise<void>;
	startRandomEvents: (interval?: number) => Promise<void>;
	stopRandomEvents: () => Promise<void>;
	injectMedia: (opts?: { guildId?: number; mediaType?: string; slug?: string; historyDays?: number }) => Promise<{ id: number; name: string }>;
	clearMedia: (guildId?: number) => Promise<void>;
	injectMediaMilestone: (opts?: { guildId?: number; mediaItemId?: number; mediaType?: string; metricKey?: string; milestoneValue?: number; newValue?: number; title?: string }) => Promise<void>;
	injectOwnerMetricUpdate: (opts?: { guildId?: number; ownerId?: number; mediaType?: string; metricKey?: string; value?: number }) => Promise<void>;
	injectMediaMetrics: (mediaItemId: number, metrics: Record<string, number>, guildId?: number) => Promise<void>;
	injectLeaderboardSeed: (opts?: { guildId?: number; count?: number; baseUserId?: number; prefix?: string }) => Promise<{ injected: number; guild_id: number }>;
	injectVersionBroadcast: (opts?: { guildId?: number; serverVersion?: string; clientVersion?: string }) => Promise<void>;
	injectAchievement: (opts?: { guildId?: number; userId?: number; achievementKey?: string; count?: number; broadcast?: boolean }) => Promise<void>;
	injectAchievementBroadcast: (opts?: { guildId?: number; userId?: number; badge?: { key: string; name: string; icon: string; description: string } }) => Promise<void>;
}>({
	mockLogin: async ({ page }, use) => {
		await use(async (user = defaultUser) => {
			await waitForBackend(page);
			const response = await page.request.post('/auth/mock-login', { data: user });
			expect(response.ok()).toBeTruthy();
			// Navigate first so evaluate runs in the correct origin
			await page.goto('/');
			// Disable animations for E2E — runs before any page JS
			await page.addInitScript(() => {
				document.documentElement.classList.add('e2e');
			});
			// Suppress version-mismatch toast by syncing localStorage version
			const vResp = await page.request.get('/api/version');
			const { version } = await vResp.json();
			await page.evaluate(
				([v]) => {
					try {
						sessionStorage.removeItem('stankbot:auth');
						sessionStorage.removeItem('stankbot:guilds');
						localStorage.setItem('stankbot:version', v);
					} catch {}
				},
				[version]
			);
			await page.reload();
		});
	},

	mockBotGuilds: async ({ page }, use) => {
		await use(async (guilds) => {
			const response = await page.request.post('/api/mock/bot-guilds', { data: { guilds } });
			expect(response.ok()).toBeTruthy();
			// Clear frontend guilds cache so next page load fetches fresh data
			await page.evaluate(() => {
				try { sessionStorage.removeItem('stankbot:guilds'); } catch {}
			});
		});
	},

	newSession: async ({ page }, use) => {
		// Optional GUILD override — tests that work on a non-default guild must pass it.
		let activeGuild: number | undefined;
		await use(async (guild?: number) => {
			activeGuild = guild;
			const body = guild ? { guild_id: guild } : {};
			// Break any active chain so the counter resets to 0, then start a new session.
			// Mock endpoints commit before returning the response — no client-side wait needed.
			await page.request.post('/api/mock/break', { data: body });
			await page.request.post('/api/mock/session/end', { data: body });
			await page.reload();
		});
	},

	resetDb: async ({ page }, use) => {
		await use(async () => {
			await page.request.post('/api/mock/db/reset');
			await page.reload();
		});
	},

	injectStank: async ({ page }, use) => {
		await use(async (guildId, userId, displayName) => {
			const response = await page.request.post('/api/mock/stank', {
				data: { guild_id: guildId, user_id: userId, display_name: displayName }
			});
			if (!response.ok()) {
				const body = await response.text().catch(() => 'unknown');
				console.error('injectStank failed:', response.status(), body);
			}
			expect(response.ok()).toBeTruthy();
			return response.json() as Promise<{ message_id: number; chain_id: number; chain_length: number; sp_awarded: number }>;
		});
	},

	injectBreak: async ({ page }, use) => {
		await use(async (guildId, userId, displayName) => {
			const response = await page.request.post('/api/mock/break', {
				data: { guild_id: guildId, user_id: userId, display_name: displayName }
			});
			if (!response.ok()) {
				const body = await response.text().catch(() => 'unknown');
				console.error('injectBreak failed:', response.status(), body);
			}
			expect(response.ok()).toBeTruthy();
		});
	},

	injectReaction: async ({ page }, use) => {
		await use(async (guildId, messageId, userId) => {
			const response = await page.request.post('/api/mock/reaction', {
				data: { guild_id: guildId, message_id: messageId, user_id: userId }
			});
			if (!response.ok()) {
				const body = await response.text().catch(() => 'unknown');
				console.error('injectReaction failed:', response.status(), body);
			}
			expect(response.ok()).toBeTruthy();
		});
	},

	startRandomEvents: async ({ page }, use) => {
		await use(async (interval = 2) => {
			await page.request.post('/api/mock/random/start', { data: { interval } });
		});
	},

	stopRandomEvents: async ({ page }, use) => {
		await use(async () => {
			await page.request.post('/api/mock/random/stop');
		});
	},

	injectMedia: async ({ page }, use) => {
		await use(async (opts = {}) => {
			const guildId = opts.guildId ?? 123456789;
			const mediaType = opts.mediaType ?? 'youtube';
			const name = opts.slug ?? `e2e-test-${Date.now() % 100000}`;
			const historyDays = opts.historyDays ?? 30;
			const response = await page.request.post('/api/mock/media', {
				data: { guild_id: guildId, media_type: mediaType, name, history_days: historyDays }
			});
			if (!response.ok()) {
				const body = await response.text().catch(() => 'unknown');
				console.error('injectMedia failed:', response.status(), body);
			}
			expect(response.ok()).toBeTruthy();
			return response.json() as Promise<{ id: number; name: string }>;
		});
	},

	clearMedia: async ({ page }, use) => {
		await use(async (guildId = 123456789) => {
			await page.request.post('/api/mock/clear-media', { data: { guild_id: guildId } });
		});
	},

	injectMediaMilestone: async ({ page }, use) => {
		await use(async (opts = {}) => {
			const response = await page.request.post('/api/mock/media-milestone', {
				data: {
					guild_id: opts.guildId ?? 123456789,
					media_item_id: opts.mediaItemId ?? 1,
					media_type: opts.mediaType ?? 'youtube',
					metric_key: opts.metricKey ?? 'view_count',
					milestone_value: opts.milestoneValue ?? 10000,
					new_value: opts.newValue ?? 10001,
					title: opts.title ?? 'Mock Milestone'
				}
			});
			expect(response.ok()).toBeTruthy();
		});
	},

	injectOwnerMetricUpdate: async ({ page }, use) => {
		await use(async (opts = {}) => {
			const response = await page.request.post('/api/mock/owner-metric-update', {
				data: {
					guild_id: opts.guildId ?? 123456789,
					owner_id: opts.ownerId ?? 1,
					media_type: opts.mediaType ?? 'youtube',
					metric_key: opts.metricKey ?? 'subscriber_count',
					value: opts.value ?? 1_000_000
				}
			});
			expect(response.ok()).toBeTruthy();
		});
	},

	injectMediaMetrics: async ({ page }, use) => {
		await use(async (mediaItemId, metrics, guildId = 123456789) => {
			const response = await page.request.post('/api/mock/media-metrics', {
				data: { guild_id: guildId, media_item_id: mediaItemId, metrics }
			});
			expect(response.ok()).toBeTruthy();
		});
	},

	injectLeaderboardSeed: async ({ page }, use) => {
		await use(async (opts = {}) => {
			const response = await page.request.post('/api/mock/leaderboard-seed', {
				data: {
					guild_id: opts.guildId ?? 123456789,
					count: opts.count ?? 25,
					base_user_id: opts.baseUserId ?? 10_000,
					prefix: opts.prefix ?? 'SeedUser'
				}
			});
			expect(response.ok()).toBeTruthy();
			return response.json() as Promise<{ injected: number; guild_id: number }>;
		});
	},

	injectVersionBroadcast: async ({ page }, use) => {
		await use(async (opts = {}) => {
			const response = await page.request.post('/api/mock/version-broadcast', {
				data: {
					guild_id: opts.guildId ?? 123456789,
					server_version: opts.serverVersion ?? '99.99.99',
					client_version: opts.clientVersion ?? '0.0.0'
				}
			});
			expect(response.ok()).toBeTruthy();
		});
	},

	injectAchievement: async ({ page }, use) => {
		await use(async (opts = {}) => {
			const response = await page.request.post('/api/mock/achievement', {
				data: {
					guild_id: opts.guildId ?? 123456789,
					user_id: opts.userId ?? 1001,
					achievement_key: opts.achievementKey ?? 'first_stank',
					count: opts.count ?? 1,
					broadcast: opts.broadcast ?? false
				}
			});
			if (!response.ok()) {
				const body = await response.text().catch(() => 'unknown');
				console.error('injectAchievement failed:', response.status(), body);
			}
			expect(response.ok()).toBeTruthy();
		});
	},

	injectAchievementBroadcast: async ({ page }, use) => {
		await use(async (opts = {}) => {
			const response = await page.request.post('/api/mock/achievement-broadcast', {
				data: {
					guild_id: opts.guildId ?? 123456789,
					user_id: opts.userId ?? 1001,
					badge: opts.badge ?? {
						key: 'first_stank',
						name: 'First Stank',
						icon: '✨',
						description: 'Dropped your very first stank.'
					}
				}
			});
			expect(response.ok()).toBeTruthy();
		});
	}
});
