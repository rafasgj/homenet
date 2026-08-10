Feature: WAN status
  Show the status of all enabled WAN interfaces.

  Scenario: Show connected WAN interfaces
    Given a router with WAN interfaces
    When I run wan status
    Then the output contains "WAN1 (WAN)"
    And the output contains "WAN2 (WAN/LAN1)"
    And the output contains "Upstream"
    And the output contains "Downstream"

  Scenario: Show unconfigured WAN port
    Given a router with WAN interfaces
    And WAN/LAN2 is enabled but not connected
    When I run wan status
    Then the output contains "WAN/LAN2"
    And the output contains "Down"

  Scenario: No WAN interfaces found
    Given a router with no WAN interfaces
    When I run wan status
    Then the output contains "No WAN interfaces found"

  Scenario: JSON output
    Given a router with WAN interfaces
    When I run wan status with --json
    Then the output is valid JSON
    And the JSON output has 2 entries
