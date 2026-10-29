// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ready(function () {
	// Rendered by Jinja on the server; kept in a string so the file stays plain JavaScript.
	const has_open_campaigns = "{{ 1 if has_open_campaigns else 0 }}";
	if (has_open_campaigns === "1") return;
	$(".web-form").hide();
	$(".web-form-introduction").html(
		"<p>There are no campaigns open for pledges at this time. Please check back later.</p>"
	);
});
