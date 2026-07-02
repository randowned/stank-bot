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
		id: number;
		guild_id: string;
		channel_id: string;
		sticker_name_pattern: string;
		sticker_id: string | null;
		sticker_ids: string[];
		reaction_emoji_name: string | null;
		reaction_emoji_display: string | null;
		enabled: boolean;
	}

	let altar = $state<Altar | null>(null);
	let altarLoaded = $state(false);
	let altarSaving = $state(false);
	let altarMsg = $state<string | null>(null);
	let channelId = $state('');
	let legacyPattern = $state('');
	let emoji = $state('');
	let selectedStickerIds = $state<string[]>([]);

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
				legacyPattern = altar.sticker_name_pattern;
				emoji = altar.reaction_emoji_display ?? '';
				selectedStickerIds = altar.sticker_ids ?? [];
			}
		} catch (err) {
			altarMsg = toErrorMessage(err, 'Failed to load');
		} finally {
			altarLoaded = true;
		}
	}

	function onValidStickersChange(stickerIds: string[]) {
		selectedStickerIds = stickerIds;
	}

	async function saveAltar() {
		altarSaving = true;
		altarMsg = null;
		try {
			await apiPost('/api/admin/altar/set', {
				channel_id: channelId.trim(),
				sticker_pattern: legacyPattern,
				sticker_ids: selectedStickerIds.length > 0 ? selectedStickerIds : null,
				display_sticker_id: selectedStickerIds.length > 0 ? selectedStickerIds[0] : null,
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

		<!-- Valid stickers (multi-select) -->
		<FormField label="Valid stank stickers" hint="Select which stickers count as stanks. The first selected sticker is the display sticker shown on leaderboards." for="altar-stickers">
			<StickerPicker
				guildId={altar?.guild_id ?? ''}
				selectedIds={selectedStickerIds}
				onchange={onValidStickersChange}
			/>
		</FormField>

		<FormField
			label="Sticker name pattern (legacy)"
			hint="Fallback text-based matching: comma-separated, case-insensitive substring. Empty = name matching disabled."
			for="altar-pattern-legacy"
		>
			<Input bind:value={legacyPattern} id="altar-pattern-legacy" placeholder="e.g. stank, maphra wink" />
		</FormField>

		<FormField
			label="Reaction emoji"
			hint="Search and select emojis. The first is primary (used for the display name and auto-react). Leave blank to skip reactions."
			for="altar-emoji"
		>
			<EmojiPicker
				guildId={altar?.guild_id ?? ''}
				value={emoji}
				onchange={(v: string) => emoji = v}
			/>
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
