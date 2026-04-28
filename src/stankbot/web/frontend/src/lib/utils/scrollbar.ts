/**
 * Detects if `overflow: overlay` is supported (Chromium only, non-standard).
 * Can't use @supports for this since it's not a standard CSS value.
 */
function supportsOverflowOverlay(): boolean {
	const test = document.createElement('div');
	test.style.overflow = 'overlay';
	document.body.appendChild(test);
	const supported = window.getComputedStyle(test).overflow === 'overlay';
	document.body.removeChild(test);
	return supported;
}

/**
 * Detects if a custom JS scrollbar is needed.
 * Only Internet Explorer needs this — every other browser supports either
 * `scrollbar-width` (Firefox 64+, Chrome 134+) or `::-webkit-scrollbar`
 * (Chrome 2+, Safari 5+, Edge 79+, Opera 15+) for CSS scrollbar styling.
 */
function shouldUseCustomScrollbar(): boolean {
	const ua = navigator.userAgent;
	return ua.includes('MSIE ') || ua.includes('Trident/');
}

/**
 * Shows the scrollbar while scrolling, fades it out after a brief pause.
 * Works with the CSS `.scrolling` class on `<html>`.
 */
function enableScrollDrivenVisibility(): () => void {
	const html = document.documentElement;
	let timeout: ReturnType<typeof setTimeout> | null = null;
	const SCROLL_DEBOUNCE_MS = 600;

	function onScroll(): void {
		html.classList.add('scrolling');
		if (timeout) clearTimeout(timeout);
		timeout = setTimeout(() => {
			html.classList.remove('scrolling');
			timeout = null;
		}, SCROLL_DEBOUNCE_MS);
	}

	window.addEventListener('scroll', onScroll, { passive: true });
	return () => {
		window.removeEventListener('scroll', onScroll);
		if (timeout) {
			clearTimeout(timeout);
			timeout = null;
		}
		html.classList.remove('scrolling');
	};
}

/**
 * Initializes OverlayScrollbars as a fully custom overlay scrollbar.
 * Loaded lazily — only for browsers that can't style native scrollbars.
 */
async function initCustomScrollbar(): Promise<() => void> {
	await import('overlayscrollbars/overlayscrollbars.css');
	const { OverlayScrollbars } = await import('overlayscrollbars');

	const instance = OverlayScrollbars({
		target: document.body,
		cancel: { body: false },
	}, {
		scrollbars: {
			visibility: 'auto',
			autoHide: 'scroll',
			autoHideDelay: 600,
			theme: 'os-theme-stank',
		},
		overflow: {
			x: 'hidden',
			y: 'scroll',
		},
	});

	return () => {
		instance.destroy();
	};
}

/**
 * Enhances the page scrollbar to behave like mobile:
 * - Modern browsers: thin (4px), overlay, auto-hides after scroll stops
 * - Legacy browsers (IE): fully custom overlay scrollbar via OverlayScrollbars
 *
 * Call once on mount. Returns a cleanup function for teardown.
 */
export function enhancePageScrollbar(): () => void {
	if (typeof window === 'undefined') return () => {};

	const cleanups: (() => void)[] = [];
	let osCleanup: (() => void) | null = null;
	let destroyed = false;

	if (supportsOverflowOverlay()) {
		document.body.style.overflowY = 'overlay';
	}

	if (!shouldUseCustomScrollbar()) {
		cleanups.push(enableScrollDrivenVisibility());
	} else {
		initCustomScrollbar().then((cleanup) => {
			if (destroyed) {
				cleanup();
			} else {
				osCleanup = cleanup;
			}
		});
	}

	return () => {
		destroyed = true;
		for (const fn of cleanups) fn();
		if (osCleanup) osCleanup();
	};
}
