<p>A room booking is waiting for approval:</p>

<ul>
  <li><strong>Room:</strong> {{ doc.room }}</li>
  <li><strong>Requester:</strong> {{ doc.requester }}</li>
  <li><strong>Purpose:</strong> {{ doc.purpose }}</li>
  <li><strong>Start:</strong> {{ frappe.utils.format_datetime(doc.start_datetime) }}</li>
  <li><strong>End:</strong> {{ frappe.utils.format_datetime(doc.end_datetime) }}</li>
  {% if doc.function %}<li><strong>Function:</strong> {{ doc.function }}</li>{% endif %}
</ul>

{% if doc.notes %}<p>{{ doc.notes }}</p>{% endif %}

<p>Please review and approve in the system.</p>
