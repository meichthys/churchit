# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Paper connection card capture: the photo of a card is read by AI into a draft for a person to check."""


def dispatch(doc, method=None) -> None:
	"""After insert of a Connection Card Photo: queue the reading of the photo (A7.1)."""
