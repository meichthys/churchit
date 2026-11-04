// The installed app, on the website and the desk alike. Registers the service worker (www/sw.js),
// makes the desk installable, and offers a signed-in user the install: a card that "Not now" puts
// off for 30 days on this device. Chromium browsers install from the card; Safari and Firefox
// for Android have no install API, so the card shows the steps instead.
window.church = window.church || {};

(function () {
	const SNOOZE_KEY = "churchit-install-snoozed-until";
	const SNOOZE_DAYS = 30;
	const ICON = "/assets/churchit/icons/pwa/icon-192.png";
	// Pages that fill the screen on a shared device.
	const NO_OFFER_PAGES = ["/check-in-kiosk", "/sermon_presentation"];
	const agent = navigator.userAgent;
	// iPadOS asks for the desktop site, so it reads as a Mac with a touch screen.
	const is_ios =
		/iPhone|iPad|iPod/.test(agent) ||
		(/Macintosh/.test(agent) && navigator.maxTouchPoints > 1);
	const is_mac = /Macintosh/.test(agent) && !is_ios;
	const is_safari =
		/Safari/.test(agent) && !/Chrome|Chromium|CriOS|Edg|Firefox|FxiOS|OPR/.test(agent);
	const is_android = /Android/.test(agent);

	let install_event = null;
	let card = null;

	if ("serviceWorker" in navigator) {
		navigator.serviceWorker.register("/sw.js");
	}

	// The desk renders Frappe's own <head>; its boot carries what the website puts there.
	if (frappe.boot && frappe.boot.pwa_install_tags) {
		document.head.insertAdjacentHTML("beforeend", frappe.boot.pwa_install_tags);
	}

	function is_installed() {
		return matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
	}

	function is_signed_in() {
		const user = frappe.get_cookie("user_id");
		return Boolean(user) && user !== "Guest";
	}

	function manual_steps() {
		if (is_ios) return __("Tap Share, then Add to Home Screen.");
		if (is_mac && is_safari) return __("In the menu bar, choose File, then Add to Dock.");
		if (is_android && /Firefox/.test(agent))
			return __("Open the browser menu, then tap Install.");
		return null;
	}

	function snoozed_until() {
		try {
			return Number(localStorage.getItem(SNOOZE_KEY)) || 0;
		} catch (e) {
			return 0;
		}
	}

	function snooze() {
		try {
			localStorage.setItem(SNOOZE_KEY, Date.now() + SNOOZE_DAYS * 24 * 60 * 60 * 1000);
		} catch (e) {
			// Storage is blocked: the card comes back on the next page instead.
		}
	}

	function should_offer() {
		return (
			Boolean(document.querySelector('meta[name="churchit-offer-install"]')) &&
			is_signed_in() &&
			!is_installed() &&
			!NO_OFFER_PAGES.includes(location.pathname) &&
			Date.now() >= snoozed_until()
		);
	}

	function card_text() {
		const meta = document.querySelector('meta[name="application-name"]');
		const name = meta ? meta.content : document.title;
		const steps = install_event ? null : manual_steps();
		if (is_mac && steps) {
			return { title: __("Add {0} to the Dock", [name]), text: steps };
		}
		if (is_ios || is_android) {
			const text = steps || __("Open it from your home screen and get notifications.");
			return { title: __("Get the {0} app", [name]), text: text };
		}
		return {
			title: __("Install {0} on this computer", [name]),
			text: is_mac
				? __("It opens in its own window, and you can keep it in the Dock.")
				: __("It opens in its own window, and you can pin it to the taskbar."),
		};
	}

	function build_card() {
		const { title, text } = card_text();
		const element = document.createElement("div");
		element.className = "churchit-install";
		element.setAttribute("role", "dialog");
		element.innerHTML = `
			<img class="churchit-install-icon" src="${ICON}" alt="">
			<p class="churchit-install-title"></p>
			<p class="churchit-install-text"></p>
			<div class="churchit-install-actions">
				<button type="button" class="btn btn-default btn-sm" data-action="later"></button>
				<button type="button" class="btn btn-primary btn-sm" data-action="install"></button>
			</div>`;
		element.setAttribute("aria-label", title);
		element.querySelector(".churchit-install-title").textContent = title;
		element.querySelector(".churchit-install-text").textContent = text;
		element.querySelector('[data-action="later"]').textContent = __("Not now");
		element.querySelector('[data-action="install"]').textContent = install_event
			? __("Install")
			: __("Got it");
		element.addEventListener("click", on_card_click);
		return element;
	}

	function on_card_click(event) {
		const button = event.target.closest("[data-action]");
		if (!button) return;
		if (button.dataset.action === "install" && install_event) return prompt_install();
		snooze();
		hide_card();
	}

	function show_card() {
		hide_card();
		card = build_card();
		document.body.append(card);
	}

	function hide_card() {
		if (card) card.remove();
		card = null;
	}

	// A prompt shows once per event; Chromium sends a new one on a later page.
	function prompt_install() {
		const event = install_event;
		install_event = null;
		hide_card();
		refresh_install_sections();
		event.prompt();
		event.userChoice.then((choice) => {
			if (choice.outcome !== "accepted") snooze();
		});
	}

	// Install App in the desk user menu, and any [data-install-app] section, such as the one on
	// /preferences. They ignore "Not now", which is only for the card that comes by itself.
	church.can_install_app = function () {
		return !is_installed() && Boolean(install_event || manual_steps());
	};

	church.install_app = function () {
		if (install_event) return prompt_install();
		if (manual_steps()) show_card();
	};

	function refresh_install_sections() {
		const can_install = church.can_install_app();
		document.querySelectorAll("[data-install-app]").forEach((section) => {
			section.classList.toggle("d-none", !can_install);
		});
	}

	document.addEventListener("click", (event) => {
		if (event.target.closest("[data-install-app-button]")) church.install_app();
	});

	// Only a signed-in user's prompt is ours: a guest keeps the browser's own install hint.
	window.addEventListener("beforeinstallprompt", (event) => {
		if (!is_signed_in()) return;
		event.preventDefault();
		install_event = event;
		refresh_install_sections();
		if (should_offer()) show_card();
	});

	window.addEventListener("appinstalled", () => {
		install_event = null;
		hide_card();
		refresh_install_sections();
	});

	function when_ready(callback) {
		if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", callback);
		} else {
			callback();
		}
	}

	when_ready(() => {
		refresh_install_sections();
		if (manual_steps() && should_offer()) show_card();
	});
})();
