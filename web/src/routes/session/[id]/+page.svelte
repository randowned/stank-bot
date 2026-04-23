<script lang="ts">
	import { base } from '$app/paths';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	let { data } = $props();

	const session = $derived(data.session);

	function fmt(s: string | null): string {
		if (!s) return '—';
		return new Date(s).toLocaleString();
	}
</script>

<div class="p-4 space-y-4 max-w-3xl mx-auto">
	{#if session}
		<PageHeader title="Session #{session.session_id}" subtitle={fmt(session.started_at)} />

		<Card title="Summary">
			<dl class="grid grid-cols-2 gap-4 text-sm">
				<div>
					<dt class="text-muted uppercase text-xs">Started</dt>
					<dd>{fmt(session.started_at)}</dd>
				</div>
				<div>
					<dt class="text-muted uppercase text-xs">Ended</dt>
					<dd>{fmt(session.ended_at)}</dd>
				</div>
				<div>
					<dt class="text-muted uppercase text-xs">Chains started</dt>
					<dd class="text-lg font-bold">{session.chains_started}</dd>
				</div>
				<div>
					<dt class="text-muted uppercase text-xs">Chains broken</dt>
					<dd class="text-lg font-bold">{session.chains_broken}</dd>
				</div>
			</dl>
		</Card>

		{#if session.top_earner}
			<Card title="Top earner">
				<a
					href="{base}/player/{session.top_earner[0]}"
					class="flex items-center justify-between hover:bg-border/40 -m-2 p-2 rounded-md"
				>
					<span class="font-mono text-sm">#{session.top_earner[0]}</span>
					<span class="font-bold text-accent">{session.top_earner[1]} SP</span>
				</a>
			</Card>
		{/if}

		{#if session.top_breaker}
			<Card title="Top chainbreaker">
				<a
					href="{base}/player/{session.top_breaker[0]}"
					class="flex items-center justify-between hover:bg-border/40 -m-2 p-2 rounded-md"
				>
					<span class="font-mono text-sm">#{session.top_breaker[0]}</span>
					<span class="font-bold text-danger">{session.top_breaker[1]}×</span>
				</a>
			</Card>
		{/if}

		<a href="{base}/sessions" class="btn btn-secondary w-full text-center">← All sessions</a>
	{:else}
		<EmptyState icon="📜" title="Session not found" />
	{/if}
</div>
