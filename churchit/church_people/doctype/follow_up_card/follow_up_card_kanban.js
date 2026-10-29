// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.kanban_v2.settings["Follow-up Card"] = {
	callbacks: {
		// A move hands the card to the new step's person and restarts its due date on the server, but the
		// board keeps only the new column from the save. Frappe gives move callbacks no board handle, so
		// the open board is reached through its view, and reloads once the move has settled.
		onAfterCardMove() {
			setTimeout(() => {
				if (cur_list?.doctype === "Follow-up Card") cur_list._kanban?.board?.refresh();
			});
		},
	},
};
