<p>A visitation follow-up is due tomorrow:</p>

<ul>
  <li><strong>Person:</strong> {{ doc.person }}</li>
  <li><strong>Original Visit:</strong> {{ frappe.utils.formatdate(doc.visit_date) }} ({{ doc.visit_type }})</li>
  <li><strong>Follow-Up Date:</strong> {{ frappe.utils.formatdate(doc.follow_up_date) }}</li>
</ul>

<p><strong>Original Notes:</strong></p>
<p>{{ doc.notes }}</p>