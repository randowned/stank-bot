import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		proxy: {
			'^/v2/api': {
				target: 'http://localhost:8000',
				changeOrigin: true
			},
			'^/v2/ws': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				ws: true
			},
			'^/v2/auth': {
				target: 'http://localhost:8000',
				changeOrigin: true
			},
			'^/v2/ping': {
				target: 'http://localhost:8000',
				changeOrigin: true
			},
			'^/auth': {
				target: 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});