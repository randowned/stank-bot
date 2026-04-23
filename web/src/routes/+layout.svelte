<script lang="ts">
	import '../app.css';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import {
		user,
		guildId,
		guilds,
		connectionStatus,
		toasts,
		removeToast,
		addToast,
		lastWsEvent
	} from '$lib/stores';
	import type { WsEvent } from '$lib/stores';
	import { onMount } from 'svelte';
	import { connect, disconnect } from '$lib/ws';
	import type { User, GuildInfo } from '$lib/types';
	import UserMenu from '$lib/components/UserMenu.svelte';

	let { data, children } = $props();

	const userData = $derived(data.user as User | null);
	const guildIdData = $derived((data.guild_id as string | null) ?? null);
	const guildList = $derived((data.guilds as GuildInfo[] | undefined) ?? []);
	const isAdmin = $derived(Boolean(data.is_admin));
	const currentPath = $derived($page.url.pathname);
	const onAdminRoute = $derived(currentPath.startsWith(base + '/admin'));

	$effect(() => {
		user.set(userData);
		guildId.set(guildIdData);
		guilds.set(guildList);
	});

	$effect(() => {
		const event = $lastWsEvent;
		if (!event) return;
		handleWsEvent(event);
	});

	onMount(() => {
		connect();
		return () => {
			disconnect();
		};
	});

	function handleWsEvent(event: WsEvent): void {
		switch (event.kind) {
			case 'connected':
				addToast('Connected to live updates', 'success');
				break;
			case 'reconnect-failed':
				addToast('Unable to reconnect. Please refresh.', 'error', 0);
				break;
			case 'error':
				addToast(event.message, 'error');
				break;
			case 'achievement':
				addToast(`Achievement unlocked: ${event.badge.name}!`, 'success');
				break;
			case 'session':
				addToast(
					event.action === 'start'
						? `Session ${event.sessionId} started`
						: `Session ${event.sessionId} ended`,
					'info'
				);
				break;
			case 'disconnected':
				break;
		}
	}

	const navItems = $derived([
		{ href: base + '/', label: 'Board', icon: '🏠' },
		{ href: base + '/chains', label: 'Chains', icon: '⛓️' },
		{ href: base + '/sessions', label: 'Sessions', icon: '📜' }
	]);

	const adminItems = $derived([
		{ href: base + '/admin/settings', label: 'Settings', icon: '⚙️' },
		{ href: base + '/admin/altar', label: 'Altar', icon: '🗿' },
		{ href: base + '/admin/templates', label: 'Templates', icon: '📝' }
	]);

	void browser;
</script>

<div class="min-h-screen flex flex-col">
	{#if data.env === 'dev'}
		<div class="bg-gold text-bg text-xs px-2 py-1 text-center font-bold">
			DEV MODE — Mock Discord / Mock Auth Active
		</div>
	{/if}

	<!-- Header -->
	<header class="sticky top-0 z-40 bg-panel border-b border-border">
		<div class="flex items-center justify-between px-4 py-3 gap-3">
			<a href={base} class="flex items-center gap-2 shrink-0">
				<img src="/static/Stank.gif" alt="Stank" class="w-6 h-6" />
				<span class="font-semibold text-text">StankBot</span>
			</a>

			<div class="flex items-center gap-3 shrink-0">
				{#if $connectionStatus === 'connected'}
					<span
						class="w-2 h-2 rounded-full bg-ok animate-pulse"
						title="Live"
						data-testid="connection-dot"
					></span>
				{:else}
					<span
						class="w-2 h-2 rounded-full bg-muted"
						title="Offline"
						data-testid="connection-dot"
					></span>
				{/if}

				{#if $user}
					<UserMenu
						user={$user}
						guilds={guildList}
						activeGuildId={guildIdData}
						{isAdmin}
						onerror={(msg) => addToast(msg, 'error')}
					/>
				{:else}
					<a href="/auth/login" class="text-sm text-muted hover:text-text">Login</a>
				{/if}
			</div>
		</div>

		<!-- Navigation -->
		<nav class="flex gap-1 px-4 pb-3 overflow-x-auto scrollbar-thin">
			{#each navItems as item}
				<a
					href={item.href}
					class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors
						{currentPath === item.href ? 'bg-accent text-[#1a1425]' : 'text-muted hover:text-text'}"
				>
					<span>{item.icon}</span>
					<span class="whitespace-nowrap">{item.label}</span>
				</a>
			{/each}

			{#if $user}
				<a
					href="{base}/player/{$user.id}"
					class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors
						{currentPath === `${base}/player/${$user.id}` ? 'bg-accent text-[#1a1425]' : 'text-muted hover:text-text'}"
				>
					<span>👤</span>
					<span class="whitespace-nowrap">Me</span>
				</a>
			{/if}

			{#if onAdminRoute && isAdmin}
				<div class="w-px h-6 bg-border mx-1"></div>
				{#each adminItems as item}
					<a
						href={item.href}
						class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors
							{currentPath === item.href ? 'bg-accent text-[#1a1425]' : 'text-muted hover:text-text'}"
					>
						<span>{item.icon}</span>
						<span class="whitespace-nowrap">{item.label}</span>
					</a>
				{/each}
			{/if}
		</nav>
	</header>

	<!-- Main Content -->
	<main class="flex-1">
		{@render children()}
	</main>

	<!-- Toasts -->
	{#if $toasts.length > 0}
		<div
			class="fixed bottom-20 left-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
		>
			{#each $toasts as toast (toast.id)}
				<div
					class="pointer-events-auto px-4 py-3 rounded-lg shadow-lg backdrop-blur-md
						{toast.type === 'success' ? 'bg-ok/90 text-bg' : ''}
						{toast.type === 'error' ? 'bg-danger/90 text-white' : ''}
						{toast.type === 'warning' ? 'bg-gold/90 text-bg' : ''}
						{toast.type === 'info' ? 'bg-panel/90 text-text' : ''}"
					role="alert"
				>
					<div class="flex items-center justify-between gap-2">
						<span>{toast.message}</span>
						<button onclick={() => removeToast(toast.id)} class="text-lg">&times;</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
