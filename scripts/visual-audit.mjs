// Local-only visual audit — NOT in CI. Run with `node scripts/visual-audit.mjs`.
// Captures a screenshot of every key route at 4 viewports, checks for horizontal
// overflow and undersized touch targets. Output: PNG snapshots in
// scripts/visual-audit-snapshots/ + a findings list printed to stdout.
//
// Reason this isn't in CI: pixel-level checks are inherently flaky across
// minor CSS tweaks, and the same checks (touch-target ≥44px, no horizontal
// overflow) belong in a linter or static a11y check. Kept here as a manual
// QA tool for design review.

import { chromium } from 'playwright';
import { spawn } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import * as fs from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');
const snapDir = resolve(__dirname, 'visual-audit-snapshots');

const viewports = [
	{ name: 'mobile-sm', width: 375, height: 812 },
	{ name: 'mobile-lg', width: 430, height: 932 },
	{ name: 'tablet', width: 768, height: 1024 },
	{ name: 'desktop', width: 1440, height: 900 }
];

const routes = [
	{ path: '/', name: 'empty' },
	{ path: '/media', name: 'media-cards', auth: true, seed: true },
	{ path: '/media/profiles', name: 'media-empty-profiles', auth: true },
	{ path: '/admin', name: 'admin', auth: 'admin' },
	{ path: '/admin/settings', name: 'admin-settings', auth: 'admin' },
	{ path: '/admin/templates', name: 'admin-templates', auth: 'admin' },
	{ path: '/admin/media', name: 'admin-media', auth: 'admin' }
];

function startBackend() {
	const log = fs.createWriteStream(resolve(repoRoot, '.stankbot_backend.log'), { flags: 'w' });
	const proc = spawn('uv', ['run', 'python', '-m', 'stankbot'], {
		cwd: repoRoot,
		env: { ...process.env, ENV: 'dev-mock', PYTHONPATH: resolve(repoRoot, 'src') },
		stdio: ['ignore', 'pipe', 'pipe']
	});
	proc.stdout.pipe(log);
	proc.stderr.pipe(log);
	return proc;
}

async function healthCheck() {
	for (let i = 0; i < 60; i++) {
		try {
			const r = await fetch('http://127.0.0.1:8000/healthz');
			if (r.ok) return true;
		} catch {}
		await new Promise((r) => setTimeout(r, 500));
	}
	return false;
}

async function main() {
	if (!fs.existsSync(snapDir)) fs.mkdirSync(snapDir, { recursive: true });

	console.log('Starting backend...');
	const backend = startBackend();
	if (!(await healthCheck())) {
		console.error('Backend failed to start within 30s. Check .stankbot_backend.log');
		backend.kill();
		process.exit(1);
	}

	const browser = await chromium.launch();
	const findings = [];

	try {
		for (const vp of viewports) {
			const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
			const page = await ctx.newPage();

			for (const r of routes) {
				const user = r.auth === 'admin'
					? { user_id: 222222222, username: 'AuditAdmin', guild: 123456789, is_global_admin: true, is_guild_admin: true }
					: { user_id: 111111111, username: 'Audit', guild: 123456789, is_global_admin: false, is_guild_admin: false };
				await page.request.post('http://127.0.0.1:8000/auth/mock-login', { data: user });

				await page.goto(`http://127.0.0.1:8000${r.path}`);
				await page.waitForLoadState('domcontentloaded');
				const file = `${snapDir}/${r.name}_${vp.name}.png`;
				await page.screenshot({ path: file, fullPage: true });
				const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
				if (overflow) findings.push(`[${vp.name}] ${r.path}: horizontal overflow`);
				const small = await page.evaluate(() => {
					const els = document.querySelectorAll('button, a, [role="button"], input, select, textarea');
					const bad = [];
					els.forEach((el) => {
						const r = el.getBoundingClientRect();
						if (r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44)) {
							bad.push(`${el.tagName.toLowerCase()} (${Math.round(r.width)}×${Math.round(r.height)})`);
						}
					});
					return bad.slice(0, 5);
				});
				for (const t of small) findings.push(`[${vp.name}] ${r.path}: small touch target ${t}`);
			}
			await ctx.close();
		}
	} finally {
		await browser.close();
		backend.kill();
	}

	console.log(`\n=== ${findings.length} visual audit findings ===`);
	for (const f of findings) console.log('  ' + f);
	console.log(`Snapshots: ${snapDir}/`);
	process.exit(findings.length === 0 ? 0 : 1);
}

main().catch((e) => {
	console.error(e);
	process.exit(1);
});
