window.church = window.church || {};

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

// Make Script Report Link cells show the linked doc's title while staying clickable.
//
// Reports built on `church.utils.set_report_link_titles` ship a
// `_<fieldname>_link_title` key on each row. Wrap the desk's Link formatter so
// it reads that key, primes `frappe._link_titles`, and the standard `<a>` tag
// it builds shows the title instead of the hash name.
(function patchLinkFormatterForReportTitles() {
	if (!window.frappe || !frappe.form || !frappe.form.formatters) return;
	const original = frappe.form.formatters.Link;
	if (!original || original._churchTitlePatched) return;

	const patched = function(value, docfield, options, doc) {
		if (doc && docfield && docfield.fieldname && value) {
			const title = doc[`_${docfield.fieldname}_link_title`];
			const doctype = (docfield._options || docfield.options);
			if (title && doctype && frappe.utils && frappe.utils.add_link_title) {
				frappe.utils.add_link_title(doctype, value, title);
			}
		}
		return original(value, docfield, options, doc);
	};
	patched._churchTitlePatched = true;
	frappe.form.formatters.Link = patched;
})();
