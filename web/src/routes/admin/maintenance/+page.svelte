<script lang="ts">
	import { apiFetch, apiPost, FetchError } from '$lib/api';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Toggle from '$lib/components/Toggle.svelte';

	let enabled = $state(false);
	let loaded = $state(false);
	let message = $state<string | null>(null);

	async function load() {
		try {
			const res = await apiFetch<{ enabled: boolean }>('/v2/api/admin/maintenance');
			enabled = res.enabled;
			loaded = true;
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Failed to load';
		}
	}

	async function toggle(val: boolean) {
		try {
			await apiPost('/v2/api/admin/maintenance', { enabled: val });
			message = val ? 'Maintenance mode ON' : 'Maintenance mode OFF';
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Failed';
			enabled = !val;
		}
	}

	onMount(load);
</script>

<PageHeader title="Maintenance" subtitle="Pause event processing without stopping the bot" />

<Card>
	{#if loaded}
		<Toggle bind:checked={enabled} label="Maintenance mode" onchange={toggle} />
	{/if}
	{#if message}<p class="text-sm text-muted mt-3">{message}</p>{/if}

	<p class="text-sm text-muted mt-4">
		When enabled the bot skips scoring, chain detection, and record updates — messages are still
		read (so the gateway stays healthy) but no state is mutated. Useful during migrations.
	</p>
</Card>
