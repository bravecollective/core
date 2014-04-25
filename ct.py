# encoding: utf-8

from __future__ import unicode_literals, print_function

from datetime import datetime
from json import dumps
from binascii import hexlify, unhexlify
from hashlib import sha256

from ecdsa.keys import SigningKey, VerifyingKey
from ecdsa.curves import NIST256p


def emit(obj):
    return hexlify(obj.to_string())

def httpdate(dt):
    """Return a string representation of a date according to RFC 1123
    (HTTP/1.1).

    The supplied date must be in UTC.

    """
    weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
             "Oct", "Nov", "Dec"][dt.month - 1]
    return "%s, %02d %s %04d %02d:%02d:%02d UTC" % (weekday, dt.day, month,
        dt.year, dt.hour, dt.minute, dt.second)




provider = SigningKey.generate(NIST256p, hashfunc=sha256)
service = SigningKey.generate(NIST256p, hashfunc=sha256)


print("Private Keys Generated")
print("Provider:", emit(provider))
print(" Service:", emit(service))


provider_pub = provider.get_verifying_key()
service_pub = service.get_verifying_key()


print("\nPublic Keys Extracted")
print("Provider:", emit(provider_pub))
print(" Service:", emit(service_pub))

print("\nAt this point the application would register its application:")
print(" * Create an application request.")
print(" * Supply public key.")
print(" * Server would generate a per-application private key.")
print(" * Server would present the per-application public key.")

print("\nApplication requests may take any of the following forms:")
print(" * Standard form-encoded POST or bare GET.")
print(" * JSON or Bencode dictionary POST body.")
print("\nRequired on any request is the X-Identity and X-Request-ECDSA signature headers.")
print("Additionally, the Date header is important: clocks must be synced to prevent replay attacks.")
print("Both the client and server should verify that these headers are present and valid!")

print("\nSome API calls are literal RPC, others are for REST data access.  REST may use other verbs.")




dt = httpdate(datetime.utcnow())
auth_data = dumps(dict(
        requires = ['identity.basic'],
        uses = ['eve.character.wallet.balance'],
        success = "https://wiki.bravenewbies.org/auth/success",
        failure = "https://wiki.bravenewbies.org/auth/failure"
    ))

auth_request = """POST https://auth.bravenewbies.org/api/auth/request HTTP/1.1
Date: {0}
Connection: Close
Content-Type: application/json
X-Identity: 51840e196f692b74c5065208
X-Request-ECDSA: {1}

{2}""".format(
        dt,
        hexlify(service.sign("https://auth.bravenewbies.org/api/auth/request\n" + dt + "\n" + auth_data)),
        auth_data
    )

print("\nAn example request would look like the following:\n\n" + auth_request)

print("\nThe request signature is calculated by newline separating the request URL, date, and request body.")
print("The response signature is calculated by newline separating the date and response body.")



dt = httpdate(datetime.utcnow())
resp_data = dumps(dict(
        success = True,
        location = "https://auth.bravenewbies.org/518b16f06f692b73ce139b32"
    ))

response = """HTTP/1.1 200 OK
Date: {0}
Server: Nginx/9
Content-Type: application/json
X-Response-ECDSA: {1}\n\n{2}""".format(
        dt,
        hexlify(provider.sign(dt + "\n" + resp_data)),
        resp_data
    )


print("The response to the above example would be:\n\n" + response)

print("\nBecause this is a request for authentication the service should redirect to the given one-use")
print("time-limited URL.  (These exist for roughly a minute.)  One of three things will happen:")
print(" * The user cancels or logs in and/or denies the permissoin request.")
print(" ** The user will be redirected to the failure URL.")
print(" * The user logs in and/or has already authorized the service.")
print(" ** The user is immediately redirected to the success ")
print(" * The user may need to sign in and authorize the app.")
print("\nA token GET argument is provided to the success page; this token must be supplied on subsequent requests.")
print("Tokens only live for four hours after the last request using them, and are only valid for one service.")
print("The first partition (on .) of the token is a unique identifier for that user.")



token = "518ba7d96f692b73ce139b33"
token = token + "." + hexlify(provider.sign(token + '.' + '51840e196f692b74c5065208'))


dt = httpdate(datetime.utcnow())
data = dumps(dict(
        token = token
    ))

auth_request = """POST https://auth.bravenewbies.org/api/identity/basic HTTP/1.1
Date: {0}
Connection: Close
Content-Type: application/json
X-Identity: 51840e196f692b74c5065208
X-Request-ECDSA: {1}

{2}""".format(
        dt,
        hexlify(service.sign("https://auth.bravenewbies.org/api/identity/basic\n" + dt + "\n" + data)),
        data
    )

print("\nNow the service can request the active user's identity:\n\n" + auth_request)




dt = httpdate(datetime.utcnow())
data = dumps(dict(
        identity = "518ba7d96f692b73ce139b33",
        name = "Billy Bob",
        email = "bob@billy.eu"
    ))

auth_request = """HTTP/1.1 200 OK
Date: {0}
Server: Nginx/9
Content-Type: application/json
X-Response-ECDSA: {1}

{2}""".format(
        dt,
        hexlify(provider.sign(dt + "\n" + data)),
        data
    )

print("\nThe response would be similar to:\n\n" + auth_request)
