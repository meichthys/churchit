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
		show_theme_palette(frm);
	},
	website_theme(frm) {
		show_theme_palette(frm);
	},
	after_save(frm) {
		const still_linked = [...frm.doc.top_bar_items, ...frm.doc.footer_items].map(
			(row) => row.url
		);
		const urls = [...(frm.removed_link_urls || [])].filter(
			(url) => !still_linked.includes(url)
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
		const page = await frappe.xcall("churchit.church_website.api.get_published_web_page", {
			url,
		});
		if (page) await confirm_unpublish(page);
	}
}

function confirm_unpublish(page) {
	return new Promise((resolve) => {
		frappe.confirm(
			__(
				"The page <b>{0}</b> is no longer linked from the website menu, but it is still published and reachable at <code>/{1}</code>. Un-publish it?",
				[frappe.utils.escape_html(page.title), frappe.utils.escape_html(page.route)]
			),
			() => unpublish(page).then(resolve),
			resolve
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
						page.name
					)}">${frappe.utils.escape_html(page.title)}</a>`,
				]),
				indicator: "green",
			});
		});
}

// A row of swatches beside the Website Theme picker, so a church can see a
// theme's colors without opening it.
frappe.dom.set_style(`
	.ch-theme-palette-host { display: flex; flex-wrap: wrap; align-items: center; gap: var(--margin-sm); }
	.ch-theme-palette-host > .control-input { flex: 1; }
	.ch-theme-palette-host > .help-box { flex-basis: 100%; }
	.ch-theme-palette { display: flex; gap: 4px; }
	.ch-theme-swatch {
		width: 16px; height: 16px; border-radius: 50%;
		box-shadow: inset 0 0 0 1px var(--border-color);
	}
`);

async function show_theme_palette(frm) {
	const theme = frm.doc.website_theme;
	const $host = frm.fields_dict.website_theme.$wrapper.find(".control-input-wrapper");
	$host.find(".ch-theme-palette").remove();
	if (!theme) return;

	const swatches = await frappe.xcall(
		"churchit.church_website.theme_palette.get_website_theme_palette",
		{ theme }
	);
	if (frm.doc.website_theme !== theme) return;
	$host.find(".ch-theme-palette").remove();
	const $palette = $('<div class="ch-theme-palette">');
	for (const { label, color } of swatches) {
		$('<span class="ch-theme-swatch">')
			.attr("title", `${label}: ${color}`)
			.css("background", color)
			.appendTo($palette);
	}
	$host.addClass("ch-theme-palette-host").append($palette);
}
