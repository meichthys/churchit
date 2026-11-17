frappe.ready(function () {
	var recipient_ctrl = frappe.web_form.fields_dict["recipient"];
	var type_ctrl = frappe.web_form.fields_dict["recipient_type"];

	// The read view draws its fields without an input, so there is nothing to search from
	if (recipient_ctrl && type_ctrl && recipient_ctrl.$input) {
		var $input = recipient_ctrl.$input;
		var $wrap = recipient_ctrl.$wrapper;
		var real_name = (frappe.web_form.doc && frappe.web_form.doc.recipient) || "";

		// Override get_value so the form submits the document name, not the display label
		var original_get_value = recipient_ctrl.get_value.bind(recipient_ctrl);
		recipient_ctrl.get_value = function () {
			return real_name || original_get_value();
		};

		// A name typed without a click on the list has no record behind it
		frappe.web_form.validate = function () {
			if (real_name || !$input.val()) return true;
			frappe.msgprint({
				message: __("Choose who it is for from the list that shows as you type."),
				indicator: "orange",
			});
			return false;
		};

		// Custom dropdown for searching recipients by label; styled in website.css
		var $dd = $('<ul class="recipient-search-results">').hide();
		$wrap.css("position", "relative").append($dd);

		var timer;
		var search = function (term) {
			var doctype = type_ctrl.get_value();
			if (!doctype) {
				$dd.empty().hide();
				return;
			}

			clearTimeout(timer);
			timer = setTimeout(function () {
				frappe.call({
					method: "churchit.church_website.api.search_church_recipient",
					type: "GET",
					args: { doctype: doctype, txt: term || "" },
					callback: function (r) {
						$dd.empty().hide();
						var results = r.message || [];
						results.forEach(function (d) {
							$("<li>")
								.text(d.label)
								.on("mousedown", function (e) {
									e.preventDefault();
									real_name = d.name;
									$input.val(d.label);
									$dd.hide();
								})
								.appendTo($dd);
						});
						if (results.length) $dd.show();
					},
				});
			}, 250);
		};

		$input.on("input", function () {
			real_name = "";
			search($(this).val());
		});
		$input.on("focus", function () {
			search($(this).val());
		});
		$input.on("blur", function () {
			setTimeout(function () {
				$dd.hide();
			}, 200);
		});

		frappe.web_form.on("recipient_type", function () {
			real_name = "";
			$input.val("");
			$dd.empty().hide();
		});

		// On edit, the server resolves recipient to its title; map it back to the doc name
		if (real_name && frappe.web_form.doc.recipient_type) {
			frappe.call({
				method: "churchit.church_website.api.search_church_recipient",
				type: "GET",
				args: { doctype: frappe.web_form.doc.recipient_type, txt: real_name },
				callback: function (r) {
					var results = r.message || [];
					for (var i = 0; i < results.length; i++) {
						if (results[i].name === real_name || results[i].label === real_name) {
							real_name = results[i].name;
							$input.val(results[i].label);
							break;
						}
					}
				},
			});
		}

		// On new forms, default recipient and requestor to the current user's Person record
		if (!frappe.web_form.doc.name) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Person",
					filters: { user: frappe.session.user },
					fieldname: ["name", "full_name"],
				},
				callback: function (r) {
					if (!r.message || !r.message.name) return;
					var person_name = r.message.name;
					var person_label = r.message.full_name || person_name;

					var requestor_ctrl = frappe.web_form.fields_dict["requestor"];
					if (requestor_ctrl) requestor_ctrl.set_value(person_name);

					// Setting recipient_type fires our change handler which clears state;
					// assign real_name/input afterwards so they aren't clobbered.
					Promise.resolve(type_ctrl.set_value("Person")).then(function () {
						real_name = person_name;
						$input.val(person_label);
					});
				},
			});
		}
	}
});
