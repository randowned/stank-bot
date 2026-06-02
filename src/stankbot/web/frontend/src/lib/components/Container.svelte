<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
		class?: string;
		children: Snippet;
	}

	const sizeCls: Record<string, string> = {
		sm: 'max-w-xl',
		md: 'max-w-3xl',
		lg: 'max-w-4xl',
		xl: 'max-w-6xl',
		full: ''
	};

	let { size = 'md', class: klass = '', children }: Props = $props();

	const cls = $derived(`w-full mx-auto ${sizeCls[size]} ${klass}`.trim());
</script>

<div class={cls}>
	{@render children()}
</div>
