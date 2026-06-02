import { test, expect } from './fixtures';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const GUILD = 123456789;
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SNAPSHOT_DIR = path.resolve(__dirname, '__snapshots__');

const viewports = [
	{ name: 'mobile-sm', width: 375, height: 812 },
	{ name: 'mobile-lg', width: 430, height: 932 },
	{ name: 'tablet', width: 768, height: 1024 },
	{ name: 'desktop', width: 1440, height: 900 },
];

function shotPath(route: string, viewport: string, suffix = '') {
	const safe = route.replace(/[^a-z0-9]/gi, '_').replace(/_+/g, '_').replace(/_$/, '');
	const file = `${safe}_${viewport}${suffix ? '_' + suffix : ''}.png`;
	return path.join(SNAPSHOT_DIR, file);
}

function ensureDir() {
	if (!fs.existsSync(SNAPSHOT_DIR)) {
		fs.mkdirSync(SNAPSHOT_DIR, { recursive: true });
	}
}

async function safeEvaluate(page: any, fn: () => any, retries = 3): Promise<any> {
	for (let i = 0; i < retries; i++) {
		try {
			return await page.evaluate(fn);
		} catch (e) {
			if (i === retries - 1) throw e;
			await page.waitForTimeout(300);
		}
	}
}

async function safeGoto(page: any, url: string, retries = 3) {
	for (let i = 0; i < retries; i++) {
		try {
			await page.goto(url);
			return;
		} catch (e: any) {
			if (i === retries - 1) throw e;
			if (e.message?.includes('ERR_ABORTED')) {
				await page.waitForTimeout(500);
			} else {
				throw e;
			}
		}
	}
}

async function checkOverflow(page: any, route: string, viewport: string, findings: string[]) {
	const overflow = await safeEvaluate(page, () => {
		return document.documentElement.scrollWidth > window.innerWidth;
	});
	if (overflow) {
		findings.push(`[${viewport}] ${route}: horizontal overflow detected`);
	}
}

async function checkTouchTargets(page: any, route: string, viewport: string, findings: string[]) {
	const small = await safeEvaluate(page, () => {
		const els = document.querySelectorAll('button, a, [role="button"], input, select, textarea, [onclick]');
		const bad: string[] = [];
		els.forEach((el) => {
			const rect = el.getBoundingClientRect();
			if (rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44)) {
				const text = (el.textContent || '').slice(0, 30).trim();
				bad.push(`${el.tagName.toLowerCase()}${text ? ` "${text}"` : ''} (${Math.round(rect.width)}×${Math.round(rect.height)})`);
			}
		});
		return bad.slice(0, 10);
	});
	for (const item of small) {
		findings.push(`[${viewport}] ${route}: small touch target ${item}`);
	}
}

test.describe('Visual Audit', () => {
	test.beforeAll(() => {
		ensureDir();
	});

	test('capture all routes at all viewports', async ({ page, mockLogin, newSession, injectMedia, injectLeaderboardSeed, clearMedia }) => {
		test.setTimeout(120_000);
		const findings: string[] = [];

		// ---- Seed data once (outside viewport loop) ----
		await mockLogin();
		await newSession();
		await injectLeaderboardSeed({ guildId: GUILD, count: 22, prefix: 'AuditUser' });
		await clearMedia();
		const item1 = await injectMedia({ guildId: GUILD, slug: `audit-video-${Date.now()}`, historyDays: 7 });
		const item2 = await injectMedia({ guildId: GUILD, slug: `audit-spotify-${Date.now()}`, mediaType: 'spotify', historyDays: 7 });

		for (const vp of viewports) {
			await page.setViewportSize({ width: vp.width, height: vp.height });

			// ---- Unauthenticated welcome page ----
			await safeGoto(page, '/');
			await page.waitForLoadState('domcontentloaded');
			await page.screenshot({ path: shotPath('/', vp.name), fullPage: true });
			await checkOverflow(page, '/', vp.name, findings);
			await checkTouchTargets(page, '/', vp.name, findings);

			// ---- Authenticated empty dashboard ----
			await safeGoto(page, '/');
			await page.waitForLoadState('domcontentloaded');
			await page.screenshot({ path: shotPath('/empty', vp.name), fullPage: true });
			await checkOverflow(page, '/ (empty)', vp.name, findings);
			await checkTouchTargets(page, '/ (empty)', vp.name, findings);

			// ---- Populated dashboard ----
			await safeGoto(page, '/');
			await page.waitForLoadState('domcontentloaded');
			await page.waitForTimeout(500);
			await page.screenshot({ path: shotPath('/populated', vp.name), fullPage: true });
			await checkOverflow(page, '/ (populated)', vp.name, findings);

			// ---- Player profile ----
			await safeGoto(page, `/player/10001`);
			await page.waitForLoadState('domcontentloaded');
			await page.screenshot({ path: shotPath('/player', vp.name), fullPage: true });
			await checkOverflow(page, '/player', vp.name, findings);

			// ---- Media list empty ----
			await safeGoto(page, '/media');
			await page.waitForLoadState('domcontentloaded');
			await page.screenshot({ path: shotPath('/media-empty', vp.name), fullPage: true });
			await checkOverflow(page, '/media (empty)', vp.name, findings);

			// ---- Media list with cards ----
			await safeGoto(page, '/media');
			await page.waitForLoadState('domcontentloaded');
			await page.screenshot({ path: shotPath('/media-cards', vp.name), fullPage: true });
			await checkOverflow(page, '/media (cards)', vp.name, findings);

			// ---- Media detail single chart ----
			await safeGoto(page, `/media/${item1.id}`);
			await page.waitForLoadState('domcontentloaded');
			await page.waitForTimeout(800);
			await page.screenshot({ path: shotPath('/media-detail', vp.name), fullPage: true });
			await checkOverflow(page, '/media/:id', vp.name, findings);

			// ---- Media detail compare mode ----
			await safeGoto(page, `/media/${item1.id}?compare=${item2.id}&metric=view_count&days=2`);
			await page.waitForLoadState('domcontentloaded');
			await page.waitForTimeout(800);
			await page.screenshot({ path: shotPath('/media-compare', vp.name), fullPage: true });
			await checkOverflow(page, '/media/:id (compare)', vp.name, findings);

			// ---- Admin dashboard ----
			await safeGoto(page, '/admin');
			await page.waitForLoadState('domcontentloaded');
			await page.screenshot({ path: shotPath('/admin', vp.name), fullPage: true });
			await checkOverflow(page, '/admin', vp.name, findings);

			// ---- Admin settings ----
			await safeGoto(page, '/admin/settings');
			await page.waitForLoadState('domcontentloaded');
			await page.waitForTimeout(500);
			await page.screenshot({ path: shotPath('/admin-settings', vp.name), fullPage: true });
			await checkOverflow(page, '/admin/settings', vp.name, findings);

			// ---- Admin templates ----
			await safeGoto(page, '/admin/templates');
			await page.waitForLoadState('domcontentloaded');
			await page.waitForTimeout(500);
			await page.screenshot({ path: shotPath('/admin-templates', vp.name), fullPage: true });
			await checkOverflow(page, '/admin/templates', vp.name, findings);

			// ---- Admin media ----
			await page.goto('/admin/media');
			await page.waitForLoadState('domcontentloaded');
			await page.screenshot({ path: shotPath('/admin-media', vp.name), fullPage: true });
			await checkOverflow(page, '/admin/media', vp.name, findings);
		}

		// Print findings summary
		console.log('\n=== VISUAL AUDIT FINDINGS ===\n');
		if (findings.length === 0) {
			console.log('No issues detected.\n');
		} else {
			for (const f of findings) {
				console.log(f);
			}
			console.log(`\nTotal findings: ${findings.length}\n`);
		}
		console.log(`Snapshots written to: ${SNAPSHOT_DIR}\n`);

		expect(findings.length).toBe(0);
	});
});
