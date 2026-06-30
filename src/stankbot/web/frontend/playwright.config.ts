import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: './e2e',
	// Per-file parallelism: tests within a file run sequentially in one worker
	// (preserves the per-test DB reset guarantee), different files run in
	// parallel via worker pool. Per-file GUILD constants (achievements: 123456800,
	// board: 123456804, etc.) prevent cross-file data collision.
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: 3,
	reporter: 'html',

	projects: [
		{
			name: 'smoke',
			testMatch: /smoke\.spec\.ts/,
			use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:8000' }
		},
		{
			name: 'e2e',
			testMatch: /\.spec\.ts/,
			testIgnore: /smoke\.spec\.ts/,
			use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:8000' }
		}
	]
});
