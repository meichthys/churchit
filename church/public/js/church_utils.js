window.church = window.church || {};

// Bible Memory assignment helpers. Used by both the Bible Reference form and
// list view to open a small picker (user or group) that calls the server's
// assign_memory endpoint and surfaces created/skipped/missing-user counts.
church.bible_memory = church.bible_memory || {};

church.bible_memory.can_assign = function() {
	const roles = frappe.user_roles || [];
	return (
		roles.includes('Church Manager') ||
		roles.includes('System Manager') ||
		roles.includes('Administrator')
	);
};

church.bible_memory.open_assign_dialog = function(references, mode, on_done) {
	const is_group = mode === 'group';
	const dialog = new frappe.ui.Dialog({
		title: is_group
			? __('Assign to Group for Memorization')
			: __('Assign to User for Memorization'),
		fields: [
			is_group
				? {
					fieldtype: 'Link',
					fieldname: 'group',
					label: __('Group'),
					options: 'Group',
					reqd: 1,
				}
				: {
					fieldtype: 'Link',
					fieldname: 'user',
					label: __('User'),
					options: 'User',
					reqd: 1,
					get_query: () => ({ filters: { enabled: 1 } }),
				},
		],
		primary_action_label: __('Assign'),
		primary_action(values) {
			const args = { references };
			if (is_group) args.group = values.group;
			else args.users = [values.user];
			frappe.call({
				method: 'church.church_study.bible_api.assign_memory',
				args,
				freeze: true,
				freeze_message: __('Assigning…'),
			}).then(r => {
				if (r && !r.exc) {
					const { created = 0, skipped = 0, missing_users = [] } = r.message || {};
					frappe.show_alert({
						message: __('{0} new item(s) created, {1} already existed.', [created, skipped]),
						indicator: 'green',
					}, 5);
					if (missing_users.length) {
						frappe.msgprint({
							title: __('Skipped — no App User'),
							indicator: 'orange',
							message: __('The following group members have no linked App User and were not assigned:<br><br>{0}',
								[missing_users.join('<br>')]),
						});
					}
					dialog.hide();
					if (typeof on_done === 'function') on_done();
				}
			});
		},
	});
	dialog.show();
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
