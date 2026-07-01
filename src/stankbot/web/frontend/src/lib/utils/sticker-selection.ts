export function filterStickers<T extends { name: string }>(
	stickers: T[],
	search: string
): T[] {
	if (!search.trim()) return stickers;
	const query = search.toLowerCase();
	return stickers.filter(s => s.name.toLowerCase().includes(query));
}

export function filterByValidIds<T extends { id: string }>(
	stickers: T[],
	validIds: number[]
): T[] {
	const idSet = new Set(validIds.map(String));
	return stickers.filter(s => idSet.has(s.id));
}
