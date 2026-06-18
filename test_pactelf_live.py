#!/usr/bin/env python3
# Live end-to-end test of the pact ELF's networking, exercising the REAL notesync.c code paths
# (HTTP parse, gzip serve, /config, POST /send -> peer link -> /poll relay) over AF_UNIX, because
# this host firewalls TCP loopback. Build under test: notesync_ut (gcc -DUNIXSOCK notesync.c) — the
# ONLY difference from the shipped ELF is the socket family/address; all request handling is identical.
import socket, subprocess, os, time, gzip, json, base64, sys

SECRET = "alice<->bob pact 2026"
SOCK = lambda p: f"/tmp/notesync_{p}.sock"

def http(port, req):
    c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); c.connect(SOCK(port))
    c.sendall(req); buf = b""
    while True:
        d = c.recv(65536)
        if not d: break
        buf += d
    c.close()
    head, _, body = buf.partition(b"\r\n\r\n")
    return head.decode("latin1"), body

def wait_sock(p, t=5.0):
    end = time.time() + t
    while time.time() < end:
        if os.path.exists(SOCK(p)): return True
        time.sleep(0.05)
    return False

for p in (8787, 8788, 9777):
    try: os.unlink(SOCK(p))
    except OSError: pass

env = dict(os.environ); env["NS_BPORT"] = "8787"
host = subprocess.Popen(["./notesync_ut", SECRET, "host", "9777"], env=env,
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
assert wait_sock(8787) and wait_sock(9777), "host sockets did not appear"
env2 = dict(os.environ); env2["NS_BPORT"] = "8788"
join = subprocess.Popen(["./notesync_ut", SECRET, "join", "127.0.0.1", "9777"], env=env2,
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
assert wait_sock(8788), "join HTTP socket did not appear"
time.sleep(0.4)   # let join connect to host's peer listener

ok = True
def check(name, cond):
    global ok
    print(("  PASS " if cond else "  FAIL ") + name); ok = ok and cond

try:
    # 1. GET / serves the gzipped bundle; gunzip must byte-match pactbundle.html
    head, body = http(8787, b"GET / HTTP/1.1\r\nHost:x\r\nConnection:close\r\n\r\n")
    check("GET / -> 200 + gzip header", "200 OK" in head and "Content-Encoding:gzip" in head)
    want = open("pactbundle.html", "rb").read()
    check("served bundle gunzips byte-identical to pactbundle.html", gzip.decompress(body) == want)

    # 2. GET /config advertises role + seed
    head, body = http(8787, b"GET /config HTTP/1.1\r\nHost:x\r\nConnection:close\r\n\r\n")
    cfg = json.loads(body.decode())
    check("GET /config -> role=host, correct seed", cfg["role"] == "host" and cfg["seed"] == SECRET)
    hj = json.loads(http(8788, b"GET /config HTTP/1.1\r\nConnection:close\r\n\r\n")[1].decode())
    check("join node reports role=join", hj["role"] == "join")

    # 3. join's queue starts empty
    head, body = http(8788, b"GET /poll HTTP/1.1\r\nConnection:close\r\n\r\n")
    check("join /poll initially empty []", body.decode().strip() == "[]")

    # 4. THE RELAY: POST a sealed delta to HOST -> peer link -> JOIN's /poll returns it intact
    delta = bytes(range(37))               # stand-in for a 37-byte AES-256-GCM sealed delta
    b64 = base64.b64encode(delta)
    req = (b"POST /send HTTP/1.1\r\nContent-Length:%d\r\nConnection:close\r\n\r\n" % len(b64)) + b64
    head, _ = http(8787, req)
    check("POST /send -> 200", "200 OK" in head)
    time.sleep(0.3)                        # host -> peer TCP -> join qput
    head, body = http(8788, b"GET /poll HTTP/1.1\r\nConnection:close\r\n\r\n")
    arr = json.loads(body.decode())
    got = base64.b64decode(arr[0]) if arr else b""
    check("relayed delta arrives at join, byte-identical", got == delta)
    check("join /poll drains after read", json.loads(http(8788, b"GET /poll HTTP/1.1\r\nConnection:close\r\n\r\n")[1].decode()) == [])

    # 5. multiple deltas preserved + ordered through the framing
    deltas = [b"alpha-delta-one", b"\x00\x01\x02\xff\xfe", b"third"]
    for d in deltas:
        b = base64.b64encode(d)
        http(8787, (b"POST /send HTTP/1.1\r\nContent-Length:%d\r\nConnection:close\r\n\r\n" % len(b)) + b)
    time.sleep(0.3)
    arr = json.loads(http(8788, b"GET /poll HTTP/1.1\r\nConnection:close\r\n\r\n")[1].decode())
    check("3 framed deltas relayed in order", [base64.b64decode(x) for x in arr] == deltas)

    # 6. unknown path -> 404
    head, _ = http(8787, b"GET /nope HTTP/1.1\r\nConnection:close\r\n\r\n")
    check("unknown path -> 404", "404" in head)
finally:
    host.terminate(); join.terminate()
    for p in (8787, 8788, 9777):
        try: os.unlink(SOCK(p))
        except OSError: pass

print("\nLIVE PACT NETWORKING:", "ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
