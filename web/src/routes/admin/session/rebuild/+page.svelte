<script lang="ts">
	import { apiPost, FetchError } from '$lib/api';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';

	let open = $state(false);
	let message = $state<string | null>(null);
	let busy = $state(false);

	async function confirm() {
		busy = true;
		message = null;
		try {
			const res = await apiPost<Record<string, unknown>>('/v2/api/admin/rebuild');
			message = `Rebuild complete. ${JSON.stringify(res)}`;
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Rebuild failed';
		} finally {
			busy = false;
		}
	}
</script>

<PageHeader title="Rebuild" subtitle="Re-derive all state from the raw event log" />

<Card>
	<p class="text-sm text-muted mb-3">
		Replays the append-only event log to recompute chains, totals, and records. Use this after
		changing scoring settings or fixing a bug in the chain logic. The raw event log itself is not
		modified.
	</p>
	<Button variant="danger" onclick={() => (open = true)}>Rebuild</Button>
	{#if message}<p class="text-sm text-muted mt-3 break-all">{message}</p>{/if}
</Card>

<ConfirmDialog
	bind:open
	title="Rebuild state?"
	body="Re-derives chains, totals, and records from the event log. May take a while on large guilds."
	confirmLabel="Rebuild"
	danger
	onconfirm={confirm}
/>
