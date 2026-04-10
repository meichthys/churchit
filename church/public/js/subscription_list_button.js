// Adds a "Subscribe" button to list views for doctypes that use the
// church_subscriptions child table. Only visible to Church Managers and
// System Managers. Lets a church opt in to documents they have access to
// but haven't yet subscribed to.

(function () {
	"use strict";

	function patch_listview() {
		if (!frappe.views || !frappe.views.ListView) return;

		const _orig = frappe.views.ListView.prototype.setup_page_head;
		frappe.views.ListView.prototype.setup_page_head = function () {
			_orig.call(this);
			maybe_add_subscribe_button(this);
		};
	}

	function maybe_add_subscribe_button(listview) {
		// Only desk managers need this; portal users (Church User) don't.
		if (!frappe.user.has_role(["Church Manager", "System Manager"])) return;

		const doctype = listview.doctype;

		// Defer until meta is loaded so we can inspect fields.
		frappe.model.with_doctype(doctype, function () {
			const meta = frappe.get_meta(doctype);
			if (!meta) return;

			const has_field = meta.fields.some(
				(f) => f.fieldname === "church_subscriptions" && f.fieldtype === "Table"
			);
			if (!has_field) return;

			listview.page.add_inner_button(__("Subscribe"), () => {
				show_subscribe_dialog(doctype, listview);
			});
		});
	}

	function show_subscribe_dialog(doctype, listview) {
		frappe.call({
			method: "church.church_foundations.catalog_api.get_pending_subscriptions",
			callback(r) {
				const pending = (r.message || []).filter((d) => d.doctype === doctype);

				if (!pending.length) {
					frappe.msgprint({
						title: __("Nothing to Subscribe To"),
						message: __(
							"Your church has no pending {0} documents available to subscribe to.",
							[__(doctype)]
						),
						indicator: "blue",
					});
					return;
				}

				// Build one Check field per pending doc.
				const item_fields = pending.map((doc) => ({
					fieldname: doc.name,
					fieldtype: "Check",
					label: doc.title || doc.name,
				}));

				const dialog = new frappe.ui.Dialog({
					title: __("Subscribe to {0}", [__(doctype)]),
					fields: [
						{
							fieldname: "_info",
							fieldtype: "HTML",
							options: `<p class="small text-muted mb-3">${__(
								"Documents checked below will become visible to your church."
							)}</p>`,
						},
						...item_fields,
					],
					primary_action_label: __("Subscribe"),
					primary_action(values) {
						const selected = pending.filter((doc) => values[doc.name]);
						if (!selected.length) {
							frappe.msgprint(__("Select at least one document."));
							return;
						}

						dialog.hide();

						Promise.all(
							selected.map((doc) =>
								frappe.call({
									method: "church.church_foundations.catalog_api.subscribe",
									args: {
										doctype_name: doc.doctype,
										doc_name: doc.name,
									},
									quiet: true,
								})
							)
						).then(() => {
							frappe.show_alert({
								message: __(
									"Subscribed to {0} document(s).",
									[selected.length]
								),
								indicator: "green",
							});
							listview.refresh();
						});
					},
				});

				dialog.show();
			},
		});
	}

	// ListView prototype is in the desk bundle which loads before app JS.
	// Patch it immediately; if for some reason it isn't ready, retry once.
	if (frappe.views && frappe.views.ListView) {
		patch_listview();
	} else {
		$(document).one("app_ready", patch_listview);
	}
})();
