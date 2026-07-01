<p>A new alms request was submitted:</p>

<ul>
  <li><strong>Recipient:</strong> {{ doc.recipient_name or doc.recipient }}</li>
  <li><strong>Amount:</strong> {{ frappe.utils.fmt_money(doc.amount) }}</li>
  <li><strong>Status:</strong> {{ doc.status }}</li>
</ul>

<p>Description:</p>
<p>{{ doc.description }}</p>