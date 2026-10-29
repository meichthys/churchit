<p>Dear {{ frappe.db.get_value("Person", doc.person, "first_name") }},</p>

<p>On {{ frappe.utils.formatdate(doc.recorded_on) }} you agreed that {{ church_name(doc) or "your church" }} may email you. Please tell us that you still want to hear from us.</p>

<p><a href="{{ consent_renewal_link(doc) }}">Yes, keep in touch</a></p>

<p>To choose what you get from us, sign in and open Communication Preferences. If you do nothing, we keep your current choices, and we will not ask again until you next change them.</p>
