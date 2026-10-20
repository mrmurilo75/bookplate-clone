Feature: Accounts
  The first visit creates the owner's account; after that sign-up is closed
  unless registration is open. Every API route needs a signed-in reader.

  Scenario: The first visit asks for the owner's account
    Given a new Bookplate
    When a visitor opens "/"
    Then they end up on "/setup"
    And the page shows "Create your account"

  Scenario: Sign-up closes once the owner exists
    Given "Ada" has an account
    When a visitor tries to sign up as "Bob"
    Then the response status is 400
    And the page shows "Sign-up is closed"

  Scenario: Open registration lets others sign up to their own library
    Given registration is open
    And "Ada" has an account
    When a visitor tries to sign up as "Bob"
    Then they end up on "/"

  Scenario: A wrong password is refused
    Given "Ada" has an account
    When a visitor signs in as "ada@example.com" with "wrong-password"
    Then the response status is 400
    And the page shows "Wrong email or password."

  Scenario: Signing in and out
    Given "Ada" has an account
    When a visitor signs in as "ada@example.com" with "password123"
    Then they end up on "/"
    When they sign out
    Then they end up on "/login"

  Scenario: The API needs a session
    Given "Ada" has an account
    When a visitor calls "/api/books"
    Then the response status is 401

  Scenario: Changing the password signs out other devices
    Given "Ada" has an account
    And "Ada" is also signed in on a second device
    When "Ada" changes the password from "password123" to "new-password-1"
    Then the second device is signed out
    And "Ada" can sign in with "new-password-1"

  Scenario: Deleting the account removes everything in it
    Given "Ada" has an account
    And the library has "Dune" by "Frank Herbert" with status "read"
    When "Ada" deletes the account with "password123"
    Then they end up on "/setup"
    And no rows or images of "Ada" are left
