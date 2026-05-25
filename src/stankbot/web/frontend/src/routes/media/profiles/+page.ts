import type { Load } from '@sveltejs/kit';
import { loadWithFallback } from '$lib/api-utils';
import { apiFetch } from '$lib/api';
import type { MediaOwner, ProviderDef } from '$lib/types';

export const load: Load = async ({ fetch, parent }) => {
	const { user } = await parent();
	if (!user) return { profiles: [], providers: [] };

	const profiles = await loadWithFallback<MediaOwner[]>(
		() =>
			apiFetch<{ profiles: MediaOwner[] }>('/api/media/profiles', { fetch }).then(
				(r) => r.profiles
			),
		{ fallback: [] }
	);

	const providers = await loadWithFallback<ProviderDef[]>(
		() =>
			apiFetch<{ providers: ProviderDef[] }>('/api/media/providers', {
				fetch
			}).then((r) => r.providers),
		{ fallback: [] }
	);

	return { profiles, providers };
};
