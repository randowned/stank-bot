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
	let altarLoaded = $state(false);
	let altarSaving = $state(false);
	let altarMsg = $state<string | null>(null);
	let channelId = $state('');
	let pattern = $state('stank');
	let emoji = $state('');

	let channelIds = $state<string[]>([]);
	let newChannel = $state('');
	let annError = $state<string | null>(null);

	async function loadAltar() {
		altarLoaded = false;
		try {
			const res = await apiFetch<{ altar: Altar | null }>('/api/admin/altar');
			altar = res.altar;
			if (altar) {
				channelId = altar.channel_id;
				pattern = altar.sticker_name_pattern;
				emoji = altar.reaction_emoji_name ?? '';
			}
		} catch (err) {
			altarMsg = err instanceof FetchError ? err.message : 'Failed to load';
		} finally {
			altarLoaded = true;
		}
	}

	async function saveAltar() {
		altarSaving = true;
		altarMsg = null;
		try {
			await apiPost('/api/admin/altar/set', {
				channel_id: Number(channelId),
				sticker_pattern: pattern,
				reaction_emoji: emoji || null
			});
			await loadAltar();
			altarMsg = 'Altar saved.';
		} catch (err) {
			altarMsg = err instanceof FetchError ? err.message : 'Save failed';
		} finally {
			altarSaving = false;
		}
	}

	async function loadAnnouncements() {
		try {
			const res = await apiFetch<{ channel_ids: string[] }>('/api/admin/announcements');
			channelIds = res.channel_ids;
		} catch (err) {
			annError = err instanceof FetchError ? err.message : 'Failed';
		}
	}

	async function addAnnouncement() {
		if (!newChannel.trim()) return;
		try {
			await apiPost('/api/admin/announcements', { channel_id: Number(newChannel) });
			newChannel = '';
			await loadAnnouncements();
		} catch (err) {
			annError = err instanceof FetchError ? err.message : 'Add failed';
		}
	}

	async function removeAnnouncement(id: string) {
		try {
			await apiPost('/api/admin/announcements/remove', { channel_id: Number(id) });
			await loadAnnouncements();
		} catch (err) {
			annError = err instanceof FetchError ? err.message : 'Remove failed';
		}
	}

	onMount(() => {
		loadAltar();
		loadAnnouncements();
	});
</script>

<PageHeader title="Channels" subtitle="Altar and announcement channel configuration" />

<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
	<Card title="Altar">
		{#if !altarLoaded}
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
		<FormField
			label="Reaction emoji"
			hint="Custom emoji like <:stank:12345> or a unicode emoji. Leave blank to skip reactions."
		>
			<Input bind:value={emoji} placeholder="<:stank:1234567890>" />
		</FormField>
		<div class="flex justify-end mt-2">
			<Button onclick={saveAltar} loading={altarSaving}>Set</Button>
		</div>
		{#if altarMsg}<p class="text-sm text-muted mt-3">{altarMsg}</p>{/if}
	</Card>

	<Card title="Announcements">
		{#if annError}<p class="text-sm text-danger mb-2">{annError}</p>{/if}
		<ul class="mb-4 space-y-1">
			{#each channelIds as id (id)}
				<li class="flex items-center justify-between text-sm">
					<span class="font-mono">{id}</span>
					<button class="text-danger text-sm" onclick={() => removeAnnouncement(id)}>Remove</button>
				</li>
			{:else}
				<li class="text-muted text-sm">No announcement channels configured.</li>
			{/each}
		</ul>
		<FormField label="Add channel ID">
			<Input bind:value={newChannel} type="number" placeholder="Discord channel ID" />
		</FormField>
		<div class="flex justify-end mt-2">
			<Button onclick={addAnnouncement}>Add</Button>
		</div>
	</Card>
</div>
