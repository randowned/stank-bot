<script lang="ts">
	import { apiFetch, apiPost } from '$lib/api';
	import { toErrorMessage } from '$lib/api-utils';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Card from '$lib/components/Card.svelte';
	import Button from '$lib/components/Button.svelte';
	import Input from '$lib/components/Input.svelte';
	import FormField from '$lib/components/FormField.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import RemovableItem from '$lib/components/RemovableItem.svelte';

	interface RolesDoc {
		role_ids: string[];
		role_names: Record<string, string>;
		global_user_ids: string[];
		names: Record<string, string>;
	}

	let doc = $state<RolesDoc | null>(null);
	let error = $state<string | null>(null);
	let newRole = $state('');
	let newUser = $state(''); // keep as string — number input coerces to Number, breaking .trim() and losing precision on large Discord IDs

	async function load() {
		try {
			doc = await apiFetch<RolesDoc>('/api/admin/roles');
		} catch (err) {
			error = toErrorMessage(err, 'Failed to load');
		}
	}

	async function addRole() {
		if (!newRole.trim()) return;
		error = null;
		try {
			await apiPost('/api/admin/roles/add', { role_id: Number(newRole) });
			newRole = '';
			await load();
		} catch (err) {
			error = toErrorMessage(err, 'Add failed');
		}
	}

	async function removeRole(role: string) {
		error = null;
		try {
			await apiPost('/api/admin/roles/remove', { role_id: Number(role) });
			await load();
		} catch (err) {
			error = toErrorMessage(err, 'Remove failed');
		}
	}

	async function addUser() {
		const trimmed = String(newUser).trim();
		if (!trimmed) return;
		error = null;
		try {
			await apiPost('/api/admin/roles/users/add', { user_id: parseInt(trimmed, 10) });
			newUser = '';
			await load();
		} catch (err) {
			error = toErrorMessage(err, 'Add failed');
		}
	}

	async function removeUser(uid: string) {
		error = null;
		try {
			await apiPost('/api/admin/roles/users/remove', { user_id: Number(uid) });
			await load();
		} catch (err) {
			error = toErrorMessage(err, 'Remove failed');
		}
	}

	onMount(load);
</script>

<PageHeader title="Admins" subtitle="Per-guild admin roles and global admin users" />

{#if error}
	<ErrorState message={error} onretry={load} />
{/if}

<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
	<Card title="Guild admin roles">
		{#if doc}
			<ul class="mb-4 space-y-1">
				{#each doc.role_ids as r (r)}
					<RemovableItem onremove={() => removeRole(r)}>
						<span>
							{#if doc.role_names[r]}
								<span class="font-medium">{doc.role_names[r]}</span>
								<span class="text-muted font-mono ml-1">#{r}</span>
							{:else}
								<span class="font-mono">{r}</span>
							{/if}
						</span>
					</RemovableItem>
				{:else}
					<li class="text-muted text-sm">No roles configured.</li>
				{/each}
			</ul>
		{:else}
			<div class="mb-4 space-y-2">
				{#each Array(3) as _}
					<div class="flex items-center justify-between">
						<div class="h-4 bg-border/60 animate-pulse rounded w-40"></div>
						<div class="h-4 bg-border/60 animate-pulse rounded w-16"></div>
					</div>
				{/each}
			</div>
		{/if}
		<FormField label="Add role ID">
			<Input bind:value={newRole} type="number" placeholder="Discord role ID" />
		</FormField>
		<div class="flex justify-end mt-2">
			<Button onclick={addRole}>Add</Button>
		</div>
	</Card>

	<Card title="Global admin users">
		{#if doc}
			<ul class="mb-4 space-y-1">
				{#each doc.global_user_ids as u (u)}
					<RemovableItem onremove={() => removeUser(u)}>
						<span>
							{#if doc.names[u]}
								<span class="font-medium">{doc.names[u]}</span>
								<span class="text-muted font-mono ml-1">#{u}</span>
							{:else}
								<span class="font-mono">{u}</span>
							{/if}
						</span>
					</RemovableItem>
				{:else}
					<li class="text-muted text-sm">No global admins.</li>
				{/each}
			</ul>
		{:else}
			<div class="mb-4 space-y-2">
				{#each Array(2) as _}
					<div class="flex items-center justify-between">
						<div class="h-4 bg-border/60 animate-pulse rounded w-36"></div>
						<div class="h-4 bg-border/60 animate-pulse rounded w-16"></div>
					</div>
				{/each}
			</div>
		{/if}
		<FormField label="Add user ID">
			<Input bind:value={newUser} type="text" placeholder="Discord user ID" />
		</FormField>
		<div class="flex justify-end mt-2">
			<Button onclick={addUser}>Add</Button>
		</div>
	</Card>
</div>
