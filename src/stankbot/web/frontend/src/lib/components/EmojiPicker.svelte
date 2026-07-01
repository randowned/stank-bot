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

	interface SelectedEmoji {
		id: string | null;
		name: string;
		image_url: string | null;
		type: 'custom' | 'default';
		animated?: boolean;
	}

	interface Props {
		guildId: string;
		value: string;
		onchange?: (value: string) => void;
	}

	let {
		guildId: _guildId,
		value: _value = '',
		onchange
	}: Props = $props();

	let emojis = $state<Emoji[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showDefault = $state(false);
	let search = $state('');

	let selected = $state<SelectedEmoji[]>(parseValue(_value));

	// Dropdown state
	let open = $state(false);
	let dropdownEl = $state<HTMLDivElement>();
	let searchInputEl = $state<HTMLInputElement>();

	// --- Parse initial value into selected emojis ---------------------------

	function parseValue(raw: string): SelectedEmoji[] {
		if (!raw.trim()) return [];
		const parts = raw.split(',').map(p => p.trim()).filter(Boolean);
		const results: SelectedEmoji[] = [];
		for (const p of parts) {
			const match = p.match(/^<(a?):([^:]+):(\d+)>$/);
			if (match) {
				results.push({
					id: match[3],
					name: match[2],
					image_url: null, // populated from emoji list later
					type: 'custom',
					animated: match[1] === 'a'
				});
			} else {
				results.push({
					id: null,
					name: p,
					image_url: null,
					type: 'default'
				});
			}
		}
		return results;
	}

	// --- Load emojis from API --------------------------------------------

	async function loadEmojis() {
		loading = true;
		error = null;
		try {
			const res = await apiFetch<{ emojis: Emoji[] }>(
				`/api/admin/guild-emojis?include_default=${showDefault}`
			);
			emojis = res.emojis;
			// Patch image_url into parsed selections from the loaded emoji list
			patchSelectedImages();
		} catch (err) {
			error = toErrorMessage(err, 'Failed to load emojis');
		} finally {
			loading = false;
		}
	}

	function patchSelectedImages() {
		// For custom emojis with IDs, look up the image_url from the loaded list
		for (const sel of selected) {
			if (sel.type === 'custom' && sel.id && !sel.image_url) {
				const match = emojis.find(e => e.id === sel.id);
				if (match) sel.image_url = match.image_url;
			}
		}
	}

	// --- Emit the tag string to parent -----------------------------------

	function buildTag(emojis: SelectedEmoji[]): string {
		const parts: string[] = [];
		for (const e of emojis) {
			if (e.type === 'custom' && e.id) {
				const prefix = e.animated ? 'a' : '';
				parts.push(`<${prefix}:${e.name}:${e.id}>`);
			} else {
				parts.push(e.name);
			}
		}
		return parts.join(', ');
	}

	function emit() {
		onchange?.(buildTag(selected));
	}

	// --- Selection -------------------------------------------------------

	function addEmoji(emoji: Emoji) {
		// Don't add duplicates
		const already = selected.find(s =>
			s.type === emoji.type &&
			(s.type === 'custom' ? s.id === emoji.id : s.name === emoji.name)
		);
		if (already) {
			search = '';
			if (searchInputEl) searchInputEl.focus();
			return;
		}
		selected.push({
			id: emoji.id,
			name: emoji.name,
			image_url: emoji.image_url,
			type: emoji.type,
			animated: emoji.animated
		});
		search = '';
		emit();
		if (searchInputEl) searchInputEl.focus();
	}

	function removeEmoji(idx: number) {
		selected.splice(idx, 1);
		emit();
	}

	// --- Dropdown --------------------------------------------------------

	function handleFocus() {
		open = true;
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

	// --- Init ------------------------------------------------------------

	// Sync from external value prop changes (e.g., parent load)
	$effect(() => {
		const newParsed = parseValue(_value);
		// Only sync if the external value has genuinely changed
		const currentTag = buildTag(selected);
		if (_value !== currentTag && newParsed.length !== selected.length || _value !== buildTag(newParsed)) {
			selected = newParsed;
			patchSelectedImages();
		}
	});

	$effect(() => {
		loadEmojis();
	});

	// --- Filtering -------------------------------------------------------

	let filtered = $derived(
		search.trim()
			? emojis.filter(e => e.name.toLowerCase().includes(search.toLowerCase()))
			: emojis
	);
</script>

<div bind:this={dropdownEl} class="relative">
	<!-- Search input (autocomplete trigger) -->
	<div
		role="combobox"
		aria-expanded={open}
		aria-controls="emoji-dropdown"
		tabindex="0"
		class="w-full flex items-center gap-2 px-3 py-2 rounded-md border border-border bg-transparent min-h-[42px] cursor-text"
		onclick={() => { open = true; searchInputEl?.focus(); }}
		onkeydown={(e: KeyboardEvent) => {
			if (e.key === 'Enter' || e.key === ' ') {
				e.preventDefault();
				open = !open;
				if (open) searchInputEl?.focus();
			}
		}}
	>
		<div class="flex flex-wrap gap-1 flex-1 items-center">
			<!-- Selected emoji chips -->
			{#each selected as emoji, idx (emoji.id ?? emoji.name)}
				<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-accent/20 whitespace-nowrap">
					{#if emoji.image_url}
						<img src={emoji.image_url} alt={emoji.name} class="w-4 h-4 object-contain" />
					{:else}
						{emoji.name}
					{/if}
					<span
						role="button"
						tabindex="0"
						onclick={(e: MouseEvent) => { e.stopPropagation(); removeEmoji(idx); }}
						onkeydown={(e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); e.preventDefault(); removeEmoji(idx); } }}
						class="ml-0.5 hover:text-danger text-muted cursor-pointer"
					>&times;</span>
				</span>
			{/each}
			<input
				bind:this={searchInputEl}
				bind:value={search}
				onfocus={handleFocus}
				placeholder={selected.length === 0 ? 'Search emojis...' : ''}
				class="flex-1 min-w-[80px] bg-transparent border-none outline-none text-sm placeholder:text-muted"
			/>
		</div>
		<span class="text-muted text-xs flex-shrink-0">{open ? '▲' : '▼'}</span>
	</div>

	<!-- Dropdown -->
	{#if open}
		<div id="emoji-dropdown" class="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-md border border-border bg-background shadow-lg">
			<div class="px-3 py-2 border-b border-border">
				<Toggle label="Include default emojis" checked={showDefault} onchange={(v: boolean) => { showDefault = v; loadEmojis(); }} />
			</div>

			{#if loading}
				<div class="px-3 py-6 text-center text-sm text-muted">Loading...</div>
			{:else if error}
				<div class="px-3 py-4 text-sm text-danger">{error}</div>
			{:else if filtered.length === 0}
				<div class="px-3 py-4">
					<EmptyState
						icon="😶"
						title="No emojis found"
						message={search
							? `No emojis match "${search}"`
							: 'No emojis available.'}
					/>
				</div>
			{:else}
				<div class="py-1">
					{#each filtered as emoji (emoji.id ?? emoji.name)}
						{@const isSelected =
							(emoji.type === 'custom' && emoji.id && selected.some(s => s.type === 'custom' && s.id === emoji.id)) ||
							(emoji.type === 'default' && selected.some(s => s.type === 'default' && s.name === emoji.name))}
						<button
							type="button"
							onclick={() => addEmoji(emoji)}
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
