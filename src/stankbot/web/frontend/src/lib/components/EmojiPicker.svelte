<script lang="ts">
	import { apiFetch } from '$lib/api';
	import { toErrorMessage } from '$lib/api-utils';
	import Toggle from '$lib/components/Toggle.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	interface Emoji {
		id: string | null;
		name: string;
		image_url: string | null;
		animated?: boolean;
		type: 'custom' | 'default';
	}

	interface Props {
		guildId: string;
		selectedIds: number[];
		onchange?: (ids: number[]) => void;
	}

	let {
		guildId: _guildId,
		selectedIds = [],
		onchange
	}: Props = $props();

	let emojis = $state<Emoji[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showDefault = $state(false);
	let open = $state(false);

	// Track selection by emoji name for default emojis (no IDs), by ID for custom
	let selectedNames = $state<Set<string>>(new Set());
	let selectedIdSet = $state<Set<number>>(new Set(selectedIds.map(Number)));

	let dropdownEl = $state<HTMLDivElement>();

	async function loadEmojis() {
		loading = true;
		error = null;
		try {
			const res = await apiFetch<{ emojis: Emoji[] }>(
				`/api/admin/guild-emojis?include_default=${showDefault}`
			);
			emojis = res.emojis;
		} catch (err) {
			error = toErrorMessage(err, 'Failed to load emojis');
		} finally {
			loading = false;
		}
	}

	function emit() {
		const ids: number[] = [];
		for (const e of emojis) {
			if (e.type === 'custom' && e.id && selectedIdSet.has(Number(e.id))) {
				ids.push(Number(e.id));
			}
		}
		// Default emojis are tracked by name; include them as synthetic IDs?
		// For now, only custom emoji IDs are sent to backend (matches current schema)
		onchange?.(ids);
	}

	function toggleEmoji(emoji: Emoji) {
		if (emoji.type === 'custom' && emoji.id) {
			const id = Number(emoji.id);
			if (selectedIdSet.has(id)) {
				selectedIdSet.delete(id);
			} else {
				selectedIdSet.add(id);
			}
		} else if (emoji.type === 'default') {
			if (selectedNames.has(emoji.name)) {
				selectedNames.delete(emoji.name);
			} else {
				selectedNames.add(emoji.name);
			}
		}
		emit();
	}

	function toggleDefaults(v: boolean) {
		showDefault = v;
		loadEmojis();
	}

	function handleClickOutside(e: MouseEvent) {
		if (dropdownEl && !dropdownEl.contains(e.target as Node)) {
			open = false;
		}
	}

	$effect(() => {
		if (open) {
			document.addEventListener('click', handleClickOutside);
			return () => document.removeEventListener('click', handleClickOutside);
		}
	});

	$effect(() => {
		loadEmojis();
	});

	let selectedCount = $derived(
		emojis.filter(e =>
			(e.type === 'custom' && e.id && selectedIdSet.has(Number(e.id))) ||
			(e.type === 'default' && selectedNames.has(e.name))
		).length
	);
</script>

<div bind:this={dropdownEl} class="relative">
	<!-- Trigger -->
	<button
		type="button"
		onclick={() => open = !open}
		class="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-md border border-border bg-transparent text-sm hover:border-muted transition-colors"
	>
		<span class={selectedCount > 0 ? '' : 'text-muted'}>
			{#if selectedCount > 0}
				{selectedCount} emoji{selectedCount !== 1 ? 's' : ''} selected
			{:else}
				Select emojis...
			{/if}
		</span>
		<span class="text-muted text-xs">{open ? '▲' : '▼'}</span>
	</button>

	<!-- Dropdown -->
	{#if open}
		<div class="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-md border border-border bg-background shadow-lg">
			<div class="px-3 py-2 border-b border-border">
				<Toggle label="Include default emojis" checked={showDefault} onchange={toggleDefaults} />
			</div>

			{#if loading}
				<div class="px-3 py-6 text-center text-sm text-muted">Loading...</div>
			{:else if error}
				<div class="px-3 py-4 text-sm text-danger">{error}</div>
			{:else if emojis.length === 0}
				<div class="px-3 py-4">
					<EmptyState
						icon="😶"
						title="No emojis found"
						message={showDefault
							? 'No emojis available.'
							: 'This guild has no custom emojis. Enable default emojis to pick from standard Unicode set.'}
					/>
				</div>
			{:else}
				<div class="py-1">
					{#each emojis as emoji (emoji.id ?? emoji.name)}
						{@const isSelected =
							(emoji.type === 'custom' && emoji.id && selectedIdSet.has(Number(emoji.id))) ||
							(emoji.type === 'default' && selectedNames.has(emoji.name))}
						<button
							type="button"
							onclick={() => toggleEmoji(emoji)}
							class="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-border/40 transition-colors text-left"
						>
							<span class="w-5 h-5 flex items-center justify-center flex-shrink-0">
								{#if emoji.type === 'custom' && emoji.image_url}
									<img src={emoji.image_url} alt={emoji.name} class="w-5 h-5 object-contain" />
								{:else}
									{emoji.name}
								{/if}
							</span>
							<span class="flex-1 truncate">{emoji.type === 'custom' ? `:${emoji.name}:` : emoji.name}</span>
							{#if isSelected}
								<span class="text-accent text-xs">✓</span>
							{/if}
							{#if emoji.type === 'default'}
								<span class="text-[10px] text-muted bg-border/40 px-1 rounded">Default</span>
							{/if}
						</button>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
