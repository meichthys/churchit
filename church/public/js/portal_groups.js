// Injects a "+ Join a public group" button into the /groups Web Form
// list header. The Web Form list view doesn't run client_script, so a
// loaded-everywhere script is the only entry point for this UI hook.
(function () {
	const path = window.location.pathname.replace(/\/$/, "");
	if (path !== "/groups" && path !== "/groups/list") return;

	// Portal pages don't ship the desk's tooltip CSS, so Frappe's
	// auto-rendered .tooltip-content span (containing the fieldname)
	// leaks into the dialog as visible text. Suppress it.
	const style = document.createElement("style");
	style.textContent = ".modal .tooltip-content { display: none !important; }";
	document.head.appendChild(style);

	function openPicker() {
		frappe
			.call({ method: "church.church_people.group_api.joinable_public_groups" })
			.then((r) => {
				const groups = (r && r.message) || [];
				if (!groups.length) {
					frappe.msgprint({
						title: __("Nothing to join"),
						message: __("There are no public groups available to join right now."),
					});
					return;
				}
				const labels = groups.map((g) => g.group_name);
				const dialog = new frappe.ui.Dialog({
					title: __("Join a public group"),
					fields: [
						{
							fieldtype: "Select",
							fieldname: "group",
							label: __("Group"),
							options: labels.join("\n"),
							reqd: 1,
						},
					],
					primary_action_label: __("Join"),
					primary_action(values) {
						const chosen = groups.find((g) => g.group_name === values.group);
						if (!chosen) return;
						frappe
							.call({
								method: "church.church_people.group_api.join_group",
								args: { group: chosen.name },
							})
							.then((rr) => {
								if (rr && !rr.exc) {
									frappe.show_alert({ message: __("Joined!"), indicator: "green" }, 3);
									dialog.hide();
									setTimeout(() => window.location.reload(), 700);
								}
							});
					},
				});
				dialog.show();
			});
	}

	function place() {
		const actions = document.querySelector(".web-list-actions");
		if (!actions || actions.querySelector(".group-join-action")) return false;
		const btn = document.createElement("button");
		btn.className = "btn btn-primary btn-sm group-join-action";
		btn.textContent = "+ Join a public group";
		btn.addEventListener("click", openPicker);
		actions.appendChild(btn);
		return true;
	}

	if (place()) return;
	let tries = 0;
	const t = setInterval(() => {
		if (place() || ++tries > 50) clearInterval(t);
	}, 100);
})();
