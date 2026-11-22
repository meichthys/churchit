import { computed, ref, watch, type Ref } from "vue";
import { useRoute, useRouter } from "vue-router";

/**
 * The open state of a request form sheet. The old web form paths still work: /new, /<name> and
 * /<name>/edit open the sheet over the list, and closing it returns to the list at *basePath*.
 */
export function useRequestSheet<T extends { name: string }>(basePath: string, items: Ref<T[] | undefined>, canOpen: (item: T) => boolean = () => true) {
	const route = useRoute();
	const router = useRouter();
	const open = ref(false);
	const editing = ref<T | null>(null) as Ref<T | null>;
	const legacy = computed(() => [route.params.rest].flat().filter((part) => part && part !== "list") as string[]);

	watch(
		[legacy, items],
		() => {
			const [first] = legacy.value;
			if (!first || !items.value) return;
			const found = items.value.find((item) => item.name === first);
			editing.value = first === "new" || !found || !canOpen(found) ? null : found;
			open.value = first === "new" || Boolean(editing.value);
		},
		{ immediate: true },
	);
	watch(open, (isOpen) => {
		if (!isOpen && legacy.value.length) router.replace(basePath);
	});

	return {
		open,
		editing,
		openNew() {
			editing.value = null;
			open.value = true;
		},
		openEdit(item: T) {
			editing.value = item;
			open.value = true;
		},
	};
}
