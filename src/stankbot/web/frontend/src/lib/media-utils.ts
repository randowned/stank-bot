export function providerBrandBorder(mediaType: string): string {
	if (mediaType === 'youtube') return 'border-l-[3px] border-l-[#ff0000]/70';
	if (mediaType === 'spotify') return 'border-l-[3px] border-l-[#1db954]/70';
	return '';
}

export function providerBrandBadge(mediaType: string): string {
	if (mediaType === 'youtube') return 'bg-[#ff0000]/15 text-[#ff0000]';
	if (mediaType === 'spotify') return 'bg-[#1db954]/15 text-[#1db954]';
	return 'bg-border text-muted';
}
