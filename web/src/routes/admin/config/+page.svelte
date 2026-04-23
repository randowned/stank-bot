<script lang="ts">
	import { apiFetch, FetchError } from '$lib/api';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';

	interface ConfigDoc {
		guild_id: string;
		guild_name: string;
		settings: Record<string, unknown>;
		altars: Array<Record<string, unknown>>;
		labels: Record<string, { title: string; help: string }>;
	}

	let doc = $state<ConfigDoc | null>(null);
	let error = $state<string | null>(null);

	async function load() {
		try {
			doc = await apiFetch<ConfigDoc>('/v2/api/admin/config');
		} catch (err) {
			error = err instanceof FetchError ? err.message : 'Failed';
		}
	}

	onMount(load);
</script>

<PageHeader title="Config snapshot" subtitle={doc?.guild_name ?? ''} />

{#if error}
	<ErrorState message={error} onretry={load} />
{:else if doc}
	<Card title="Settings">
		<dl class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2 text-sm">
			{#each Object.entries(doc.settings) as [k, v] (k)}
				<div class="flex justify-between border-b border-border/30 py-1">
					<dt class="text-muted">{doc.labels[k]?.title ?? k}</dt>
					<dd class="font-mono text-text text-right max-w-[60%] truncate">
						{Array.isArray(v) ? v.join(', ') : String(v)}
					</dd>
				</div>
			{/each}
		</dl>
	</Card>

	<div class="mt-4">
		<Card title="Altars">
			{#if doc.altars.length === 0}
				<p class="text-muted text-sm">No altars configured.</p>
			{:else}
				<ul class="text-sm space-y-1">
					{#each doc.altars as a (a.id)}
						<li>
							<span class="font-mono">#{a.channel_id}</span>
							<span class="text-muted ml-2">pattern: {a.sticker_name_pattern}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</Card>
	</div>
{/if}
