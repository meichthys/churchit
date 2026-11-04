# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Store the church's favicon, splash and logo as settings, and turn off other apps' email footers.

They came from hooks, where the app installed last wins, so ERPNext added to a church site would
have shown its own brand on the website, the login page and every email.
"""

from churchit.patches.after_install import set_church_brand


def execute():
	set_church_brand()
