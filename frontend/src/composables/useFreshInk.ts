import { reactive } from "vue";

/** How long a changed line keeps its fresh ink before only the new words remain. */
const FRESH_MS = 8000;

/**
 * Mark the lines a live update just changed, by key (a record name). Bind `:fresh="isFresh(row.name)"`
 * on OrderEntry or IndexRow, or the class "is-fresh" on your own element. If the change is not on screen,
 * show a toast instead (never both).
 */
export function useFreshInk() {
	const fresh = reactive(new Set<string>());

	function mark(key: string) {
		fresh.add(key);
		setTimeout(() => fresh.delete(key), FRESH_MS);
	}

	return { mark, isFresh: (key: string) => fresh.has(key) };
}
