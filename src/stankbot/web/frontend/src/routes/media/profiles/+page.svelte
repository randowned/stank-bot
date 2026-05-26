<script lang="ts">
	import { base } from '$app/paths';
	import { formatNumber, formatFreshness } from '$lib/format';
	import type { MediaOwner, ProviderDef } from '$lib/types';
	import { providersByType, loadProviders, ownerMetricUpdates, user } from '$lib/stores';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Tabs from '$lib/components/Tabs.svelte';
	import Button from '$lib/components/Button.svelte';

	let { data } = $props();

	const profiles = $derived((data.profiles as MediaOwner[]) ?? []);
	const providers = $derived((data.providers as ProviderDef[]) ?? []);

	$effect(() => {
		if (providers.length > 0) {
			const map: Record<string, ProviderDef> = {};
			for (const p of providers) map[p.type] = p;
			providersByType.set(map);
		}
	});

	void loadProviders();

	let activeType = $state<string>('');
	let searchQuery = $state('');

	const isAdmin = $derived(($user as { is_admin?: boolean } | null)?.is_admin ?? false);

	let liveMetrics = $state<Record<number, Record<string, number>>>({});
	$effect(() => {
		const update = $ownerMetricUpdates;
		if (!update) return;
		const ownerId = update.ownerId;
		const cur = liveMetrics[ownerId] ?? {};
		for (const m of update.metrics) {
			cur[m.key] = m.value;
		}
		liveMetrics[ownerId] = cur;
	});

	const typeTabs = $derived([
		{ value: '', label: 'All' },
		...providers.map((p) => ({ value: p.type, label: p.label }))
	]);

	const filteredProfiles = $derived.by(() => {
		let list = activeType
			? profiles.filter((p) => p.media_type === activeType)
			: profiles;
		const q = searchQuery.trim().toLowerCase();
		if (q) {
			list = list.filter((p) => p.name.toLowerCase().includes(q));
		}
		return list;
	});

	function metricValue(profile: MediaOwner, key: string): number {
		return (
			liveMetrics[profile.id]?.[key] ??
			profile.metrics?.find((m) => m.key === key)?.value ??
			0
		);
	}

	function providerFor(profile: MediaOwner): ProviderDef | undefined {
		return providers.find((p) => p.type === profile.media_type);
	}
</script>

<div class="max-w-6xl mx-auto p-4 space-y-4">
	<PageHeader title="Profiles" subtitle="All tracked channels & artists" />

	{#if profiles.length === 0}
		<EmptyState
			icon="🎬"
			title="No profiles yet"
			message="Add media from YouTube or Spotify to start tracking channels and artists."
		>
			{#snippet actions()}
				{#if isAdmin}
					<a href="{base}/admin/media/add" class="no-underline">
						<Button variant="primary">Add Media</Button>
					</a>
				{/if}
			{/snippet}
		</EmptyState>
	{:else}
		<div class="mb-4 flex flex-wrap items-center gap-3">
			<div class="flex-1 min-w-0">
				<Tabs tabs={typeTabs} bind:value={activeType} />
			</div>
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search profiles…"
				class="px-3 py-1.5 text-sm rounded border border-border bg-panel text-text placeholder:text-muted focus:outline-none focus:border-accent w-48"
				data-testid="profiles-search"
			/>
		</div>

		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each filteredProfiles as profile (profile.id)}
				{@const prov = providerFor(profile)}
				<a
					href="{base}/media/profile/{profile.id}"
					class="panel hover:border-accent/50 transition-colors cursor-pointer block no-underline rounded-lg overflow-hidden"
					data-testid="profile-card"
				>
					<div
						class="h-{profile.cover_url ? '32' : '20'} bg-cover bg-center relative"
						style:background-image={profile.cover_url
							? `url(${profile.cover_url})`
							: 'none'}
						class:bg-gradient-to-br={!profile.cover_url}
						class:from-border={!profile.cover_url}
						class:to-bg={!profile.cover_url}
					>
						{#if profile.cover_url}
							<div
								class="absolute inset-0"
								style="background: linear-gradient(transparent 30%, var(--bg) 95%)"
							></div>
						{:else if prov}
							<div class="absolute inset-0 flex items-center justify-center text-3xl opacity-30">
								{prov.icon}
							</div>
						{/if}
						<div class="absolute bottom-3 left-3 flex items-center gap-3">
							{#if profile.thumbnail_url}
								<img
									src={profile.thumbnail_url}
									alt={profile.name}
									class="w-10 h-10 rounded-full object-cover border-2 border-border"
									loading="lazy"
								/>
							{:else}
								<div
									class="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center text-accent font-bold text-sm border-2 border-border"
								>
									{profile.name.charAt(0)}
								</div>
							{/if}
							<div>
								<div class="font-semibold text-text text-sm leading-tight">
									{profile.name}
								</div>
								{#if prov}
									<span class="text-xs text-muted">
										{prov.icon} {prov.label}
									</span>
								{/if}
							</div>
						</div>
					</div>
					<div class="p-3">
						<div class="flex flex-wrap gap-3 mb-2">
							{#each (profile.metrics ?? []).slice(0, 3) as m}
								<div class="text-center min-w-[60px]">
									<div class="text-sm font-bold text-text">
										{formatNumber(metricValue(profile, m.key))}
									</div>
									<div class="text-[10px] text-muted uppercase">
										{m.icon} {m.label}
									</div>
								</div>
							{/each}
						</div>
						<div class="flex items-center justify-between text-xs text-muted mt-1">
							<span>
								{profile.media_items_count ?? 0} tracked
								{profile.media_type === 'spotify' ? 'tracks' : 'videos'}
							</span>
							{#if profile.fetched_at}
								{@const freshness = formatFreshness(profile.fetched_at)}
								<span
									class="text-xs px-2 py-0.5 rounded-full border {freshness.state === 'fresh'
										? 'border-green-700 text-green-400'
										: freshness.state === 'stale'
											? 'border-amber-700 text-amber-400'
											: 'border-red-700 text-red-400'}"
									title={freshness.label}
								>
									● {freshness.label}
								</span>
							{/if}
						</div>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
