<p>A new expense is pending approval:</p>

<ul>
  <li><strong>Amount:</strong> {{ frappe.utils.fmt_money(doc.amount) }}</li>
  <li><strong>Paid To:</strong> {{ doc.paid_to or doc.vendor or '—' }}</li>
  <li><strong>Type:</strong> {{ doc.type or '—' }}</li>
  <li><strong>Fund:</strong> {{ doc.fund or '—' }}</li>
  <li><strong>Description:</strong> {{ doc.description or '—' }}</li>
</ul>

<p>Please review and approve in the system.</p>