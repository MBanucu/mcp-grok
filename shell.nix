{ pkgs ? import <nixpkgs> {}, dontrunmenu ? "" }:

pkgs.mkShell {
  packages = with pkgs; [
    uv
    nodejs_latest
  ];

  shellHook = ''
    uv sync --all-extras
    export PATH="$PWD/bin:$PATH"

    if [ -t 1 ] && [ "${dontrunmenu}" != "1" ]; then
      uv run menu.py
    fi
'';
}
