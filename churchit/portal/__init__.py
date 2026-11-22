# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app at /portal: a Vue and frappe-ui front end (frontend/) over the endpoints in this package.

One module serves each area of the app. A read takes GET and a change takes POST. Member data comes from
the signed-in user's Person, never from a church the browser names. Every endpoint refuses a page that is
switched off (access.require_page), because /portal/<page> never reaches the page renderers that answer 404
for the old route.
"""
