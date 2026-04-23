<script lang="ts">
	import { apiPost, FetchError } from '$lib/api';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import Input from '$lib/components/Input.svelte';
	import FormField from '$lib/components/FormField.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';

	let typed = $state('');
	let message = $state<string | null>(null);
	let open = $state(false);

	async function confirm() {
		message = null;
		try {
			await apiPost('/v2/api/admin/reset', { confirm: 'RESET' });
			message = 'Guild state reset.';
			typed = '';
		} catch (err) {
			message = err instanceof FetchError ? err.message : 'Reset failed';
		}
	}
</script>

<PageHeader title="Reset guild" subtitle="Wipe all events, chains, records, and totals" />

<Card>
	<p class="text-sm text-muted mb-3">
		This is irreversible. Every event, chain, cooldown, record, achievement, and point total for
		this guild is deleted. Settings and altar configuration are kept.
	</p>

	<FormField label="Type RESET to enable the button" hint="Prevents accidental clicks">
		<Input bind:value={typed} placeholder="RESET" />
	</FormField>

	<Button variant="danger" disabled={typed !== 'RESET'} onclick={() => (open = true)}>
		Reset everything
	</Button>
	{#if message}<p class="text-sm text-muted mt-3">{message}</p>{/if}
</Card>

<ConfirmDialog
	bind:open
	title="Irreversible: reset guild state?"
	body="Deletes events, chains, cooldowns, records, achievements, and totals. Not undoable."
	confirmLabel="Reset"
	danger
	onconfirm={confirm}
/>
