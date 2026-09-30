window.church = window.church || {};

// Bible Memory assignment helpers. Used by both the Bible Reference form and
// list view to open a small picker (user or group) that calls the server's
// assign_memory endpoint and surfaces created/skipped/missing-user counts.
church.bible_memory = church.bible_memory || {};

church.bible_memory.can_assign = function () {
	const roles = frappe.user_roles || [];
	return (
		roles.includes("Church Manager") ||
		roles.includes("System Manager") ||
		roles.includes("Administrator")
	);
};

church.bible_memory.open_assign_dialog = function (references, mode, on_done) {
	const is_group = mode === "group";
	const dialog = new frappe.ui.Dialog({
		title: is_group
			? __("Assign to Group for Memorization")
			: __("Assign to User for Memorization"),
		fields: [
			is_group
				? {
						fieldtype: "Link",
						fieldname: "group",
						label: __("Group"),
						options: "Group",
						reqd: 1,
				  }
				: {
						fieldtype: "Link",
						fieldname: "user",
						label: __("User"),
						options: "User",
						reqd: 1,
						get_query: () => ({ filters: { enabled: 1 } }),
				  },
		],
		primary_action_label: __("Assign"),
		primary_action(values) {
			const args = { references };
			if (is_group) args.group = values.group;
			else args.users = [values.user];
			frappe
				.call({
					method: "churchit.church_study.bible_api.assign_memory",
					args,
					freeze: true,
					freeze_message: __("Assigning…"),
				})
				.then((r) => {
					if (r && !r.exc) {
						const { created = 0, skipped = 0, missing_users = [] } = r.message || {};
						frappe.show_alert(
							{
								message: __("{0} new item(s) created, {1} already existed.", [
									created,
									skipped,
								]),
								indicator: "green",
							},
							5
						);
						if (missing_users.length) {
							frappe.msgprint({
								title: __("Skipped: no Portal User"),
								indicator: "orange",
								message: __(
									"The following group members have no linked Portal User and were not assigned:<br><br>{0}",
									[missing_users.join("<br>")]
								),
							});
						}
						dialog.hide();
						if (typeof on_done === "function") on_done();
					}
				});
		},
	});
	dialog.show();
};

// Multi-church helpers. frappe.boot.churchit comes from churchit.church_scope.extend_bootinfo.
church.is_multi_church = function () {
	return Boolean(frappe.boot.churchit && frappe.boot.churchit.multi_church);
};

// Report filter for the church, only once branches exist and the user can see
// more than one. Spread it into a report's `filters`:
// `filters: [...church.report_filters(), ...]`. It starts on the user's own
// church (the main church for unrestricted users) and is left blank for a user
// who has chosen to include branch churches.
church.report_filters = function () {
	if (!church.is_multi_church()) return [];
	const boot = frappe.boot.churchit;
	if (boot.single_church) return [];
	return [
		{
			fieldname: "church",
			label: __("Church"),
			fieldtype: "Link",
			options: "Church",
			default: boot.include_branches ? null : boot.church,
		},
	];
};

// User-menu switch (hooks.py standard_navbar_items) for parent-church users.
church.toggle_branch_churches = function () {
	const include = !frappe.boot.churchit.include_branches;
	frappe.confirm(
		include
			? __("Include branch churches in your lists, reports and dashboards?")
			: __("Show only your own church again?"),
		() => {
			frappe
				.xcall("churchit.church_foundations.church_access.set_include_branches", {
					include,
				})
				.then(() => window.location.reload());
		}
	);
};

// A user who can see one church only never needs to pick it. The form hides the
// field through its own `depends_on`, which the layout resolves while it renders;
// hiding it here instead let it paint first and then vanish. desk.css hides the
// matching list filter, which has no `depends_on` of its own.
church.has_church_field = function (frm) {
	const field = frappe.meta.get_docfield(frm.doctype, "church", frm.doc.name);
	return Boolean(field && field.options === "Church");
};

// Fill the church in before the user ever sees the form. An empty church means
// "shared with every church", so a new record must never look empty while it is
// simply unsaved.
church.prefill_church = function (frm) {
	if (!church.is_multi_church() || !frm.is_new() || frm.doc.church) return;
	if (church.has_church_field(frm) && frappe.boot.churchit.church) {
		frm.set_value("church", frappe.boot.churchit.church);
	}
};

// Say when a shared record came from another church, and match the server guard by
// locking the checkbox. A shared record looks identical whoever shared it, so
// without this the only clue is the PermissionError you get after unticking it.
church.note_shared_by_another_church = function (frm) {
	const owner = frm.doc.is_shared ? frm.doc.shared_by_church : null;
	const mine = church.is_multi_church() ? frappe.boot.churchit.churches : null;
	const from_another_church = Boolean(owner && mine && !mine.includes(owner));

	if (frm.__churchit_shared_note && !from_another_church) {
		frm.set_intro();
		frm.__churchit_shared_note = false;
	}
	if (!from_another_church) return;

	frm.set_df_property("is_shared", "read_only", 1);
	frm.__churchit_shared_note = true;

	const note = (name) =>
		frm.set_intro(
			__("Shared with your church by {0}. Only they can stop sharing it.", [name]),
			"blue"
		);
	const title = frappe.utils.get_link_title("Church", owner);
	if (title) {
		note(title);
	} else {
		frappe.utils.fetch_link_title("Church", owner).then(note);
	}
};

frappe.ui.form.on("*", {
	onload: church.prefill_church,
	refresh: church.note_shared_by_another_church,
});

// Every church reads the people directory, but only a person's own church may
// change them. The server refuses the save either way; this says so up front.
church.lock_another_churchs_people = function (frm) {
	const mine = church.is_multi_church() ? frappe.boot.churchit.churches : null;
	const theirs = Boolean(
		mine && !frm.is_new() && frm.doc.church && !mine.includes(frm.doc.church)
	);

	if (frm.__churchit_people_lock && !theirs) {
		frm.set_intro();
		frm.__churchit_people_lock = false;
	}
	if (!theirs) return;

	frm.disable_form();
	frm.__churchit_people_lock = true;
	const note = (name) =>
		frm.set_intro(__("This belongs to {0}. Only that church can change it.", [name]), "blue");
	const title = frappe.utils.get_link_title("Church", frm.doc.church);
	if (title) {
		note(title);
	} else {
		frappe.utils.fetch_link_title("Church", frm.doc.church).then(note);
	}
};

frappe.ui.form.on("Person", { refresh: church.lock_another_churchs_people });
frappe.ui.form.on("Family", { refresh: church.lock_another_churchs_people });

// Persistent note while branch churches are included, in the same spot and
// style as Frappe's own announcement widget at the top of the desk.
church.show_branches_banner = function () {
	if (!church.is_multi_church() || frappe.boot.churchit.include_branches !== true) return;
	if ($("header .churchit-branches-banner").length) return;
	const expand = frappe.boot.churchit.expand_church_filters ? "checked" : "";
	const banner = $(`
		<div class="churchit-branches-banner announcement-widget form-message blue">
			<div class="container flex justify-between align-center mx-auto">
				<span>${__(
					"Branch churches are included: lists, reports and dashboards show every church you can see."
				)}</span>
				<span class="churchit-banner-actions">
					<label class="churchit-expand-filters" title="${__(
						"When a church is picked in a list or report Church filter, also show the records of its branches. Remembered for you only."
					)}">
						<input type="checkbox" ${expand}>
						${__("Expand filters to branches")}
					</label>
					<a href="#" class="churchit-hide-branches">${__("Hide Branch Churches")}</a>
				</span>
			</div>
		</div>`);
	banner.find(".churchit-expand-filters input").on("change", (event) => {
		frappe
			.xcall("churchit.church_foundations.church_access.set_church_filter_expansion", {
				expand: event.target.checked,
			})
			.then(() => window.location.reload());
	});
	banner.find(".churchit-hide-branches").on("click", (event) => {
		event.preventDefault();
		church.toggle_branch_churches();
	});
	$("header").prepend(banner);
};

// With "Expand filters to branches" on, a church picked in a list view's Church
// filter is sent as Frappe's own tree operator, so the list (and report view,
// kanban and calendar, which build their filters here too) shows the branches
// as well. User permissions still apply on top. Falls back to exact matching
// if a Frappe upgrade moves the hook.
(function expandListChurchFilters() {
	const base = frappe.views && frappe.views.BaseList && frappe.views.BaseList.prototype;
	if (!base || !base.get_filters_for_args || base.get_filters_for_args._churchPatched) return;
	const original = base.get_filters_for_args;
	const patched = function () {
		const filters = original.call(this);
		if (!church.is_multi_church() || !frappe.boot.churchit.expand_church_filters)
			return filters;
		return filters.map((filter) => {
			const [doctype, fieldname, operator, value] = filter;
			const field = frappe.meta.get_docfield(doctype, fieldname);
			if (operator === "=" && value && field && field.options === "Church") {
				return [doctype, fieldname, "descendants of (inclusive)", value];
			}
			return filter;
		});
	};
	patched._churchPatched = true;
	base.get_filters_for_args = patched;
})();

$(document).on("toolbar_setup", () => {
	if (church.is_multi_church() && frappe.boot.churchit.single_church) {
		$("body").addClass("churchit-one-church");
	}
	church.show_branches_banner();
});

// Sets a query filter on a DocType link field to only show DocTypes belonging to the church app.
// fieldname: the Link field to filter
// child_table: (optional) the child table fieldname if the field is in a child doctype
church.set_church_doctype_query = function (frm, fieldname, child_table) {
	frappe.db
		.get_list("Module Def", {
			filters: { app_name: "churchit" },
			fields: ["name"],
			limit: 0,
		})
		.then((modules) => {
			const module_names = modules.map((m) => m.name);
			const query = function () {
				return {
					filters: [["DocType", "module", "in", module_names]],
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
// Reports built on `churchit.utils.set_report_link_titles` ship a
// `_<fieldname>_link_title` key on each row. Wrap the desk's Link formatter so
// it reads that key, primes `frappe._link_titles`, and the standard `<a>` tag
// it builds shows the title instead of the hash name.
(function patchLinkFormatterForReportTitles() {
	if (!window.frappe || !frappe.form || !frappe.form.formatters) return;
	const original = frappe.form.formatters.Link;
	if (!original || original._churchTitlePatched) return;

	const patched = function (value, docfield, options, doc) {
		if (doc && docfield && docfield.fieldname && value) {
			const title = doc[`_${docfield.fieldname}_link_title`];
			const doctype = docfield._options || docfield.options;
			if (title && doctype && frappe.utils && frappe.utils.add_link_title) {
				frappe.utils.add_link_title(doctype, value, title);
			}
		}
		return original(value, docfield, options, doc);
	};
	patched._churchTitlePatched = true;
	frappe.form.formatters.Link = patched;
})();
