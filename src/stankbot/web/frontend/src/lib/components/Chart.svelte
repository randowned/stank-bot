<script lang="ts" module>
	import ChartJS from 'chart.js/auto';
	import 'chartjs-adapter-date-fns';
	import { chart as chartTokens } from '$lib/tokens';
	ChartJS.defaults.font.family = chartTokens.fontFamily;
</script>

<script lang="ts">
	import { onDestroy } from 'svelte';
	import type { ChartType } from 'chart.js';
	import { colors } from '$lib/tokens';

	interface ChartDataset {
		label: string;
		data: Array<{ x: number; y: number }>;
		borderColor?: string;
		backgroundColor?: string;
		fill?: boolean;
		tension?: number;
		pointRadius?: number;
	}

	interface Props {
		type?: ChartType;
		labels?: string[];
		datasets?: ChartDataset[];
		options?: Record<string, unknown>;
		width?: number;
		height?: number;
	}

	let {
		type = 'line' as ChartType,
		labels,
		datasets,
		options,
		width,
		height
	}: Props = $props();

	let canvasEl: HTMLCanvasElement;
	let chart: ChartJS | undefined;

	const COLORS = chartTokens.series;

	function buildDatasets(input?: ChartDataset[]) {
		if (!input || input.length === 0) return [];
		return input.map((ds, i) => ({
			label: ds.label,
			data: ds.data,
			borderColor: ds.borderColor ?? COLORS[i % COLORS.length],
			backgroundColor: ds.backgroundColor ?? COLORS[i % COLORS.length] + chartTokens.backgroundAlpha,
			fill: ds.fill ?? false,
			tension: ds.tension ?? 0.2,
			pointRadius: ds.pointRadius ?? (ds.data.length > 60 ? 0 : 3),
		}));
	}

	$effect(() => {
		if (!canvasEl) return;

		const data = {
			labels,
			datasets: buildDatasets(datasets),
		};

		const defaultOptions: Record<string, unknown> = {
			responsive: true,
			maintainAspectRatio: false,
			animation: typeof document !== 'undefined' && document.documentElement.classList.contains('e2e')
				? false
				: { duration: 300 },
			interaction: { intersect: false, mode: 'index' },
			plugins: {
				legend: {
					position: 'bottom',
					labels: {
						color: colors.muted,
						font: { size: 11 },
						padding: 16,
						boxWidth: 10,
						boxHeight: 10,
					},
				},
				tooltip: {
					backgroundColor: colors.tooltipBg,
					titleColor: colors.text,
					bodyColor: colors.muted,
					borderColor: colors.border,
					borderWidth: 1,
					padding: 10,
				},
			},
			scales: {
				x: {
					ticks: { color: colors.muted, font: { size: 10 } },
					grid: { display: false },
				},
				y: {
					ticks: { color: colors.muted, font: { size: 10 } },
					grid: { color: colors.chartGrid, drawBorder: false },
				},
			},
		};

		const merged = { ...defaultOptions, ...(options ?? {}) };

		if (chart) {
			chart.data = data as never;
			chart.options = merged as never;
			chart.update('none');
			return;
		}
		chart = new ChartJS(canvasEl, { type, data: data as never, options: merged as never });
	});

	onDestroy(() => {
		chart?.destroy();
	});
</script>

<div class="relative" style="width:{width ? width + 'px' : '100%'}; height:{height ? height + 'px' : '300px'}">
	<canvas bind:this={canvasEl}></canvas>
</div>
