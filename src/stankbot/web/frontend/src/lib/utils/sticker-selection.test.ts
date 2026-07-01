import { describe, it, expect } from 'vitest';
import { filterStickers, filterByValidIds } from './sticker-selection';

describe('filterStickers', () => {
	it('returns all stickers when search is empty', () => {
		const stickers = [
			{ id: '1', name: 'stank_face' },
			{ id: '2', name: 'party_hat' }
		];
		expect(filterStickers(stickers, '')).toEqual(stickers);
		expect(filterStickers(stickers, '  ')).toEqual(stickers);
	});

	it('filters by name (case-insensitive)', () => {
		const stickers = [
			{ id: '1', name: 'stank_face' },
			{ id: '2', name: 'party_hat' },
			{ id: '3', name: 'Stank_Logo' }
		];
		const result = filterStickers(stickers, 'stank');
		expect(result).toEqual([
			{ id: '1', name: 'stank_face' },
			{ id: '3', name: 'Stank_Logo' }
		]);
	});

	it('returns empty array when no matches', () => {
		const stickers = [
			{ id: '1', name: 'stank_face' }
		];
		expect(filterStickers(stickers, 'xyz')).toEqual([]);
	});

	it('handles partial matches', () => {
		const stickers = [
			{ id: '1', name: 'stank_face' },
			{ id: '2', name: 'party_hat' }
		];
		const result = filterStickers(stickers, 'hat');
		expect(result).toEqual([
			{ id: '2', name: 'party_hat' }
		]);
	});
});

describe('filterByValidIds', () => {
	it('returns stickers matching valid IDs', () => {
		const stickers = [
			{ id: '1', name: 'a' },
			{ id: '2', name: 'b' },
			{ id: '3', name: 'c' }
		];
		const result = filterByValidIds(stickers, [1, 3]);
		expect(result).toEqual([
			{ id: '1', name: 'a' },
			{ id: '3', name: 'c' }
		]);
	});

	it('returns empty array when no valid IDs', () => {
		const stickers = [
			{ id: '1', name: 'a' }
		];
		expect(filterByValidIds(stickers, [])).toEqual([]);
	});

	it('handles non-existent IDs', () => {
		const stickers = [
			{ id: '1', name: 'a' }
		];
		expect(filterByValidIds(stickers, [99, 100])).toEqual([]);
	});

	it('handles mixed valid/invalid IDs', () => {
		const stickers = [
			{ id: '1', name: 'a' },
			{ id: '2', name: 'b' }
		];
		const result = filterByValidIds(stickers, [1, 99, 2]);
		expect(result).toEqual([
			{ id: '1', name: 'a' },
			{ id: '2', name: 'b' }
		]);
	});
});
