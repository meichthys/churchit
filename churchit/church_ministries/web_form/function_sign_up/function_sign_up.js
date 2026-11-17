frappe.ready(function() {
	{% if not has_sign_up_functions and not reference_name %}
	$('.web-form').hide();
	{% if not register_functions %}
	$('.web-form-introduction').html(
		$('<p>').text({{ _("There are no functions with sign-ups enabled at this time. Please check back later.") | tojson }})
	);
	{% endif %}
	{% endif %}

	{% if register_functions and not reference_name %}
	// This form has no option or question inputs, so it links to /register for the functions that have them.
	var register_list = $('<ul class="mb-0">');
	$.each({{ register_functions | tojson }}, function(i, row) {
		register_list.append($('<li>').append(
			$('<a>').attr('href', '/register?function=' + encodeURIComponent(row.name)).text(row.function_name)
		));
	});
	$('.web-form-introduction').append($('<div class="alert alert-info mt-3">').append(
		$('<p class="mb-2">').text({{ _("Sign up for these functions on the Register page. There you choose the options, answer the questions and add the people of your household.") | tojson }}),
		register_list
	));
	{% endif %}

	{% if reference_name %}
	// A saved sign-up shows its status, its people and its money, and offers Cancel to a member who may change it.
	var summary = frappe.web_form.fields_dict.summary_display;
	frappe.call({
		method: 'churchit.church_ministries.web_form.function_sign_up.function_sign_up.get_sign_up_summary',
		type: 'GET',
		args: { name: {{ reference_name | tojson }} },
		callback: function(r) {
			if (summary && r.message) render_summary(summary.$wrapper, r.message);
		},
	});

	function render_summary(wrapper, data) {
		var people = data.attendees.map(function(row) {
			return row.selection ? row.name + ' (' + row.selection + ')' : row.name;
		});
		var rows = [
			[{{ _("Status") | tojson }}, data.status],
			[{{ _("Attendees") | tojson }}, people.join(', ')],
			[{{ _("Amount Due") | tojson }}, data.amount_due],
			[{{ _("Amount Paid") | tojson }}, data.amount_paid],
			[{{ _("Payment Status") | tojson }}, data.payment_status],
		];
		var list = $('<dl class="row mb-3">');
		rows.forEach(function(row) {
			if (!row[1]) return;
			list.append($('<dt class="col-sm-4">').text(row[0]), $('<dd class="col-sm-8">').text(row[1]));
		});
		wrapper.empty().append(list);
		if (!data.can_cancel) return;

		var question = data.amount_paid
			? {{ _("Cancel this sign-up? The church office gives back what you paid.") | tojson }}
			: {{ _("Cancel this sign-up?") | tojson }};
		$('<button type="button" class="btn btn-default btn-sm mb-3">')
			.text({{ _("Cancel my sign-up") | tojson }})
			.appendTo(wrapper)
			.on('click', function() {
				frappe.confirm(question, function() {
					frappe.call({
						method: 'run_doc_method',
						args: { dt: 'Function Sign-Up', dn: {{ reference_name | tojson }}, method: 'cancel_registration' },
						callback: function() { window.location.reload(); },
					});
				});
			});
	}
	{% endif %}

	{% if link_titles %}
	// Read-only Link fields show the raw docname, since the portal renders them as
	// Autocomplete. Display the title instead; the values on the doc stay as docnames
	// so the client script can look up the function's sign-up items. Overriding the
	// display rather than writing to it once keeps the title through later re-renders.
	$.each({{ link_titles | json }}, function(fieldname, title) {
		var field = frappe.web_form.fields_dict[fieldname];
		if (!field || !field.disp_area || !field.df.read_only || !title) return;
		field.set_disp_area = function() {
			$(this.disp_area).text(title);
		};
		field.refresh();
	});
	{% endif %}
})
