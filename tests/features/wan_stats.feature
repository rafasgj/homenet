Feature: WAN stats
  Show or clear traffic statistics for WAN interfaces.

  Scenario: Show traffic statistics
    Given a router with WAN interfaces
    And the router has interface statistics
    When I run wan stats
    Then the output contains "RX Rate"
    And the output contains "TX Rate"
    And the output contains "Total RX"

  Scenario: Clear statistics
    Given a router with WAN interfaces
    When I run wan stats --clear
    Then the output contains "Statistics cleared"
    And the API endpoint "/admin/ifstat?form=list" was called with method "clear"

  Scenario: JSON output
    Given a router with WAN interfaces
    And the router has interface statistics
    When I run wan stats with --json
    Then the output is valid JSON
