import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ fetch }) => {
	try {
		const [authRes, envRes] = await Promise.all([
			fetch('/v2/auth'),
			fetch('/v2/api/env')
		]);

		const user = authRes.ok ? await authRes.json() : null;
		const envData = envRes.ok ? await envRes.json() : { env: 'production', guild_id: null, is_admin: false };

		return {
			user,
			guild_id: envData.guild_id,
			is_admin: envData.is_admin,
			env: envData.env
		};
	} catch {
		return { user: null, guild_id: null, is_admin: false, env: 'production' };
	}
};
