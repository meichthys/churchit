// Service worker for the installed app. Deliberately small: every page and
// API call goes to the network, so a signed-in member never sees a stale page
// or another user's. All it keeps is the offline page, shown when a navigation
// fails instead of the browser's error. Served from www/ so its scope is the
// site root, which /assets could not give it.
const CACHE = "churchit-v1";
const OFFLINE_URL = "/offline";
const OFFLINE_ICON = "/assets/churchit/icons/pwa/icon-192.png";

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll([OFFLINE_URL, OFFLINE_ICON]))
			.then(() => self.skipWaiting())
	);
});

self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
			)
			.then(() => self.clients.claim())
	);
});

self.addEventListener("fetch", (event) => {
	if (event.request.mode === "navigate") {
		event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE_URL)));
	}
});
