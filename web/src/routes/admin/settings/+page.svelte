<script lang="ts">
	import { apiFetch, apiPost, FetchError } from '$lib/api';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import FormField from '$lib/components/FormField.svelte';
	import Input from '$lib/components/Input.svelte';
	import Toggle from '$lib/components/Toggle.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';

	interface SettingsDoc {
		guild_id: string;
		guild_name: string;
		values: Record<string, unknown>;
		labels: Record<string, { title: string; help: string }>;
	}

	const INT_KEYS = [
		'sp_flat',
		'sp_position_bonus',
		'sp_starter_bonus',
		'sp_finish_bonus',
		'sp_reaction',
		'sp_team_player_bonus',
		'pp_break_base',
		'pp_break_per_stank',
		'restank_cooldown_seconds',
		'stank_ranking_rows',
		'board_name_max_len'
	];
	const BOOL_KEYS = [
		'chain_continues_across_sessions',
		'enable_reaction_bonus',
		'maintenance_mode'
	];
	const LIST_KEYS = ['reset_hours_utc', 'reset_warning_minutes'];

	let doc = $state<SettingsDoc | null>(null);
	let loadError = $state<string | null>(null);
	let saving = $state(false);
	let saveMsg = $state<string | null>(null);

	let ints = $state<Record<string, string>>({});
	let bools = $state<Record<string, boolean>>({});
	let lists = $state<Record<string, string>>({});

	async function load() {
		loadError = null;
		try {
			doc = await apiFetch<SettingsDoc>('/v2/api/admin/settings');
			for (const k of INT_KEYS) ints[k] = String(doc.values[k] ?? '');
			for (const k of BOOL_KEYS) bools[k] = Boolean(doc.values[k]);
			for (const k of LIST_KEYS) {
				const raw = doc.values[k];
				lists[k] = Array.isArray(raw) ? raw.join(', ') : String(raw ?? '');
			}
		} catch (err) {
			loadError = err instanceof FetchError ? err.message : 'Failed to load settings';
		}
	}

	async function save() {
		saving = true;
		saveMsg = null;
		try {
			const values: Record<string, unknown> = {};
			for (const k of INT_KEYS) {
				if (ints[k].trim()) values[k] = Number(ints[k]);
			}
			for (const k of BOOL_KEYS) values[k] = bools[k];
			for (const k of LIST_KEYS) {
				if (lists[k].trim()) values[k] = lists[k];
			}
			await apiPost('/v2/api/admin/settings', { values });
			saveMsg = 'Saved.';
		} catch (err) {
			saveMsg = err instanceof FetchError ? err.message : 'Save failed';
		} finally {
			saving = false;
		}
	}

	onMount(load);
</script>

<PageHeader title="Settings" subtitle={doc?.guild_name ?? ''} />

{#if loadError}
	<ErrorState message={loadError} onretry={load} />
{:else if !doc}
	<Card>
		{#each Array(6) as _, i (i)}
			<div class="mb-3"><Skeleton height="1.5rem" /></div>
		{/each}
	</Card>
{:else}
	<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
		<Card title="Scoring">
			{#each INT_KEYS as k (k)}
				{#if doc.labels[k]}
					<FormField label={doc.labels[k].title} hint={doc.labels[k].help}>
						<Input type="number" bind:value={ints[k]} />
					</FormField>
				{/if}
			{/each}
		</Card>

		<Card title="Behavior">
			{#each BOOL_KEYS as k (k)}
				{#if doc.labels[k]}
					<FormField label={doc.labels[k].title} hint={doc.labels[k].help}>
						<Toggle bind:checked={bools[k]} label={doc.labels[k].title} />
					</FormField>
				{/if}
			{/each}

			<h3 class="text-sm font-semibold mt-3 mb-2 text-muted uppercase tracking-wide">
				Reset windows
			</h3>
			{#each LIST_KEYS as k (k)}
				{#if doc.labels[k]}
					<FormField label={doc.labels[k].title} hint="{doc.labels[k].help} (comma-separated)">
						<Input bind:value={lists[k]} placeholder="0, 6, 12, 18" />
					</FormField>
				{/if}
			{/each}
		</Card>
	</div>

	<div class="mt-4 flex items-center gap-3">
		<Button onclick={save} loading={saving}>Save</Button>
		{#if saveMsg}<span class="text-sm text-muted">{saveMsg}</span>{/if}
	</div>
{/if}
