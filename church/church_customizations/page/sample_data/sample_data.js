frappe.pages["sample-data"].on_page_show = function (wrapper) {
	if (wrapper._page_built) return;
	wrapper._page_built = true;

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Sample Data"),
		single_column: true,
	});

	const $container = $(`
		<div class="sample-data-page" style="max-width: 600px; margin: 40px auto;">
			<p style="font-size: var(--text-lg); color: var(--text-muted);">
				${__(
					"Sample data lets you explore the Church app with a pre-populated " +
					"church, people, families, missionaries, funds, collections, expenses, " +
					"prayer requests, functions, sermons, beliefs, and related Bible study data."
				)}
			</p>
			<div class="mt-3">
				<button class="btn btn-primary btn-md btn-create-sample-data">
					${__("Create Sample Data")}
				</button>
				<button class="btn btn-danger btn-md ml-2 btn-delete-sample-data">
					${__("Delete All Data")}
				</button>
			</div>
			<div class="mt-4">
				<a href="/app/welcome" class="btn btn-default btn-md">
					${__("Back to Welcome")}
				</a>
			</div>
		</div>
	`);

	$(page.body).html($container);

	$container.find(".btn-create-sample-data").on("click", function () {
		frappe.confirm(
			__("This will create sample records. Continue?"),
			function () {
				frappe.call({
					method: "church.setup.sample_data.create",
					freeze: true,
					freeze_message: __("Creating sample data..."),
					callback: function () {
						frappe.show_alert({
							message: __("Sample data has been created."),
							indicator: "green",
						});
					},
				});
			}
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
						<div style="color: var(--red-600); margin-bottom: 12px;">
							<p style="margin-bottom: 8px;"><strong>🛑 This cannot be undone.</strong></p>
							<p style="margin-bottom: 8px;">This will permanently delete <strong>ALL</strong> records in:</p>
							<p style="margin-bottom: 8px;">
								Persons, Families, Missionaries, Prayer Requests, Functions,
								Collections, Expenses, Funds, Bible Memory, Help Articles
								<em>…and more.</em>
							</p>
							<p style="margin-bottom: 0;">Any data you created after installation will <strong>also be deleted</strong>.</p>
						</div>
					`,
				},
				{
					fieldtype: "Data",
					fieldname: "confirm_phrase",
					label: __('Type <code>{0}</code> to confirm', [confirm_phrase]),
					reqd: 1,
				},
			],
			primary_action_label: __("Delete All Data"),
			primary_action(values) {
				if ((values.confirm_phrase || "").trim() !== confirm_phrase) {
					frappe.msgprint({
						title: __("Confirmation phrase doesn't match"),
						indicator: "orange",
						message: __('Please type <code>{0}</code> exactly to confirm.', [confirm_phrase]),
					});
					return;
				}
				dialog.hide();
				frappe.call({
					method: "church.setup.sample_data.delete",
					freeze: true,
					freeze_message: __("Deleting all data..."),
					callback: function () {
						frappe.show_alert({
							message: __("All data has been deleted."),
							indicator: "green",
						});
					},
				});
			},
		});
		dialog.show();
		dialog.get_primary_btn().removeClass("btn-primary").addClass("btn-danger");
	});
};
