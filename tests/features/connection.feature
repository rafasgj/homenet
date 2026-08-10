Feature: Connection errors
  Handle router connection failures gracefully.

  Scenario: TLS certificate verification failure
    Given the router's TLS certificate has changed
    When I run any command against the router
    Then the error output contains "TLS certificate verification failed"
    And the error output contains "homenet certificate trust"

  Scenario: Invalid password
    Given the router rejects the password
    When I run any command against the router
    Then the error output contains "Invalid username or password"
