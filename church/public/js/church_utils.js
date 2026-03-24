window.church = window.church || {};

// Cache the church count so we only fetch it once per page load.
church._church_count = null;
church._get_church_count = function() {
	if (church._church_count !== null) {
		return Promise.resolve(church._church_count);
	}
	return frappe.db.count("Church").then(count => {
		church._church_count = count;
		return count;
	});
};

// Hide the `church` field on all forms when there is only one church in the system.
// use the document-level "form-refresh" event that Frappe fires after every form render instead.
$(document).on("form-refresh", function(_e, frm) {
	if (!frm.fields_dict.church) return;
	church._get_church_count().then(count => {
		frm.toggle_display("church", count > 1);
	});
});

// Returns standard church + include_sub_churches filter definitions for Script Reports.
church.get_church_report_filters = function() {
	return [
		{
			fieldname: "church",
			label: __("Church"),
			fieldtype: "Link",
			options: "Church",
		},
		{
			fieldname: "include_sub_churches",
			label: __("Include Sub-Churches"),
			fieldtype: "Check",
			default: 0,
			depends_on: "eval:doc.church",
		},
	];
};

// Sets up a Script Report with default church value and hides church filters when only one church exists.
church.setup_church_report = function(report) {
	const default_church = frappe.defaults.get_user_default("church");
	if (default_church) {
		report.set_filter_value("church", default_church);
	}
	church._get_church_count().then(count => {
		if (count <= 1) {
			if (report.page.fields_dict.church) {
				report.page.fields_dict.church.toggle(false);
			}
			if (report.page.fields_dict.include_sub_churches) {
				report.page.fields_dict.include_sub_churches.toggle(false);
			}
		}
	});
};

// Sets a query filter on a DocType link field to only show DocTypes belonging to the church app.
// fieldname: the Link field to filter
// child_table: (optional) the child table fieldname if the field is in a child doctype
church.set_church_doctype_query = function(frm, fieldname, child_table) {
	frappe.db.get_list('Module Def', {
		filters: { app_name: 'church' },
		fields: ['name'],
		limit: 0
	}).then(modules => {
		const module_names = modules.map(m => m.name);
		const query = function() {
			return {
				filters: [['DocType', 'module', 'in', module_names]]
			};
		};
		if (child_table) {
			frm.set_query(fieldname, child_table, query);
		} else {
			frm.set_query(fieldname, query);
		}
	});
};
