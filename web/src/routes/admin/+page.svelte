<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import type { GuildInfo } from '$lib/types';

	const guilds = $derived(($page.data.guilds as GuildInfo[] | undefined) ?? []);
	const missingBot = $derived(guilds.filter((g) => g.is_admin && !g.bot_present));

	const tiles = [
		{ href: `${base}/admin/settings`, label: 'Settings', icon: '⚙️', desc: 'Scoring, cooldowns, resets' },
		{ href: `${base}/admin/altar`, label: 'Altar', icon: '🗿', desc: 'Channel / sticker / emoji' },
		{ href: `${base}/admin/roles`, label: 'Roles', icon: '👥', desc: 'Admin role & user grants' },
		{ href: `${base}/admin/templates`, label: 'Templates', icon: '📝', desc: 'Edit bot embeds' },
		{ href: `${base}/admin/announcements`, label: 'Announcements', icon: '📢', desc: 'Scheduled messages' },
		{ href: `${base}/admin/audit`, label: 'Audit log', icon: '📋', desc: 'History of admin actions' },
		{ href: `${base}/admin/maintenance`, label: 'Maintenance', icon: '🛠', desc: 'Pause event processing' },
		{ href: `${base}/admin/config`, label: 'Config', icon: '🔍', desc: 'Read-only snapshot' }
	];
</script>

<PageHeader title="Admin" subtitle="Per-guild configuration and operations" />

<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
	{#each tiles as tile (tile.href)}
		<a
			href={tile.href}
			class="panel hover:border-accent transition-colors block"
		>
			<div class="flex items-start gap-3">
				<div class="text-2xl" aria-hidden="true">{tile.icon}</div>
				<div class="min-w-0">
					<div class="font-semibold truncate">{tile.label}</div>
					<div class="text-xs text-muted">{tile.desc}</div>
				</div>
			</div>
		</a>
	{/each}
</div>

{#if missingBot.length > 0}
	<section class="mt-6">
		<Card title="Invite the bot to your other guilds">
			<ul class="divide-y divide-border -mb-4 -mx-4">
				{#each missingBot as g (g.id)}
					<li class="flex items-center justify-between px-4 py-2">
						<div class="flex items-center gap-3 min-w-0">
							{#if g.icon_url}
								<img src={g.icon_url} alt="" class="w-8 h-8 rounded-full" />
							{:else}
								<div class="w-8 h-8 rounded-full bg-border flex items-center justify-center text-xs">
									{g.name[0] ?? '?'}
								</div>
							{/if}
							<div class="truncate">{g.name}</div>
						</div>
						<a
							href="/auth/login?install_guild={g.id}"
							class="text-sm text-accent hover:underline"
						>Add bot</a>
					</li>
				{/each}
			</ul>
		</Card>
	</section>
{/if}

<section class="mt-6">
	<Card title="Destructive operations">
		<div class="flex flex-wrap gap-2">
			<a href="{base}/admin/session/new" class="btn btn-secondary">New session</a>
			<a href="{base}/admin/session/reset" class="btn btn-secondary">Reset</a>
			<a href="{base}/admin/session/rebuild" class="btn btn-secondary">Rebuild</a>
		</div>
	</Card>
</section>
