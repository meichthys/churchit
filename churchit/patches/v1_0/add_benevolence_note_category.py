# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Benevolence Note Category for alms case notes, and no other category."""

from churchit.church_people.doctype.note_category.note_category import BENEVOLENCE, create_note_categories


def execute():
	create_note_categories((BENEVOLENCE,))
