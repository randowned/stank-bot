<script lang="ts">
	import { base } from '$app/paths';
	import type { SessionSummary } from '$lib/types';
	import { formatDateTime } from '$lib/datetime';
	import { formatNumber } from '$lib/format';
	import Duration from '$lib/components/Duration.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Container from '$lib/components/Container.svelte';

	let { data } = $props();

	const sessions = $derived(data.sessions as SessionSummary[]);

	function dateRange(started: string | null, ended: string | null | undefined): string {
		const start = formatDateTime(started);
		if (!ended) return start;
		return `${start} → ${formatDateTime(ended)}`;
	}

	function stats(s: SessionSummary): Array<{ label: string; value: string }> {
		return [
			{ label: 'Stankers', value: String(s.unique_stankers ?? 0) },
			{ label: 'Stanks', value: String(s.stanks ?? 0) },
			{ label: 'Chains', value: String(s.chains ?? 0) },
			{ label: 'Reactions', value: String(s.reactions ?? 0) },
			{ label: 'SP', value: formatNumber(s.total_sp ?? 0) },
			{ label: 'PP', value: formatNumber(s.total_pp ?? 0) },
		];
	}
</script>

<Container size="xl" class="p-4 space-y-4">
	<PageHeader title="Session History" subtitle="Each entry is one reset window." />

	{#if !sessions.length}
		<div class="panel">
			<EmptyState icon="📜" title="No sessions yet" message="Completed sessions will appear here after the first reset." />
		</div>
	{:else}
		<div class="space-y-2">
			{#each sessions as s}
				<a href="{base}/session/{s.session_id}" class="panel block">
					<div class="flex items-center justify-between mb-1">
						<span class="font-medium">Session #{s.session_id}</span>
						{#if s.active}
							<span class="text-xs font-semibold text-ok">ACTIVE</span>
						{:else}
							<span class="text-xs font-semibold text-muted">ENDED</span>
						{/if}
					</div>
					<div class="text-xs text-muted mb-2">{dateRange(s.started_at, s.ended_at)}</div>
					{#if s.ended_at}
						<div class="text-xs text-muted mb-2"><Duration start={s.started_at} end={s.ended_at} /></div>
					{/if}
					<div class="flex flex-wrap gap-1.5">
						{#each stats(s) as stat}
							<span class="inline-flex items-center gap-1 px-2 py-0.5 bg-border/50 rounded text-xs">
								<span class="text-muted">{stat.label}</span>
								<span class="text-text font-mono font-medium">{stat.value}</span>
							</span>
						{/each}
					</div>
				</a>
			{/each}
		</div>
	{/if}

	<a href="{base}/" class="btn btn-secondary w-full text-center">← Back to Board</a>
</Container>