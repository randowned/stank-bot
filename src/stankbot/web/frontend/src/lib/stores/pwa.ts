import { writable } from 'svelte/store';

/**
 * PWA install state.
 *
 * Listens for `beforeinstallprompt` (Chrome/Edge/Samsung) to surface
 * an install toast. If the user dismisses the toast, the option moves
 * to the user menu instead. Once the app is running standalone or was
 * installed via `beforeinstallprompt`, everything hides.
 *
 * Dismissal is persisted in localStorage so the toast only shows once
 * per browser profile.
 */

const STORAGE_KEY = 'stankbot-pwa-dismissed';

interface BeforeInstallPromptEvent extends Event {
	readonly platforms: string[];
	readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
	prompt(): Promise<void>;
}

export interface PwaState {
	/** Whether to show the install toast banner at top-middle */
	showInstallToast: boolean;
	/** User dismissed the toast — show menu item instead */
	dismissedInstall: boolean;
	/** App is already running in standalone/PWA mode */
	isStandalone: boolean;
	/** App was installed (native prompt accepted or appinstalled event) */
	isInstalled: boolean;
}

/** The deferred BeforeInstallPromptEvent, kept outside the writable
 *  because Event objects aren't serializable store values. */
let deferredBeforeInstallPrompt: BeforeInstallPromptEvent | null = null;

function createPwaStore() {
	const isStandalone =
		typeof window !== 'undefined' &&
		typeof window.matchMedia === 'function' &&
		(window.matchMedia('(display-mode: standalone)').matches ||
			( navigator as typeof navigator & { standalone?: boolean }).standalone === true);

	const wasDismissed =
		typeof window !== 'undefined' &&
		typeof localStorage !== 'undefined' &&
		localStorage.getItem(STORAGE_KEY) === 'true';

	const { subscribe, update } = writable<PwaState>({
		showInstallToast: false,
		dismissedInstall: wasDismissed,
		isStandalone,
		isInstalled: isStandalone,
	});

	if (typeof window !== 'undefined') {
		window.addEventListener('beforeinstallprompt', (e: Event) => {
			e.preventDefault();
			deferredBeforeInstallPrompt = e as BeforeInstallPromptEvent;
			update((s) => ({
				...s,
				// Only show toast if user hasn't permanently dismissed it
				showInstallToast: !s.dismissedInstall && !s.isStandalone && !s.isInstalled,
			}));
		});

		window.addEventListener('appinstalled', () => {
			deferredBeforeInstallPrompt = null;
			localStorage.removeItem(STORAGE_KEY);
			update((s) => ({
				...s,
				isInstalled: true,
				showInstallToast: false,
			}));
		});
	}

	return {
		subscribe,
		/** Trigger the native install prompt. */
		triggerInstall() {
			const prompt = deferredBeforeInstallPrompt;
			if (!prompt) return;
			prompt.prompt();
			prompt.userChoice.then((choice) => {
				if (choice.outcome === 'accepted') {
					deferredBeforeInstallPrompt = null;
					localStorage.removeItem(STORAGE_KEY);
					update((s) => ({
						...s,
						isInstalled: true,
						showInstallToast: false,
					}));
				}
			});
			update((s) => ({
				...s,
				showInstallToast: false,
				dismissedInstall: false,
			}));
		},
		/** Dismiss the install toast — show menu item instead.
		 *  Persisted in localStorage so it only fires once. */
		dismissInstallToast() {
			localStorage.setItem(STORAGE_KEY, 'true');
			update((s) => ({
				...s,
				showInstallToast: false,
				dismissedInstall: true,
			}));
		},
	};
}

export const pwaState = createPwaStore();
