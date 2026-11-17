<p>A background check expires in 30 days:</p>

<ul>
  <li><strong>Person:</strong> {{ doc.person_name or doc.person }}</li>
  <li><strong>Check Type:</strong> {{ doc.check_type }}</li>
  <li><strong>Expires On:</strong> {{ frappe.utils.formatdate(doc.expires_on, "EEEE, MMMM d, yyyy") }}</li>
  <li><strong>Provider:</strong> {{ doc.provider or "Not recorded" }}</li>
</ul>

<p>Ask them to renew it before then. Without it they cannot serve in a position that needs this check.</p>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the background check</a></p>