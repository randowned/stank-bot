import { writable, type Writable } from 'svelte/store';
import type { User, GuildInfo } from '$lib/types';

export const guildId: Writable<string | null> = writable(null);

export const user: Writable<User | null> = writable(null);

export const guilds: Writable<GuildInfo[]> = writable([]);
