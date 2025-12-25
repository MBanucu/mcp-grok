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
    export UV_PYTHON=$(which python)
    export PYTHONPATH=$PWD/src:$PWD/tests
    export PATH="$PWD/bin:$PATH"
    uv sync --all-extras
    echo "uv     python version = $(uv run python --version)"
    echo "system python version = $(python --version)"
    if [ -t 1 ] && [ "${dontrunmenu}" != "1" ]; then
      uv run python -m menu.menu
      exit $?
    fi
  '';
}
