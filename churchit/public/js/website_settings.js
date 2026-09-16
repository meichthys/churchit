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
