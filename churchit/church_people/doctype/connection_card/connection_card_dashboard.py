# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).


def get_data() -> dict:
	"""The Follow-up Cards made from this record, through their Source link."""
	return {
		"fieldname": "source_name",
		"dynamic_links": {"source_name": ["Connection Card", "source_type"]},
		"transactions": [{"items": ["Follow-up Card"]}],
	}
