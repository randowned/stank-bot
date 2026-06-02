<script lang="ts">
	import { base } from '$app/paths';
	import { formatNumber, formatFreshness } from '$lib/format';
	import type { MediaItem, MediaOwner, ProfileDetail, ProviderDef, MetricSnapshot } from '$lib/types';
	import { providersByType, loadProviders, ownerMetricUpdates } from '$lib/stores';
	import { apiFetch } from '$lib/api';
	import StatTile from '$lib/components/StatTile.svelte';
	import Chart from '$lib/components/Chart.svelte';
	import Select from '$lib/components/Select.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import MediaItemCard from '$lib/components/MediaItemCard.svelte';
	import Container from '$lib/components/Container.svelte';

	let { data } = $props();

	const profileId = $derived(data.profileId as number);
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

	const providerIntervalMs = $derived((provider?.interval_minutes ?? 60) * 60_000);

	const _AGG_BUCKET_MS: Record<string, number> = {
		minutely: 60_000,
		'5min': 300_000,
		'15min': 900_000,
		'30min': 1_800_000,
		hourly: 3_600_000,
		daily: 86_400_000,
		weekly: 604_800_000,
		monthly: 2_592_000_000,
	};

	const aggregationOptions = $derived.by(() => {
		const rangeHours = selectedHours;
		const minMs = providerIntervalMs;
		const all: Array<{ value: string; label: string; icon: string }> = [
			{ value: 'auto', label: 'Auto', icon: '🤖' },
			{ value: 'minutely', label: 'Min', icon: '🕐' },
			{ value: '5min', label: '5 Min', icon: '🕐' },
			{ value: '15min', label: '15 Min', icon: '🕐' },
			{ value: '30min', label: '30 Min', icon: '🕐' },
			{ value: 'hourly', label: 'Hourly', icon: '⏱️' },
			{ value: 'daily', label: 'Daily', icon: '📅' },
			{ value: 'weekly', label: 'Weekly', icon: '📆' },
			{ value: 'monthly', label: 'Monthly', icon: '🗓️' },
		];
		const bucketMs: Record<string, number> = _AGG_BUCKET_MS;
		return all.filter(
			(o) =>
				o.value === 'auto' ||
				((bucketMs[o.value] ?? 0) * 2 < rangeHours * 3_600_000 &&
					(bucketMs[o.value] ?? 0) >= minMs)
		);
	});

	const serverAggregations = new Set(['5min', '15min', '30min', 'hourly', 'daily', 'weekly', 'monthly']);

	const resolvedAggregation = $derived.by(() => {
		if (selectedAggregation !== 'auto') return selectedAggregation;
		const bms = selectedHours * 3_600_000;
		const idealBucketMs = bms / 24;
		const buckets = [60_000, 300_000, 900_000, 1_800_000, 3_600_000, 86_400_000, 604_800_000, 2_592_000_000];
		const eligible = buckets.filter((b) => b >= providerIntervalMs && b * 2 < bms);
		const found = eligible.find((b) => b >= idealBucketMs) ?? eligible[eligible.length - 1] ?? null;
		if (found === null) return null;
		return Object.entries(_AGG_BUCKET_MS).find(
			([k, ms]) => ms === found && serverAggregations.has(k)
		)?.[0] ?? null;
	});

	const useServerAggregation = $derived(serverAggregations.has(resolvedAggregation ?? ''));

	let selectedMetric = $state('subscriber_count');
	let selectedHours = $state<number>(24);
	let selectedView = $state('total');
	let selectedAggregation = $state('auto');
	let compareMode = $state(false);
	let compareMetric = $state('');

	$effect(() => {
		if (metricOptions.length > 0 && !metricOptions.find((o) => o.value === selectedMetric)) {
			selectedMetric = metricOptions[0].value;
		}
		if (metricOptions.length > 1 && !compareMetric) {
			compareMetric = metricOptions.find((o) => o.value !== selectedMetric)?.value ?? metricOptions[0].value;
		}
	});

	$effect(() => {
		if (metricOptions.length > 0 && !metricOptions.find((o) => o.value === selectedMetric)) {
			selectedMetric = metricOptions[0].value;
		}
		if (metricOptions.length > 1 && !compareMetric) {
			compareMetric = metricOptions.find((o) => o.value !== selectedMetric)?.value ?? metricOptions[0].value;
		}
	});

	let history = $state<MetricSnapshot[]>([]);
	let compareHistory = $state<MetricSnapshot[]>([]);
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
			if (useServerAggregation && resolvedAggregation) {
				queryStr += `&aggregation=${resolvedAggregation}`;
			}
			const res = await apiFetch<{ history: MetricSnapshot[] }>(
				`/api/media/profile/${profile.id}/history?${queryStr}`
			);
			history = res.history ?? [];
		} catch {
			history = [];
		}

		if (compareMode && compareMetric && compareMetric !== selectedMetric) {
			try {
				const h = selectedHours;
				let q = `metric=${encodeURIComponent(compareMetric)}`;
				if (h > 48) {
					q += `&days=${Math.round(h / 24)}`;
				} else {
					q += `&hours=${h}`;
				}
				if (selectedView === 'delta') q += '&mode=delta';
				if (useServerAggregation && resolvedAggregation) {
					q += `&aggregation=${resolvedAggregation}`;
				}
				const res = await apiFetch<{ history: MetricSnapshot[] }>(
					`/api/media/profile/${profile.id}/history?${q}`
				);
				compareHistory = res.history ?? [];
			} catch {
				compareHistory = [];
			}
		} else {
			compareHistory = [];
		}

		chartLoading = false;
	}

	$effect(() => {
		void selectedMetric;
		void selectedHours;
		void selectedView;
		void selectedAggregation;
		void compareMode;
		void compareMetric;

		if (!aggregationOptions.some((o) => o.value === selectedAggregation)) {
			selectedAggregation = 'auto';
			return;
		}
		if (profile) {
			void loadChartData();
		}
	});

	let chartDatasets = $derived.by(() => {
		const datasets: Array<{ label: string; data: { x: number; y: number }[] }> = [];
		if (history.length > 0) {
			datasets.push({
				label: profile?.metrics?.find((m) => m.key === selectedMetric)?.label ?? selectedMetric,
				data: history.map((p) => ({
					x: new Date(p.fetched_at).getTime(),
					y: p.value
				}))
			});
		}
		if (compareMode && compareHistory.length > 0 && compareMetric && compareMetric !== selectedMetric) {
			datasets.push({
				label: profile?.metrics?.find((m) => m.key === compareMetric)?.label ?? compareMetric,
				data: compareHistory.map((p) => ({
					x: new Date(p.fetched_at).getTime(),
					y: p.value
				}))
			});
		}
		return datasets;
	});

	const chartLabel = $derived(
		profile?.metrics?.find((m) => m.key === selectedMetric)?.label ?? selectedMetric
	);

	const sparseHint = $derived(history.length > 0 && history.length < 2);

	const chartMinUnit = $derived.by<'minute' | 'hour' | 'day' | 'week' | 'month' | undefined>(() => {
		const bucketMs = _AGG_BUCKET_MS[resolvedAggregation ?? ''] ?? providerIntervalMs;
		if (bucketMs < 3_600_000) return 'minute';
		if (bucketMs < 86_400_000) return 'hour';
		if (bucketMs < 604_800_000) return 'day';
		if (bucketMs < 2_592_000_000) return 'week';
		return 'month';
	});

	function timeDisplayFormats(): Record<string, string> {
		return {
			millisecond: 'HH:mm:ss.SSS',
			second: 'HH:mm:ss',
			minute: 'HH:mm',
			hour: selectedHours <= 48 ? 'HH:mm' : 'MMM d HH:mm',
			day: 'MMM d',
			week: 'MMM d',
			month: 'MMM yyyy',
			quarter: 'MMM yyyy',
			year: 'yyyy'
		};
	}

	function buildChartOptions(): Record<string, unknown> {
		const timeScaleOpts: Record<string, unknown> = {
			tooltipFormat: 'MMM d, yyyy HH:mm',
			displayFormats: timeDisplayFormats()
		};
		if (chartMinUnit) {
			timeScaleOpts.minUnit = chartMinUnit;
		}
		return {
			datasets: { line: { spanGaps: true } },
			scales: {
				x: {
					type: 'time',
					time: timeScaleOpts,
					ticks: { maxTicksLimit: 8, color: '#9aa4b2', font: { size: 10 }, source: 'auto' },
					grid: { display: false }
				},
				y: {
					title: { display: false },
					beginAtZero: false,
					ticks: { color: '#9aa4b2', font: { size: 10 } },
					grid: { color: '#262a33', drawBorder: false }
				}
			},
			plugins: {
				legend: {
					display: compareMode
				},
				tooltip: {
					backgroundColor: '#181b22',
					titleColor: '#e5e7eb',
					bodyColor: '#9aa4b2',
					borderColor: '#262a33',
					borderWidth: 1,
					padding: 10,
				},
			}
		};
	}
</script>

{#key profileId}
{#if !profile}
	<ErrorState title="Profile not found" message="This channel or artist doesn't exist or has no tracked media in this guild." />
{:else}
	<Container size="xl" class="p-4 space-y-4">
		<!-- Back link + freshness -->
		<div class="flex items-center justify-between">
			<a href="{base}/media/profiles" class="text-sm text-muted hover:text-accent transition-colors">
				← Back to Profiles
			</a>
			{#if freshness}
				<span
					class="text-xs px-2 py-0.5 rounded-full border {freshness.state === 'fresh'
						? 'border-green-700 text-green-400'
						: freshness.state === 'stale'
							? 'border-amber-700 text-amber-400'
							: 'border-red-700 text-red-400'}"
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
			{#if !profile.cover_url && provider}
				<div class="absolute inset-0 flex items-center justify-center text-5xl opacity-20">
					{provider.icon}
				</div>
			{/if}
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
					{compareMode ? 'Comparing metrics' : `${chartLabel} over time`}
				</h2>
				<div class="flex flex-wrap gap-2 mb-3">
					<Select
						options={metricOptions}
						bind:value={selectedMetric}
						testId="profile-chart-metric"
					/>
					<Select
						options={metricOptions}
						bind:value={compareMetric}
						testId="profile-chart-compare-metric"
						class={compareMode ? '' : 'hidden'}
					/>
					<Select
						options={rangeOptions}
						bind:value={selectedHours}
						testId="profile-chart-range"
					/>
					<Select
						options={aggregationOptions}
						bind:value={selectedAggregation}
						testId="profile-chart-resolution"
						native={true}
					/>
					<Select
						options={viewOptions}
						bind:value={selectedView}
						testId="profile-chart-mode"
					/>
					<button
						type="button"
						class="inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1 text-sm {compareMode
							? 'bg-accent text-[#1a1425] hover:opacity-90'
							: 'bg-border text-text hover:bg-border/80'}"
						class:hidden={metricOptions.length <= 1}
						onclick={() => { compareMode = !compareMode; }}
						data-testid="profile-chart-compare-toggle"
					>
						{compareMode ? 'Single' : 'Compare'}
					</button>
				</div>
				{#if chartLoading}
					<div class="h-64 panel opacity-50 flex items-center justify-center text-muted text-sm">
						Loading chart...
					</div>
				{:else if chartDatasets.length === 0}
					<div class="h-64 panel flex items-center justify-center text-muted text-sm">
						No history data yet — waiting for the next scheduled poll.
					</div>
				{:else}
					<div class="panel" data-testid="profile-chart">
						<Chart datasets={chartDatasets} options={buildChartOptions()} />
					</div>
					{#if sparseHint}
						<div class="text-xs text-muted mt-2">
							Only 1 data point yet — refresh again or wait for the next scheduled poll.
						</div>
					{/if}
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
	</Container>
{/if}
{/key}
