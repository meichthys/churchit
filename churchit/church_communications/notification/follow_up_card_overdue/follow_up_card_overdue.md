<p>A follow-up card assigned to you was due yesterday:</p>

<ul>
  <li><strong>Person:</strong> {{ doc.person_name or doc.person }}</li>
  <li><strong>Workflow:</strong> {{ doc.workflow }}</li>
  <li><strong>Step:</strong> {{ doc.step }}</li>
  <li><strong>Due On:</strong> {{ frappe.utils.formatdate(doc.due_on) }}</li>
</ul>

<p>Open the card to note what happened, move it to its next step, or snooze it.</p>