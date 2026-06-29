<script lang="ts">
	import { apiFetch, apiPost } from '$lib/api';
	import { toErrorMessage } from '$lib/api-utils';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import FormField from '$lib/components/FormField.svelte';
	import Input from '$lib/components/Input.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import RemovableItem from '$lib/components/RemovableItem.svelte';
	import StickerPicker from '$lib/components/StickerPicker.svelte';
	import EmojiPicker from '$lib/components/EmojiPicker.svelte';

	interface Altar {
		interface Altar {
			id: number;
			guild_id: string;
			channel_id: string;
			sticker_name_pattern: string;
			sticker_id: string | null;
			sticker_ids: number[];
			reaction_emoji_name: string | null;
			reaction_emoji_display: string | null;
			enabled: boolean;
		}

	let altar = $state<Altar | null>(null);
	let altarLoaded = $state(false);
	let altarSaving = $state(false);
	let altarMsg = $state<string | null>(null);
	let channelId = $state('');
	let pattern = $state('stank');
	let emoji = $state('');
	let selectedStickerIds = $state<number[]>([]);
	let displayStickerId = $state<number | null>(null);

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
				emoji = altar.reaction_emoji_display ?? '';
				selectedStickerIds = altar.sticker_ids ?? [];
				displayStickerId = altar.sticker_id ? Number(altar.sticker_id) : null;
			}
		} catch (err) {
			altarMsg = toErrorMessage(err, 'Failed to load');
		} finally {
			altarLoaded = true;
		}
	}

	function onStickerChange(data: { stickerIds: number[]; displayStickerId: number | null }) {
		selectedStickerIds = data.stickerIds;
		displayStickerId = data.displayStickerId;
	}

	let selectedEmojiIds = $state<number[]>([]);

	async function saveAltar() {
		altarSaving = true;
		altarMsg = null;
		try {
			await apiPost('/api/admin/altar/set', {
				channel_id: channelId.trim(),
				sticker_pattern: pattern,
				sticker_ids: selectedStickerIds.length > 0 ? selectedStickerIds : null,
				display_sticker_id: displayStickerId,
				reaction_emoji: emoji || null
			});
			await loadAltar();
			altarMsg = 'Altar saved.';
		} catch (err) {
			altarMsg = toErrorMessage(err, 'Save failed');
		} finally {
			altarSaving = false;
		}
	}

	async function loadAnnouncements() {
		try {
			const res = await apiFetch<{ channel_ids: string[] }>('/api/admin/announcements');
			channelIds = res.channel_ids;
		} catch (err) {
			annError = toErrorMessage(err, 'Failed');
		}
	}

	async function addAnnouncement() {
		if (!newChannel.trim()) return;
		try {
			await apiPost('/api/admin/announcements', { channel_id: newChannel.trim() });
			newChannel = '';
			await loadAnnouncements();
		} catch (err) {
			annError = toErrorMessage(err, 'Add failed');
		}
	}

	async function removeAnnouncement(id: string) {
		try {
			await apiPost('/api/admin/announcements/remove', { channel_id: id });
			await loadAnnouncements();
		} catch (err) {
			annError = toErrorMessage(err, 'Remove failed');
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
			<div class="space-y-3">
				<div>
					<div class="h-3 bg-border/60 animate-pulse rounded w-20 mb-1"></div>
					<div class="h-9 bg-border/60 animate-pulse rounded w-full"></div>
				</div>
				<div>
					<div class="h-3 bg-border/60 animate-pulse rounded w-24 mb-1"></div>
					<div class="h-9 bg-border/60 animate-pulse rounded w-full"></div>
				</div>
				<div>
					<div class="h-3 bg-border/60 animate-pulse rounded w-28 mb-1"></div>
					<div class="h-9 bg-border/60 animate-pulse rounded w-full"></div>
				</div>
				<div class="flex justify-end">
					<div class="h-9 w-12 bg-border/60 animate-pulse rounded-md"></div>
				</div>
			</div>
		{:else if !altar}
			<EmptyState
				icon="🗿"
				title="No altar configured"
				message="Pick a channel the bot should watch for stank sticker posts."
			/>
		{/if}
		<FormField label="Channel ID" required hint="Right-click channel in Discord → Copy Channel ID" for="altar-channel-id">
			<Input type="text" bind:value={channelId} placeholder="e.g. 1234567890" id="altar-channel-id" />
		</FormField>

		<!-- Visual sticker picker (replaces the old pattern text field) -->
		<FormField label="Stickers" hint="Select which stickers count as stanks. Click a sticker to toggle; use ★ to set the display sticker." for="altar-stickers">
			<StickerPicker
				guildId={altar?.channel_id ?? ''}
				selectedIds={selectedStickerIds}
				displayStickerId={displayStickerId}
				onchange={onStickerChange}
			/>
		</FormField>

		<!-- Advanced: show current sticker_name_pattern for transition UX -->
		{#if pattern && pattern !== 'stank'}
			<FormField
				label="Sticker pattern (legacy)"
				hint="Previously configured name pattern. Kept as fallback during transition. Will be removed after all guilds migrate to sticker IDs."
				for="altar-pattern-legacy"
			>
				<Input bind:value={pattern} id="altar-pattern-legacy" disabled />
			</FormField>
		{/if}

		<FormField
			label="Reaction emoji"
			hint="Custom emoji like <:stank:12345> or a unicode emoji. Comma-separate several to accept more than one — the first is primary (used for the stank-emoji token and auto-react). Leave blank to skip reactions."
			for="altar-emoji"
		>
			<Input bind:value={emoji} placeholder="<:stank:1234567890>" id="altar-emoji" />
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
				<RemovableItem onremove={() => removeAnnouncement(id)}>
					<span class="font-mono">{id}</span>
				</RemovableItem>
			{:else}
				<li class="text-muted text-sm">No announcement channels configured.</li>
			{/each}
		</ul>
		<FormField label="Add channel ID" for="ann-channel-id">
			<Input bind:value={newChannel} type="text" placeholder="Discord channel ID" id="ann-channel-id" />
		</FormField>
		<div class="flex justify-end mt-2">
			<Button onclick={addAnnouncement}>Add</Button>
		</div>
	</Card>
</div>
