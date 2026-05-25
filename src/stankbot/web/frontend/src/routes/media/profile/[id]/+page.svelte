<script lang="ts">
	import { base } from '$app/paths';
	import { formatNumber, formatFreshness } from '$lib/format';
	import type { MediaItem, MediaOwner, ProfileDetail, ProviderDef, MetricSnapshot } from '$lib/types';
	import { providersByType, loadProviders, ownerMetricUpdates } from '$lib/stores';
	import { apiFetch } from '$lib/api';
	import StatTile from '$lib/components/StatTile.svelte';
	import Chart from '$lib/components/Chart.svelte';
	import SelectDropdown from '$lib/components/SelectDropdown.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import MediaItemCard from '$lib/components/MediaItemCard.svelte';

	let { data } = $props();

	const detail = $derived(data.detail as ProfileDetail | null);
	const providers = $derived((data.providers as ProviderDef[]) ?? []);
	const profile = $derived(detail?.profile as MediaOwner | undefined);
	const items = $derived((detail?.items as MediaItem[]) ?? []);
	const itemsCount = $derived(detail?.items_count ?? 0);

	$effect(() => {
		if (providers.length > 0) {
			const map: Record<string, ProviderDef> = {};
			for (const p of providers) map[p.type] = p;
			providersByType.set(map);
		}
	});

	void loadProviders();

	const provider = $derived(providers.find((p) => p.type === profile?.media_type));

	let liveMetrics = $state<Record<string, number>>({});
	let flashKeys = $state<Record<string, boolean>>({});
	$effect(() => {
		const update = $ownerMetricUpdates;
		if (!update || !profile || update.ownerId !== profile.id) return;
		const cur = { ...liveMetrics };
		const flash: Record<string, boolean> = {};
		for (const m of update.metrics) {
			if (cur[m.key] !== m.value) {
				flash[m.key] = true;
			}
			cur[m.key] = m.value;
		}
		liveMetrics = cur;
		flashKeys = flash;
		setTimeout(() => {
			flashKeys = {};
		}, 1500);
	});

	function metricValue(key: string): number {
		return (
			liveMetrics[key] ??
			profile?.metrics?.find((m) => m.key === key)?.value ??
			0
		);
	}

	const freshness = $derived(
		profile?.fetched_at ? formatFreshness(profile.fetched_at) : null
	);

	const metricOptions = $derived(
		(profile?.metrics ?? []).map((m) => ({
			value: m.key,
			label: `${m.icon ?? ''} ${m.label}`,
			icon: m.icon ?? ''
		}))
	);

	const rangeOptions = [
		{ value: 1, label: '1 hour', icon: '⏱️' },
		{ value: 6, label: '6 hours', icon: '⏱️' },
		{ value: 12, label: '12 hours', icon: '⏱️' },
		{ value: 24, label: '24h', icon: '📅' },
		{ value: 48, label: '48h', icon: '📅' },
		{ value: 24 * 7, label: '7 days', icon: '📅' },
		{ value: 24 * 30, label: '30 days', icon: '📅' },
		{ value: 24 * 90, label: '90 days', icon: '📅' },
		{ value: 24 * 365, label: '1 year', icon: '📅' }
	];

	const viewOptions = [
		{ value: 'delta', label: 'Change', icon: 'Δ' },
		{ value: 'total', label: 'Cumulative', icon: 'Σ' }
	];

	let selectedMetric = $state('subscriber_count');
	let selectedHours = $state<number>(24);
	let selectedView = $state('total');

	$effect(() => {
		if (metricOptions.length > 0 && !metricOptions.find((o) => o.value === selectedMetric)) {
			selectedMetric = metricOptions[0].value;
		}
	});

	let history = $state<MetricSnapshot[]>([]);
	let chartLoading = $state(false);

	async function loadChartData() {
		if (!profile) return;
		chartLoading = true;
		try {
			const key = selectedMetric;
			const h = selectedHours;
			let queryStr = `metric=${encodeURIComponent(key)}`;
			if (h > 48) {
				queryStr += `&days=${Math.round(h / 24)}`;
			} else {
				queryStr += `&hours=${h}`;
			}
			if (selectedView === 'delta') queryStr += '&mode=delta';
			const res = await apiFetch<{ history: MetricSnapshot[] }>(
				`/api/media/profile/${profile.id}/history?${queryStr}`
			);
			history = res.history ?? [];
		} catch {
			history = [];
		} finally {
			chartLoading = false;
		}
	}

	$effect(() => {
		void selectedMetric;
		void selectedHours;
		void selectedView;
		if (profile) {
			void loadChartData();
		}
	});

	let chartDatasets = $derived.by(() => {
		if (history.length === 0) return [];
		const points = history.map((p) => ({
			x: new Date(p.fetched_at).getTime(),
			y: p.value
		}));
		return [
			{
				label: profile?.metrics?.find((m) => m.key === selectedMetric)?.label ?? selectedMetric,
				data: points
			}
		];
	});

	const chartLabel = $derived(
		profile?.metrics?.find((m) => m.key === selectedMetric)?.label ?? selectedMetric
	);
</script>

{#if !profile}
	<ErrorState title="Profile not found" message="This channel or artist doesn't exist or has no tracked media in this guild." />
{:else}
	<div class="max-w-5xl mx-auto space-y-6">
		<!-- Back link + freshness -->
		<div class="flex items-center gap-3">
			<a href="{base}/media/profiles" class="text-sm text-muted hover:text-accent transition-colors">
				← Back to Profiles
			</a>
			{#if freshness}
				<span
					class="text-xs {freshness.state === 'fresh'
						? 'text-green-400'
						: freshness.state === 'stale'
							? 'text-amber-400'
							: 'text-red-400'}"
					data-testid="profile-freshness"
				>
					● {freshness.label}
				</span>
			{/if}
		</div>

		<!-- Hero cover + avatar -->
		<div
			class="rounded-xl overflow-hidden relative {profile.cover_url ? 'h-48 md:h-56' : 'h-32 md:h-40'} bg-gradient-to-br from-border to-bg"
			style:background-image={profile.cover_url ? `url(${profile.cover_url})` : 'none'}
			style:background-size="cover"
			style:background-position="center"
		>
			<div class="absolute inset-0" style="background: linear-gradient(transparent 30%, var(--bg) 95%)"></div>
			<div class="absolute bottom-4 left-4 flex items-center gap-4">
				{#if profile.thumbnail_url}
					<img src={profile.thumbnail_url} alt={profile.name} class="w-14 h-14 rounded-full object-cover border-2 border-border" loading="lazy" />
				{:else}
					<div class="w-14 h-14 rounded-full bg-accent/20 flex items-center justify-center text-accent font-bold text-xl border-2 border-border">
						{profile.name.charAt(0)}
					</div>
				{/if}
				<div>
					<h1 class="text-xl md:text-2xl font-bold text-text">{profile.name}</h1>
					<div class="flex items-center gap-2 text-sm text-muted">
						{#if provider}
							<span>{provider.icon} {provider.label}</span>
						{/if}
						{#if profile.external_url}
							<span>·</span>
							<a
								href={profile.external_url}
								target="_blank"
								rel="noopener noreferrer"
								class="text-accent hover:underline"
								data-testid="profile-external-link"
							>
								View on {provider?.label ?? 'Platform'} ↗
							</a>
						{/if}
					</div>
					<div class="text-xs text-muted mt-1">
						{itemsCount} tracked {profile.media_type === 'spotify' ? 'tracks' : 'videos'}
					</div>
				</div>
			</div>
		</div>

		<!-- Metric tiles -->
		<div
			class="grid gap-3"
			style="grid-template-columns: repeat({Math.max(1, Math.min(5, (profile.metrics ?? []).length))}, minmax(0, 1fr));"
		>
			{#each (profile.metrics ?? []) as om}
				<div class="panel p-3">
					<StatTile
						value={formatNumber(metricValue(om.key))}
						label="{om.icon} {om.label}"
						flash={!!flashKeys[om.key]}
						testId="profile-metric-{om.key}"
						fontSize="lg"
					/>
				</div>
			{/each}
		</div>

		<!-- Chart section -->
		{#if metricOptions.length > 0}
			<div>
				<h2 class="text-lg font-semibold text-text mb-3">
					{chartLabel} over time
				</h2>
				<div class="flex flex-wrap gap-2 mb-3">
					<SelectDropdown
						options={metricOptions}
						bind:value={selectedMetric}
						testId="profile-chart-metric"
					/>
					<SelectDropdown
						options={rangeOptions}
						bind:value={selectedHours}
						testId="profile-chart-range"
					/>
					<SelectDropdown
						options={viewOptions}
						bind:value={selectedView}
						testId="profile-chart-mode"
					/>
				</div>
				{#if chartLoading}
					<div class="h-64 panel opacity-50 flex items-center justify-center text-muted text-sm">
						Loading chart...
					</div>
				{:else if history.length === 0}
					<div class="h-64 panel flex items-center justify-center text-muted text-sm">
						No history data yet — waiting for the next scheduled poll.
					</div>
				{:else}
					<div class="panel">
						<Chart datasets={chartDatasets} />
					</div>
				{/if}
			</div>
		{/if}

		<!-- Tracked media items -->
		<div>
			<h2 class="text-lg font-semibold text-text mb-3">
				Tracked Media ({itemsCount})
			</h2>
			{#if items.length === 0}
				<EmptyState icon="🎬" title="No media yet" message="No tracked media from this channel/artist in this guild." />
			{:else}
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
					{#each items as item (item.id)}
						<MediaItemCard
							id={item.id}
							title={item.title}
							thumbnailUrl={item.thumbnail_url}
							mediaType={item.media_type ?? profile.media_type}
							publishedAt={item.published_at}
							metrics={item.metrics}
							testId="profile-media-item"
						/>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}
