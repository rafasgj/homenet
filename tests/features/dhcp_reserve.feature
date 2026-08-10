Feature: DHCP reserve
  Add or modify a DHCP address reservation.

  Scenario: Add new reservation
    Given a router with no DHCP reservations
    When I run dhcp reserve --ip 192.168.0.50 --mac AA:BB:CC:DD:EE:FF
    Then the output contains "Added reservation for 192.168.0.50"
    And the API endpoint "/admin/dhcps?form=reservation" was called with method "add"

  Scenario: Update existing reservation
    Given a router with DHCP reservations
    When I run dhcp reserve --ip 192.168.0.10 --name "new name"
    Then the output contains "Updated reservation for 192.168.0.10"
    And the API endpoint "/admin/dhcps?form=reservation" was called with method "set"

  Scenario: Error when new reservation without MAC
    Given a router with no DHCP reservations
    When I run dhcp reserve --ip 192.168.0.50 without MAC
    Then the error output contains "--mac is required"
