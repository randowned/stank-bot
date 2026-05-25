<script lang="ts">
	import { base } from '$app/paths';
	import { formatNumber } from '$lib/format';
	import type { Snippet } from 'svelte';
	import RelativeTime from './RelativeTime.svelte';

	interface Props {
		id: number;
		title: string;
		thumbnailUrl: string | null;
		mediaType: string;
		publishedAt: string | null;
		metrics: Record<string, { value?: number }>;
		href?: string | null;
		actions?: Snippet;
		compact?: boolean;
		testId?: string;
	}

	let {
		id,
		title,
		thumbnailUrl,
		mediaType,
		publishedAt,
		metrics,
		href = null,
		actions,
		compact = false,
		testId = 'media-item-card'
	}: Props = $props();

	const resolvedHref = $derived(href ?? `${base}/media/${id}`);
	const icon = $derived(mediaType === 'youtube' ? '▶️' : '🟢');
	const borderColor = $derived(
		mediaType === 'youtube'
			? 'border-l-[3px] border-l-[#ff0000]/70'
			: mediaType === 'spotify'
				? 'border-l-[3px] border-l-[#1db954]/70'
				: ''
	);

	function primaryMetrics(): Array<{ icon: string; label: string; value: number }> {
		if (mediaType === 'youtube') {
			return [
				{ icon: '👁️', label: 'Views', value: Number(metrics?.view_count?.value ?? 0) },
				{ icon: '👍', label: 'Likes', value: Number(metrics?.like_count?.value ?? 0) },
				{ icon: '💬', label: 'Comments', value: Number(metrics?.comment_count?.value ?? 0) }
			];
		}
		return [
			{ icon: '🎧', label: 'Plays', value: Number(metrics?.playcount?.value ?? 0) }
		];
	}
</script>

<div
	class="panel overflow-hidden {borderColor} hover:border-accent/50 transition-colors"
	data-testid={testId}
>
	<div class="flex gap-3 {compact ? 'p-2' : 'p-3'}">
		{#if thumbnailUrl}
			<a href={resolvedHref} class="shrink-0 no-underline">
				<img
					src={thumbnailUrl}
					alt={title}
					class="{compact ? 'w-16 h-10' : 'w-24 h-14'} rounded object-cover"
					loading="lazy"
				/>
			</a>
		{:else}
			<a
				href={resolvedHref}
				class="{compact ? 'w-16 h-10' : 'w-24 h-14'} rounded bg-border shrink-0 flex items-center justify-center text-muted text-sm no-underline"
			>
				{icon}
			</a>
		{/if}
		<div class="min-w-0 flex-1">
			<a href={resolvedHref} class="text-sm font-semibold text-text truncate block no-underline hover:text-accent transition-colors">
				{title}
			</a>
			{#if publishedAt}
				<div class="text-xs text-muted mt-0.5">
					<RelativeTime datetime={publishedAt} />
				</div>
			{/if}
			<div class="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-xs text-muted">
				{#each primaryMetrics() as m}
					<span title={m.label}>
						{m.icon}
						<span class="text-text font-mono">{formatNumber(m.value)}</span>
					</span>
				{/each}
			</div>
		</div>
		{#if actions}
			<div class="shrink-0 flex items-center">
				{@render actions()}
			</div>
		{/if}
	</div>
</div>
