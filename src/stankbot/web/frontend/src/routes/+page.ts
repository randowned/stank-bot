import type { PageLoad } from './$types';
import { apiFetch } from '$lib/api';
import { loadWithFallback } from '$lib/api-utils';
import type { BoardState } from '$lib/types';

export const load: PageLoad = async ({ fetch, parent }) => {
	const { user, guild_name: authGuildName } = await parent();
	if (!user) return { state: null, guild_name: 'StankBot' };

	const state = await loadWithFallback<BoardState | null>(
		() => apiFetch<BoardState>('/api/board', { fetch }),
		{ fallback: null }
	);
	return { state, guild_name: authGuildName || state?.guild_name || 'StankBot' };
};
