<script lang="ts">
	import { apiFetch } from '$lib/api';
	import { toErrorMessage } from '$lib/api-utils';
	import Input from '$lib/components/Input.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { filterStickers } from '$lib/utils/sticker-selection';
	import { SvelteSet } from 'svelte/reactivity';

	interface Sticker {
		id: string;
		name: string;
		image_url: string | null;
		type: 'custom' | 'default';
	}

	interface Props {
		guildId: string;
		selectedIds: string[];
		onchange?: (stickerIds: string[]) => void;
	}

	let {
		guildId: _guildId,
		selectedIds: _selectedIds = [],
		onchange
	}: Props = $props();

	let stickers = $state<Sticker[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let search = $state('');

	let selected = new SvelteSet<string>(_selectedIds);

	// Sync from parent when prop changes (e.g., after save/reload)
	$effect(() => {
		const incoming = new Set<string>(_selectedIds);
		if (incoming.size !== selected.size || [...incoming].some(id => !selected.has(id))) {
			selected.clear();
			for (const id of incoming) selected.add(id);
		}
	});

	async function loadStickers() {
		loading = true;
		error = null;
		try {
			const res = await apiFetch<{ stickers: Sticker[] }>(
				`/api/admin/guild-stickers`
			);
			stickers = res.stickers;
			// Clear selections for stickers that no longer exist
			const validIds = new Set(stickers.map(s => s.id).filter(Boolean));
			for (const sid of selected) {
				if (!validIds.has(sid)) selected.delete(sid);
			}
			emit();
		} catch (err) {
			error = toErrorMessage(err, 'Failed to load stickers');
		} finally {
			loading = false;
		}
	}

	function emit() {
		onchange?.([...selected]);
	}

	function toggleSticker(id: string) {
		if (selected.has(id)) {
			selected.delete(id);
		} else {
			selected.add(id);
		}
		emit();
	}

	function selectAll() {
		for (const s of stickers) {
			if (s.id) selected.add(s.id);
		}
		emit();
	}

	function deselectAll() {
		selected.clear();
		emit();
	}

	$effect(() => {
		loadStickers();
	});

	let filtered = $derived(filterStickers(stickers, search));
</script>

<div class="space-y-3">
	<div class="flex items-center justify-between gap-2">
		<Input
			bind:value={search}
			placeholder="Search stickers..."
			class="flex-1"
		/>
		<div class="flex items-center gap-2 text-sm text-muted">
			<button
				type="button"
				onclick={selectAll}
				class="hover:text-foreground transition-colors"
			>All</button>
			<span>/</span>
			<button
				type="button"
				onclick={deselectAll}
				class="hover:text-foreground transition-colors"
			>None</button>
		</div>
	</div>

	{#if selected.size > 0}
		<p class="text-xs text-muted">{selected.size} sticker{selected.size !== 1 ? 's' : ''} selected</p>
	{/if}

	{#if loading}
		<div class="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
			{#each Array(6) as _}
				<div class="aspect-square rounded-lg bg-border/60 animate-pulse"></div>
			{/each}
		</div>
	{:else if error}
		<p class="text-sm text-danger">{error}</p>
	{:else if filtered.length === 0}
		<EmptyState
			icon="🏷️"
			title="No stickers found"
			message="This guild has no custom stickers."
		/>
	{:else}
		<div class="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
			{#each filtered as sticker (sticker.id)}
				{@const isSelected = sticker.id ? selected.has(sticker.id) : false}
				<button
					type="button"
					onclick={() => sticker.id && toggleSticker(sticker.id)}
					class="relative group rounded-lg border-2 p-1 aspect-square flex flex-col items-center justify-center transition-all
						{isSelected
							? 'border-accent bg-accent/10'
							: 'border-border hover:border-muted bg-transparent'}"
					title={sticker.name}
				>
					{#if sticker.image_url}
						<img
							src={sticker.image_url}
							alt={sticker.name}
							class="w-full h-full object-contain rounded"
							loading="lazy"
						/>
					{:else}
						<span class="text-2xl">🏷️</span>
					{/if}
					{#if isSelected}
						<div class="absolute top-1 right-1 w-4 h-4 bg-accent rounded-full flex items-center justify-center">
							<span class="text-white text-[10px] leading-none">✓</span>
						</div>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
