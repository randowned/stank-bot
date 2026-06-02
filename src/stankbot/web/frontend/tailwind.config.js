/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			colors: {
				bg: '#0f1115',
				panel: '#181b22',
				surface: '#1e222b',
				border: '#262a33',
				'border-hover': '#3a4050',
				text: '#e5e7eb',
				muted: '#9aa4b2',
				accent: '#a47cff',
				'accent-dim': 'rgba(164,124,255,0.15)',
				gold: '#ffd166',
				danger: '#ff6b6b',
				ok: '#4ade80'
			},
			fontFamily: {
				sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif']
			},
			boxShadow: {
				card: '0 1px 3px rgba(0,0,0,0.3)',
				modal: '0 10px 40px rgba(0,0,0,0.5)',
				'glow-accent': '0 0 20px rgba(164,124,255,0.25)',
			},
			fontSize: {
				// Mobile-first semantic type scale (tight line-height for headings)
				'display-xs': ['1.25rem', { lineHeight: '1.4', fontWeight: '700' }],   // 20px
				'display-sm': ['1.5rem', { lineHeight: '1.3', fontWeight: '700' }],    // 24px
				'display-md': ['1.875rem', { lineHeight: '1.25', fontWeight: '700' }], // 30px
				'display-lg': ['2.25rem', { lineHeight: '1.2', fontWeight: '700' }],   // 36px
				'body-xs': ['0.625rem', { lineHeight: '1.5' }], // 10px
				'body-sm': ['0.75rem', { lineHeight: '1.5' }],  // 12px
				'body-md': ['0.875rem', { lineHeight: '1.5' }], // 14px
				'body-lg': ['1rem', { lineHeight: '1.5' }],     // 16px
			},
			spacing: {
				11: '2.75rem', // 44px touch target
			}
		}
	},
	plugins: []
};
