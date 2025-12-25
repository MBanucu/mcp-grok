{ pkgs ? import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixos-25.11.tar.gz") {} }:

pkgs.python312Packages.buildPythonApplication {
  pname = "mcp-grok";
  version = "0.1.0";

  src = ./.;
  format = "pyproject";

  propagatedBuildInputs = [
    pkgs.python312Packages.mcp
    pkgs.python312Packages.prompt-toolkit
    pkgs.python312Packages.pytest
  ];
  nativeBuildInputs = with pkgs.python312Packages; [
    setuptools
    wheel
    pip
  ];

  # Custom installPhase to also install superassistant-proxy
  installPhase = ''
    runHook preInstall
    # Install the python package
    ${pkgs.python312Packages.pip}/bin/pip install . --prefix=$out --no-build-isolation --no-deps
    # Install the shell script
    mkdir -p $out/bin
    cp ./bin/superassistant-proxy $out/bin/superassistant-proxy
    chmod +x $out/bin/superassistant-proxy
    runHook postInstall
  '';

  meta = with pkgs.lib; {
    description = "FastMCP-based persistent project shell server";
    homepage = "https://github.com/MBanucu/mcp-grok";
    license = licenses.gpl3Only;
    maintainers = [ ];
    mainProgram = "mcp-grok";
  };
}

