<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		href?: string;
		onclick?: (e: MouseEvent) => void;
		disabled?: boolean;
		danger?: boolean;
		active?: boolean;
		children: Snippet;
	}

	let { href, onclick, disabled = false, danger = false, active = false, children }: Props = $props();

	const base =
		'flex items-center gap-2 w-full px-3 py-2 text-sm text-left transition-colors rounded-sm';
	const state = $derived(
		disabled
			? 'text-muted opacity-60 cursor-not-allowed'
			: danger
				? 'text-danger hover:bg-danger/10'
				: active
					? 'bg-accent/15 text-accent'
					: 'text-text hover:bg-border/60'
	);
</script>

{#if href && !disabled}
	<a {href} class="{base} {state}" role="menuitem" data-testid="dropdown-item">
		{@render children()}
	</a>
{:else}
	<button
		type="button"
		{onclick}
		{disabled}
		class="{base} {state}"
		role="menuitem"
		data-testid="dropdown-item"
	>
		{@render children()}
	</button>
{/if}
