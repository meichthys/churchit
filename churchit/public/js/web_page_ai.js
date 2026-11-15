// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Translate with AI: a draft translation of a public Web Page, for a fluent person to check (A7.3).
// The server (churchit.church_website.ai) refuses a page that guests cannot open and an answer that
// changes a template tag or adds a script or an outside link; the draft opens unsaved and unpublished.
(function () {
	const METHOD = "churchit.church_website.ai.translate_web_page";
	const escape = (text) => churchit.ai.escape(text);

	function can_translate(frm) {
		return (
			!frm.is_new() &&
			churchit.ai?.can_run?.() &&
			frm.doc.published &&
			!frm.doc.members_only &&
			frm.has_perm("write")
		);
	}

	function open_draft(url) {
		const target = new URL(url, window.location.origin);
		frappe.set_route(target.pathname + target.search);
	}

	// The answer names its page; an answer for another page shows the fixed error of run_action.
	function render(frm, result) {
		if (result.page !== frm.doc.name) throw new Error("another page");
		const note = __(
			"Open Draft shows the whole page, unsaved and unpublished. Ask someone fluent in the language to check it before you publish it."
		);
		const dropped = result.dropped?.length
			? `<p class="text-muted small">${escape(
					__("Left out: {0}", [result.dropped.join(", ")])
			  )}</p>`
			: "";
		return `<p><b>${escape(result.title)}</b></p>
			${churchit.ai.paragraphs([result.meta_description])}${dropped}
			<p class="text-muted small">${escape(note)}</p>`;
	}

	function translate(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Translate with AI"),
			fields: [
				{
					fieldname: "language",
					fieldtype: "Link",
					options: "Language",
					label: __("Language"),
					reqd: 1,
					get_query: () => ({ filters: { enabled: 1 } }),
				},
			],
			primary_action_label: __("Translate"),
			primary_action({ language }) {
				dialog.hide();
				churchit.ai.run_action({
					title: __("Translate: {0}", [frm.doc.title || frm.doc.name]),
					method: METHOD,
					args: { web_page: frm.doc.name, language },
					render: (result) => render(frm, result),
					on_use: (result) => open_draft(result.url),
					use_label: __("Open Draft"),
				});
			},
		});
		dialog.show();
	}

	frappe.ui.form.on("Web Page", {
		refresh(frm) {
			if (can_translate(frm))
				frm.add_custom_button(__("Translate with AI"), () => translate(frm));
		},
	});
})();
