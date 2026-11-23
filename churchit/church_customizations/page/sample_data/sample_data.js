frappe.pages["sample-data"].on_page_show = function (wrapper) {
	if (wrapper._page_built) return;
	wrapper._page_built = true;

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Sample Data"),
		single_column: true,
	});

	const $container = $(`
		<div class="sample-data-page" style="max-width: 600px; margin: 40px auto; padding: 0 var(--padding-md);">
			<p style="font-size: var(--text-lg); color: var(--text-muted);">
				${__(
					"Sample data lets you explore Churchit with a pre-populated church: people and families, groups, follow-up, missionaries, giving and pledges, expenses, prayer requests, functions with paid sign-ups, forms, songs, rooms and equipment, tasks, sermons with handouts, bulletins, a members-only web page, and related Bible study data.",
				)}
			</p>
			<div class="alert alert-warning">
				<p>${__(
					"Demo logins use their email address as the password. Do not use sample data on a site that people can reach from the internet.",
				)}</p>
				<p class="mb-0">${__(
					"To start fresh, click Delete All Data. It removes the sample records, the demo logins and every record you added.",
				)}</p>
			</div>
			<p class="sample-data-status font-weight-bold"></p>
			<div class="mt-3 sample-data-buttons">
				<button class="btn btn-primary btn-md btn-create-sample-data" style="display: none;">
					${__("Create Sample Data")}
				</button>
				<button class="btn btn-danger btn-md btn-delete-sample-data" style="display: none;">
					${__("Delete All Data")}
				</button>
			</div>
			<div class="mt-4">
				<a href="/desk/summary" class="btn btn-default btn-md">
					${__("Back to Summary")}
				</a>
			</div>
		</div>
	`);

	$(page.body).html($container);

	const show_status = () =>
		frappe
			.xcall("churchit.setup.sample_data.get_status", {}, "GET")
			.then((status) => {
				let message = status.is_loaded
					? __("Sample data is loaded.")
					: __("No sample data.");
				if (!status.can_change) {
					message +=
						" " +
						__(
							"Only a System Manager can create or delete sample data.",
						);
				}
				$container.find(".sample-data-status").text(message);
				$container
					.find(".btn-create-sample-data")
					.toggle(status.can_change && !status.is_loaded);
				$container
					.find(".btn-delete-sample-data")
					.toggle(status.can_change && status.is_loaded);
			});
	show_status();

	$container.find(".btn-create-sample-data").on("click", function () {
		frappe.confirm(
			__("This will create sample records. Continue?"),
			function () {
				frappe.call({
					method: "churchit.setup.sample_data.create",
					freeze: true,
					freeze_message: __("Creating sample data..."),
					callback: function () {
						frappe.show_alert({
							message: __("Sample data has been created."),
							indicator: "green",
						});
						show_status();
					},
				});
			},
		);
	});

	$container.find(".btn-delete-sample-data").on("click", function () {
		const confirm_phrase = "DELETE ALL DATA";
		const dialog = new frappe.ui.Dialog({
			title: __("Permanently Delete All Data?"),
			fields: [
				{
					fieldtype: "HTML",
					options: `
						<div style="color: var(--ink-red-7); margin-bottom: 12px;">
							<p style="margin-bottom: 8px;"><strong>🛑 This cannot be undone.</strong></p>
							<p style="margin-bottom: 8px;">This will permanently delete <strong>ALL</strong> records in:</p>
							<p style="margin-bottom: 8px;">
								Persons, Families, Groups, Missionaries, Prayer Requests, Functions,
								Question Sets, Collections, Pledges, Expenses, Funds, Sermon Handouts,
								Bible Memory <em>…and more.</em>
							</p>
							<p style="margin-bottom: 0;">Any data you created after installation will <strong>also be deleted</strong>.</p>
						</div>
					`,
				},
				{
					fieldtype: "Data",
					fieldname: "confirm_phrase",
					label: __("Type <code>{0}</code> to confirm", [
						confirm_phrase,
					]),
					reqd: 1,
				},
			],
			primary_action_label: __("Delete All Data"),
			primary_action(values) {
				if ((values.confirm_phrase || "").trim() !== confirm_phrase) {
					frappe.msgprint({
						title: __("Confirmation phrase doesn't match"),
						indicator: "orange",
						message: __(
							"Please type <code>{0}</code> exactly to confirm.",
							[confirm_phrase],
						),
					});
					return;
				}
				dialog.hide();
				frappe.call({
					method: "churchit.setup.sample_data.delete",
					freeze: true,
					freeze_message: __("Deleting all data..."),
					callback: function () {
						frappe.show_alert({
							message: __("All data has been deleted."),
							indicator: "green",
						});
						show_status();
					},
				});
			},
		});
		dialog.show();
		dialog
			.get_primary_btn()
			.removeClass("btn-primary")
			.addClass("btn-danger");
	});
};
