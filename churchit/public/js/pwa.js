// Registers the service worker that makes the site work as an installed app
// (www/sw.js). Browsers only offer the install on secure origins, and the
// worker itself is what keeps a lost connection from showing a browser error.
if ("serviceWorker" in navigator) {
	navigator.serviceWorker.register("/sw.js");
}
