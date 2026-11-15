// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Draft with AI (churchit.ai.writing): a link beside each field that the boot names
// (frappe.boot.churchit.ai_writing). It writes, shortens, changes the tone of or translates the
// field's text, or writes alt text for a page's images, and fills the field unsaved when the person
// chooses Use. The Sermon form's study helpers (churchit.church_study.ai) and a new Question Set's or
// Follow-up Workflow's Describe button (churchit.church_setup.ai) are here too. Nothing is saved or sent.
(function () {
	const METHOD = "churchit.ai.writing.draft_text";
	const LINK_CLASS = "churchit-ai-writing";
	const ALT_TEXT = "alt_text";
	const PLACEHOLDER = /\{\{\s*[\w.]+\s*\}\}/g;

	const get_fields = (doctype) => frappe.boot.churchit?.ai_writing?.[doctype] || {};
	const escape = (text) => churchit.ai.escape(text);

	const action_labels = () => ({
		write: __("Write"),
		shorten: __("Shorten"),
		tone: __("Change Tone"),
		translate: __("Translate"),
	});

	function is_public_page(frm) {
		return !frm.is_new() && frm.doc.published && !frm.doc.members_only;
	}

	// target: the record whose field fills, the form's own or a table row's.
	function add_links(frm, fields_dict, target) {
		if (!churchit.ai?.can_run?.()) return;
		for (const [fieldname, config] of Object.entries(get_fields(target.doctype))) {
			const field = fields_dict[fieldname];
			if (!field?.$wrapper) continue;
			field.$wrapper.find("." + LINK_CLASS).remove();
			if (field.get_status?.() !== "Write") continue;
			if (config.public_only && !is_public_page(frm)) continue;

			const $link = $(`<a role="button" class="${LINK_CLASS} small text-muted"></a>`)
				.text(
					config.actions.includes(ALT_TEXT)
						? __("Alt Text with AI")
						: __("Draft with AI")
				)
				.css("margin-left", "8px")
				.on("click", (event) => {
					event.preventDefault();
					event.stopPropagation();
					choose(frm, target, fieldname, config.actions);
				});
			field.$wrapper.find(".clearfix label, .clearfix .label-area").first().append($link);
		}
	}

	function choose(frm, target, fieldname, actions) {
		if (actions.includes(ALT_TEXT)) return run(frm, target, fieldname, ALT_TEXT, "");
		const labels = action_labels();
		const dialog = new frappe.ui.Dialog({
			title: __("Draft with AI"),
			fields: [
				{
					fieldname: "action",
					fieldtype: "Select",
					label: __("Action"),
					options: actions.map((action) => ({ label: labels[action], value: action })),
					default: target.doc[fieldname] ? "shorten" : "write",
					reqd: 1,
				},
				{
					fieldname: "prompt",
					fieldtype: "Small Text",
					label: __("Request"),
					description: __(
						"Write: what to write. Change Tone: the tone, such as warmer or more formal. Translate: the language."
					),
				},
			],
			primary_action_label: __("Draft"),
			primary_action(values) {
				dialog.hide();
				run(frm, target, fieldname, values.action, values.prompt || "");
			},
		});
		dialog.show();
	}

	function run(frm, target, fieldname, action, prompt) {
		const source = target.doc[fieldname] || "";
		const values = Object.fromEntries(
			Object.entries(frm.doc).filter(([, value]) => typeof value !== "object")
		);
		const is_alt_text = action === ALT_TEXT;
		churchit.ai.run_action({
			title: is_alt_text ? __("Alt Text with AI") : __("Draft with AI"),
			method: METHOD,
			args: {
				doctype: target.doctype,
				fieldname,
				action,
				name: frm.is_new() ? null : frm.doc.name,
				prompt,
				text: source,
				values,
			},
			render: (result) =>
				is_alt_text ? render_alt_texts(result) : render_text(result, source),
			on_use: (result) =>
				is_alt_text
					? use_alt_texts(target, fieldname, result.alt_texts)
					: use_text(target, fieldname, result.text, source),
		});
	}

	function render_text(result, source) {
		const passages = (result.references || []).map((passage) => {
			const translation = passage.translation ? ` (${escape(passage.translation)})` : "";
			const text = passage.text ? `: ${escape(passage.text)}` : "";
			return `<li><b>${escape(passage.reference)}</b>${translation}${text}</li>`;
		});
		const kept = new Set(result.text.match(PLACEHOLDER) || []);
		const missing = [...new Set(source.match(PLACEHOLDER) || [])].filter(
			(name) => !kept.has(name)
		);
		const warnings = [
			result.dropped?.length &&
				__("Left out the part that named {0}, which is not in the Bible.", [
					result.dropped.join(", "),
				]),
			missing.length && __("The answer leaves out {0}.", [missing.join(", ")]),
		].filter(Boolean);
		return [
			`<div style="white-space: pre-wrap">${escape(result.text)}</div>`,
			passages.length
				? `<p class="mt-3 mb-1"><b>${escape(
						__("Bible passages")
				  )}</b></p><ul>${passages.join("")}</ul>`
				: "",
			...warnings.map((warning) => `<p class="text-warning small">${escape(warning)}</p>`),
		].join("");
	}

	function render_alt_texts(result) {
		const items = result.alt_texts.map((text) => `<li>${escape(text || "-")}</li>`).join("");
		return `<p>${escape(
			__("Alt text for each image without one, in page order:")
		)}</p><ol>${items}</ol>`;
	}

	function use_text(target, fieldname, text, source) {
		const fieldtype = frappe.meta.get_docfield(target.doctype, fieldname)?.fieldtype;
		if (fieldtype === "Text Editor") {
			target.set(fieldname, keep_own_images(frappe.markdown(text), source));
		} else if (fieldtype === "Data") {
			target.set(fieldname, text.replace(/\s+/g, " ").trim());
		} else {
			target.set(fieldname, text);
		}
	}

	// An image keeps its place only when the field already showed it, so an answer adds no image.
	function keep_own_images(html, source) {
		const parse = (text) => new DOMParser().parseFromString(text, "text/html");
		const own = new Set([...parse(source).images].map((image) => image.getAttribute("src")));
		const doc = parse(html);
		for (const image of [...doc.images]) {
			if (!own.has(image.getAttribute("src"))) image.remove();
		}
		return doc.body.innerHTML;
	}

	// The images without alt text, in the order churchit.ai.writing.get_images sent them.
	function use_alt_texts(target, fieldname, alt_texts) {
		const doc = new DOMParser().parseFromString(target.doc[fieldname] || "", "text/html");
		const images = [...doc.images].filter(
			(image) => !(image.getAttribute("alt") || "").trim()
		);
		images.forEach((image, index) => {
			if (alt_texts[index]) image.setAttribute("alt", alt_texts[index]);
		});
		target.set(fieldname, doc.body.innerHTML);
	}

	const form_target = (frm) => ({
		doctype: frm.doctype,
		doc: frm.doc,
		set: (fieldname, value) => frm.set_value(fieldname, value),
	});

	const row_target = (cdt, cdn) => ({
		doctype: cdt,
		doc: locals[cdt][cdn],
		set: (fieldname, value) => frappe.model.set_value(cdt, cdn, fieldname, value),
	});

	function open_draft(url) {
		const target = new URL(url, window.location.origin);
		frappe.set_route(target.pathname + target.search);
	}

	// Sermon study helpers.

	function study_helpers(frm) {
		return [
			["questions", __("Discussion Questions"), __("Copy")],
			["summary", __("Summary"), __("Copy")],
			...(frm.doc.series
				? [["series_description", __("Series Description"), __("Open Draft")]]
				: []),
			["handout_blanks", __("Handout Blanks"), __("Use")],
			...(frm.doc.publish
				? [
						["devotional", __("Devotional"), __("Copy")],
						["social_post", __("Social Post"), __("Copy")],
				  ]
				: []),
		];
	}

	function add_study_buttons(frm) {
		if (frm.is_new() || !churchit.ai?.can_run?.()) return;
		for (const [purpose, label, use_label] of study_helpers(frm)) {
			frm.add_custom_button(
				label,
				() =>
					churchit.ai.run_action({
						title: label,
						method: "churchit.church_study.ai.study_helper",
						args: { sermon: frm.doc.name, purpose },
						render: (result) => render_study(purpose, result),
						on_use: (result) => use_study(frm, purpose, result),
						use_label,
					}),
				__("Study with AI")
			);
		}
	}

	function render_study(purpose, result) {
		if (purpose === "handout_blanks") {
			const items = result.blanks.map((blank) => `<li>${escape(blank)}</li>`).join("");
			return `<p>${escape(
				__("Use puts these in [brackets] in the notes:")
			)}</p><ul>${items}</ul>`;
		}
		if (purpose === "questions") {
			return render_text({ ...result, text: number_lines(result.questions) }, "");
		}
		return render_text(result, "");
	}

	const number_lines = (lines) => lines.map((line, index) => `${index + 1}. ${line}`).join("\n");

	function use_study(frm, purpose, result) {
		if (purpose === "handout_blanks") return bracket_notes(frm, result.blanks);
		if (purpose === "series_description") {
			return frappe
				.xcall("churchit.ai.drafts.propose", {
					doctype: "Sermon Series",
					name: frm.doc.series,
					values: { description: frappe.markdown(result.text) },
				})
				.then((draft) => open_draft(draft.url));
		}
		const text = purpose === "questions" ? number_lines(result.questions) : result.text;
		frappe.utils.copy_to_clipboard(text);
	}

	// Each blank in [brackets] where the notes first show it, so Create Handout makes the blanks.
	function bracket_notes(frm, blanks) {
		const doc = new DOMParser().parseFromString(frm.doc.notes || "", "text/html");
		const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
		const texts = [];
		while (walker.nextNode()) texts.push(walker.currentNode);
		let count = 0;
		for (const blank of blanks) {
			const node = texts.find((text) => text.nodeValue.includes(blank));
			if (!node) continue;
			const at = node.nodeValue.indexOf(blank);
			if (node.nodeValue[at - 1] === "[") continue;
			const value = node.nodeValue;
			node.nodeValue = `${value.slice(0, at)}[${blank}]${value.slice(at + blank.length)}`;
			count++;
		}
		frm.set_value("notes", doc.body.innerHTML);
		frappe.show_alert({
			message: __(
				"{0} blanks added. Check the notes, then save and choose Create Handout.",
				[count]
			),
			indicator: count ? "green" : "orange",
		});
	}

	// Describe the form or the process: an unsaved Question Set or Follow-up Workflow.

	function add_describe_button(frm, method, label, description_label) {
		if (!frm.is_new() || !churchit.ai?.can_run?.()) return;
		frm.add_custom_button(label, () => {
			const dialog = new frappe.ui.Dialog({
				title: label,
				fields: [
					{
						fieldname: "description",
						fieldtype: "Small Text",
						label: description_label,
						reqd: 1,
					},
				],
				primary_action_label: __("Draft"),
				primary_action({ description }) {
					dialog.hide();
					churchit.ai.run_action({
						title: label,
						method,
						args: { description },
						render: render_draft,
						on_use: (result) => open_draft(result.url),
						use_label: __("Open Draft"),
					});
				},
			});
			dialog.show();
		});
	}

	function render_draft(result) {
		const lines = result.questions
			? result.questions.map(
					(row) =>
						`${row.label} (${__(row.question_type)}${
							row.is_required ? ", " + __("required") : ""
						})`
			  )
			: result.steps;
		const items = lines.map((line) => `<li>${escape(line)}</li>`).join("");
		const left_out = result.left_out
			? `<p class="text-warning small">${escape(
					__("Left out {0} triggers or actions that the workflow cannot do.", [
						result.left_out,
					])
			  )}</p>`
			: "";
		const note = __("Open Draft shows the whole form, unsaved, for you to check.");
		return `<ul>${items}</ul>${left_out}<p class="text-muted small">${escape(note)}</p>`;
	}

	for (const doctype of Object.keys(frappe.boot.churchit?.ai_writing || {})) {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				add_links(frm, frm.fields_dict, form_target(frm));
			},
			form_render(frm, cdt, cdn) {
				const row = frm.cur_grid;
				if (row?.doc?.name === cdn && row.grid_form) {
					add_links(frm, row.grid_form.fields_dict, row_target(cdt, cdn));
				}
			},
		});
	}

	frappe.ui.form.on("Sermon", { refresh: add_study_buttons });
	frappe.ui.form.on("Question Set", {
		refresh: (frm) =>
			add_describe_button(
				frm,
				"churchit.church_setup.ai.draft_question_set",
				__("Describe the Form"),
				__("What should the form ask?")
			),
	});
	frappe.ui.form.on("Follow-up Workflow", {
		refresh: (frm) =>
			add_describe_button(
				frm,
				"churchit.church_setup.ai.draft_followup_workflow",
				__("Describe the Process"),
				__("What should happen, step by step?")
			),
	});
})();
