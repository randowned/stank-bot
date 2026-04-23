<script lang="ts">
	import { base } from '$app/paths';
	import { untrack } from 'svelte';
	import type { PlayerRow } from '$lib/types';
	import RankBadge from './RankBadge.svelte';

	interface Props {
		rank: number;
		row: PlayerRow;
		isMe?: boolean;
	}

	let { rank, row, isMe = false }: Props = $props();

	const href = $derived(`${base}/player/${row.user_id}`);
	const net = $derived(row.earned_sp - row.punishments);

	let flash = $state(false);
	const rowKey = $derived(`${row.user_id}:${row.earned_sp}:${row.punishments}`);
	let prevKey = $state('');

	$effect(() => {
		const key = rowKey;
		const prev = untrack(() => prevKey);
		if (prev === '') {
			prevKey = key;
			return;
		}
		if (key !== prev) {
			prevKey = key;
			flash = true;
			const id = setTimeout(() => (flash = false), 900);
			return () => clearTimeout(id);
		}
	});
</script>

<a
	{href}
	class="flex items-center gap-3 p-2 -mx-2 rounded-lg transition-colors
		{isMe ? 'bg-accent/20' : 'hover:bg-border/50'}
		{flash ? 'row-flash' : ''}"
	data-testid="rank-row"
>
	<RankBadge {rank} />
	<div class="flex-1 min-w-0">
		<div class="font-medium truncate {isMe ? 'text-accent' : ''}">{row.display_name}</div>
		<div class="text-xs text-muted">
			{row.earned_sp} SP · {row.punishments} PP · <span class="font-semibold">{net}</span> net
		</div>
	</div>
	{#if isMe}
		<span class="badge text-accent">You</span>
	{/if}
</a>
