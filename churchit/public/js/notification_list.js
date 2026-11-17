// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Each row shows the notification's name, as the manuals call it, and not its subject template.
frappe.listview_settings["Notification"] = Object.assign(
	frappe.listview_settings["Notification"] || {},
	{
		hide_name_column: true,
		formatters: { subject: (value, df, doc) => frappe.utils.escape_html(doc.name) },
		before_render() {
			// The header follows the cells. A copy of the field, so the form keeps its Subject label.
			const subject = cur_list?.doctype === "Notification" && cur_list.columns?.[0];
			if (subject?.type === "Subject" && subject.df?.fieldname === "subject") {
				subject.df = { ...subject.df, label: __("Name") };
			}
		},
	}
);
