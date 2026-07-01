// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

function parse_display_fields(raw) {
	if (!raw) return [];
	try {
		let parsed = JSON.parse(raw);
		if (Array.isArray(parsed)) return parsed;
	} catch (e) {
		return raw.split(",").map((f) => f.trim()).filter((f) => f)
			.map((f) => ({ fieldname: f, show_label: 1, is_title: 0 }));
	}
	return [];
}

function save_display_fields(frm, cdt, cdn, wrapper) {
	let entries = [];
	wrapper.find("tr[data-fieldname]").each(function () {
		let $row = $(this);
		let fieldname = $row.data("fieldname");
		let show = $row.find(".field-select-check").is(":checked");
		let show_label = $row.find(".field-label-check").is(":checked");
		let is_title = $row.find(".field-title-check").is(":checked");
		if (show) {
			entries.push({
				fieldname: fieldname,
				show_label: show_label ? 1 : 0,
				is_title: is_title ? 1 : 0,
			});
		}
	});
	frappe.model.set_value(cdt, cdn, "display_fields", JSON.stringify(entries));
	frm.dirty();
}

function build_field_row_html(df, sel, cdn) {
	const show_checked = sel ? "checked" : "";
	const is_title_checked = sel && sel.is_title ? "checked" : "";
	const label_checked = sel ? (sel.show_label ? "checked" : "") : "checked";
	const disabled = sel ? "" : "disabled";

	return `
		<tr data-fieldname="${df.fieldname}">
			<td class="field-drag-handle" style="text-align: center; cursor: grab; color: var(--text-muted); user-select: none;">⠿</td>
			<td style="text-align: center;">
				<input type="checkbox" class="field-select-check" ${show_checked}>
			</td>
			<td style="text-align: center;">
				<input type="radio" name="title-field-${cdn}" class="field-title-check" ${is_title_checked} ${disabled}>
			</td>
			<td style="text-align: center;">
				<input type="checkbox" class="field-label-check" ${label_checked} ${disabled}>
			</td>
			<td>
				${df.label || df.fieldname}
				<span style="color: var(--text-muted);">(${df.fieldname})</span>
			</td>
			<td>
				<span style="color: var(--text-muted);">${df.fieldtype}</span>
			</td>
		</tr>`;
}

function render_fields_selector(frm, cdt, cdn) {
	let row = locals[cdt][cdn];

	// Access the HTML field from the currently open grid form
	let grid_row = frm.fields_dict.slides.grid.grid_rows_by_docname[cdn];
	if (!grid_row || !grid_row.grid_form) return;

	let html_field = grid_row.grid_form.fields_dict.fields_selector;
	if (!html_field) return;
	let wrapper = html_field.$wrapper;

	if (!row.slide_type) {
		wrapper.html('<p class="text-muted">Select a Slide Type to choose display fields.</p>');
		return;
	}

	frappe.model.with_doctype(row.slide_type, function () {
		let meta = frappe.get_meta(row.slide_type);
		let displayable_fieldtypes = [
			"Data", "Text", "Text Editor", "Small Text", "Long Text",
			"Select", "Link", "Dynamic Link", "Int", "Float", "Currency",
			"Date", "Datetime", "Check", "Attach", "Attach Image", "HTML",
		];
		let fields_list = meta.fields.filter(
			(df) => displayable_fieldtypes.includes(df.fieldtype) && !df.hidden
		);

		if (!fields_list.length) {
			wrapper.html(`<p class="text-muted">No displayable fields found for ${row.slide_type}.</p>`);
			return;
		}

		let selected = parse_display_fields(row.display_fields);
		let selected_map = {};
		selected.forEach((s) => { selected_map[s.fieldname] = s; });

		// Render selected fields first (in their saved order), then unselected fields
		let selected_fields = selected
			.map((s) => fields_list.find((df) => df.fieldname === s.fieldname))
			.filter(Boolean);
		let unselected_fields = fields_list.filter((df) => !selected_map[df.fieldname]);
		let ordered_fields = [...selected_fields, ...unselected_fields];

		let table_html = `
			<table class="table table-bordered" style="margin: 0; font-size: 0.9em;">
				<thead>
					<tr>
						<th style="width: 30px;"></th>
						<th style="width: 40px; text-align: center;">Show</th>
						<th style="width: 50px; text-align: center;">Title</th>
						<th style="width: 70px; text-align: center;">Show Label</th>
						<th>Field</th>
						<th>Type</th>
					</tr>
				</thead>
				<tbody>
					${ordered_fields.map((df) => build_field_row_html(df, selected_map[df.fieldname], cdn)).join("")}
				</tbody>
			</table>`;
		wrapper.html(table_html);

		// Enable drag-to-reorder rows
		new Sortable(wrapper.find("tbody")[0], {
			handle: ".field-drag-handle",
			animation: 150,
			onEnd: function () {
				save_display_fields(frm, cdt, cdn, wrapper);
			},
		});

		wrapper.find(".field-select-check").on("change", function () {
			let $tr = $(this).closest("tr");
			let $label_check = $tr.find(".field-label-check");
			let $title_check = $tr.find(".field-title-check");
			if ($(this).is(":checked")) {
				$label_check.prop("disabled", false);
				$title_check.prop("disabled", false);
			} else {
				$label_check.prop("disabled", true).prop("checked", true);
				$title_check.prop("disabled", true).prop("checked", false);
			}
			save_display_fields(frm, cdt, cdn, wrapper);
		});

		wrapper.find(".field-label-check, .field-title-check").on("change", function () {
			save_display_fields(frm, cdt, cdn, wrapper);
		});
	});
}

frappe.ui.form.on("Sermon", {
	onload(frm) {
		// Filter slide_type to DocTypes in the church app
		church.set_church_doctype_query(frm, 'slide_type', 'slides');
	},

	refresh(frm) {
		if (frm.doc.publish) {
			frm.set_intro('🌐 This sermon is published to the public website', 'blue');
		}

		if (!frm.is_new()) {
			frm.add_custom_button(__("Present"), function () {
				function open_presentation() {
					window.open(
						"/sermon_presentation?name=" + encodeURIComponent(frm.doc.name),
						"_blank"
					);
				}
				if (frm.is_dirty()) {
					frm.save("Save", open_presentation);
				} else {
					open_presentation();
				}
			}, null, "primary");
		}
	},
});

frappe.ui.form.on("Sermon Slide", {
	form_render(frm, cdt, cdn) {
		setTimeout(() => render_fields_selector(frm, cdt, cdn), 100);
	},

	slide_type(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "display_fields", "");
		setTimeout(() => render_fields_selector(frm, cdt, cdn), 100);
	},
});
