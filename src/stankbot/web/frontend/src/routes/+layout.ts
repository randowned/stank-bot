import { redirect } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';
import type { GuildInfo } from '$lib/types';
import { getCache, setCache, clearCache } from '$lib/cache';

interface AuthResponse {
	user: { id: string; username: string; avatar: string | null } | null;
	guild_id: string | null;
	guild_name: string | null;
	is_admin: boolean;
	is_global_admin: boolean;
}

export const load: LayoutLoad = async ({ fetch, url }) => {
	try {
		// Always fetch /auth to validate session
		let auth = getCache<AuthResponse>('auth');
		const authRes = await fetch('/auth');
		if (authRes.ok) {
			auth = await authRes.json();
			if (auth) setCache('auth', auth);
		} else {
			// Not logged in, clear cached guilds
			clearCache('guilds');
		}

		const user = auth?.user ?? null;
		const isPublicPath = url.pathname.includes('/auth') || url.pathname === '/';
		if (!user && !isPublicPath) {
			throw redirect(303, '/');
		}

		// Guilds: use cache if global admin
		let guilds: GuildInfo[] = [];
		if (auth?.is_global_admin) {
			// Try cache first for guilds
			guilds = getCache<GuildInfo[]>('guilds') ?? [];
			if (!guilds.length) {
				const guildsRes = await fetch('/api/guilds');
				if (guildsRes.ok) {
					guilds = await guildsRes.json();
					if (guilds.length) {
						setCache('guilds', guilds);
					}
				}
			}
		}

		return {
			user,
			guild_id: auth?.guild_id ?? null,
			guild_name: auth?.guild_name ?? null,
			is_admin: auth?.is_admin ?? false,
			is_global_admin: auth?.is_global_admin ?? false,
			guilds
		};
	} catch (e) {
		if (e && typeof e === 'object' && 'status' in e) throw e;

		return {
			user: null,
			guild_id: null,
			guild_name: null,
			is_admin: false,
			is_global_admin: false,
			guilds: [] as GuildInfo[]
		};
	}
};