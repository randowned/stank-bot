<!-- Welcome / Landing Page for unauthenticated users -->
<div class="relative min-h-[calc(100vh-57px)] flex items-center justify-center overflow-hidden">
	<div
		class="absolute inset-0 bg-cover bg-center bg-no-repeat"
		style="background-image: url('/background.webp');"
	></div>
	<div class="absolute inset-0 bg-gradient-to-b from-bg/80 via-bg/60 to-bg/90"></div>
	<div class="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(164,124,255,0.08)_0%,transparent_70%)]"></div>

	<div class="relative z-10 flex flex-col items-center text-center px-6 max-w-lg">
		<div class="mb-6 relative">
			<div class="absolute inset-0 rounded-full bg-accent/20 blur-xl animate-pulse"></div>
			<img
				src="/stank.webp"
				alt="Stank"
				class="w-20 h-20 relative drop-shadow-[0_0_20px_rgba(164,124,255,0.4)]"
			/>
		</div>

		<h1 class="text-3xl sm:text-4xl font-bold text-text mb-2 tracking-tight">
			MAPHRA Discord community
		</h1>
		<p class="text-accent font-semibold text-lg sm:text-xl mb-4 tracking-wide uppercase">
			#altar bot
		</p>

		<p class="text-muted text-sm sm:text-base mb-8 max-w-sm leading-relaxed">
			Build chains. Earn points. Rise on the leaderboard.
			<br />
			<span class="text-text/60">Stank responsibly, friends.</span>
			<br />
			<span class="mt-3 text-xs text-muted/50 italic">with love, StankBot and crew</span>
		</p>

		<a
			href="/auth/login"
			class="group relative inline-flex items-center gap-3 px-6 py-3 rounded-lg font-semibold text-white transition-all duration-200
				bg-[#5865F2] hover:bg-[#4752C4] hover:shadow-[0_0_24px_rgba(88,101,242,0.35)] active:scale-[0.98]"
		>
			<svg class="w-5 h-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
				<path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z" />
			</svg>
			Continue with Discord
			<span class="absolute inset-0 rounded-lg ring-1 ring-white/10 group-hover:ring-white/20 transition-colors"></span>
		</a>

		<p class="mt-10 text-xs text-muted/50">
			Sign in with your Discord account to access the live stank leaderboard, track your points, and see how you stack up against other stankers in the MAPHRA community.
		</p>
	</div>
</div>
