<script lang="ts">
	import { base } from '$app/paths';
	import { untrack } from 'svelte';
	import type { PlayerRow } from '$lib/types';
	import RankBadge from './RankBadge.svelte';
	import PointsDelta from './PointsDelta.svelte';

	interface Props {
		rank: number;
		row: PlayerRow;
		isMe?: boolean;
	}

	let { rank, row, isMe = false }: Props = $props();

	const href = $derived(`${base}/player/${row.user_id}`);
	const net = $derived(row.net ?? row.earned_sp - row.punishments);
	const reactionsInChain = $derived(row.reactions_in_chain ?? 0);
	const reactedPct = $derived(row.reacted_pct ?? 0);
	const hasReactionMeta = $derived(row.reactions_in_chain !== undefined);

	const netColor = $derived(net > 0 ? 'text-ok' : net < 0 ? 'text-danger' : 'text-muted');

	let flash = $state(false);
	const rowKey = $derived(
		`${row.user_id}:${row.earned_sp}:${row.punishments}:${reactionsInChain}`
	);
	let prevKey = $state('');
	let prevSp = $state(row.earned_sp);
	let prevPp = $state(row.punishments);
	let prevReacts = $state(reactionsInChain);

	type DeltaChip = { id: number; delta: number; kind: 'stank' | 'reaction' | 'break' | 'finish' | 'other' };
	let chips: DeltaChip[] = $state([]);
	let chipSeq = 0;

	$effect(() => {
		const key = rowKey;
		const prev = untrack(() => prevKey);
		if (prev === '') {
			prevKey = key;
			prevSp = row.earned_sp;
			prevPp = row.punishments;
			prevReacts = reactionsInChain;
			return;
		}
		if (key !== prev) {
			const dSp = row.earned_sp - untrack(() => prevSp);
			const dPp = row.punishments - untrack(() => prevPp);
			const dRe = reactionsInChain - untrack(() => prevReacts);

			prevKey = key;
			prevSp = row.earned_sp;
			prevPp = row.punishments;
			prevReacts = reactionsInChain;

			flash = true;
			const flashId = setTimeout(() => (flash = false), 900);

			const added: DeltaChip[] = [];
			if (dPp > 0) {
				added.push({ id: ++chipSeq, delta: -dPp, kind: 'break' });
			}
			if (dSp > 0) {
				added.push({ id: ++chipSeq, delta: dSp, kind: 'stank' });
			}
			if (dRe > 0) {
				added.push({ id: ++chipSeq, delta: dRe, kind: 'reaction' });
			}
			if (added.length) {
				chips = [...chips, ...added];
			}

			return () => clearTimeout(flashId);
		}
	});

	function removeChip(id: number) {
		chips = chips.filter((c) => c.id !== id);
	}
</script>

<a
	{href}
	class="relative grid grid-cols-[auto_1fr_auto] items-center gap-3 p-2 -mx-2 rounded-lg transition-colors
		{isMe ? 'bg-accent/20' : 'hover:bg-border/50'}
		{flash ? 'row-flash' : ''}"
	data-testid="rank-row"
>
	<RankBadge {rank} />
	<div class="min-w-0">
		<div class="font-medium truncate {isMe ? 'text-accent' : ''}">
			{row.display_name}
			{#if isMe}
				<span class="badge text-accent ml-1">You</span>
			{/if}
		</div>
		<div class="text-xs text-muted truncate">
			{#if hasReactionMeta}
				{reactionsInChain} reacts · {reactedPct}% reacted
			{:else}
				—
			{/if}
		</div>
	</div>
	<div class="relative min-w-[4ch] text-right">
		<span class="text-2xl font-semibold tabular-nums {netColor}" data-testid="net-score">{net}</span>
		{#each chips as chip (chip.id)}
			<PointsDelta
				delta={chip.delta}
				kind={chip.kind}
				onDone={() => removeChip(chip.id)}
			/>
		{/each}
	</div>
</a>
