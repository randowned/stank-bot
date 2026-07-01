import { describe, it, expect } from 'vitest';
import { providerBrandBorder, providerBrandBadge } from './media-utils';

describe('providerBrandBorder', () => {
	it('returns YouTube border classes', () => {
		expect(providerBrandBorder('youtube')).toBe('border-l-[3px] border-l-[#ff0000]/70');
	});

	it('returns Spotify border classes', () => {
		expect(providerBrandBorder('spotify')).toBe('border-l-[3px] border-l-[#1db954]/70');
	});

	it('returns empty string for unknown provider', () => {
		expect(providerBrandBorder('twitch')).toBe('');
		expect(providerBrandBorder('')).toBe('');
	});
});

describe('providerBrandBadge', () => {
	it('returns YouTube badge classes', () => {
		expect(providerBrandBadge('youtube')).toBe('bg-[#ff0000]/15 text-[#ff0000]');
	});

	it('returns Spotify badge classes', () => {
		expect(providerBrandBadge('spotify')).toBe('bg-[#1db954]/15 text-[#1db954]');
	});

	it('returns default badge classes for unknown provider', () => {
		expect(providerBrandBadge('twitch')).toBe('bg-border text-muted');
		expect(providerBrandBadge('')).toBe('bg-border text-muted');
	});
});
