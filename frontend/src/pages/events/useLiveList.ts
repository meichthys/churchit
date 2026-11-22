import { toast } from "frappe-ui";

import { useFreshInk } from "@/composables/useFreshInk";
import { useLiveRefresh } from "@/realtime";

/**
 * Read a list again when the server says *topic* changed. A line the change touched shows fresh ink; when
 * the change is not on screen the member gets one toast with *message* instead.
 */
export function useLiveList(
	topic: string,
	reload: () => Promise<unknown> | unknown,
	isOnScreen: (name: string) => boolean,
	message: () => string,
) {
	const { mark, isFresh } = useFreshInk();

	useLiveRefresh([topic], async (hint) => {
		await reload();
		if (!hint?.name) return;
		if (isOnScreen(hint.name)) mark(hint.name);
		else toast.success(message());
	});

	return { isFresh };
}
