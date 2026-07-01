import { describe, it, expect } from 'vitest';
import { parseEmojiValue, buildEmojiTag } from './emoji-parser';

describe('parseEmojiValue', () => {
	it('parses empty string', () => {
		expect(parseEmojiValue('')).toEqual([]);
		expect(parseEmojiValue('  ')).toEqual([]);
	});

	it('parses single custom emoji', () => {
		const result = parseEmojiValue('<:stank:123456>');
		expect(result).toEqual([
			{ id: '123456', name: 'stank', type: 'custom', animated: false }
		]);
	});

	it('parses animated custom emoji', () => {
		const result = parseEmojiValue('<a:party:789>');
		expect(result).toEqual([
			{ id: '789', name: 'party', type: 'custom', animated: true }
		]);
	});

	it('parses unicode emoji', () => {
		const result = parseEmojiValue('🔥');
		expect(result).toEqual([
			{ id: null, name: '🔥', type: 'default' }
		]);
	});

	it('parses multiple emojis', () => {
		const result = parseEmojiValue('<:a:1>, 🔥, <a:b:2>');
		expect(result).toEqual([
			{ id: '1', name: 'a', type: 'custom', animated: false },
			{ id: null, name: '🔥', type: 'default' },
			{ id: '2', name: 'b', type: 'custom', animated: true }
		]);
	});

	it('handles whitespace', () => {
		const result = parseEmojiValue('  <:x:1>  ,  🎉  ');
		expect(result).toEqual([
			{ id: '1', name: 'x', type: 'custom', animated: false },
			{ id: null, name: '🎉', type: 'default' }
		]);
	});
});

describe('buildEmojiTag', () => {
	it('builds empty string', () => {
		expect(buildEmojiTag([])).toBe('');
	});

	it('builds single custom emoji', () => {
		const result = buildEmojiTag([
			{ id: '123', name: 'stank', type: 'custom', animated: false }
		]);
		expect(result).toBe('<:stank:123>');
	});

	it('builds animated custom emoji', () => {
		const result = buildEmojiTag([
			{ id: '456', name: 'party', type: 'custom', animated: true }
		]);
		expect(result).toBe('<a:party:456>');
	});

	it('builds unicode emoji', () => {
		const result = buildEmojiTag([
			{ id: null, name: '🔥', type: 'default' }
		]);
		expect(result).toBe('🔥');
	});

	it('builds multiple emojis', () => {
		const result = buildEmojiTag([
			{ id: '1', name: 'a', type: 'custom', animated: false },
			{ id: null, name: '🔥', type: 'default' },
			{ id: '2', name: 'b', type: 'custom', animated: true }
		]);
		expect(result).toBe('<:a:1>, 🔥, <a:b:2>');
	});
});

describe('roundtrip', () => {
	it('parse → build preserves data', () => {
		const original = '<:stank:123>, 🔥, <a:party:456>';
		const parsed = parseEmojiValue(original);
		const rebuilt = buildEmojiTag(parsed);
		expect(rebuilt).toBe(original);
	});
});
