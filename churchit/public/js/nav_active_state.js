// Marks the current page's link in the top navbar, since Frappe's navbar
// ships no active-state logic for Website Settings' top_bar_items.
(function () {
	frappe.ready(function () {
		const current = window.location.pathname.replace(/\/$/, "") || "/";

		document.querySelectorAll(".navbar-nav > .nav-item > .nav-link").forEach(function (link) {
			if (!link.pathname) return;
			const href = link.pathname.replace(/\/$/, "") || "/";
			if (href === current) {
				link.closest(".nav-item").classList.add("active");
			}
		});
	});
})();
