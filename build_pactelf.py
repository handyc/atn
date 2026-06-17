#!/usr/bin/env python3
# build_pactelf.py — assemble the 64 KB "pact" ELF: a cover utility that, given the secret key, serves
# the entire CA-OS (regenerated from its embedded program) to the local browser. Outsider sees an
# ordinary little "notes" tool; the recipient runs it with the key and gets the OS out of nothing.
# Milestone 2 = serve only. (Networking/relay added in a later milestone.)
import gzip, subprocess, os, sys

SECRET = "alice<->bob pact 2026"          # the key the recipient knows (also the pact seed)
html = open("pactbundle.html", "rb").read()
gz = gzip.compress(html, 9)
print(f"bundle {len(html)} B -> gzip {len(gz)} B")

def carr(b):
    return ",".join(str(x) for x in b)

C = r'''/* notesync — a tiny note-sync utility. (Carries a sealed workspace; the key unlocks it.) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

static const unsigned char BUNDLE[] = {__BUNDLE__};
static const int BUNDLE_LEN = __BLEN__;
static const char *SECRET = "__SECRET__";

/* cover: a handful of saved "notes" */
static const char *NOTES[] = {
  "remember to water the plants",
  "call the dentist re: appointment",
  "groceries: oat milk, lentils, lemons",
  "idea: weekend trip to the coast",
  "book club is Thursday at 7",
  "back up the laptop this weekend",
};

int main(int argc, char **argv) {
  /* outsider view: print a random saved note and exit */
  if (argc < 2 || strcmp(argv[1], SECRET) != 0) {
    srand((unsigned)time(0) ^ (unsigned)getpid());
    int n = sizeof(NOTES)/sizeof(NOTES[0]);
    printf("%s\n", NOTES[rand()%n]);
    return 0;
  }
  /* recipient with the key: serve the regenerated workspace to the local browser */
  signal(SIGPIPE, SIG_IGN);
  signal(SIGCHLD, SIG_IGN);
  int port = 8787, s = socket(AF_INET, SOCK_STREAM, 0), one = 1;
  setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
  struct sockaddr_in a; memset(&a,0,sizeof(a));
  a.sin_family = AF_INET; a.sin_port = htons(port); a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if (bind(s,(struct sockaddr*)&a,sizeof(a)) || listen(s,8)) { perror("bind"); return 1; }
  fprintf(stderr, "workspace ready  ->  http://127.0.0.1:%d\n", port);
  /* try to open a browser (ignore failure) */
  if (fork()==0){ execlp("xdg-open","xdg-open","http://127.0.0.1:8787",(char*)0); _exit(0); }
  char hdr[256];
  int hl = snprintf(hdr, sizeof(hdr),
     "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
     "Content-Encoding: gzip\r\nContent-Length: %d\r\nConnection: close\r\n\r\n", BUNDLE_LEN);
  for (;;) {
    int c = accept(s, 0, 0);
    if (c < 0) continue;
    if (fork() == 0) {                                  /* one child per connection: a stuck client can't wedge the server */
      struct timeval tv = {2,0};
      setsockopt(c, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
      char req[2048]; recv(c, req, sizeof(req), 0);     /* best-effort drain of the request */
      write(c, hdr, hl);
      int off = 0; while (off < BUNDLE_LEN) { int w = write(c, BUNDLE+off, BUNDLE_LEN-off); if (w<=0) break; off += w; }
      close(c); _exit(0);
    }
    close(c);
  }
}
'''
C = (C.replace("__BUNDLE__", carr(gz))
       .replace("__BLEN__", str(len(gz)))
       .replace("__SECRET__", SECRET.replace("\\", "\\\\").replace('"', '\\"')))
open("notesync.c", "w").write(C)
r = subprocess.run(["gcc", "-Os", "-s", "-o", "notesync", "notesync.c"], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
sz = os.path.getsize("notesync")
print(f"built ./notesync  =  {sz} bytes  ({sz/1024:.1f} KB)   {'OK <= 64 KB' if sz<=65536 else 'OVER 64 KB!'}")
