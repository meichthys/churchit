# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe import _


def get_data() -> dict:
	"""The Person form dashboard: the attendance heatmap from `person.get_timeline_data`.

	The Connections come from the doctype's `links`, which Frappe adds to this.
	"""
	return {"heatmap": True, "heatmap_message": _("Functions attended in the last year.")}
