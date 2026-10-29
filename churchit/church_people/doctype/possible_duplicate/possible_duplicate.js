// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ui.form.on("Possible Duplicate", {
	refresh(frm) {
		render_comparison(frm);
		if (frm.doc.status !== "Open") return;

		if (frappe.model.can_delete("Person")) {
			frm.add_custom_button(__("Merge"), () => choose_person_to_keep(frm));
		}
		if (frm.has_perm("write")) {
			frm.add_custom_button(__("Not a Duplicate"), () => {
				frm.set_value("status", "Not a Duplicate");
				frm.save();
			});
		}
	},
});

// [field, label, fieldtype], in the order the form shows them.
const COMPARED_FIELDS = [
	["full_name", __("Name")],
	["nickname", __("Nickname")],
	["birth_date", __("Birth Date"), "Date"],
	["gender", __("Gender")],
	["family_name", __("Family")],
	["membership", __("Membership")],
	["membership_status", __("Status")],
	["church", __("Church")],
	["emails", __("Emails")],
	["phones", __("Phone Numbers")],
	["addresses", __("Addresses")],
	["last_attended_on", __("Last Attended"), "Date"],
	["creation", __("Added On"), "Datetime"],
];

function render_comparison(frm) {
	const people = frm.doc.__onload?.people || {};
	const names = [frm.doc.person, frm.doc.other_person];
	const fields = COMPARED_FIELDS.filter(
		([field]) => field !== "church" || frappe.boot.churchit?.multi_church
	);

	const header = names
		.map((name) => {
			const label = frappe.utils.escape_html(people[name]?.full_name || name);
			return `<th>${frappe.utils.get_form_link("Person", name, true, label)}</th>`;
		})
		.join("");
	const rows = fields.map(([field, label, fieldtype]) => {
		const values = names.map((name) =>
			people[name] ? format_value(people[name][field], fieldtype) : ""
		);
		const muted = values[0] === values[1] ? "text-muted" : "";
		const cells = values.map((value) => `<td>${value}</td>`).join("");
		return `<tr class="${muted}"><th scope="row">${label}</th>${cells}</tr>`;
	});
	const unreadable = names.some((name) => !people[name])
		? `<p class="text-muted">${__("You cannot see one of these people.")}</p>`
		: "";

	frm.get_field("comparison").$wrapper.html(`
		${unreadable}
		<table class="table table-bordered">
			<thead><tr><th></th>${header}</tr></thead>
			<tbody>${rows.join("")}</tbody>
		</table>`);
}

function format_value(value, fieldtype) {
	if (Array.isArray(value)) {
		return value.map((item) => frappe.utils.escape_html(item)).join("<br>");
	}
	if (value === null || value === undefined || value === "") return "";
	if (fieldtype) return frappe.format(value, { fieldtype });
	return frappe.utils.escape_html(String(value));
}

function choose_person_to_keep(frm) {
	const people = frm.doc.__onload?.people || {};
	const option = (name) => ({
		value: name,
		label: `${people[name]?.full_name || name} (${name})`,
	});
	const dialog = new frappe.ui.Dialog({
		title: __("Merge People"),
		fields: [
			{
				fieldname: "keep",
				fieldtype: "Select",
				label: __("Person to Keep"),
				options: [option(frm.doc.person), option(frm.doc.other_person)],
				default: frm.doc.person,
				reqd: 1,
				description: __(
					"The other person is merged into this one. Everything that names them moves to the person you keep, and their record is deleted. You cannot undo this."
				),
				onchange: () => show_choices(),
			},
			{ fieldname: "choices", fieldtype: "HTML" },
		],
		primary_action_label: __("Merge"),
		primary_action({ keep }) {
			const take_from_removed = churchit.merge_choices.get_taken(choices());
			dialog.hide();
			frappe
				.call({
					method: "churchit.church_people.merge.merge_people",
					args: { keep, remove: other(keep), take_from_removed },
					freeze: true,
					freeze_message: __("Merging..."),
				})
				.then(() => frm.reload_doc());
		},
	});
	const other = (keep) => (keep === frm.doc.person ? frm.doc.other_person : frm.doc.person);
	const choices = () => dialog.get_field("choices").$wrapper;
	const show_choices = () => {
		const keep = dialog.get_value("keep");
		churchit.merge_choices.render(choices(), keep, other(keep));
	};
	dialog.show();
	show_choices();
}
