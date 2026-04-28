<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		onremove: () => void;
		children: Snippet;
	}

	let { onremove, children }: Props = $props();
</script>

<li class="flex items-center justify-between text-sm">
	{@render children()}
	<button class="text-danger text-sm" onclick={onremove}>Remove</button>
</li>
