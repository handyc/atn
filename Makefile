CC      ?= cc
CFLAGS  ?= -std=c11 -O2 -Wall -Wextra
LDLIBS  := -lm
PREFIX  ?= /usr/local

SRC := main.c util.c magic.c stats.c structure.c scan.c dump.c disasm.c yara.c fleet.c attn.c gpt.c cm.c prep.c content.c
OBJ := $(SRC:.c=.o)

atn: $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(LDLIBS)

$(OBJ): atn.h

install: atn
	install -d $(DESTDIR)$(PREFIX)/bin
	install -m 755 atn $(DESTDIR)$(PREFIX)/bin/atn

clean:
	rm -f atn $(OBJ)

# fast, deterministic, network-free regression suite
test: atn
	@sh tests/regression.sh

.PHONY: install clean test
