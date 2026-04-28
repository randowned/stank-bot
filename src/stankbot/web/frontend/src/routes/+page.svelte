<script lang="ts">
	import WelcomePage from '$lib/components/WelcomePage.svelte';
	import Dashboard from '$lib/components/Dashboard.svelte';

	let { data } = $props();

	const isLoggedIn = $derived(Boolean(data.user));
</script>

{#if !isLoggedIn}
	<WelcomePage />
{:else}
	<Dashboard {data} />
{/if}
