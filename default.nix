# default.nix – legacy non-flake entrypoint that forwards to the flake
let
  flake = builtins.getFlake (toString ./.);
  system = builtins.currentSystem or "x86_64-linux";
in
flake.packages.${system}.default