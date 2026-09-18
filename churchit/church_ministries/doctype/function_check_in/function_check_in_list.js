frappe.listview_settings["Function Check-In"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Check-In Station"), () => frappe.set_route("check-in"));
		listview.page.add_action_item(__("Print Name Tags"), () => {
			const check_ins = listview.get_checked_items().map((row) => row.name);
			if (!check_ins.length) return frappe.msgprint(__("Select at least one check-in."));
			church.name_tags.print_for({ check_ins });
		});
		listview.page.add_inner_message(
			`<div style="background: var(--yellow-highlight-color); padding: \
            8px 12px; border-radius: 6px; display: inline-block;">
                💡 Tip: Use the <a href="/app/check-in"><strong>Check-In Station</strong></a> \
                to check people in by name or phone and print name tags, or open the \
                <a href="/app/person"><strong>Person list</strong></a>, select people and \
                choose <i>Actions → Check In</i>.
            </div>`
		);
	},
};
