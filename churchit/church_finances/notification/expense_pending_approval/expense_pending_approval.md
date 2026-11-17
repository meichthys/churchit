<p>A new expense is pending approval:</p>

<ul>
  <li><strong>Amount:</strong> {{ frappe.utils.fmt_money(doc.amount, currency=frappe.db.get_default("currency")) }}</li>
  <li><strong>Paid To:</strong> {{ doc.vendor or 'Not set' }}</li>
  <li><strong>Type:</strong> {{ doc.type or 'Not set' }}</li>
  <li><strong>Fund:</strong> {{ (doc.associated_fund and frappe.db.get_value('Fund', doc.associated_fund, 'fund')) or 'Not set' }}</li>
  <li><strong>Description:</strong> {{ doc.notes or 'Not set' }}</li>
</ul>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Review and approve the expense</a></p>