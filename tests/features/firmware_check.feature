Feature: Firmware check
  Check current firmware version and available updates.

  Scenario: Firmware is up to date
    Given a router with firmware version "2.4.5 Build 20260721 Rel.81048"
    And the latest firmware available is "2.4.5"
    When I run firmware check
    Then the output contains "Firmware: 2.4.5 Build 20260721 Rel.81048"
    And the output contains "up to date"

  Scenario: Firmware update available
    Given a router with firmware version "2.3.3 Build 20251029 Rel.70391"
    And the latest firmware available is "2.4.5"
    When I run firmware check
    Then the output contains "Update available: 2.4.5"
    And the output contains "support.omadanetworks.com"

  Scenario: Cannot reach support page
    Given a router with firmware version "2.4.5 Build 20260721 Rel.81048"
    And the support page is unreachable
    When I run firmware check
    Then the output contains "Firmware: 2.4.5"
    And the error output contains "Could not check for updates"

  Scenario: JSON output when up to date
    Given a router with firmware version "2.4.5 Build 20260721 Rel.81048"
    And the latest firmware available is "2.4.5"
    When I run firmware check with --json
    Then the output is valid JSON
    And the JSON field "update_available" is false

  Scenario: JSON output when update available
    Given a router with firmware version "2.3.3 Build 20251029 Rel.70391"
    And the latest firmware available is "2.4.5"
    When I run firmware check with --json
    Then the output is valid JSON
    And the JSON field "update_available" is true
