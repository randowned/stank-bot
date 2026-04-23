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
			const res = await apiPost<{ new_session_id: number }>('/v2/api/admin/new-session');
			message = `Started session ${res.new_session_id}.`;
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Failed';
		} finally {
			busy = false;
		}
	}
</script>

<PageHeader title="New session" subtitle="End the current session and start a new one" />

<Card>
	<p class="text-sm text-muted mb-3">
		Ends the currently running session and starts a fresh one. The previous session stays in
		history and its records are preserved.
	</p>
	<Button onclick={() => (open = true)}>Start new session</Button>
	{#if message}<p class="text-sm text-muted mt-3">{message}</p>{/if}
</Card>

<ConfirmDialog
	bind:open
	title="End current session?"
	body="This ends the current session immediately and starts a new one."
	confirmLabel="Start new session"
	onconfirm={confirm}
/>
