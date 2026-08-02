frappe.ready(function() {
	{% if not has_sign_up_functions %}
	$('.web-form').hide();
	$('.web-form-introduction').html(
		'<p>There are no functions with sign-ups enabled at this time. Please check back later.</p>'
	);
	{% endif %}

	{% if link_titles %}
	// Read-only Link fields show the raw docname, since the portal renders them as
	// Autocomplete. Display the title instead — the values on the doc stay as docnames
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