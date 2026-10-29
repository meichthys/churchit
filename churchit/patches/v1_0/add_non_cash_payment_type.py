# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Non-Cash Payment Type, unless they have a type for donated property already."""

from churchit.church_finances.doctype.payment_type.payment_type import create_non_cash_payment_type


def execute():
	create_non_cash_payment_type()
