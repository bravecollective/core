# https://github.com/cocagne/pysrp

# An example SRP-6a authentication
# WARNING: Do not use for real cryptographic purposes beyond testing.
# based on http://srp.stanford.edu/design.html
import hashlib
import random
 
def global_print(*names):
    x = lambda s: ["%s", "0x%x"][isinstance(s, long)] % s
    print "".join("%s = %s\n" % (name, x(globals()[name])) for name in names)
 
# note: str converts as is, str( [1,2,3,4] ) will convert to "[1,2,3,4]" 
def H(*a):  # a one-way hash function
    return int(hashlib.sha256(str(a)).hexdigest(), 16)
 
def cryptrand(n=1024):  
    return random.SystemRandom().getrandbits(n) % N
 
# A large safe prime (N = 2q+1, where q is prime)
# All arithmetic is done modulo N
# (generated using "openssl dhparam -text 1024")
N = '''00:c0:37:c3:75:88:b4:32:98:87:e6:1c:2d:a3:32:
       4b:1b:a4:b8:1a:63:f9:74:8f:ed:2d:8a:41:0c:2f:
       c2:1b:12:32:f0:d3:bf:a0:24:27:6c:fd:88:44:81:
       97:aa:e4:86:a6:3b:fc:a7:b8:bf:77:54:df:b3:27:
       c7:20:1f:6f:d1:7f:d7:fd:74:15:8b:d3:1c:e7:72:
       c9:f5:f8:ab:58:45:48:a9:9a:75:9b:5a:2c:05:32:
       16:2b:7b:62:18:e8:f1:42:bc:e2:c3:0d:77:84:68:
       9a:48:3e:09:5e:70:16:18:43:79:13:a8:c3:9c:3d:
       d0:d4:ca:3c:50:0b:88:5f:e3'''
N = int(''.join(N.split()).replace(':', ''), 16)
g = 2        # A generator modulo N
 
k = H(N, g)  # Multiplier parameter (k=3 in legacy SRP-6)
 
print "#. H, N, g, and k are known beforehand to both client and server:"
global_print("H", "N", "g", "k")
 
print "0. server stores (I, s, v) in its password database"
 
# the server must first generate the password verifier
I = "person"         # Username
p = "password1234"   # Password
s = cryptrand(64)    # Salt for the user
x = H(s, p)          # Private key
v = pow(g, x, N)     # Password verifier
global_print("I", "p", "s", "x", "v")
 
print "1. client sends username I and public ephemeral value A to the server"
a = cryptrand()
A = pow(g, a, N)
global_print("I", "A")  # client->server (I, A)
 
print "2. server sends user's salt s and public ephemeral value B to client"
b = cryptrand()
B = (k * v + pow(g, b, N)) % N
global_print("s", "B")  # server->client (s, B)
 
print "3. client and server calculate the random scrambling parameter"
u = H(A, B)  # Random scrambling parameter
global_print("u")
 
print "4. client computes session key"
x = H(s, p)
S_c = pow(B - k * pow(g, x, N), a + u * x, N)
K_c = H(S_c)
global_print("S_c", "K_c")
 
print "5. server computes session key"
S_s = pow(A * pow(v, u, N), b, N)
K_s = H(S_s)
global_print("S_s", "K_s")
 
print "6. client sends proof of session key to server"
M_c = H(H(N) ^ H(g), H(I), s, A, B, K_c)
global_print("M_c")
# client->server (M_c) ; server verifies M_c
 
print "7. server sends proof of session key to client"
M_s = H(A, M_c, K_s)
global_print("M_s")
# server->client (M_s) ;  client verifies M_s
