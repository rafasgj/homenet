Feature: DHCP unreserve
  Remove a DHCP address reservation.

  Scenario: Delete existing reservation
    Given a router with DHCP reservations
    When I run dhcp unreserve --ip 192.168.0.10
    Then the output contains "Deleted reservation for 192.168.0.10"
    And the API endpoint "/admin/dhcps?form=reservation" was called with method "delete"

  Scenario: Error when reservation not found
    Given a router with no DHCP reservations
    When I run dhcp unreserve --ip 192.168.0.99
    Then the error output contains "No reservation found"
