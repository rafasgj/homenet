Feature: DHCP reserved
  List static DHCP address reservations.

  Scenario: List reservations
    Given a router with DHCP reservations
    When I run dhcp reserved
    Then the output contains "server"
    And the output contains "192.168.0.10"

  Scenario: Filter by LAN
    Given a router with DHCP reservations
    When I run dhcp reserved --lan LAN
    Then the output contains "192.168.0.10"

  Scenario: No reservations
    Given a router with no DHCP reservations
    When I run dhcp reserved
    Then the output contains "No DHCP reservations found"

  Scenario: JSON output
    Given a router with DHCP reservations
    When I run dhcp reserved with --json
    Then the output is valid JSON
