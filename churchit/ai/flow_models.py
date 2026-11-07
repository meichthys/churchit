# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A privacy label on each Flow Model: where a model sends church data and what its provider may do
with it. Flow owns providers and models; churchit only adds the label. Nothing here runs without Flow.
"""


def add_privacy_label_field() -> None:
	"""Stub, A2.6: after_install and after_migrate; add the label field to Flow Model when Flow exists."""


def stamp_privacy_label(doc, method=None) -> None:
	"""Stub, A2.6: Flow Model validate; stamp who set the label and when."""
