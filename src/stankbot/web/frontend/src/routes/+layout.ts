import type { LayoutLoad } from './$types';
import type { GuildInfo } from '$lib/types';

export const load: LayoutLoad = async ({ fetch }) => {
	try {
		const [authRes, envRes] = await Promise.all([
			fetch('/auth'),
			fetch('/api/env')
		]);

		const user = authRes.ok ? await authRes.json() : null;
		const envData = envRes.ok
			? await envRes.json()
			: { env: 'production', guild_id: null, is_admin: false };

		let guilds: GuildInfo[] = [];
		if (user) {
			const guildsRes = await fetch('/api/guilds');
			if (guildsRes.ok) {
				guilds = await guildsRes.json();
			}
		}

		return {
			user,
			guild_id: envData.guild_id,
			is_admin: envData.is_admin,
			env: envData.env,
			invite_url: envData.invite_url as string | null,
			guilds
		};
	} catch {
		return {
			user: null,
			guild_id: null,
			is_admin: false,
			env: 'production',
			invite_url: null,
			guilds: [] as GuildInfo[]
		};
	}
};
