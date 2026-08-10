Feature: WAN test
  Test WAN connectivity by pinging a remote host.

  Scenario: Ping succeeds
    Given a router with WAN interfaces
    And ping returns a successful result
    When I run wan test
    Then the output contains "OK"
    And the output contains "PASS"

  Scenario: Ping fails
    Given a router with WAN interfaces
    And ping returns a failure result
    When I run wan test
    Then the output contains "FAIL"

  Scenario: JSON output
    Given a router with WAN interfaces
    And ping returns a successful result
    When I run wan test with --json
    Then the output contains valid JSON
