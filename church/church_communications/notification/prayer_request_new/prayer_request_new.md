<p>A new prayer request has been submitted:</p>

<ul>
  <li><strong>Title:</strong> {{ doc.title }}</li>
  {% if doc.urgent %}<li><strong>Urgent</strong></li>{% endif %}
  <li><strong>Requestor:</strong> {{ doc.requestor }}</li>
  {% if doc.recipient_name %}<li><strong>For:</strong> {{ doc.recipient_name }}</li>{% endif %}
  <li><strong>Type:</strong> {{ doc.type }}</li>
</ul>

<p>{{ doc.request or doc.description }}</p>

<p>Please join us in praying.</p>