frappe.ready(function() {
	{% if not has_sign_up_functions %}
	$('.web-form').hide();
	$('.web-form-introduction').html(
		'<p>There are no functions with sign-ups enabled at this time. Please check back later.</p>'
	);
	{% endif %}

	// Ensure title fields are displayed for Link fields
	frappe.web_form.form.set_df_property('function', 'show_title_field_in_link', 1);
	frappe.web_form.form.set_df_property('person', 'show_title_field_in_link', 1);
})