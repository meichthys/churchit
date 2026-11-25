import { onBeforeUnmount, ref } from "vue";

/** Below Tailwind's md breakpoint (768px) the app uses the phone layout. */
const QUERY = "(max-width: 767.98px)";

export function useIsMobile() {
	const media = window.matchMedia(QUERY);
	const isMobile = ref(media.matches);
	const update = (event: MediaQueryListEvent) => (isMobile.value = event.matches);
	media.addEventListener("change", update);
	onBeforeUnmount(() => media.removeEventListener("change", update));
	return isMobile;
}
