import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: './e2e',
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: 1,
	reporter: 'html',

	projects: [
		{
			name: 'smoke',
			testMatch: /smoke\.spec\.ts/,
			use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:5173' }
		},
		{
			name: 'e2e',
			testMatch: /\.spec\.ts/,
			testIgnore: /smoke\.spec\.ts/,
			use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:5173' }
		}
	],

	webServer: [
		{
			command: 'npm run dev',
			url: 'http://localhost:5173',
			reuseExistingServer: !process.env.CI,
			timeout: process.env.CI ? 60000 : 30000
		}
	]
});
