// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.query_reports["People Data Quality"] = {
	filters: [
		...church.report_filters(),
		{
			fieldname: "problem",
			label: __("Problem"),
			fieldtype: "Select",
			options: [
				"",
				"No Way to Reach",
				"Invalid Email",
				"Invalid Phone Number",
				"Email Bounced",
				"Mail Returned",
				"Possible Duplicate",
				"Child Without Birth Date",
				"No Family",
			].map((value) => ({ value, label: value && __(value) })),
		},
	],

	onload(report) {
		if (!churchit.ai.can_run() || !frappe.model.can_write("Person")) return;
		report.page.add_inner_button(__("Suggest Fixes"), () => suggest_quality_fixes(report));
	},
};

// Suggest Fixes (church_people/ai_actions.py suggest_quality_fixes): a corrected value for each invalid
// email address and phone number on screen. Save Ticked saves each ticked person as the form does.
function suggest_quality_fixes(report) {
	const dialog = churchit.ai.run_action({
		title: __("Suggest Fixes"),
		method: "churchit.church_people.ai_actions.suggest_quality_fixes",
		args: { filters: report.get_filter_values() },
		render: render_quality_fixes,
		on_use: (result) => save_ticked_fixes(report, result, dialog),
		use_label: __("Save Ticked"),
	});
}

function render_quality_fixes({ fixes }) {
	const escape = churchit.ai.escape;
	const rows = fixes
		.map(
			(fix, index) => `<tr>
				<td><input type="checkbox" class="quality-fix" data-index="${index}"></td>
				<td>${escape(fix.person_name || fix.person)}</td>
				<td>${escape(fix.problem)}</td>
				<td>${escape(fix.old)}</td>
				<td>${escape(fix.value)}</td>
			</tr>`
		)
		.join("");
	const help = __("Tick each fix to save. Each person is saved as the form saves them.");
	return `<table class="table table-sm small"><thead><tr><th></th>
			<th>${escape(__("Person"))}</th><th>${escape(__("Problem"))}</th>
			<th>${escape(__("Now"))}</th><th>${escape(__("Suggested"))}</th>
		</tr></thead><tbody>${rows}</tbody></table>
		<p class="text-muted small">${escape(help)}</p>`;
}

async function save_ticked_fixes(report, { fixes }, dialog) {
	const ticked = dialog.$wrapper.find(".quality-fix:checked").toArray();
	let saved = 0;
	for (const box of ticked) {
		const fix = fixes[Number(box.dataset.index)];
		try {
			await frappe.xcall("frappe.client.set_value", {
				doctype: fix.doctype,
				name: fix.row,
				fieldname: fix.fieldname,
				value: fix.value,
			});
			saved += 1;
		} catch (error) {
			// Frappe shows why the save was refused.
		}
	}
	if (saved) frappe.show_alert({ message: __("{0} fixes saved.", [saved]), indicator: "green" });
	report.refresh();
}
