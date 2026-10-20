Feature: Vocabulary
  A registry of words learned while reading, looked up in Wiktionary and
  optionally tagged with the book they came from.

  Background:
    Given "Ada" has signed up
    And the library has "Dune" by "Frank Herbert" with status "reading"

  Scenario: Looking a word up
    Given Wiktionary defines "melange" as "a mixture of things"
    When they look up "Melange"
    Then the lookup offers "a mixture of things"

  Scenario: A word nobody defines
    When they look up "zzxq"
    Then the lookup has no entry

  Scenario: A word tagged with a book shows on that book's page
    When they save the word "kanly" meaning "a formal feud" from "Dune"
    And they open the page of "Dune"
    Then the page shows "kanly"
    And the page shows "a formal feud"

  Scenario: Filtering the registry by book
    Given they saved the word "kanly" meaning "a formal feud" from "Dune"
    And they saved the word "petrichor" meaning "the smell of rain" from no book
    When they open "/vocabulary?book=<Dune>"
    Then the page shows "kanly"
    And the page does not show "petrichor"

  Scenario: Deleting a word
    Given they saved the word "kanly" meaning "a formal feud" from "Dune"
    When they delete the word "kanly"
    And they open "/vocabulary"
    Then the page does not show "a formal feud"

  Scenario: Saving a word never redirects off the site
    When they save a word with the return address "//evil.example/"
    Then they end up on "/vocabulary"

  Scenario: Searching the registry forgives a typo
    Given they saved the word "petrichor" meaning "the smell of rain" from no book
    And they saved the word "kanly" meaning "a formal feud" from "Dune"
    When they open "/vocabulary?q=petrichr"
    Then the page shows "the smell of rain"
    And the page does not show "a formal feud"
