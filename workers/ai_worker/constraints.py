"""Reviewed llama.cpp constrained-decoding policies owned by Curator."""

WRITER_GRAMMAR_VERSION="writer-v1-gbnf-2-natural-titles"

# Fixed key order and six ordered slots make the name distribution structural:
# 2 words, 2 words, 3 words, 3 words, then two natural 3-or-4-word titles.
WRITER_GBNF=r'''
root ::= "{" space summary-kv "," space description-kv "," space names-kv "}" space
summary-kv ::= "\"album_summary\"" space ":" space json-text
description-kv ::= "\"description\"" space ":" space json-text
names-kv ::= "\"suggested_names\"" space ":" space "[" space name2 "," space name2 "," space name3 "," space name3 "," space name34 "," space name34 "]"
name2 ::= "\"" word " " word "\""
name3 ::= "\"" word " " word " " word "\""
name4 ::= "\"" word " " word " " word " " word "\""
name34 ::= name3 | name4
word ::= upper name-char{0,23}
upper ::= [A-Z]
name-char ::= [A-Za-z'-]
json-text ::= "\"" json-char+ "\""
json-char ::= [^"\\\x7F\x00-\x1F] | "\\" (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
space ::= [ \t\n\r]*
'''.strip()
