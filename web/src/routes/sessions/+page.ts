import type { PageLoad } from './$types';
import type { SessionSummary } from '../../app.d';
import { apiFetch } from '$lib/api';

export const load: PageLoad = async () => {
	try {
		const sessions = await apiFetch<SessionSummary[]>('/v2/api/sessions');
		return { sessions };
	} catch {
		return { sessions: [] };
	}
};