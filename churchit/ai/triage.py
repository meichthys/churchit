# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Suggestions on new requests: a reviewer's AI run reads a new prayer request, care request or
connection card and suggests next steps. It never replies, publishes or changes the request."""


def dispatch(doc, method=None) -> None:
	"""Stub for A5.1 (doc_events after_insert): queue a suggestion run when every rule allows it."""


def run_triage(doctype: str, name: str) -> None:
	"""Stub for A5.1 (long-queue job): start the reviewer's run for one request."""
	raise NotImplementedError


def store(run) -> None:
	"""Stub for A5.1 (Flow Run on_complete): check the answer and keep it for the request's readers."""
	raise NotImplementedError
