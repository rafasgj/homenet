Feature: DHCP assigned
  List hosts that currently hold a DHCP lease.

  Scenario: List DHCP clients
    Given a router with DHCP clients
    When I run dhcp assigned
    Then the output contains "desktop-pc"
    And the output contains "192.168.0.100"

  Scenario: Filter by LAN
    Given a router with DHCP clients
    When I run dhcp assigned --lan LAN
    Then the output contains "192.168.0.100"

  Scenario: No DHCP clients
    Given a router with no DHCP clients
    When I run dhcp assigned
    Then the output contains "No DHCP clients found"

  Scenario: JSON output
    Given a router with DHCP clients
    When I run dhcp assigned with --json
    Then the output is valid JSON
