// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ready(function () {
	// Rendered by Jinja on the server, like the blocks below.
	const has_open_campaigns = "{{ 1 if has_open_campaigns else 0 }}";
	if (has_open_campaigns !== "1") {
		$(".web-form").hide();
		$(".web-form-introduction").html(
			"<p>There are no campaigns open for pledges at this time. Please check back later.</p>"
		);
		return;
	}

	{% if link_titles %}
	// A read-only Link shows the raw docname on the portal. Show the campaign title instead.
	$.each({{ link_titles | json }}, function (fieldname, title) {
		const field = frappe.web_form.fields_dict[fieldname];
		if (!field || !field.disp_area || !field.df.read_only || !title) return;
		field.set_disp_area = function () {
			$(this.disp_area).text(title);
		};
		field.refresh();
	});
	{% endif %}

	{% if reference_doc and reference_doc.name %}
	frappe.call({
		method: "churchit.church_finances.doctype.pledge.pledge.get_given_so_far",
		type: "GET",
		args: { pledge: {{ reference_doc.name | json }} },
		callback: function (r) {
			if (!r.message) return;
			$("<p class='given-so-far'></p>").text(r.message).prependTo(".web-form-container .web-form-body");
		},
	});
	{% else %}
	const existing_pledges = {{ existing_pledges | json }};
	const edit_label = {{ edit_pledge_label | json }};
	frappe.web_form.on("campaign", function (field, value) {
		const wrapper = field.$wrapper.find(".control-input-wrapper");
		wrapper.find(".existing-pledge").remove();
		const existing = existing_pledges[value];
		if (!existing) return;
		$("<p class='existing-pledge text-muted'></p>")
			.text(existing.message + " ")
			.append($("<a></a>").attr("href", "/pledge/" + existing.name).text(edit_label))
			.appendTo(wrapper);
	});
	{% endif %}
});
