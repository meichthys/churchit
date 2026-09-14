// Light/dark mode for the public site. The visitor's choice is kept in
// localStorage and applied as data-theme on <html>, the attribute frappe's own
// dark tokens key off. church_website.context inlines this into <head> so it
// runs before the first paint; until a choice is made, the system setting wins.
(function () {
	const STORAGE_KEY = "churchit-theme-mode";
	const root = document.documentElement;

	function saved_mode() {
		try {
			return localStorage.getItem(STORAGE_KEY);
		} catch (e) {
			return null;
		}
	}

	function apply(mode) {
		root.setAttribute("data-theme", mode);
	}

	apply(saved_mode() || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));

	document.addEventListener("click", function (event) {
		if (!event.target.closest(".theme-switch")) return;
		const mode = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
		apply(mode);
		try {
			localStorage.setItem(STORAGE_KEY, mode);
		} catch (e) {
			// private browsing: the choice lasts for this page only
		}
	});
})();
