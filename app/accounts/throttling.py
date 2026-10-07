"""Failed-login throttling for the JSON API.

Every failed sign in attempt is counted in the Django cache against the client
address and the submitted username, and further attempts for that pair are
refused with 429 while the window is open. A successful sign in clears the
count. The cache backend is LocMem by default, which is correct while the API
runs as a single process; switching to Redis later is a settings change only
because nothing outside config.settings knows where the counters live.
"""
import math
import time

from django.core.cache import cache

#five failures for one address and username before a fifteen minute pause
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW = 60 * 15


#key scoped to the client address and the submitted username, so an attacker
#cannot lock a colleague out of their own account from a different address
#while trying many usernames from one address is still counted
def login_failure_key(address, username):
    return f"login-failures:{address}:{username.strip().lower()}"


#counts a failed attempt, starting the window on the first failure and keeping
#the original window end so repeated failures never extend a lockout
def record_login_failure(key):
    now = time.time()
    entry = cache.get(key)
    if entry is None:
        cache.set(key, (1, now + LOGIN_FAILURE_WINDOW), LOGIN_FAILURE_WINDOW)
        return 1

    count, reset_at = entry
    count += 1
    cache.set(key, (count, reset_at), max(1, int(reset_at - now)))
    return count


#reports how many seconds the pair is blocked for, or zero when attempts are
#allowed because the counter is missing, incomplete, or expired
def login_retry_after(key):
    entry = cache.get(key)
    if entry is None:
        return 0

    count, reset_at = entry
    remaining = reset_at - time.time()
    if remaining <= 0:
        #the cache timeout should have removed the entry already, this branch
        #keeps the counter honest if a backend returns it late
        cache.delete(key)
        return 0

    if count < LOGIN_FAILURE_LIMIT:
        return 0

    return max(1, math.ceil(remaining))


#clears the count after a successful sign in so an honest user starts fresh
def clear_login_failures(key):
    cache.delete(key)