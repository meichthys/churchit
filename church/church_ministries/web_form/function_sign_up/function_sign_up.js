frappe.ready(function() {
	{% if not has_sign_up_functions %}
	$('.web-form').hide();
	$('.web-form-introduction').html(
		'<p>There are no functions with sign-ups enabled at this time. Please check back later.</p>'
	);
	{% endif %}
})