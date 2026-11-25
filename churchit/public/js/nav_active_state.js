// Marks the current page's link in the top navbar and the portal sidebar.
// Frappe marks only a navbar link to the exact path, which the home page ("/")
// and a sermon (/sermon/<name>) never match. Its sidebar matches the whole
// URL, so a query string (/bible?book=JHN) or a page under a menu link lost
// the mark. It also adds the Skip to content link.
(function () {
	// frappe's own page-change handler runs first: it calls the frappe.ready
	// scripts, the sidebar's among them, then make_navbar_active, which clears
	// every navbar highlight and marks only a link to the exact path.
	$(document).on("page-change", function () {
		const current = trimSlash(window.location.pathname);
		const section = navbarSection(current);

		// a menu toggle such as the account menu links to "#", which is this page
		const links = document.querySelectorAll(
			'.navbar-nav > .nav-item > .nav-link:not([href^="#"])',
		);
		links.forEach(function (link) {
			if (link.pathname && trimSlash(link.pathname) === section) {
				link.closest(".nav-item").classList.add("active");
			}
		});

		document
			.querySelectorAll(".web-sidebar .sidebar-item a")
			.forEach(function (link) {
				const href = trimSlash(link.pathname);
				link.classList.toggle(
					"active",
					current === href || current.startsWith(href + "/"),
				);
			});

		// frappe's sidebar script centres the current page with scrollIntoView,
		// which on a desktop scrolls the window past the page heading. Put the
		// window back, unless frappe then scrolled to a #link, and centre the
		// current page only in the row that scrolls sideways on a phone.
		const active = document.querySelector(
			".web-sidebar .sidebar-item a.active",
		);
		const row = active && active.closest(".sidebar-items");
		if (row) {
			if (!window.location.hash) window.scrollTo(0, 0);
			const rowBox = row.getBoundingClientRect();
			const linkBox = active.getBoundingClientRect();
			row.scrollLeft +=
				linkBox.left - rowBox.left - (rowBox.width - linkBox.width) / 2;
		}
	});

	// a keyboard user reaches the content without tabbing through the navbar and sidebar
	$(function () {
		const main = document.querySelector("main");
		if (!main || document.querySelector(".skip-link")) return;

		main.id = main.id || "page-main";
		main.setAttribute("tabindex", "-1");

		const link = document.createElement("a");
		link.className = "skip-link";
		link.href = "#" + main.id;
		link.textContent = __("Skip to content");
		link.addEventListener("click", function (event) {
			event.preventDefault();
			main.focus();
		});
		document.body.prepend(link);
	});

	// the navbar link of a page that has no link of its own
	function navbarSection(path) {
		if (path === "/") return "/home";
		if (path.startsWith("/sermon/")) return "/sermons";
		return path;
	}

	function trimSlash(path) {
		return path.replace(/\/$/, "") || "/";
	}
})();
