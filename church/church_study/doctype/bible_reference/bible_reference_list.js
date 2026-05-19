frappe.listview_settings["Bible Reference"] = {
	onload(listview) {
		if (!church.bible_memory.can_assign()) return;
		listview.page.add_action_item(__("Assign to User for Memorization"), () =>
			run_assign(listview, "user")
		);
		listview.page.add_action_item(__("Assign to Group for Memorization"), () =>
			run_assign(listview, "group")
		);

		function run_assign(listview, mode) {
			const selected = listview.get_checked_items();
			if (!selected.length) {
				frappe.msgprint(__("Select at least one reference."));
				return;
			}
			church.bible_memory.open_assign_dialog(
				selected.map((s) => s.name),
				mode,
				() => listview.refresh()
			);
		}
	},
};
