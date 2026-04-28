import { writable, type Writable } from 'svelte/store';
import type { BoardState } from '$lib/types';

export const boardState: Writable<BoardState | null> = writable(null);
