Feature: The library
  Books carry ratings, reading dates and their own notes, in a covers grid or
  a ledger, with search, status filters and sorting. Every row belongs to one reader.

  Background:
    Given "Ada" has signed up

  Scenario: Adding a book shows it in both views
    When they add "Dune" by "Frank Herbert" with status "read" and rating 4.5
    And they open "/"
    Then the page shows "Dune"
    When they open "/?view=ledger"
    Then the page shows "Frank Herbert"
    And the page shows "1 book"

  Scenario: A book needs a title and an author
    When they add a book without a title
    Then the response status is 400
    And the page shows "A book needs a title and an author."

  Scenario: Searching and filtering
    Given the library has "Dune" by "Frank Herbert" with status "read"
    And the library has "Emma" by "Jane Austen" with status "to-read"
    When they open "/?q=austen"
    Then the page shows "Emma"
    And the page does not show "Dune"
    When they open "/?status=read"
    Then the page shows "Dune"
    And the page does not show "Emma"

  Scenario: Sorting by title
    Given the library has "Zorba" by "Nikos Kazantzakis" with status "read"
    And the library has "Anna Karenina" by "Leo Tolstoy" with status "read"
    When they open "/?sort=title"
    Then "Anna Karenina" comes before "Zorba"

  Scenario: Editing a book
    Given the library has "Dune" by "Frank Herbert" with status "reading"
    When they change the genre of "Dune" to "Science fiction"
    And they open the page of "Dune"
    Then the page shows "Science fiction"

  Scenario: An uploaded cover is cropped to book proportions
    Given the library has "Dune" by "Frank Herbert" with status "read"
    When they upload a 1200x1200 cover for "Dune"
    Then the stored cover of "Dune" is a 600x900 JPEG

  Scenario: Deleting a book removes its notes, progress and cover
    Given the library has "Dune" by "Frank Herbert" with status "reading"
    And "Dune" has notes, progress and a cover
    When they delete "Dune"
    Then nothing of "Dune" is left

  Scenario: Readers never see each other's books
    Given registration is open
    And the library has "Dune" by "Frank Herbert" with status "read"
    And "Bob" has signed up
    When they open "/api/books"
    Then the page does not show "Dune"
    When they open "/books/<Dune>"
    Then the response status is 404
