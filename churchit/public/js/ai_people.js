// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Churchit's AI actions on people and meetings (church_people/ai_actions.py, church_operations/ai.py):
// Brief Me on Person and Group, Draft Note With AI on Person, Describe People on the People list,
// Find Action Items on Meeting Minutes and Suggest Mapping on a churchit Data Import. Each shows only
// when the boot allows it (churchit.ai.can_run) and answers in churchit.ai.run_action's dialog.
frappe.provide("churchit.ai");

(function () {
	const PEOPLE = "churchit.church_people.ai_actions";
	// churchit's data_import_providers in hooks.py (test_ai_actions checks the two agree).
	const IMPORTS = [
		"People Import",
		"Planning Center Import",
		"Rock RMS Import",
		"Breeze Import",
		"Giving Import",
	];
	const escape = (text) => churchit.ai.escape(text);

	// A link the server made, on this desk's own address.
	const path_of = (url) => {
		const target = new URL(url, window.location.origin);
		return target.pathname + target.search;
	};

	// Open an AI draft's link (churchit.ai.drafts) in this tab; ai_drafts.js fills the form.
	function open_draft(url) {
		const target = new URL(url, window.location.origin);
		frappe.set_route(target.pathname + target.search);
	}

	// The paragraphs of a Text Editor value that the server built from escaped text, as plain lines.
	function lines_of(html) {
		const body = new DOMParser().parseFromString(html || "", "text/html").body;
		return [...body.querySelectorAll("p")].map((paragraph) => paragraph.textContent);
	}

	function ask(title, field, action_label, run) {
		const dialog = new frappe.ui.Dialog({
			title,
			fields: [field],
			primary_action_label: action_label,
			primary_action(values) {
				dialog.hide();
				run(values);
			},
		});
		dialog.show();
	}

	// Brief Me

	function brief(frm) {
		churchit.ai.run_action({
			title: __("Brief Me: {0}", [frm.get_title()]),
			method: `${PEOPLE}.brief`,
			args: { doctype: frm.doctype, name: frm.doc.name },
			render: render_brief,
		});
	}

	function render_brief(result, response) {
		const links = (response.sources || [])
			.map(({ title, url }) => `<a href="${escape(path_of(url))}">${escape(title)}</a>`)
			.join(", ");
		const why = links ? `<p class="small"><b>${escape(__("Why"))}:</b> ${links}</p>` : "";
		const check = __("Check the timeline before you act.");
		return `${churchit.ai.paragraphs(result.summary.split("\n"))}${why}
			<p class="text-muted small">${escape(check)}</p>`;
	}

	// Draft Note With AI

	function draft_note(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Draft Note With AI"),
			fields: [
				{
					fieldtype: "Select",
					fieldname: "doctype",
					label: __("Draft"),
					options: [
						{ value: "Person Note", label: __("Person Note") },
						{ value: "Visitation Log", label: __("Visitation Log") },
					],
					default: "Person Note",
				},
				{
					fieldtype: "Small Text",
					fieldname: "text",
					label: __("Your Notes"),
					reqd: 1,
					description: __(
						"Paste or dictate rough notes. Nothing is saved until you save the draft."
					),
				},
			],
			primary_action_label: __("Draft"),
			primary_action({ doctype, text }) {
				dialog.hide();
				// render_note reads the draft's labels and field types.
				frappe.model.with_doctype(doctype, () =>
					churchit.ai.run_action({
						title: __("{0} Draft", [__(doctype)]),
						method: `${PEOPLE}.draft_note`,
						args: { person: frm.doc.name, text, doctype },
						render: render_note,
						on_use: (result) => open_note(frm, result),
						use_label: __("Open the Draft"),
					})
				);
			},
		});
		dialog.show();
	}

	function render_note({ doctype, values }) {
		const rows = Object.entries(values)
			.map(([fieldname, value]) => {
				const df = frappe.meta.get_docfield(doctype, fieldname) || {};
				const text =
					df.fieldtype === "Text Editor"
						? churchit.ai.paragraphs(lines_of(value))
						: escape(
								df.fieldtype === "Check" ? (value ? __("Yes") : __("No")) : value
						  );
				return `<tr><th class="text-muted">${escape(
					__(df.label || fieldname)
				)}</th><td>${text}</td></tr>`;
			})
			.join("");
		return `<table class="table table-sm small">${rows}</table>`;
	}

	function open_note(frm, { doctype, values }) {
		frappe
			.xcall("churchit.ai.drafts.propose", {
				doctype,
				values: { ...values, person: frm.doc.name },
			})
			.then(({ url }) => open_draft(url));
	}

	// Describe People on the People list

	churchit.ai.add_describe_people = function (listview) {
		if (!churchit.ai.can_run()) return;
		listview.page.add_menu_item(__("Describe People"), () =>
			ask(
				__("Describe People"),
				{
					fieldtype: "Small Text",
					fieldname: "text",
					label: __("Who do you want to see?"),
					reqd: 1,
					description: __(
						"For example: members who have not attended in 2 months and are not in a group."
					),
				},
				__("Find"),
				({ text }) =>
					churchit.ai.run_action({
						title: __("Describe People"),
						method: `${PEOPLE}.describe_people`,
						args: { text },
						render: render_people,
						on_use: (result) => show_people(result.filters),
						use_label: __("Apply Filters"),
					})
			)
		);
	};

	function render_people({ count, words, notes }) {
		const filters = words.map((text) => `<li>${escape(text)}</li>`).join("");
		const keep = __("Check the list, then save the filters to keep them.");
		const people = count === 1 ? __("1 person") : __("{0} people", [count]);
		return `<p><b>${escape(people)}</b></p>
			<ul>${filters}</ul>${churchit.ai.paragraphs([...notes, keep])}`;
	}

	// The list reads route options when it shows, as when a link opens it with filters.
	function show_people(filters) {
		const options = {};
		for (const [doctype, fieldname, operator, value] of filters) {
			const key = doctype === "Person" ? fieldname : `${doctype}.${fieldname}`;
			(options[key] = options[key] || []).push([operator, value]);
		}
		frappe.route_options = options;
		frappe.set_route("List", "Person");
	}

	// Find Action Items on Meeting Minutes

	function find_action_items(frm) {
		churchit.ai.run_action({
			title: __("Action Items: {0}", [frm.get_title()]),
			method: "churchit.church_operations.ai.action_items",
			args: { minutes: frm.doc.name },
			render: render_tasks,
		});
	}

	function render_tasks({ tasks }) {
		const rows = tasks
			.map(
				(task) => `<tr>
					<td>${escape(task.title)}</td>
					<td>${escape(task.owner)}</td>
					<td>${escape(task.due_date ? frappe.datetime.str_to_user(task.due_date) : "")}</td>
					<td>${escape(__(task.priority || ""))}</td>
					<td><a href="${escape(path_of(task.url))}" target="_blank" rel="noopener">${escape(
					__("Open")
				)}</a></td>
				</tr>`
			)
			.join("");
		const head = [__("Task"), __("Owner in the Minutes"), __("Due"), __("Priority"), ""]
			.map((label) => `<th>${escape(label)}</th>`)
			.join("");
		const help = __(
			"Open each task to keep, check it and save it, then pick its owner with Assign To."
		);
		return `<table class="table table-sm small"><thead><tr>${head}</tr></thead>
			<tbody>${rows}</tbody></table><p class="text-muted small">${escape(help)}</p>`;
	}

	// Suggest Mapping on a churchit Data Import

	function suggest_mapping(frm) {
		churchit.ai.run_action({
			title: __("Suggest Mapping"),
			method: `${PEOPLE}.suggest_import_mapping`,
			args: { data_import: frm.doc.name },
			render: (result) => render_mapping(frm, get_new_mapping(frm, result)),
			on_use: (result) =>
				frm.import_preview.events.remap_column(get_new_mapping(frm, result)),
			use_label: __("Use This Mapping"),
		});
	}

	// The suggested columns that the preview shows as unmatched, for this import only.
	function get_new_mapping(frm, result) {
		if (result.import !== frm.doc.reference_doctype) throw new Error("another import");
		const columns = frm.import_preview?.preview_data?.columns || [];
		return Object.fromEntries(
			Object.entries(result.mapping).filter(([index]) => {
				const column = columns[Number(index) + 1]; // the preview's first column numbers the rows
				return column && !column.df;
			})
		);
	}

	function render_mapping(frm, mapping) {
		const columns = frm.import_preview.preview_data.columns;
		const rows = Object.entries(mapping)
			.map(([index, fieldname]) => {
				const heading = columns[Number(index) + 1].header_title;
				const label = frappe.meta.get_label(frm.doc.reference_doctype, fieldname);
				return `<tr><td>${escape(heading)}</td><td>${escape(__(label))}</td></tr>`;
			})
			.join("");
		if (!rows)
			return churchit.ai.paragraphs([__("The AI found no field for these headings.")]);
		const help = __("Save the import to see the new mapping in the preview.");
		return `<table class="table table-sm small"><thead><tr>
				<th>${escape(__("Heading"))}</th><th>${escape(__("Field"))}</th>
			</tr></thead><tbody>${rows}</tbody></table>
			<p class="text-muted small">${escape(help)}</p>`;
	}

	frappe.ui.form.on("Person", {
		refresh(frm) {
			if (frm.is_new() || !churchit.ai.can_run()) return;
			frm.add_custom_button(__("Brief Me"), () => brief(frm), __("View"));
			if (churchit.ai.can_run(true)) {
				frm.add_custom_button(
					__("Draft Note With AI"),
					() => draft_note(frm),
					__("Actions")
				);
			}
		},
	});

	frappe.ui.form.on("Group", {
		refresh(frm) {
			if (frm.is_new() || !churchit.ai.can_run()) return;
			frm.add_custom_button(__("Brief Me"), () => brief(frm), __("View"));
		},
	});

	frappe.ui.form.on("Meeting Minutes", {
		refresh(frm) {
			const can_find =
				!frm.is_new() &&
				frm.doc.minutes &&
				frappe.user.has_role("Church Manager") &&
				churchit.ai.can_run(true);
			if (can_find) {
				frm.add_custom_button(
					__("Find Action Items"),
					() => find_action_items(frm),
					__("Actions")
				);
			}
		},
	});

	frappe.ui.form.on("Data Import", {
		refresh(frm) {
			const can_map =
				!frm.is_new() &&
				IMPORTS.includes(frm.doc.reference_doctype) &&
				(frm.doc.import_file || frm.doc.google_sheets_url) &&
				frm.doc.status !== "Success" &&
				churchit.ai.can_run();
			if (can_map) {
				frm.add_custom_button(__("Suggest Mapping"), () => {
					if (!frm.import_preview) {
						frappe.msgprint(__("Wait for the preview of the file, then try again."));
						return;
					}
					suggest_mapping(frm);
				});
			}
		},
	});
})();
