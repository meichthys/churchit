// Keeps a visitor's chosen branch (?church=) while they browse, without a cookie.
// The navbar's Locations dropdown picks a church for the current page; this
// carries that choice onto every other page of the site and offers it to the
// public API calls, so the whole site follows until the parameter is dropped.
// A cookie would be invisible to Frappe's page cache, which keys on path alone;
// the parameter takes the request off that cache by itself.
(function () {
	const church = new URLSearchParams(window.location.search).get("church");
	window.churchit = window.churchit || {};
	churchit.site_church = church || null;
	churchit.with_church = function (args) {
		return church ? Object.assign({ church: church }, args) : args;
	};
	// Puts the choice on each plain link under root; website_live.js runs it on each part it reads again.
	churchit.carry_church = function (root) {
		if (!church) return;
		root.querySelectorAll("a[href]").forEach(function (link) {
			if (
				link.origin !== window.location.origin ||
				link.search ||
				link.hash
			)
				return;
			if (!link.pathname || link.pathname.startsWith("/app")) return;
			if (link.hasAttribute("download")) return;
			link.search = "?church=" + encodeURIComponent(church);
		});
	};

	frappe.ready(function () {
		churchit.carry_church(document);
		// A web form's own `church` field needs nothing here: Frappe fills fields from the query string.
	});
})();
