Feature: Outside services
  Open Library, iTunes and Wiktionary responses are shaped for the forms.
  These scenarios feed sample responses in each service's documented format.

  Scenario: Open Library search results carry the work id
    Given Open Library answers a search with "Dune" by "Frank Herbert", work "/works/OL893415W", cover 11481354
    When the catalogue is searched for "dune"
    Then the first result is "Dune" by "Frank Herbert" with work id "OL893415W" and cover 11481354

  Scenario: Wiktionary definitions arrive as plain text
    Given Wiktionary answers "melange" with the definition '<a href="/wiki/x">A</a> mixture &amp; blend'
    When the dictionary is asked for "Melange"
    Then the first sense is a "noun" meaning "A mixture & blend"

  Scenario: The cover falls back to iTunes only for the same book
    Given Open Library has no cover and iTunes lists "The Dune Encyclopedia" by "Willis McNelly" then "Dune" by "Frank Herbert"
    When a cover is found for "Dune" by "Frank Herbert"
    Then the iTunes artwork for "Dune" is used
