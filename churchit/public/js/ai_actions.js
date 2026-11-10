// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Churchit's AI actions in the desk (churchit.ai.runner): one dialog that waits for the answer, which
// the server sends to this user's browser, and shows it as a suggestion with a Use button. An answer
// is always shown as text. The Explain item of churchit's script reports is here too.
frappe.provide("churchit.ai");

(function () {
	const EVENT = "churchit_ai_result";
	const ANSWER_METHOD = "churchit.ai.runner.get_answer";
	// A local model can take many minutes. The runner keeps the caller for an hour (RUN_SECONDS).
	const WAIT_MS = 30 * 60 * 1000;
	// A realtime message sent while the socket reconnects is lost, so the dialog also asks the server.
	const ASK_MS = 20 * 1000;
	const answers = {};
	const waiting = {};
	let is_listening = false;

	const escape = (text) => frappe.utils.escape_html(String(text ?? ""));
	churchit.ai.escape = escape;

	// True when the boot allows this user churchit's AI actions; a private action needs Private Work too.
	churchit.ai.can_run = (is_private = false) =>
		Boolean(frappe.boot.churchit?.ai?.[is_private ? "private_actions" : "actions"]);

	churchit.ai.paragraphs = (texts) =>
		texts
			.filter((text) => text)
			.map((text) => `<p>${escape(text)}</p>`)
			.join("");

	function listen() {
		if (is_listening) return;
		is_listening = true;
		frappe.realtime.on(EVENT, (message) => {
			if (!message || !message.token) return;
			if (waiting[message.token]) waiting[message.token](message);
			else answers[message.token] = message;
		});
	}

	// The answer for *token*, until the dialog closes; a closed dialog resolves with an empty message.
	function wait_for(token, dialog) {
		return new Promise((resolve) => {
			const finish = (message) => {
				clearTimeout(timer);
				clearInterval(asking);
				delete waiting[token];
				resolve(message);
			};
			const timer = setTimeout(
				() =>
					finish({
						error: __(
							"The AI did not answer in time. Try again, or ask your administrator to check Flow."
						),
					}),
				WAIT_MS
			);
			const asking = setInterval(() => {
				if (!dialog.display) return finish({});
				frappe
					.xcall(ANSWER_METHOD, { token }, "GET", { silent: true })
					.then((message) => message && finish(message))
					.catch(() => {});
			}, ASK_MS);
			waiting[token] = finish;
			if (answers[token]) {
				finish(answers[token]);
				delete answers[token];
			}
		});
	}

	// Bootstrap ignores hide() while the dialog still fades in.
	function close(dialog) {
		if (dialog.display) dialog.hide();
		else dialog.$wrapper.one("shown.bs.modal", () => dialog.hide());
	}

	function show_html(dialog, html) {
		dialog.get_field("answer").$wrapper.html(html);
	}

	function show_error(dialog, text) {
		show_html(
			dialog,
			`<div class="form-message red"><div>${escape(
				text || __("The AI answer could not be used.")
			)}</div></div>`
		);
	}

	function show_answer(dialog, html, on_use, use_label) {
		const note = __("Suggestion. Check it before you use it.");
		show_html(
			dialog,
			`<div class="form-message yellow mb-3"><div>${escape(note)}</div></div>${html}`
		);
		if (!on_use) return;
		dialog.set_primary_action(use_label || __("Use"), () => {
			dialog.hide();
			on_use();
		});
	}

	// Run a churchit AI action. *title* is text; *method* is a POST endpoint that returns {token, ...};
	// render(result, response) returns HTML built with churchit.ai.escape; on_use(result, response)
	// applies it.
	churchit.ai.run_action = function ({ title, method, args, render, on_use, use_label }) {
		listen();
		const dialog = new frappe.ui.Dialog({
			title: escape(title),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "answer" }],
		});
		show_html(dialog, `<p class="text-muted">${escape(__("Working..."))}</p>`);
		dialog.show();

		frappe
			.xcall(method, args || {}, "POST")
			.then(async (response) => {
				const message = await wait_for(response.token, dialog);
				if (!dialog.display) return;
				if (message.error || message.result === undefined) {
					show_error(dialog, message.error);
					return;
				}
				let html;
				try {
					html = render
						? render(message.result, response)
						: paragraphs_of(message.result);
				} catch (error) {
					show_error(dialog);
					return;
				}
				show_answer(
					dialog,
					html,
					on_use && (() => on_use(message.result, response)),
					use_label
				);
			})
			// Frappe shows the server's message, such as a refusal.
			.catch(() => close(dialog));
		return dialog;
	};

	function paragraphs_of(result) {
		return churchit.ai.paragraphs(
			typeof result === "string" ? [result] : [JSON.stringify(result, null, 2)]
		);
	}

	// The Church AI Suggestion on a request (churchit.ai.triage), which only its readers fetch: Pastoral
	// Care and Church Managers. describe(suggestion) returns {rows: [[label, text]], uses: [[label,
	// action]], note}. Each value shows as text in a form section; a Use button fills the form unsaved.
	churchit.ai.show_suggestion = function (frm, describe) {
		const doctype = "Church AI Suggestion";
		if (frm.is_new() || !frappe.boot.churchit?.ai?.on || !frappe.model.can_read(doctype))
			return;
		const name = frm.doc.name;
		const fields = [
			"suggested_type",
			"suggested_urgent",
			"suggested_urgency",
			"suggested_flags",
			"public_wording",
		];
		frappe.db
			.get_value(doctype, { reference_doctype: frm.doctype, reference_name: name }, fields)
			.then(({ message }) => {
				if (!message || !Object.keys(message).length || frm.doc.name !== name) return;
				const { rows, uses, note } = describe(message);
				const html = rows
					.filter(([, text]) => text)
					.map(
						([label, text]) =>
							`<p><strong>${escape(label)}:</strong> ${escape(text)}</p>`
					)
					.join("");
				frm.dashboard.add_section(
					`${html}<p class="text-muted small">${escape(note)}</p>`,
					__("AI Suggestion")
				);
				frm.dashboard.show();
				if (!frm.has_perm("write")) return;
				for (const [label, action] of uses) {
					frm.add_custom_button(label, action, __("AI Suggestion"));
				}
			});
	};

	// Explain on churchit's script reports.

	function is_explainable(report_doc) {
		const ai = frappe.boot.churchit?.ai || {};
		return (
			report_doc.report_type === "Script Report" &&
			frappe.boot.module_app?.[frappe.scrub(report_doc.module || "")] === "churchit" &&
			!(ai.no_explain || []).includes(report_doc.name)
		);
	}

	// Frappe builds a report's menu after it loads the report, and again when the person returns to
	// it, so the item is added for a few seconds after each route change; adding it twice does nothing.
	function add_explain_item(report_name, tries) {
		const report = frappe.query_report;
		if (frappe.get_route()[0] !== "query-report" || frappe.get_route()[1] !== report_name)
			return;
		if (report?.report_doc?.name === report_name && report.report_settings && report.page) {
			if (is_explainable(report.report_doc)) {
				report.page.add_menu_item(__("Explain"), () => explain(report));
			}
		}
		if (tries > 0) setTimeout(() => add_explain_item(report_name, tries - 1), 250);
	}

	function on_route() {
		// The router has no route yet when the desk first loads.
		const [view, report_name] = frappe.get_route() || [];
		if (view === "query-report" && report_name && churchit.ai.can_run()) {
			add_explain_item(report_name, 40);
		}
	}

	function explain(report) {
		churchit.ai.run_action({
			title: __("Explain {0}", [__(report.report_name)]),
			method: "churchit.ai.reports.explain_report",
			args: { report_name: report.report_name, filters: report.get_filter_values() },
			render: render_explanation,
		});
	}

	function render_explanation(result, response) {
		const questions = (result.questions || [])
			.map((text) => `<li>${escape(text)}</li>`)
			.join("");
		const missing = get_missing_numbers(result, response.rows);
		const text = [
			churchit.ai.paragraphs([result.summary, result.trend]),
			questions
				? `<p class="mb-1"><b>${escape(__("Ask next"))}</b></p><ul>${questions}</ul>`
				: "",
			missing.length
				? `<p class="text-warning small">${escape(
						__("These numbers are not in the rows: {0}", [missing.join(", ")])
				  )}</p>`
				: "",
		].join("");
		return `<div class="row">
			<div class="col-md-5">${text}</div>
			<div class="col-md-7">${rows_table(response)}</div>
		</div>`;
	}

	function rows_table({ columns, rows, total_rows }) {
		const head = columns.map((label) => `<th>${escape(label)}</th>`).join("");
		const body = rows
			.map((row) => `<tr>${row.map((value) => `<td>${escape(value)}</td>`).join("")}</tr>`)
			.join("");
		const shown = __("The AI got {0} of {1} rows.", [rows.length, total_rows]);
		return `<p class="text-muted small">${escape(shown)}</p>
			<div style="max-height: 24rem; overflow: auto">
				<table class="table table-bordered table-sm small"><thead><tr>${head}</tr></thead>
				<tbody>${body}</tbody></table>
			</div>`;
	}

	function numbers_in(text) {
		return (String(text ?? "").match(/\d[\d,]*(\.\d+)?/g) || []).map((number) =>
			Number(number.replace(/,/g, ""))
		);
	}

	function get_missing_numbers(result, rows) {
		const known = new Set(rows.flat().flatMap(numbers_in));
		const said = [result.summary, result.trend, ...(result.questions || [])].flatMap(
			numbers_in
		);
		return [...new Set(said)].filter((number) => !known.has(number));
	}

	frappe.router.on("change", on_route);
	$(document).ready(() => setTimeout(on_route, 0));
})();
