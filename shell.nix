{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    python312
    uv
    nodejs_latest
  ];

  shellHook = ''
    uv sync
    export PATH="$PWD/.venv/bin:$PWD/.bin:$PWD/bin:$PWD/node_modules/.bin:$PATH"
    alias test=".venv/bin/pytest"

  if [ ! -z "$TEST_MENU" ]; then
    echo "Running shell test mode via pytest"
    .venv/bin/pytest
    exit $?
  fi

  if [ -t 1 ]; then
    python menu.py
  fi
'';
}
