<script lang="ts">
	import type { GuildInfo } from '$lib/types';
	import Avatar from './Avatar.svelte';

	interface Props {
		guilds: GuildInfo[];
		activeGuildId: string | null;
		switchingTo: string | null;
		onswitch: (guildId: string) => void;
		ontoggle: (e: MouseEvent) => void;
		open: boolean;
	}

	let { guilds, activeGuildId, switchingTo, onswitch, ontoggle, open }: Props = $props();

	const active = $derived(guilds.find((g) => g.id === activeGuildId) ?? null);
</script>

<div class="border-t border-border my-1"></div>
<div class="px-1">
	<button
		type="button"
		onclick={ontoggle}
		class="flex items-center gap-2 w-full px-3 py-2 text-sm text-left rounded-sm text-text hover:bg-border/60 transition-colors"
		aria-expanded={open}
		aria-controls="guild-switch-list"
		data-testid="guild-switcher-toggle"
	>
		{#if active}
			<Avatar src={active.icon_url} name={active.name} userId={active.id} size="sm" />
			<span class="flex-1 truncate">{active.name}</span>
		{:else}
			<span>🌐</span>
			<span class="flex-1 truncate text-muted">Switch Guild</span>
		{/if}
		<svg
			class="w-3 h-3 text-muted transition-transform {open ? 'rotate-180' : ''}"
			viewBox="0 0 12 12"
			aria-hidden="true"
		>
			<path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" fill="none" />
		</svg>
	</button>

	{#if open && guilds.length > 0}
		<ul
			id="guild-switch-list"
			class="max-h-64 overflow-y-auto py-1 border-t border-border/50 mt-1"
			role="menu"
		>
			{#each guilds as g (g.id)}
				<li>
					<button
						type="button"
						onclick={() => onswitch(g.id)}
						disabled={switchingTo !== null || g.id === activeGuildId}
						class="flex items-center gap-2 w-full px-3 py-2 text-sm text-left rounded-sm transition-colors
							{g.id === activeGuildId
							? 'bg-accent/15 text-accent'
							: 'text-text hover:bg-border/60'}
							{switchingTo !== null && switchingTo !== g.id ? 'opacity-60' : ''}"
						role="menuitem"
						data-testid="guild-switch-item"
					>
						<Avatar src={g.icon_url} name={g.name} userId={g.id} size="sm" />
						<span class="flex-1 truncate">{g.name}</span>
						{#if g.id === activeGuildId}
							<span class="text-xs text-accent shrink-0">Active</span>
						{:else if switchingTo === g.id}
							<span class="text-xs text-muted shrink-0">…</span>
						{/if}
					</button>
				</li>
			{/each}
		</ul>
	{:else if open && guilds.length === 0}
		<div class="px-3 py-2 text-xs text-muted">
			Bot isn't installed on any of your guilds yet.
		</div>
	{/if}
</div>
