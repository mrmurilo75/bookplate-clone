Feature: Reading progress
  One update per book per day, in pages when the book has a page count and
  as a percentage otherwise.

  Background:
    Given "Ada" has signed up

  Scenario: Logging pages shows the percentage and the pace
    Given the library has "Dune" by "Frank Herbert", 600 pages, read on 2024-03-10 rated 5
    When they log page 100 of "Dune" on 2024-03-01
    And they log page 400 of "Dune" on 2024-03-04
    And they open the page of "Dune"
    Then the page shows "67%"
    And the page shows "page 400 of 600"
    And the page shows "read in 9 days"

  Scenario: The first update marks a waiting book as started
    Given the library has "Emma" by "Jane Austen" with status "to-read"
    When they log page 30 of "Emma" on 2024-03-01
    Then "Emma" has status "reading"

  Scenario: A second update on the same day replaces the first
    Given the library has "Emma" by "Jane Austen" with status "reading"
    When they log page 30 of "Emma" on 2024-03-01
    And they log page 45 of "Emma" on 2024-03-01
    Then "Emma" has 1 progress entry at 45 percent

  Scenario: The API refuses a page past the end
    Given the library has "Dune" by "Frank Herbert", 600 pages, read on 2024-03-10 rated 5
    When they send page 700 of "Dune" to the API
    Then the response status is 400
