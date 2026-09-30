<p>A new expense is pending approval:</p>

<ul>
  <li><strong>Amount:</strong> {{ frappe.utils.fmt_money(doc.amount) }}</li>
  <li><strong>Paid To:</strong> {{ doc.paid_to or doc.vendor or 'Not set' }}</li>
  <li><strong>Type:</strong> {{ doc.type or 'Not set' }}</li>
  <li><strong>Fund:</strong> {{ doc.fund or 'Not set' }}</li>
  <li><strong>Description:</strong> {{ doc.description or 'Not set' }}</li>
</ul>

<p>Please review and approve in the system.</p>