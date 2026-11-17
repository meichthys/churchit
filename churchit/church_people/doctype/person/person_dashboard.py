# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).


def get_data() -> dict:
	"""The Person form dashboard. The Connections come from the doctype's `links`, which Frappe adds to this.

	No heatmap: Frappe's bundled chart drops the latest weeks. The Connections tab shows the attendance fields.
	"""
	return {}
