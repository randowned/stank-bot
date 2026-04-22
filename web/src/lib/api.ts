import { Packr } from 'msgpackr';

const packr = new Packr({ useRecords: false });

export async function apiFetch<T>(path: string, options?: { fetch?: typeof fetch; init?: RequestInit }): Promise<T> {
	const customFetch = options?.fetch ?? fetch;
	const headers = new Headers(options?.init?.headers);
	if (!headers.has('Accept')) {
		headers.set('Accept', 'application/msgpack, application/json');
	}

	const response = await customFetch(path, { ...options?.init, headers });

	if (!response.ok) {
		throw new Error(`API request failed: ${response.status} ${response.statusText}`);
	}

	const contentType = response.headers.get('content-type') || '';
	if (contentType.includes('msgpack')) {
		return packr.unpack(new Uint8Array(await response.arrayBuffer())) as T;
	}
	return response.json() as Promise<T>;
}
