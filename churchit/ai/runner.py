# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The one way churchit's own AI actions run a model: Flow's run API, as the caller, with the answer
sent to the caller's browser and never saved by itself."""


def start(
	feature: str,
	prompt: str,
	*,
	sends: tuple[str, ...] = (),
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	check: str | None = None,
) -> dict:
	"""Stub for A4.1: check the model's label for what the prompt sends, start the run, return {"token"}."""
	raise NotImplementedError


def wrap_data(text: str, source: str) -> str:
	"""Stub for A4.1: text that guests or members wrote, as a data block the model must not obey."""
	raise NotImplementedError


def complete(run) -> None:
	"""Stub for A4.1 (Flow Run on_complete): check the answer and send it to the caller's browser."""
	raise NotImplementedError
