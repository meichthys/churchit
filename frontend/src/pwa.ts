import { ref } from "vue";

/** The browser's install offer, kept until the app shows its own install button. */
export const installPrompt = ref<(Event & { prompt: () => Promise<void> }) | null>(null);

/** Register the site's one service worker (/sw.js: offline page and push). The website's pwa.js does
 * this on every other page, but needs the desk's globals, so the app does it itself. */
export function setUpPwa(): void {
	if ("serviceWorker" in navigator) {
		navigator.serviceWorker.register("/sw.js").catch(() => {});
	}
	window.addEventListener("beforeinstallprompt", (event) => {
		event.preventDefault();
		installPrompt.value = event as Event & { prompt: () => Promise<void> };
	});
	window.addEventListener("appinstalled", () => (installPrompt.value = null));
}
