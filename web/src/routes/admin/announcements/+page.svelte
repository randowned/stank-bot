<script lang="ts">
	import { apiFetch, apiPost, FetchError } from '$lib/api';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Input from '$lib/components/Input.svelte';
	import FormField from '$lib/components/FormField.svelte';
	import Button from '$lib/components/Button.svelte';

	let channelIds = $state<string[]>([]);
	let newChannel = $state('');
	let error = $state<string | null>(null);

	async function load() {
		try {
			const res = await apiFetch<{ channel_ids: string[] }>('/v2/api/admin/announcements');
			channelIds = res.channel_ids;
		} catch (err) {
			error = err instanceof FetchError ? err.message : 'Failed';
		}
	}

	async function add() {
		if (!newChannel.trim()) return;
		try {
			await apiPost('/v2/api/admin/announcements', { channel_id: Number(newChannel) });
			newChannel = '';
			await load();
		} catch (err) {
			error = err instanceof FetchError ? err.message : 'Add failed';
		}
	}

	async function remove(id: string) {
		try {
			await apiPost('/v2/api/admin/announcements/remove', { channel_id: Number(id) });
			await load();
		} catch (err) {
			error = err instanceof FetchError ? err.message : 'Remove failed';
		}
	}

	onMount(load);
</script>

<PageHeader title="Announcements" subtitle="Channels that receive bot announcements" />

<Card>
	{#if error}<p class="text-sm text-danger mb-2">{error}</p>{/if}

	<ul class="mb-4 space-y-1">
		{#each channelIds as id (id)}
			<li class="flex items-center justify-between text-sm">
				<span class="font-mono">{id}</span>
				<button class="text-danger text-sm" onclick={() => remove(id)}>Remove</button>
			</li>
		{:else}
			<li class="text-muted text-sm">No announcement channels configured.</li>
		{/each}
	</ul>

	<FormField label="Add channel ID">
		<Input bind:value={newChannel} type="number" placeholder="Discord channel ID" />
	</FormField>
	<Button onclick={add}>Add</Button>
</Card>
