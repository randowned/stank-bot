/// <reference types="@sveltejs/kit" />

import { build, files, version } from '$service-worker';

const CACHE = `cache-${version}`;

self.addEventListener('install', (event) => {
	event.waitUntil(
		(async () => {
			try {
				const cache = await caches.open(CACHE);
				await cache.addAll(build.concat(files));
			} catch (err) {
				console.error('[SW] Install failed:', err);
			}
		})()
	);
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			try {
				const keys = await caches.keys();
				await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
			} catch (err) {
				console.error('[SW] Activate failed:', err);
			}
		})()
	);
});

self.addEventListener('fetch', (event) => {
	if (event.request.method !== 'GET') return;
	event.respondWith(
		(async () => {
			try {
				const cached = await caches.match(event.request);
				return cached ?? fetch(event.request);
			} catch {
				return fetch(event.request);
			}
		})()
	);
});
