<p>Minutes for <strong>{{ doc.title }}</strong> ({{ frappe.utils.formatdate(doc.meeting_date, "EEEE, MMMM d, yyyy") }}) have been published.</p>

<p>See the attached document for details.</p>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the minutes</a></p>