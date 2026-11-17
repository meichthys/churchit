// The list page of a portal web form. frappe shows a form's introduction only
// on the form itself and names the doctype in an empty list ("No Room Booking
// found"). Its list template has no slot for either and runs no client
// script, so this loaded-everywhere script shows the introduction above the
// list and words the empty list plainly. It does nothing on other pages.
(function () {
	frappe.ready(function () {
		const container = document.querySelector(".web-list-container");
		const web_form = frappe.web_form_doc;
		if (!container || !web_form) return;

		hideSecondsInDatetimes();

		// website.css hides the selection boxes of a list that cannot delete. frappe adds its
		// Delete button only for the doctype's delete right, which a member's right to delete
		// their own records is not, so ask the same question.
		container.classList.add("web-list-without-delete");
		if (web_form.allow_delete && !web_form.web_form_request_key) {
			frappe.has_permission(web_form.doc_type, "", "delete", () =>
				container.classList.remove("web-list-without-delete")
			);
		}

		if (web_form.introduction_text) {
			const introduction = document.createElement("div");
			introduction.className = "web-list-introduction";
			introduction.innerHTML = __(web_form.introduction_text);
			container.querySelector(".web-list-header").appendChild(introduction);
		}

		// frappe draws the empty list after its permission call returns
		const table = container.querySelector(".web-list-table");
		new MutationObserver(() => relabelEmptyList(table)).observe(table, {
			childList: true,
			subtree: true,
		});
	});

	// The list cells follow the System Settings time format, which has seconds. Desk is untouched.
	function hideSecondsInDatetimes() {
		const formatters = frappe.form && frappe.form.formatters;
		if (!formatters || !formatters.Datetime) return;

		formatters.Datetime = function (value) {
			if (!value) return "";
			const time_format = (frappe.boot.sysdefaults.time_format || "HH:mm:ss").replace(
				/[:.]ss/,
				""
			);
			return moment(frappe.datetime.convert_to_user_tz(value)).format(
				frappe.boot.sysdefaults.date_format.toUpperCase() + " " + time_format
			);
		};
	}

	function relabelEmptyList(table) {
		const message = table.querySelector(".no-result p");
		if (!message || message.textContent === __("Nothing here yet.")) return;

		message.textContent = __("Nothing here yet.");
		const button = table.querySelector(".no-result .btn-new-doc");
		if (button) button.textContent = __("New");
	}
})();
