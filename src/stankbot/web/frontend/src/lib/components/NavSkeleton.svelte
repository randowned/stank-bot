<script lang="ts">
	interface Props {
		isAdminRoute: boolean;
	}

	let { isAdminRoute }: Props = $props();
</script>

{#if isAdminRoute}
	<div class="flex gap-0 min-h-[calc(100vh-57px)]">
		<div class="w-56 shrink-0 bg-panel border-r border-border hidden md:block p-4 space-y-2">
			{#each Array(7) as _}
				<div class="h-9 bg-border/60 animate-pulse rounded-md"></div>
			{/each}
		</div>
		<div class="flex-1 p-4 md:p-6 space-y-4">
			<div class="flex items-center gap-2 mb-4">
				<div class="h-6 bg-border/60 animate-pulse rounded w-8"></div>
				<div>
					<div class="h-5 bg-border/60 animate-pulse rounded w-28 mb-1"></div>
					<div class="h-3 bg-border/60 animate-pulse rounded w-44"></div>
				</div>
			</div>
			<div class="panel">
				<div class="space-y-3">
					{#each Array(6) as _}
						<div class="h-5 bg-border/60 animate-pulse rounded w-full"></div>
					{/each}
				</div>
			</div>
		</div>
	</div>
{:else}
	<div class="p-4 flex flex-col gap-4 max-w-3xl mx-auto">
		<div class="panel">
			<div class="flex items-center gap-2 mb-4">
				<div class="w-6 h-6 bg-border/60 animate-pulse rounded-full"></div>
				<div class="h-5 bg-border/60 animate-pulse rounded w-32"></div>
			</div>
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
				<div class="text-center">
					<div class="h-7 bg-border/60 animate-pulse rounded mx-auto w-16 mb-1"></div>
					<div class="h-3 bg-border/60 animate-pulse rounded mx-auto w-20"></div>
				</div>
				<div class="text-center">
					<div class="h-7 bg-border/60 animate-pulse rounded mx-auto w-16 mb-1"></div>
					<div class="h-3 bg-border/60 animate-pulse rounded mx-auto w-20"></div>
				</div>
				<div class="text-center">
					<div class="h-7 bg-border/60 animate-pulse rounded mx-auto w-16 mb-1"></div>
					<div class="h-3 bg-border/60 animate-pulse rounded mx-auto w-20"></div>
				</div>
				<div class="text-center">
					<div class="h-7 bg-border/60 animate-pulse rounded mx-auto w-16 mb-1"></div>
					<div class="h-3 bg-border/60 animate-pulse rounded mx-auto w-20"></div>
				</div>
			</div>
		</div>

		<div class="grid grid-cols-2 gap-4">
			<div class="panel">
				<div class="h-3 bg-border/60 animate-pulse rounded w-16 mb-3 mx-auto"></div>
				<div class="h-4 bg-border/60 animate-pulse rounded w-24 mx-auto mb-2"></div>
				<div class="h-3 bg-border/60 animate-pulse rounded w-12 mx-auto"></div>
			</div>
			<div class="panel">
				<div class="h-3 bg-border/60 animate-pulse rounded w-16 mb-3 mx-auto"></div>
				<div class="h-4 bg-border/60 animate-pulse rounded w-24 mx-auto mb-2"></div>
				<div class="h-3 bg-border/60 animate-pulse rounded w-12 mx-auto"></div>
			</div>
		</div>

		<div class="panel">
			<div class="flex items-center justify-between mb-3">
				<div class="h-5 bg-border/60 animate-pulse rounded w-24"></div>
			</div>
			<div class="space-y-3">
				{#each Array(5) as _}
					<div class="flex items-center gap-3">
						<div class="w-8 h-8 bg-border/60 animate-pulse rounded-full shrink-0"></div>
						<div class="flex-1">
							<div class="h-4 bg-border/60 animate-pulse rounded w-24 mb-2"></div>
							<div class="h-3 bg-border/60 animate-pulse rounded w-16"></div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
{/if}
