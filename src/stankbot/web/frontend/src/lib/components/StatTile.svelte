<script lang="ts">
	interface Props {
		value: string;
		label: string;
		sublabel?: string;
		color?: string;
		flash?: boolean;
		testId?: string;
		valueTestId?: string;
		title?: string;
		fontSize?: string;
	}

	let { value, label, sublabel, color = 'text-accent', flash = false, testId, valueTestId, title, fontSize = 'xl' }: Props = $props();
</script>

<div class="text-center cursor-default" {title} data-testid={testId}>
	<div class={`text-${fontSize} font-bold ${color} ${flash ? 'row-flash' : ''}`} data-testid={valueTestId}>{value}</div>
	{#if sublabel}
		<div class="text-[10px] text-muted/70 -mt-0.5 mb-0.5">{sublabel}</div>
	{/if}
	<div class="text-xs text-muted uppercase">{label}</div>
</div>
