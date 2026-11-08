# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""AI drafts: an agent proposes a record, a person checks the filled form and saves it."""


def propose(doctype: str, values: dict | str, name: str | None = None) -> dict:
	"""Stub for A3.2: keep a draft for the caller and return the link that opens it in a form."""
	raise NotImplementedError


def make_draft(doctype: str, values: dict, name: str | None = None, source: str | None = None) -> dict:
	"""Stub for A3.2: what propose does, for churchit's own AI features (A4) to call."""
	raise NotImplementedError


def get_draft(token: str) -> dict:
	"""Stub for A3.2: the caller's draft, with stale set when the record changed after it."""
	raise NotImplementedError


def label_saved(doctype: str, name: str, token: str) -> None:
	"""Stub for A3.3: the Info Comment that says a saved record was drafted with AI help."""
	raise NotImplementedError
