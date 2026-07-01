<script lang="ts">
	import { apiFetch } from '$lib/api';
	import { toErrorMessage } from '$lib/api-utils';
	import Input from '$lib/components/Input.svelte';
	import Toggle from '$lib/components/Toggle.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	interface Sticker {
		id: string;
		name: string;
		image_url: string | null;
		type: 'custom' | 'default';
	}

	interface Props {
		guildId: string;
		selectedIds: number[];
		displayStickerId?: number | null;
		mode?: 'multi' | 'single';
		validStickerIds?: number[];
		onchange?: (data: { stickerIds: number[]; displayStickerId: number | null }) => void;
	}

	let {
		guildId: _guildId,
		selectedIds: _selectedIds = [],
		displayStickerId: _displayStickerId = null,
		mode = 'multi',
		validStickerIds = [],
		onchange
	}: Props = $props();

	let stickers = $state<Sticker[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showDefault = $state(false);
	let search = $state('');

	let selected = $state<Set<number>>(new Set(_selectedIds.map(Number)));
	let displayId = $state<number | null>(_displayStickerId ? Number(_displayStickerId) : null);

	async function loadStickers() {
		loading = true;
		error = null;
		try {
			const res = await apiFetch<{ stickers: Sticker[] }>(
				`/api/admin/guild-stickers?include_default=${showDefault}`
			);
			stickers = res.stickers;
			// Clear selections for stickers that no longer exist
			const validIds = new Set(stickers.map(s => Number(s.id)).filter(Boolean));
			for (const sid of selected) {
				if (!validIds.has(sid)) selected.delete(sid);
			}
			if (displayId && !validIds.has(displayId)) displayId = null;
			emit();
		} catch (err) {
			error = toErrorMessage(err, 'Failed to load stickers');
		} finally {
			loading = false;
		}
	}

	function emit() {
		onchange?.({
			stickerIds: [...selected],
			displayStickerId: displayId
		});
	}

	// -- multi mode: toggle selection ----------------------------------------

	function toggleSticker(id: number) {
		if (selected.has(id)) {
			selected.delete(id);
		} else {
			selected.add(id);
		}
		emit();
	}

	// -- single mode: radio-button selection ---------------------------------

	function selectDisplay(id: number) {
		if (displayId === id) return;
		displayId = id;
		selected.clear();
		selected.add(id);
		emit();
	}

	function selectAll() {
		if (mode === 'single') return;
		for (const s of stickers) {
			const id = Number(s.id);
			if (id) selected.add(id);
		}
		emit();
	}

	function deselectAll() {
		selected.clear();
		if (mode === 'single') displayId = null;
		emit();
	}

	function toggleDefaults(v: boolean) {
		showDefault = v;
		loadStickers();
	}

	$effect(() => {
		loadStickers();
	});

	let filtered = $derived(
		search.trim()
			? stickers.filter(s => s.name.toLowerCase().includes(search.toLowerCase()))
			: stickers
	);

	// In single mode, only show stickers in the valid set
	let eligible = $derived(
		mode === 'single'
			? filtered.filter(s => validStickerIds.includes(Number(s.id)))
			: filtered
	);

	let showAllNone = $derived(mode === 'multi');

	let isSingleEmpty = $derived(mode === 'single' && validStickerIds.length === 0);
</script>

<div class="space-y-3">
	<div class="flex items-center justify-between gap-2">
		<Input
			bind:value={search}
			placeholder="Search stickers..."
			class="flex-1"
		/>
		{#if showAllNone}
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
		{/if}
	</div>

	<Toggle label="Show default Discord stickers" checked={showDefault} onchange={toggleDefaults} />

	{#if mode === 'multi' && selected.size > 0}
		<p class="text-xs text-muted">{selected.size} sticker{selected.size !== 1 ? 's' : ''} selected</p>
	{/if}
	{#if mode === 'single' && displayId !== null}
		<p class="text-xs text-accent">Display sticker set ★</p>
	{/if}

	{#if loading}
		<div class="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
			{#each Array(6) as _}
				<div class="aspect-square rounded-lg bg-border/60 animate-pulse"></div>
			{/each}
		</div>
	{:else if error}
		<p class="text-sm text-danger">{error}</p>
	{:else if isSingleEmpty}
		<EmptyState
			icon="🏷️"
			title="No valid stickers selected"
			message="Select valid stank stickers above first, then pick a display sticker here."
		/>
	{:else if eligible.length === 0}
		<EmptyState
			icon="🏷️"
			title="No stickers found"
			message={showDefault
				? 'No custom or default stickers available.'
				: 'This guild has no custom stickers. Enable default stickers to pick from Discord\'s built-in packs.'}
		/>
	{:else}
		<div class="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
			{#each eligible as sticker (sticker.id)}
				{@const id = Number(sticker.id)}
				{@const isSelected = id ? selected.has(id) : false}
				{@const isDisplay = mode === 'single' && id && displayId === id}
				<button
					type="button"
					onclick={() => {
						if (!id) return;
						if (mode === 'single') {
							selectDisplay(id);
						} else {
							toggleSticker(id);
						}
					}}
					class="relative group rounded-lg border-2 p-1 aspect-square flex flex-col items-center justify-center transition-all
						{isSelected || isDisplay
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

					<!-- Multi mode: checkmark badge -->
					{#if mode === 'multi' && isSelected}
						<div class="absolute top-1 right-1 w-4 h-4 bg-accent rounded-full flex items-center justify-center">
							<span class="text-white text-[10px] leading-none">✓</span>
						</div>
					{/if}

					<!-- Single mode: always-visible ★ on the selected display sticker -->
					{#if mode === 'single' && isDisplay}
						<div class="absolute bottom-1 right-1 w-5 h-5 rounded-full bg-yellow-400 flex items-center justify-center">
							<span class="text-white text-[10px] leading-none">★</span>
						</div>
					{/if}
				</button>
			{/each}
		</div>
	{/if}

	{#if mode === 'single' && displayId === null && validStickerIds.length > 0}
		<p class="text-xs text-warning">Select a display sticker before saving.</p>
	{/if}
</div>
