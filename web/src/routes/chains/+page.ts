import type { PageLoad } from './$types';
import type { ChainSummary } from '../../app.d';
import { apiFetch } from '$lib/api';

export const load: PageLoad = async () => {
	try {
		const chains = await apiFetch<ChainSummary[]>('/v2/api/chains');
		return { chains };
	} catch {
		return { chains: [] };
	}
};