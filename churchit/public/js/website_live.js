// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Live website pages. church_website/live.py tells every open page, through Frappe's
// website room, the doctype of a public record that changed. A part of a page that shows
// such records carries an id and data-live="<Doctype>,<Doctype>". When one of those
// changes, the page reads itself again from the server, puts in each part that changed
// and marks its new rows as fresh ink. A page drawn by a script asks with
// churchit.live.on(doctypes, read_again) instead. A page with neither never connects.
frappe.provide("churchit.live");

(function () {
	const EVENT = "churchit_website";
	// Spread the reads of many open pages over a few seconds, and read once for a burst of saves.
	const DELAY_MS = 1000;
	const SPREAD_MS = 3000;
	// A page that was out of sight this long reads itself again when it comes back.
	const AWAY_MS = 60 * 1000;
	const listeners = [];

	churchit.live.on = function (doctypes, read_again) {
		if (!listeners.length) subscribe();
		listeners.push({ doctypes: new Set(doctypes), read_again, timer: null, missed: false });
	};

	function subscribe() {
		if (!frappe.realtime) return;
		frappe.realtime.on(EVENT, (data) => {
			listeners
				.filter((listener) => data && listener.doctypes.has(data.doctype))
				.forEach(schedule);
		});
		watch_visibility();
	}

	function schedule(listener) {
		if (document.hidden) {
			listener.missed = true;
			return;
		}
		clearTimeout(listener.timer);
		listener.timer = setTimeout(listener.read_again, DELAY_MS + Math.random() * SPREAD_MS);
	}

	function watch_visibility() {
		let hidden_at = null;
		document.addEventListener("visibilitychange", () => {
			if (document.hidden) {
				hidden_at = Date.now();
				return;
			}
			const away = hidden_at && Date.now() - hidden_at > AWAY_MS;
			for (const listener of listeners) {
				if (listener.missed || away) schedule(listener);
				listener.missed = false;
			}
		});
	}

	frappe.ready(function () {
		const regions = document.querySelectorAll("[data-live][id]");
		if (!regions.length) return;

		const doctypes = new Set();
		regions.forEach((region) =>
			region.dataset.live.split(",").forEach((doctype) => doctypes.add(doctype.trim()))
		);
		churchit.live.on(doctypes, read_page);
	});

	async function read_page() {
		// A query string keeps the read out of Frappe's page cache.
		const url = new URL(window.location.href);
		url.searchParams.set("_live", Date.now());
		const response = await fetch(url, { credentials: "same-origin" });
		if (!response.ok) return;
		const page = new DOMParser().parseFromString(await response.text(), "text/html");
		document.querySelectorAll("[data-live][id]").forEach((region) => {
			const fresh = page.getElementById(region.id);
			if (!fresh) return;
			// The page's links carry the visitor's church; so must the new part's, or every part differs.
			if (churchit.carry_church) churchit.carry_church(fresh);
			if (fresh.innerHTML !== region.innerHTML && !is_in_use(region)) swap(region, fresh);
		});
	}

	// The visitor uses this part: a recording in it plays, or it holds the focus (an opened sermon in a
	// series). It catches up with the next change.
	function is_in_use(region) {
		const playing = [...region.querySelectorAll("audio, video")].some(
			(media) => !media.paused
		);
		return playing || region.contains(document.activeElement);
	}

	function swap(region, fresh) {
		const before = new Set([...get_entries(region)].map((entry) => entry.outerHTML));
		region.innerHTML = fresh.innerHTML;
		for (const entry of get_entries(region)) {
			if (before.has(entry.outerHTML)) continue;
			entry.classList.add("is-fresh");
			setTimeout(() => entry.classList.remove("is-fresh"), 1600);
		}
	}

	// The rows of an index (.ch-row), so only a new or changed row is marked; else the region's parts.
	function get_entries(region) {
		return region.querySelector(".ch-row")
			? region.querySelectorAll(".ch-row")
			: region.children;
	}
})();
