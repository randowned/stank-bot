<script lang="ts">
	interface Props {
		value?: string | number;
		type?: 'text' | 'number' | 'email' | 'password' | 'url' | 'search';
		placeholder?: string;
		disabled?: boolean;
		readonly?: boolean;
		name?: string;
		id?: string;
		min?: number;
		max?: number;
		step?: number;
		autocomplete?: HTMLInputElement['autocomplete'];
		class?: string;
		oninput?: (e: Event) => void;
		onchange?: (e: Event) => void;
		error?: string;
	}

	let {
		value = $bindable(''),
		type = 'text',
		placeholder,
		disabled = false,
		readonly = false,
		name,
		id,
		min,
		max,
		step,
		autocomplete,
		class: klass = '',
		oninput,
		onchange,
		error
	}: Props = $props();

	const errorCls = $derived(error ? 'border-danger focus:border-danger' : '');
</script>

{#if type === 'number'}
	<input
		type="number"
		bind:value
		{placeholder}
		{disabled}
		{readonly}
		{name}
		{id}
		{min}
		{max}
		{step}
		{autocomplete}
		class="input {errorCls} {klass}"
		{oninput}
		{onchange}
		aria-invalid={error ? 'true' : 'false'}
	/>
{:else}
	<input
		{type}
		bind:value
		{placeholder}
		{disabled}
		{readonly}
		{name}
		{id}
		{autocomplete}
		class="input {errorCls} {klass}"
		{oninput}
		{onchange}
		aria-invalid={error ? 'true' : 'false'}
	/>
{/if}
