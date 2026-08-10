Feature: WAN config
  Configure WAN bandwidth and enable/disable WAN ports.

  Scenario: Set downstream and upstream bandwidth
    Given a router with WAN interfaces
    And WAN1 has bandwidth configuration
    When I run wan config WAN --downstream 500m --upstream 250m
    Then the output contains "bandwidth updated"
    And the API endpoint "/admin/interface_wan?form=wanconfig" was called with method "set"

  Scenario: Set only downstream bandwidth
    Given a router with WAN interfaces
    And WAN1 has bandwidth configuration
    When I run wan config WAN --downstream 300m
    Then the output contains "bandwidth updated"

  Scenario: Enable a WAN port
    Given a router with WAN interfaces
    When I run wan config --enable WAN/LAN2
    Then the output contains "Enabling WAN/LAN2"
    And the API endpoint "/admin/interface_wan?form=wanmode" was called with method "set"

  Scenario: Disable a WAN port
    Given a router with WAN interfaces
    When I run wan config --disable WAN/LAN1
    Then the output contains "Disabling WAN/LAN1"

  Scenario: Error when no options given
    Given a router with WAN interfaces
    When I run wan config with no options
    Then the error output contains "at least one of"

  Scenario: Error when bandwidth without WAN name
    Given a router with WAN interfaces
    When I run wan config --downstream 100m without WAN name
    Then the error output contains "WAN_NAME is required"
