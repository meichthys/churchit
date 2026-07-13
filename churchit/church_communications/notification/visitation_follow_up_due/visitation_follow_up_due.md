<p>A scheduled visitation follow-up is due tomorrow:</p>

<ul>
  <li><strong>Person:</strong> {{ doc.person }}</li>
  <li><strong>Visit Date:</strong> {{ frappe.utils.formatdate(doc.visit_date) }} ({{ doc.visit_type }})</li>
</ul>

<p><strong>Notes:</strong></p>
<p>{{ doc.notes }}</p>