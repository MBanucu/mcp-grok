{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    python312
    uv
    nodejs_latest
  ];

  shellHook = ''
    uv sync --all-extras
    export PATH="$PWD/.venv/bin:$PWD/.bin:$PWD/bin:$PWD/node_modules/.bin:$PATH"

  if [ -t 1 ]; then
    python menu.py
  fi
'';
}
