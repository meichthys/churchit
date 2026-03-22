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
					${__("Delete Sample Data")}
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
		frappe.confirm(
			__("Are you sure you want to permanently delete all sample data?"),
			function () {
				frappe.call({
					method: "church.setup.sample_data.delete",
					freeze: true,
					freeze_message: __("Removing sample data..."),
					callback: function () {
						frappe.show_alert({
							message: __("Sample data has been removed."),
							indicator: "green",
						});
					},
				});
			}
		);
	});
};
