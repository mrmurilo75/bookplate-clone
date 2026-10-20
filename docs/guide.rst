User guide
==========

The library
-----------

The library (``/``) shows every book in one of two views:

**Covers**
   A grid of front covers. Books without a photo wear a generated cloth cover
   in one of twelve binding colours.

**Ledger**
   A table of every volume with status badges, ratings, dates and pages,
   ending in a count row. The Title, Author, Rating and Finished headings sort
   by that column.

Above them, free-text search looks through titles, authors, genres and notes;
the chips filter by status (Read, Reading, TBR, Didn't finish); and the sort
menu orders by recently added, title, author, rating or date finished.
**Show notes** drapes a bookmark ribbon over every book that has notes.

Search is forgiving. Every word you type must appear in the book, in any
order, ignoring case and accents (``herbert dune`` and ``emile`` both work),
and part of a word is enough (``herb`` finds *Herbert*). A word that appears
nowhere in the library is matched to words within a small typo of it, so
``Herbrt`` and ``tolkein`` still find their books; a correctly spelled word
never brings in look-alikes. Words of four letters or fewer must be spelled
right (see :mod:`bookplate.search`).

Adding and editing books
------------------------

**Add book** first offers a search of the Open Library catalogue: picking a
result fills in the title, author and page count, and its cover is fetched
when the book is saved (from Open Library, falling back to iTunes artwork).
Everything can also be typed by hand.

Each book carries a title, author, genre, page count, status, a rating in half
stars, the date it was finished (or stopped, for a book you didn't finish),
an ISBN and a cover. A cover photo can be uploaded in any common image format;
it is centre-cropped to book proportions (2 : 3) and stored as a JPEG of at
most 600 × 900. Without one, the book keeps its generated cover, whose colour
can be chosen.

Two more details are optional, off until switched on in **Settings →
Preferences**: the *source* (book store, Kindle, audiobook, borrowed, second
hand, gifted, library, or your own) and whether a physical *copy* lives at
home. Switching one off only hides it; the data stays, in exports too.

A book's page
-------------

Every book has its own page (``/books/<id>``) with its details, reading
progress, notes and the words learned from it.

Reading progress
   Log the page you're on (or a percentage, for a book without a page count)
   for any day; a second update on the same day replaces the first. The page
   shows how far along you are, when you started, your pace and the days left
   at that pace, and for a finished book how many days it took. The first
   update on a book waiting to be read marks it as *Reading*.

Notes
   Notes are written in Markdown (``## heading``, ``**bold**``, lists, quotes)
   and shown rendered; raw HTML is shown as text. Images pasted or dropped into
   the text, or picked with *add one*, are uploaded at once (downscaled to a
   1600 px long edge) and inserted where the cursor is. Nothing orphans: each
   save deletes images the text no longer uses, *Cancel* discards both the
   edits and any images pasted meanwhile, and deleting a book removes its
   notes, images, progress and cover together.

Vocabulary
----------

The vocabulary page (``/vocabulary``) is a registry of words learned while
reading. Type a word and press **Look up** to search Wiktionary, then pick the
sense to keep, with its part of speech and an example; or write your own
definition. Words can be tagged with the book they came from, and each book's
page lists its own words. The registry can be searched (as forgivingly as the
library), sorted (newest first or A–Z) and filtered by book.

Statistics
----------

The statistics page (``/statistics``) shows tiles for books read, books read
this year, pages read and the average rating (counting only books read to the
end), then charts of books finished per year, ratings given, genres on the
shelf, sources (when switched on) and the books currently being read.

Everything drills down: click a year for that year's books, with its
highest-rated ones first; a rating, genre or source for its books; or *See all
genres* for the full breakdown.

Showcase your year
------------------

**Settings → Profile → Showcase your year** makes a public page of one year's
reading for anyone you send the link to: the year's numbers, every book under
the month it was finished, what you're reading now (this year only) and your
five-star reads. It shows covers, titles, authors, ratings and page counts,
never notes, sources or vocabulary, and always reflects the library as it is
now. Choose the year, whether to show Read, Reading or both, and the name on
it. There is one link per year; saving the same year again keeps its address,
and *Turn off* makes the address stop working at once. Showcases live at
``/s/<random id>`` and ask search engines not to list them.

Import and export
-----------------

**Settings → Import & export** offers:

Export library
   One zip of plain JSON, markdown and image files, in the original
   Bookplate's format (see :mod:`bookplate.archive`).

Import a Bookplate export
   Reads such a zip back into any Bookplate, this port or the original.
   Records with the same ids are overwritten; nothing is deleted.

Import from Goodreads or StoryGraph
   Reads their CSV exports. Re-importing is safe: each row is matched to a
   book already in the library (by the id an earlier import gave it, then
   ISBN, then title and author) and updated in place, keeping its cover,
   colour and notes. Reviews become notes pages.

Accounts
--------

The first visit creates the owner's account. After that, sign-up is closed,
unless the server runs with ``REGISTRATION=open``, which gives everyone who
signs up their own separate library. A sign-in lasts 30 days from the last
visit. **Settings → Security** changes the password (signing out every other
device) or deletes the account with everything in it.
