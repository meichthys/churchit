// Marks the current page's link in the top navbar and the portal sidebar.
// Frappe's navbar ships no active-state logic for Website Settings'
// top_bar_items, and its sidebar matches the whole URL, so a query string
// (/bible?book=JHN) or a web form's own page (/prayer-request/new) lost it.
(function () {
	frappe.ready(function () {
		const current = trimSlash(window.location.pathname);

		document.querySelectorAll(".navbar-nav > .nav-item > .nav-link").forEach(function (link) {
			if (link.pathname && trimSlash(link.pathname) === current) {
				link.closest(".nav-item").classList.add("active");
			}
		});

		// Runs after frappe's own sidebar script, which this corrects.
		document.querySelectorAll(".web-sidebar .sidebar-item a").forEach(function (link) {
			const href = trimSlash(link.pathname);
			link.classList.toggle("active", current === href || current.startsWith(href + "/"));
		});
		// On a phone the sidebar is a row that scrolls sideways.
		const active = document.querySelector(".web-sidebar .sidebar-item a.active");
		if (active) active.scrollIntoView({ block: "nearest", inline: "center" });
	});

	function trimSlash(path) {
		return path.replace(/\/$/, "") || "/";
	}
})();
