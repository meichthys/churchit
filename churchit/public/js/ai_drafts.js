// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Fill a form from an AI draft (?ai_draft=<token>, from churchit.ai.drafts.propose) and label the
// record after its first save. Frappe drops the query string when it turns /new into a new form's
// name, so the token is taken when the page loads and at each route change, before the form shows.
(function () {
	const PARAM = "ai_draft";
	let pending = null;

	function take_token_from_url() {
		const token = new URLSearchParams(window.location.search).get(PARAM);
		if (token) pending = token;
	}

	function take_pending() {
		take_token_from_url();
		const token = pending;
		pending = null;
		if (frappe.route_options) delete frappe.route_options[PARAM];

		const url = new URL(window.location.href);
		if (url.searchParams.has(PARAM)) {
			url.searchParams.delete(PARAM);
			history.replaceState(history.state, "", url.pathname + url.search + url.hash);
		}
		return token;
	}

	function show_banner(frm, is_stale) {
		frm.set_intro(
			is_stale
				? __("This record changed after the AI draft. Check each field before you save.")
				: __("AI draft: check every field before you save."),
			is_stale ? "orange" : "yellow"
		);
	}

	async function fill_rows(frm, fieldname, rows) {
		// A new form starts a mandatory table with an empty row, which would block the save.
		if (frm.is_new()) frm.clear_table(fieldname);
		for (const { name, ...values } of rows) {
			const row =
				(name && (frm.doc[fieldname] || []).find((stored) => stored.name === name)) ||
				frm.add_child(fieldname);
			await frappe.model.set_value(row.doctype, row.name, values);
		}
		frm.refresh_field(fieldname);
	}

	async function fill(frm, token) {
		// Frappe shows the server's message, such as "Draft not found".
		const draft = await frappe
			.xcall("churchit.ai.drafts.get_draft", { token }, "GET")
			.catch(() => null);
		const is_target =
			draft &&
			draft.doctype === frm.doctype &&
			(draft.name ? draft.name === frm.doc.name : frm.is_new());
		if (!is_target) return;

		for (const [fieldname, value] of Object.entries(draft.values)) {
			if (Array.isArray(value)) await fill_rows(frm, fieldname, value);
			else await frm.set_value(fieldname, value);
		}
		frm.__ai_draft = { token, docname: frm.doc.name, is_stale: draft.stale };
		show_banner(frm, draft.stale);
	}

	take_token_from_url();
	frappe.router.on("change", take_token_from_url);

	frappe.ui.form.on("*", {
		refresh(frm) {
			const draft = frm.__ai_draft;
			if (draft && draft.docname === frm.doc.name && frm.is_dirty()) {
				show_banner(frm, draft.is_stale);
			}

			const token = take_pending();
			if (token) fill(frm, token);
		},

		after_save(frm) {
			const draft = frm.__ai_draft;
			const names = draft ? [draft.docname, frappe.model.new_names[draft.docname]] : [];
			if (!names.includes(frm.doc.name)) return;

			frm.__ai_draft = null;
			frappe
				.xcall("churchit.ai.drafts.label_saved", {
					doctype: frm.doctype,
					name: frm.doc.name,
					token: draft.token,
				})
				.then((is_labelled) => is_labelled && frm.reload_doc());
		},
	});
})();
