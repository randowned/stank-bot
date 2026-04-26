const STORAGE_PREFIX = 'stankbot:';

export function getCache<T>(key: string): T | null {
	if (typeof window === 'undefined') return null;
	const data = sessionStorage.getItem(STORAGE_PREFIX + key);
	if (!data) return null;
	try {
		return JSON.parse(data) as T;
	} catch {
		return null;
	}
}

export function setCache<T>(key: string, value: T): void {
	if (typeof window === 'undefined') return;
	sessionStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
}

export function clearCache(key?: string): void {
	if (typeof window === 'undefined') return;
	if (key) {
		sessionStorage.removeItem(STORAGE_PREFIX + key);
	} else {
		// Clear all stankbot caches
		const keysToRemove: string[] = [];
		for (let i = 0; i < sessionStorage.length; i++) {
			const k = sessionStorage.key(i);
			if (k?.startsWith(STORAGE_PREFIX)) {
				keysToRemove.push(k);
			}
		}
		keysToRemove.forEach((k) => sessionStorage.removeItem(k));
	}
}