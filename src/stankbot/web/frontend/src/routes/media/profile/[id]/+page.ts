import type { Load } from '@sveltejs/kit';
import { loadWithFallback } from '$lib/api-utils';
import { apiFetch } from '$lib/api';
import type { ProfileDetail, ProviderDef } from '$lib/types';

export const load: Load = async ({ params, fetch }) => {
	const profileId = Number(params.id);

	const detail = await loadWithFallback<ProfileDetail | null>(
		() => apiFetch<ProfileDetail>(`/api/media/profile/${profileId}`, { fetch }),
		{ fallback: null }
	);

	const providers = await loadWithFallback<ProviderDef[]>(
		() =>
			apiFetch<{ providers: ProviderDef[] }>('/api/media/providers', {
				fetch
			}).then((r) => r.providers),
		{ fallback: [] }
	);

	return { detail, profileId, providers };
};
