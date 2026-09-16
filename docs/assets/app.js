// churchit marketing site — tiny progressive-enhancement helpers.
(function () {
	"use strict";

	// Dark-mode toggle. The initial theme is set by an inline <head> script
	// (before paint); here we just wire the button to flip and persist it.
	var themeBtn = document.querySelector(".theme-toggle");
	if (themeBtn) {
		var root = document.documentElement;
		var syncPressed = function () {
			themeBtn.setAttribute(
				"aria-pressed",
				root.getAttribute("data-theme") === "dark" ? "true" : "false"
			);
		};
		syncPressed();
		themeBtn.addEventListener("click", function () {
			var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
			root.setAttribute("data-theme", next);
			try {
				localStorage.setItem("theme", next);
			} catch (e) {
				// localStorage may be unavailable (private mode).
			}
			syncPressed();
		});
		// Follow the OS theme as long as the visitor hasn't picked one explicitly.
		try {
			matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
				if (localStorage.getItem("theme")) return;
				root.setAttribute("data-theme", e.matches ? "dark" : "light");
				syncPressed();
			});
		} catch (e) {
			// matchMedia may be unavailable.
		}
	}

	// Mobile nav toggle
	var toggle = document.querySelector(".nav-toggle");
	var links = document.querySelector(".nav-links");
	if (toggle && links) {
		toggle.addEventListener("click", function () {
			links.classList.toggle("open");
		});
		links.addEventListener("click", function (e) {
			if (e.target.tagName === "A") links.classList.remove("open");
		});
	}

	// Copy buttons on command blocks (getting-started). Hidden where the
	// Clipboard API is unavailable (insecure context / very old browsers).
	document.querySelectorAll(".cmd [data-copy]").forEach(function (btn) {
		if (!navigator.clipboard) {
			btn.hidden = true;
			return;
		}
		btn.addEventListener("click", function () {
			var code = btn.parentNode.querySelector("code");
			navigator.clipboard.writeText(code.textContent.trim()).then(function () {
				btn.textContent = "Copied ✓";
				setTimeout(function () {
					btn.textContent = "Copy";
				}, 1600);
			});
		});
	});

	// Tabs (getting-started deployment paths): one panel visible at a time.
	document.querySelectorAll("[role='tablist']").forEach(function (list) {
		var tabs = list.querySelectorAll("[role='tab']");
		tabs.forEach(function (tab) {
			tab.addEventListener("click", function () {
				tabs.forEach(function (other) {
					other.setAttribute("aria-selected", other === tab ? "true" : "false");
					document.getElementById(other.getAttribute("aria-controls")).hidden =
						other !== tab;
				});
			});
		});
	});

	// Reveal-on-scroll
	var reveals = document.querySelectorAll(".reveal");
	if ("IntersectionObserver" in window && reveals.length) {
		var io = new IntersectionObserver(
			function (entries) {
				entries.forEach(function (en) {
					if (en.isIntersecting) {
						en.target.classList.add("in");
						io.unobserve(en.target);
					}
				});
			},
			{ threshold: 0.12 }
		);
		reveals.forEach(function (el) {
			io.observe(el);
		});
	} else {
		reveals.forEach(function (el) {
			el.classList.add("in");
		});
	}

	// Documentation scrollspy — highlight sidebar link for the section in view
	var sections = document.querySelectorAll(".doc-section[id]");
	var navLinks = document.querySelectorAll(".doc-side a[href^='#']");
	if (sections.length && navLinks.length && "IntersectionObserver" in window) {
		var map = {};
		navLinks.forEach(function (a) {
			map[a.getAttribute("href").slice(1)] = a;
		});
		var spy = new IntersectionObserver(
			function (entries) {
				entries.forEach(function (en) {
					if (en.isIntersecting) {
						navLinks.forEach(function (a) {
							a.classList.remove("active");
						});
						if (map[en.target.id]) map[en.target.id].classList.add("active");
					}
				});
			},
			{ rootMargin: "-45% 0px -50% 0px" }
		);
		sections.forEach(function (s) {
			spy.observe(s);
		});
	}
})();
