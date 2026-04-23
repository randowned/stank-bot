<script lang="ts">
	import { apiFetch, apiPost, FetchError } from '$lib/api';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import FormField from '$lib/components/FormField.svelte';
	import Input from '$lib/components/Input.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	interface Altar {
		id: number;
		channel_id: string;
		sticker_name_pattern: string;
		reaction_emoji_name: string | null;
		enabled: boolean;
	}

	let altar = $state<Altar | null>(null);
	let loaded = $state(false);
	let saving = $state(false);
	let message = $state<string | null>(null);

	let channelId = $state('');
	let pattern = $state('stank');
	let emoji = $state('');

	async function load() {
		loaded = false;
		try {
			const res = await apiFetch<{ altar: Altar | null }>('/v2/api/admin/altar');
			altar = res.altar;
			if (altar) {
				channelId = altar.channel_id;
				pattern = altar.sticker_name_pattern;
				emoji = altar.reaction_emoji_name ?? '';
			}
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Failed to load';
		} finally {
			loaded = true;
		}
	}

	async function save() {
		saving = true;
		message = null;
		try {
			await apiPost('/v2/api/admin/altar/set', {
				channel_id: Number(channelId),
				sticker_pattern: pattern,
				reaction_emoji: emoji || null
			});
			await load();
			message = 'Altar saved.';
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Save failed';
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (!confirm('Remove this altar?')) return;
		try {
			await apiPost('/v2/api/admin/altar/remove');
			altar = null;
			channelId = '';
			pattern = 'stank';
			emoji = '';
			message = 'Altar removed.';
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Remove failed';
		}
	}

	onMount(load);
</script>

<PageHeader title="Altar" subtitle="Channel the bot watches for stank stickers" />

<Card>
	{#if !loaded}
		<p class="text-muted text-sm">Loading…</p>
	{:else if !altar}
		<EmptyState
			icon="🗿"
			title="No altar configured"
			message="Pick a channel the bot should watch for stank sticker posts."
		/>
	{/if}

	<FormField label="Channel ID" required hint="Right-click channel in Discord → Copy Channel ID">
		<Input type="number" bind:value={channelId} placeholder="e.g. 1234567890" />
	</FormField>
	<FormField label="Sticker pattern" hint="Substring match, case-insensitive">
		<Input bind:value={pattern} />
	</FormField>
	<FormField label="Reaction emoji" hint="Custom emoji like <:stank:12345> or a unicode emoji. Leave blank to skip reactions.">
		<Input bind:value={emoji} placeholder="<:stank:1234567890>" />
	</FormField>

	<div class="flex gap-2 mt-2">
		<Button onclick={save} loading={saving}>{altar ? 'Update' : 'Create'}</Button>
		{#if altar}
			<Button variant="danger" onclick={remove}>Remove</Button>
		{/if}
	</div>
	{#if message}<p class="text-sm text-muted mt-3">{message}</p>{/if}
</Card>
