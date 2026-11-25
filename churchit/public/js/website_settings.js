// Removing a navbar or footer link leaves its Web Page live (#235). Remember
// the links removed in this session and, once the removal is saved, offer to
// un-publish each page that is still published.
frappe.ui.form.on("Top Bar Item", {
	before_top_bar_items_remove(frm, cdt, cdn) {
		remember_removed_link(frm, cdt, cdn);
	},
	before_footer_items_remove(frm, cdt, cdn) {
		remember_removed_link(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Website Settings", {
	refresh(frm) {
		show_theme_picker(frm);
	},
	website_theme(frm) {
		mark_picked_theme(frm);
	},
	after_save(frm) {
		const still_linked = [
			...frm.doc.top_bar_items,
			...frm.doc.footer_items,
		].map((row) => row.url);
		const urls = [...(frm.removed_link_urls || [])].filter(
			(url) => !still_linked.includes(url),
		);
		frm.removed_link_urls = new Set();
		offer_to_unpublish(urls);
	},
});

function remember_removed_link(frm, cdt, cdn) {
	const url = frappe.get_doc(cdt, cdn)?.url;
	if (!url) return;
	frm.removed_link_urls = frm.removed_link_urls || new Set();
	frm.removed_link_urls.add(url);
}

async function offer_to_unpublish(urls) {
	for (const url of urls) {
		const page = await frappe.xcall(
			"churchit.church_website.api.get_published_web_page",
			{ url },
			"GET",
		);
		if (page) await confirm_unpublish(page);
	}
}

function confirm_unpublish(page) {
	return new Promise((resolve) => {
		frappe.confirm(
			__(
				"The page <b>{0}</b> is no longer linked from the website menu, but it is still published and reachable at <code>/{1}</code>. Un-publish it?",
				[
					frappe.utils.escape_html(page.title),
					frappe.utils.escape_html(page.route),
				],
			),
			() => unpublish(page).then(resolve),
			resolve,
		);
	});
}

function unpublish(page) {
	return frappe
		.xcall("frappe.client.set_value", {
			doctype: "Web Page",
			name: page.name,
			fieldname: "published",
			value: 0,
		})
		.then(() => {
			frappe.show_alert({
				message: __("Un-published {0}", [
					`<a href="/app/web-page/${encodeURIComponent(
						page.name,
					)}">${frappe.utils.escape_html(page.title)}</a>`,
				]),
				indicator: "green",
			});
		});
}

// The theme picker under the Website Theme field: each theme as a card with its
// light and dark page, so a church sees the colors before it picks. A click picks
// the theme; Preview opens the home page in it for this user only.
frappe.dom.set_style(`
	.ch-theme-picker { margin-top: var(--margin-sm); }
	.ch-theme-picker-help { color: var(--text-muted); font-size: var(--text-sm); margin-bottom: var(--margin-sm); }
	.ch-theme-grid {
		display: grid; gap: var(--margin-sm);
		grid-template-columns: repeat(auto-fill, minmax(8.5rem, 1fr));
	}
	.ch-theme-card {
		display: flex; flex-direction: column; gap: 6px; padding: 6px 6px 8px;
		border: 1px solid var(--border-color); border-radius: var(--border-radius-md);
		background: var(--fg-color); text-align: start; cursor: pointer;
	}
	.ch-theme-card:hover { border-color: var(--gray-500); }
	.ch-theme-card[aria-checked="true"] { border-color: var(--text-color); box-shadow: 0 0 0 1px var(--text-color); }
	.ch-theme-pages { display: grid; grid-template-columns: 1fr 1fr; border-radius: var(--border-radius-sm); overflow: hidden; }
	.ch-theme-page { display: flex; flex-direction: column; gap: 4px; padding: 8px 8px 10px; min-width: 0; }
	.ch-theme-sample { font-family: Georgia, serif; font-size: 18px; font-weight: 500; line-height: 1; }
	.ch-theme-line { display: block; height: 3px; border-radius: 2px; }
	.ch-theme-line + .ch-theme-line { width: 70%; }
	.ch-theme-dot { display: block; width: 12px; height: 12px; border-radius: 50%; margin-top: 2px; }
	.ch-theme-name { display: flex; justify-content: space-between; align-items: center; gap: 4px; padding: 0 2px; font-weight: 500; }
	.ch-theme-name a { font-weight: 400; font-size: var(--text-xs); color: var(--text-muted); }
`);

async function show_theme_picker(frm) {
	const $wrapper = frm.fields_dict.website_theme.$wrapper;
	$wrapper.find(".ch-theme-picker").remove();
	const themes = await frappe.xcall(
		"churchit.church_website.theme_palette.get_website_theme_palettes",
		{},
		"GET",
	);
	$wrapper.find(".ch-theme-picker").remove();
	const $grid = $('<div class="ch-theme-grid" role="radiogroup">').attr(
		"aria-label",
		__("Website Theme"),
	);
	for (const theme of themes) {
		$grid.append(make_theme_card(frm, theme));
	}
	$('<div class="ch-theme-picker">')
		.append(
			$('<div class="ch-theme-picker-help">').text(
				__(
					"Pick the colors of your website and member portal, then save. Each theme has a light and a dark page. Preview opens your home page in a theme before you save.",
				),
			),
			$grid,
		)
		.appendTo($wrapper);
	mark_picked_theme(frm);
}

function make_theme_card(frm, theme) {
	// "/" sends a desk user to the desk, so the preview opens the home page by its route.
	const home = (frm.doc.home_page || "home").replace(/^\/+/, "");
	const preview_url = `/${encodeURI(home)}?theme_preview=${encodeURIComponent(theme.name)}`;
	return $('<div class="ch-theme-card" role="radio" tabindex="0">')
		.attr("data-theme-name", theme.name)
		.append(
			$('<div class="ch-theme-pages">').append(
				make_theme_page(theme.light),
				make_theme_page(theme.dark),
			),
			$('<div class="ch-theme-name">').append(
				$("<span>").text(theme.name),
				$('<a target="_blank" rel="noopener">')
					.attr("href", preview_url)
					.text(__("Preview"))
					.on("click", (event) => event.stopPropagation()),
			),
		)
		.on("click", () => frm.set_value("website_theme", theme.name))
		.on("keydown", (event) => {
			// Enter on the Preview link inside the card opens the preview, not a pick
			if (event.target !== event.currentTarget) return;
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				frm.set_value("website_theme", theme.name);
			}
		});
}

function make_theme_page(colors) {
	return $('<div class="ch-theme-page" aria-hidden="true">')
		.css({ background: colors.paper, color: colors.ink })
		.append(
			$('<span class="ch-theme-sample">').text("Aa"),
			$('<span class="ch-theme-line">').css("background", colors.muted),
			$('<span class="ch-theme-line">').css("background", colors.rule),
			$('<span class="ch-theme-dot">').css("background", colors.accent),
		);
}

function mark_picked_theme(frm) {
	frm.fields_dict.website_theme.$wrapper
		.find(".ch-theme-card")
		.each(function () {
			this.setAttribute(
				"aria-checked",
				this.dataset.themeName === frm.doc.website_theme,
			);
		});
}
