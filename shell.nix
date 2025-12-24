{ pkgs ? import <nixpkgs> {}
, pythonVersion ? "312"
, dontrunmenu ? ""
}:

let
  python = builtins.getAttr ("python" + pythonVersion) pkgs;
in
pkgs.mkShell {
  packages = with pkgs; [
    python
    uv
    nodejs_latest
  ];

  shellHook = ''
    export PATH="$PWD/bin:$PATH"
    uv sync --all-extras
    if [ -t 1 ] && [ "${dontrunmenu}" != "1" ]; then
      uv run menu.py
      exit $?
    fi
  '';
}
