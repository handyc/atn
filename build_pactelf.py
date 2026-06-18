#!/usr/bin/env python3
# build_pactelf.py — assemble the 64 KB "pact" ELF.
#   ./notesync                          -> cover: prints a random saved note (looks ordinary)
#   ./notesync "<key>"                  -> solo: serve the regenerated CA-OS on http://127.0.0.1:8787
#   ./notesync "<key>" host [pport]     -> Alice: also listen on pport (default 9777) for the peer node
#   ./notesync "<key>" join <ip> [pport]-> Bob:   also connect to the peer at ip:pport
# In host/join mode the ELF is a zero-knowledge relay: the browser seals each input delta with
# AES-256-GCM (key from the CA grown from the shared seed) and POSTs it to /send; the ELF forwards the
# opaque bytes over the peer TCP link; the peer's ELF queues them for its browser's /poll. The OS is
# regenerated on both ends from the (identical) packet -- only sealed deltas ever cross the wire.
import gzip, subprocess, os, sys

SECRET = "alice<->bob pact 2026"          # the key the recipient knows (also the pact seed)
BROWSER_PORT = 8787
html = open("pactbundle.html", "rb").read()
gz = gzip.compress(html, 9)
print(f"bundle {len(html)} B -> gzip {len(gz)} B")
carr = lambda b: ",".join(str(x) for x in b)

C = r'''/* notesync — a tiny note-sync utility. (Carries a sealed workspace; the key unlocks it.) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>

static const unsigned char BUNDLE[] = {__BUNDLE__};
static const int BUNDLE_LEN = __BLEN__;
static const char *SECRET = "__SECRET__";
static const int BPORT = __BPORT__;
static const char *NOTES[] = {
  "remember to water the plants","call the dentist re: appointment",
  "groceries: oat milk, lentils, lemons","idea: weekend trip to the coast",
  "book club is Thursday at 7","back up the laptop this weekend",
};

/* ---- a tiny ring buffer of sealed deltas arrived from the peer, awaiting the local browser's /poll ---- */
#define QCAP (1<<16)
static unsigned char q[QCAP]; static int qhead=0, qtail=0;   /* byte ring of [4-byte LE len][delta]... frames */
static int qbytes(){ return (qtail-qhead+QCAP)%QCAP; }
static void qput(const unsigned char*p,int n){ for(int i=0;i<n;i++){ q[qtail]=p[i]; qtail=(qtail+1)%QCAP; if(qtail==qhead) qhead=(qhead+1)%QCAP; } }
static int  qget(unsigned char*p,int max){ int n=qbytes(); if(n>max)n=max; for(int i=0;i<n;i++){ p[i]=q[qhead]; qhead=(qhead+1)%QCAP; } return n; }

static const char B64[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static int b64enc(const unsigned char*in,int n,char*out){int o=0;for(int i=0;i<n;i+=3){int v=in[i]<<16|(i+1<n?in[i+1]<<8:0)|(i+2<n?in[i+2]:0);
  out[o++]=B64[(v>>18)&63];out[o++]=B64[(v>>12)&63];out[o++]=(i+1<n)?B64[(v>>6)&63]:'=';out[o++]=(i+2<n)?B64[v&63]:'=';}return o;}
static int b64dec(const char*in,int n,unsigned char*out){int o=0,buf=0,bits=0;for(int i=0;i<n;i++){char c=in[i];int d;
  if(c>='A'&&c<='Z')d=c-'A';else if(c>='a'&&c<='z')d=c-'a'+26;else if(c>='0'&&c<='9')d=c-'0'+52;else if(c=='+')d=62;else if(c=='/')d=63;else continue;
  buf=(buf<<6)|d;bits+=6;if(bits>=8){bits-=8;out[o++]=(buf>>bits)&0xFF;}}return o;}

static int listen_on(int port){ int s=socket(AF_INET,SOCK_STREAM,0),one=1; setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));
  struct sockaddr_in a; memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_port=htons(port); a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
  if(port>=9000) a.sin_addr.s_addr=htonl(INADDR_ANY);   /* peer port reachable from the other machine */
  if(bind(s,(struct sockaddr*)&a,sizeof(a))||listen(s,8)){perror("bind");exit(1);} return s; }

int main(int argc,char**argv){
  if(argc<2||strcmp(argv[1],SECRET)!=0){ srand((unsigned)time(0)^(unsigned)getpid());
    printf("%s\n",NOTES[rand()%(int)(sizeof(NOTES)/sizeof(NOTES[0]))]); return 0; }
  signal(SIGPIPE,SIG_IGN);
  const char *role="solo"; int pport=9777; const char *peerip=0;
  if(argc>=3&&!strcmp(argv[2],"host")){ role="host"; if(argc>=4)pport=atoi(argv[3]); }
  else if(argc>=4&&!strcmp(argv[2],"join")){ role="join"; peerip=argv[3]; if(argc>=5)pport=atoi(argv[4]); }

  int httpL=listen_on(BPORT), peerL=-1, peer=-1;
  if(!strcmp(role,"host")){ peerL=listen_on(pport); fprintf(stderr,"hosting: peer may connect on tcp/%d\n",pport); }
  else if(!strcmp(role,"join")){ peer=socket(AF_INET,SOCK_STREAM,0); struct sockaddr_in pa; memset(&pa,0,sizeof(pa));
    pa.sin_family=AF_INET; pa.sin_port=htons(pport); inet_pton(AF_INET,peerip,&pa.sin_addr);
    if(connect(peer,(struct sockaddr*)&pa,sizeof(pa))){ perror("connect peer"); peer=-1; } else fprintf(stderr,"joined peer %s:%d\n",peerip,pport); }
  fprintf(stderr,"workspace ready  ->  http://127.0.0.1:%d   (role=%s)\n",BPORT,role);
  if(fork()==0){ char u[64]; snprintf(u,sizeof(u),"http://127.0.0.1:%d",BPORT); execlp("xdg-open","xdg-open",u,(char*)0); _exit(0); }

  char hbuf[8192]; static unsigned char pbuf[QCAP];
  for(;;){
    fd_set rf; FD_ZERO(&rf); int mx=httpL; FD_SET(httpL,&rf);
    if(peerL>=0){ FD_SET(peerL,&rf); if(peerL>mx)mx=peerL; }
    if(peer>=0){ FD_SET(peer,&rf); if(peer>mx)mx=peer; }
    if(select(mx+1,&rf,0,0,0)<0) continue;

    if(peerL>=0&&FD_ISSET(peerL,&rf)){ int c=accept(peerL,0,0); if(c>=0){ if(peer>=0)close(peer); peer=c; fprintf(stderr,"peer connected\n"); } }
    if(peer>=0&&FD_ISSET(peer,&rf)){ int n=recv(peer,pbuf,sizeof(pbuf),0); if(n<=0){ close(peer); peer=-1; } else qput(pbuf,n); }

    if(FD_ISSET(httpL,&rf)){
      int c=accept(httpL,0,0); if(c<0) continue;
      struct timeval tv={2,0}; setsockopt(c,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));
      int n=recv(c,hbuf,sizeof(hbuf)-1,0); if(n<=0){ close(c); continue; } hbuf[n]=0;
      if(!strncmp(hbuf,"GET / ",6)||!strncmp(hbuf,"GET /index",10)){
        char h[256]; int hl=snprintf(h,sizeof(h),"HTTP/1.1 200 OK\r\nContent-Type:text/html;charset=utf-8\r\nContent-Encoding:gzip\r\nContent-Length:%d\r\nConnection:close\r\n\r\n",BUNDLE_LEN);
        write(c,h,hl); int off=0; while(off<BUNDLE_LEN){int w=write(c,BUNDLE+off,BUNDLE_LEN-off); if(w<=0)break; off+=w;}
      } else if(!strncmp(hbuf,"GET /config",11)){
        char body[256]; int bl=snprintf(body,sizeof(body),"{\"role\":\"%s\",\"seed\":\"%s\"}",role,SECRET);
        char h[160]; int hl=snprintf(h,sizeof(h),"HTTP/1.1 200 OK\r\nContent-Type:application/json\r\nContent-Length:%d\r\nAccess-Control-Allow-Origin:*\r\nConnection:close\r\n\r\n",bl);
        write(c,h,hl); write(c,body,bl);
      } else if(!strncmp(hbuf,"GET /poll",9)){
        /* hand the browser all queued sealed deltas as a JSON array of base64 frames */
        static unsigned char tmp[QCAP]; int got=qget(tmp,sizeof(tmp));
        char *out=malloc(got*2+64); int o=0; out[o++]='[';
        int i=0; while(i+4<=got){ int L=tmp[i]|tmp[i+1]<<8|tmp[i+2]<<16|tmp[i+3]<<24; i+=4; if(i+L>got)break;
          if(o>1)out[o++]=','; out[o++]='"'; o+=b64enc(tmp+i,L,out+o); out[o++]='"'; i+=L; }
        out[o++]=']';
        char h[160]; int hl=snprintf(h,sizeof(h),"HTTP/1.1 200 OK\r\nContent-Type:application/json\r\nContent-Length:%d\r\nConnection:close\r\n\r\n",o);
        write(c,h,hl); write(c,out,o); free(out);
      } else if(!strncmp(hbuf,"POST /send",10)){
        char *body=strstr(hbuf,"\r\n\r\n"); int dl=0;
        if(body){ body+=4; int blen=n-(body-hbuf); unsigned char raw[4096]; dl=b64dec(body,blen,raw);
          if(peer>=0&&dl>0){ unsigned char hdr[4]={dl&0xFF,(dl>>8)&0xFF,(dl>>16)&0xFF,(dl>>24)&0xFF}; write(peer,hdr,4); write(peer,raw,dl); } }
        const char *ok="HTTP/1.1 200 OK\r\nContent-Length:0\r\nAccess-Control-Allow-Origin:*\r\nConnection:close\r\n\r\n"; write(c,ok,strlen(ok));
      } else { const char *nf="HTTP/1.1 404 Not Found\r\nContent-Length:0\r\nConnection:close\r\n\r\n"; write(c,nf,strlen(nf)); }
      close(c);
    }
  }
}
'''
C = (C.replace("__BUNDLE__", carr(gz)).replace("__BLEN__", str(len(gz)))
       .replace("__BPORT__", str(BROWSER_PORT))
       .replace("__SECRET__", SECRET.replace("\\","\\\\").replace('"','\\"')))
open("notesync.c","w").write(C)
r = subprocess.run(["gcc","-Os","-s","-o","notesync","notesync.c"], capture_output=True, text=True)
if r.returncode: print(r.stderr); sys.exit(1)
sz = os.path.getsize("notesync")
print(f"built ./notesync = {sz} bytes ({sz/1024:.1f} KB)  {'OK <= 64 KB' if sz<=65536 else 'OVER 64 KB!'}")
