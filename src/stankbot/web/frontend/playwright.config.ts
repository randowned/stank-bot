import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: './e2e',
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: 3,
	reporter: 'html',

	projects: [
		{
			name: 'smoke',
			testMatch: /smoke\.spec\.ts/,
			use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:4173' }
		},
		{
			name: 'e2e',
			testMatch: /\.spec\.ts/,
			testIgnore: /smoke\.spec\.ts/,
			use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:4173' }
		}
	],

	webServer: [
		{
			command: 'npm run build && node ../../../../scripts/static-server.mjs',
			url: 'http://localhost:4173',
			reuseExistingServer: !process.env.CI,
			timeout: process.env.CI ? 180000 : 60000
		}
	]
});
