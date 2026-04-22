import type { PageLoad } from './$types';
import { apiFetch } from '$lib/api';
import type { BoardState } from '../app.d';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const state = await apiFetch<BoardState>('/v2/api/board', { fetch });
		return { state, guild_name: state.guild_name || 'StankBot' };
	} catch {
		return { state: null, guild_name: 'StankBot' };
	}
};
