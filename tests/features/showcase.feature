Feature: Showcase your year
  A public page of one year's reading at /s/<id>, with covers, titles,
  authors, ratings and page counts — never notes, sources or ownership.

  Background:
    Given "Ada" has signed up
    And the library has "Dune" by "Frank Herbert", 600 pages, read on 2024-03-10 rated 5
    And the library has "Emma" by "Jane Austen", 400 pages, read on 2023-07-01 rated 4

  Scenario: A showcase shows that year's books to anyone with the link
    Given "Dune" has the notes "secret thoughts" and a cover
    When they showcase 2024 as "James"
    And a stranger opens the showcase
    Then the page shows "James’ 2024 in books"
    And the page shows "Dune"
    And the page does not show "Emma"
    And the page does not show "secret thoughts"
    And the page shows "noindex"
    And the stranger can load the cover of "Dune"

  Scenario: Saving the same year again keeps its address
    When they showcase 2024 as "Ada"
    And they showcase 2024 as "A. L."
    Then there is 1 showcase with the name "A. L."

  Scenario: Books being read only belong in this year's showcase
    When they try to showcase reading books for 2023
    Then the response status is 400
    And the page shows "only go in this year"

  Scenario: Turning a showcase off makes the address stop working
    Given they showcased 2024
    When they turn the showcase off
    And a stranger opens the showcase
    Then the response status is 404
