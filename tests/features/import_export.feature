Feature: Import and export
  Everything can be exported as a zip of plain JSON, markdown and image
  files, and read back into any Bookplate. Goodreads and StoryGraph CSV
  exports can be imported, and re-imported safely.

  Background:
    Given "Ada" has signed up

  Scenario: An export round-trips into another account
    Given registration is open
    And the library has "Dune" by "Frank Herbert", 600 pages, read on 2024-03-10 rated 5
    And "Dune" has notes with an image, progress, a cover and a word
    When they export the library
    And "Bob" signs up and imports that export
    Then "Bob" has 1 book, 1 word, 1 progress entry and the notes of "Dune"
    And "Bob" can load the cover and note image of "Dune"

  Scenario: A file that isn't an export is refused
    When they import "not a zip" as a library zip
    Then the response status is 400
    And the response says "isn't a readable zip"

  Scenario: Goodreads preview, import and re-import
    When they preview the Goodreads export
    Then the summary has total 6, added 6, read 3, reading 1, toRead 1, dnf 1, notes 2, skipped 1
    And the library has 0 books
    When they import the Goodreads export
    And they import the Goodreads export
    Then the summary has added 0, updated 6
    And the library has 6 books
    And book "gr-234225" is "Dune" with ISBN "9780441013593", rating 5 and read on "2024-03-14"
    And the notes of "gr-234225" contain 'The "spice must flow"'
    And book "gr-424242" has status "dnf"

  Scenario: StoryGraph matches books already imported from Goodreads
    Given they imported the Goodreads export
    When they import the StoryGraph export
    Then the summary has source storygraph, total 4, added 3, updated 1, dnf 1
    And the library has 9 books

  Scenario: A book added by hand keeps its colour and genre
    Given the library has "Project Hail Mary" by "Andy Weir" with status "reading"
    When they import the Goodreads export
    Then "Project Hail Mary" appears once, with status "read", rating 4 and its own id

  Scenario: A CSV from somewhere else is explained
    When they import "a,b\n1,2\n" as a CSV
    Then the response status is 400
    And the response says "Goodreads or StoryGraph"
