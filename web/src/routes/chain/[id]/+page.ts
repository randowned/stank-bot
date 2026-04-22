import type { PageLoad } from './$types';
import type { ChainSummary } from '../../../app.d';
import { apiFetch } from '$lib/api';

export const load: PageLoad = async ({ params }) => {
	const chainId = params.id;

	try {
		const chain = await apiFetch<ChainSummary>(`/v2/api/chain/${chainId}`);
		return { chain };
	} catch {
		return { chain: null };
	}
};