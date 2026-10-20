"""Forgiving free-text search for the library and the vocabulary (difflib).

Every word of the query must match a word of the entry, in any order, ignoring
case and accents. A query word matches the words that contain it ("herb" finds
"Herbert"); only when no word anywhere contains it does it fall back to the
words within a small typo of it ("Herbrt" finds "Herbert"), so a correctly
spelled word never brings in look-alikes ("brave" doesn't add "grave").
"""

import difflib
import re
import unicodedata
from collections import defaultdict

CUTOFF = 0.8  # difflib similarity a typo needs: one slip in a word of five letters or more


def words(text: str) -> set[str]:
    """The text's words, lowercased and without accents ("Émile" → "emile")."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return set(re.findall(r"\w+", "".join(c for c in decomposed if not unicodedata.combining(c))))


def search(query: str, entries: dict[str, str]) -> set[str]:
    """The keys of the entries whose text matches every word of the query."""
    index: dict[str, set[str]] = defaultdict(set)  # word → keys of the entries that have it
    for key, text in entries.items():
        for word in words(text):
            index[word].add(key)
    found = set(entries)
    for q in words(query):
        hits = [w for w in index if q in w] or difflib.get_close_matches(q, index, n=len(index) or 1, cutoff=CUTOFF)
        found &= set().union(*(index[w] for w in hits))
    return found
