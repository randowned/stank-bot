import type { PageLoad } from './$types';
import type { PlayerProfile } from '../../../app.d';
import { apiFetch } from '$lib/api';

export const load: PageLoad = async ({ params }) => {
	const userId = params.id;

	try {
		const profile = await apiFetch<PlayerProfile>(`/v2/api/player/${userId}`);
		return { profile };
	} catch {
		return { profile: null };
	}
};