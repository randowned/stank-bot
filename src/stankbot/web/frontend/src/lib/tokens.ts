// Shared design tokens — single source of truth for Tailwind + runtime JS (Chart.js, inline styles, etc.)
// Keep in sync with tailwind.config.js theme.extend

export const colors = {
	bg: '#0f1115',
	panel: '#181b22',
	surface: '#1e222b',
	border: '#262a33',
	borderHover: '#3a4050',
	text: '#e5e7eb',
	muted: '#9aa4b2',
	accent: '#a47cff',
	accentDim: 'rgba(164,124,255,0.15)',
	gold: '#ffd166',
	danger: '#ff6b6b',
	ok: '#4ade80',
	// chart-specific aliases mapped to semantic tokens
	tooltipBg: '#181b22',
	chartGrid: '#262a33',
	chartText: '#9aa4b2',
} as const;

export const shadows = {
	card: '0 1px 3px rgba(0,0,0,0.3)',
	modal: '0 10px 40px rgba(0,0,0,0.5)',
	glowAccent: '0 0 20px rgba(164,124,255,0.25)',
} as const;

export const chart = {
	// 8-color cycle for multi-series lines — high-contrast, colorblind-friendly-ish
	series: [
		'#3b82f6', // blue
		'#ef4444', // red
		'#22c55e', // green
		'#a855f7', // purple
		'#f97316', // orange
		'#14b8a6', // teal
		'#ec4899', // pink
		'#eab308', // yellow
	],
	backgroundAlpha: '20',
	fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
} as const;

export const spacing = {
	// Tailwind spacing scale additions
	touch: '2.75rem', // 44px minimum touch target
} as const;
