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
	// API calls opened as pages (PDF downloads) skip the worker: Firefox stops a worker that
	// waits over a minute, then sends the request again and fails it.
	const isApiCall = new URL(event.request.url).pathname.startsWith("/api/");
	if (event.request.mode === "navigate" && !isApiCall) {
		event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE_URL)));
	}
});

// Web Push from churchit.church_communications.push: the payload is JSON with title, body and url.
self.addEventListener("push", (event) => {
	const message = event.data ? event.data.json() : {};
	event.waitUntil(
		self.registration.showNotification(message.title || "", {
			body: message.body || "",
			icon: OFFLINE_ICON,
			data: { url: message.url || "/" },
		})
	);
});

// A click opens the notification's url, and only a page of this site.
self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	const url = new URL(event.notification.data.url, self.location.origin);
	if (url.origin === self.location.origin) {
		event.waitUntil(self.clients.openWindow(url.href));
	}
});
