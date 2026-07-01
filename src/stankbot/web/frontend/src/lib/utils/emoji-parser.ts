export interface ParsedEmoji {
	id: string | null;
	name: string;
	type: 'custom' | 'default';
	animated?: boolean;
}

export function parseEmojiValue(raw: string): ParsedEmoji[] {
	if (!raw.trim()) return [];
	const parts = raw.split(',').map(p => p.trim()).filter(Boolean);
	const results: ParsedEmoji[] = [];
	for (const p of parts) {
		const match = p.match(/^<(a?):([^:]+):(\d+)>$/);
		if (match) {
			results.push({
				id: match[3],
				name: match[2],
				type: 'custom',
				animated: match[1] === 'a'
			});
		} else {
			results.push({
				id: null,
				name: p,
				type: 'default'
			});
		}
	}
	return results;
}

export function buildEmojiTag(emojis: ParsedEmoji[]): string {
	const parts: string[] = [];
	for (const e of emojis) {
		if (e.type === 'custom' && e.id) {
			const prefix = e.animated ? 'a' : '';
			parts.push(`<${prefix}:${e.name}:${e.id}>`);
		} else {
			parts.push(e.name);
		}
	}
	return parts.join(', ');
}
