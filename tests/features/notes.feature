Feature: A notes page per book
  Notes are markdown with images pasted inline. Nothing orphans: every save
  removes stored images the text no longer references, and Cancel bins images
  pasted during the session.

  Background:
    Given "Ada" has signed up
    And the library has "Dune" by "Frank Herbert" with status "reading"

  Scenario: Notes render as markdown, with raw HTML kept as text
    When they save the notes of "Dune" as "## Arrakis\n**spice** <script>x</script>"
    And they open the page of "Dune"
    Then the page shows "<h2>Arrakis</h2>"
    And the page shows "<strong>spice</strong>"
    And the page shows "&lt;script&gt;"

  Scenario: Notes are searchable from the library
    When they save the notes of "Dune" as "The sleeper must awaken"
    And they open "/?q=sleeper"
    Then the page shows "Dune"

  Scenario: Images removed from the text are deleted on save
    Given they pasted an image into the notes of "Dune"
    When they save the notes of "Dune" as "No pictures any more"
    Then "Dune" has 0 stored note images

  Scenario: Images still in the text are kept
    Given they pasted an image into the notes of "Dune"
    When they save the notes of "Dune" with the pasted image
    Then "Dune" has 1 stored note images
    And the pasted image can be loaded

  Scenario: Cancel keeps the saved text and bins pasted images
    Given they saved the notes of "Dune" as "Kept"
    And they pasted an image into the notes of "Dune"
    When they cancel editing the notes of "Dune"
    Then "Dune" has 0 stored note images
    And the notes of "Dune" are "Kept"
