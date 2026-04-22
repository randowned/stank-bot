import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
	resolve: {
		alias: {
			'$app/paths': path.resolve(__dirname, 'src/__mocks__/app-paths.ts'),
			'$app/environment': path.resolve(__dirname, 'src/__mocks__/app-environment.ts'),
			'$lib/stores': path.resolve(__dirname, 'src/__mocks__/stores.ts')
		}
	},
	test: {
		include: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
		environment: 'jsdom',
		globals: true
	}
});