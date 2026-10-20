Feature: Statistics
  Stat tiles and charts that drill down into the books behind each number.

  Background:
    Given "Ada" has signed up
    And the library has "Dune" by "Frank Herbert", 600 pages, read on 2023-03-10 rated 5
    And the library has "Emma" by "Jane Austen", 400 pages, read on 2023-07-01 rated 3
    And the library has "Ulysses" by "James Joyce" with status "reading"

  Scenario: The tiles count only finished books
    When they open "/statistics"
    Then the page shows "1,000"
    And the page shows "4.0 ★"
    And the page shows "Ulysses"

  Scenario: Drilling into a year shows its highest-rated books first
    When they open "/statistics?drill=year&v=2023"
    Then the page shows "Read in 2023"
    And the page shows "Highest rated (5 ★)"
    And "Highest rated" comes before "In reading order"

  Scenario: Drilling into a rating
    When they open "/statistics?drill=rating&v=3"
    Then the page shows "Rated 3 ★"
    And the page shows "Emma"
