<p>This care request was due on {{ frappe.utils.formatdate(doc.due_on) }} and is still open.</p>

<ul>
  <li><strong>Person:</strong> {{ frappe.db.get_value("Person", doc.person, "full_name") or doc.person }}</li>
  <li><strong>Category:</strong> {{ doc.category }}</li>
  <li><strong>Urgency:</strong> {{ doc.urgency }}</li>
  <li><strong>Status:</strong> {{ doc.status }}</li>
  <li><strong>Caregiver:</strong> {{ frappe.db.get_value("Person", doc.caregiver, "full_name") if doc.caregiver else "Nobody yet" }}</li>
</ul>

<p>Please follow up, then update the request: <a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">{{ doc.name }}</a></p>