<script lang="ts">
	import { base } from '$app/paths';
	import { invalidateAll, goto } from '$app/navigation';
	import { apiPost, FetchError } from '$lib/api';
	import type { User, GuildInfo } from '$lib/types';
	import Avatar from './Avatar.svelte';
	import Dropdown from './Dropdown.svelte';
	import DropdownItem from './DropdownItem.svelte';

	interface Props {
		user: User;
		guilds: GuildInfo[];
		activeGuildId: string | null;
		isAdmin: boolean;
		onerror?: (msg: string) => void;
	}

	let { user, guilds, activeGuildId, isAdmin, onerror }: Props = $props();

	let open = $state(false);
	let switchingTo: string | null = $state(null);

	const switchable = $derived(guilds.filter((g) => g.is_admin));
	const hasMultipleGuilds = $derived(switchable.length > 1);

	async function switchGuild(guildId: string) {
		if (switchingTo || guildId === activeGuildId) {
			open = false;
			return;
		}
		switchingTo = guildId;
		try {
			await apiPost(`/v2/api/admin/guild?guild_id=${guildId}`);
			open = false;
			await invalidateAll();
			await goto(`${base}/`, { invalidateAll: true });
		} catch (err) {
			const msg = err instanceof FetchError ? err.message : 'Failed to switch guild';
			onerror?.(msg);
		} finally {
			switchingTo = null;
		}
	}
</script>

<Dropdown bind:open align="right">
	{#snippet trigger({ toggle, open: isOpen })}
		<button
			type="button"
			onclick={toggle}
			class="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-border/50 transition-colors"
			aria-haspopup="menu"
			aria-expanded={isOpen}
			data-testid="user-menu-trigger"
		>
			<Avatar
				name={user.username}
				userId={user.id}
				discordAvatar={user.avatar}
				size="sm"
			/>
			<span class="text-sm text-text hidden sm:inline">{user.username}</span>
			<svg
				class="w-3 h-3 text-muted transition-transform {isOpen ? 'rotate-180' : ''}"
				viewBox="0 0 12 12"
				fill="currentColor"
				aria-hidden="true"
			>
				<path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" />
			</svg>
		</button>
	{/snippet}

	<div class="px-3 py-2 border-b border-border">
		<div class="font-semibold truncate">{user.username}</div>
		<div class="text-xs text-muted truncate">ID {user.id}</div>
	</div>

	<DropdownItem href="{base}/player/{user.id}">
		<span>👤</span>
		<span>My Profile</span>
	</DropdownItem>

	{#if hasMultipleGuilds}
		<div class="border-t border-border my-1"></div>
		<div class="px-3 py-1 text-xs text-muted uppercase tracking-wide">Switch Guild</div>
		{#each switchable as g (g.id)}
			<DropdownItem
				onclick={() => switchGuild(g.id)}
				active={g.id === activeGuildId}
				disabled={switchingTo !== null}
			>
				<span class="flex-1 truncate">{g.name}</span>
				{#if g.id === activeGuildId}
					<span class="text-xs text-accent">Active</span>
				{:else if switchingTo === g.id}
					<span class="text-xs text-muted">…</span>
				{:else if !g.bot_present}
					<span class="text-xs text-muted" title="Bot not installed">• install</span>
				{/if}
			</DropdownItem>
		{/each}
	{/if}

	{#if isAdmin}
		<div class="border-t border-border my-1"></div>
		<DropdownItem href="{base}/admin">
			<span>⚙️</span>
			<span>Admin</span>
		</DropdownItem>
	{/if}

	<div class="border-t border-border my-1"></div>
	<DropdownItem href="/auth/logout" danger>
		<span>🚪</span>
		<span>Logout</span>
	</DropdownItem>
</Dropdown>
