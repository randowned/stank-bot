import { writable, type Writable } from 'svelte/store';
import type { ConnectionStatus } from '$lib/types';

export const connectionStatus: Writable<ConnectionStatus> = writable('disconnected');
/** @internal — written by ws.ts, not currently read by UI */
export const wsLatency: Writable<number> = writable(0);
