frappe.query_reports["Visitation Followups Needed"] = {
	filters: [],

	formatter: function (value, row, column, data) {
		if (!data || !value) return value;
		if (column.fieldname === "person") {
			return `<a href="/app/person/${encodeURIComponent(data.person)}">${frappe.utils.escape_html(value)}</a>`;
		}
		return value;
	},
};
