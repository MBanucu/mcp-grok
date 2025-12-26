{ pkgs ? import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixos-25.11.tar.gz") {}, pythonVersion ? "312", dontrunmenu ? "" }:

let
  python = builtins.getAttr ("python" + pythonVersion) pkgs;
in
pkgs.mkShell {
  buildInputs = [
    python
    pkgs.python312Packages.requests
    pkgs.python312Packages.pytest
    pkgs.python312Packages.flake8
    pkgs.python312Packages.prompt-toolkit
    pkgs.python312Packages.mcp
    pkgs.pyright
    pkgs.git
  ];

  shellHook = ''
    export PYTHONPATH="$PWD/src:$PWD/tests:$PYTHONPATH"
    export PATH="$PWD/bin:$PATH"
    if [ -t 1 ] && [ "${dontrunmenu}" != "1" ]; then
      python -m menu.menu
      exit $?
    fi
  '';
}
