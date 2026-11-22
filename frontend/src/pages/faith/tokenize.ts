export interface Token {
	raw: string;
	kind: "word" | "verse" | "other";
	/** Position among the words only, as record_mistake counts them. */
	wordIndex: number;
	firstLetter: string;
}

/** A letter without its accents, so "e" types "é". */
export function baseLetter(letter: string): string {
	return letter.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/** Split a passage on spaces. A word is any token with a letter, in any alphabet; a bare number is a verse
 * number and other punctuation is kept for the layout, but neither is typed or hidden. */
export function tokenize(text: string): Token[] {
	let wordIndex = 0;
	return text
		.split(/\s+/)
		.filter(Boolean)
		.map((raw) => {
			const letter = raw.match(/\p{L}/u);
			if (letter) return { raw, kind: "word", wordIndex: wordIndex++, firstLetter: baseLetter(letter[0]) };
			return { raw, kind: /^\d+$/.test(raw) ? "verse" : "other", wordIndex: -1, firstLetter: "" };
		});
}
