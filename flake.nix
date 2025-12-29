{
  description = "MCP-Grok: Persistent project shell and API server";

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in
    {
      packages.${system}.default = pkgs.python312Packages.buildPythonApplication {
        pname = "mcp-grok";
        version = "0.1.5";
        src = ./.;
        format = "pyproject";
        propagatedBuildInputs = [
          pkgs.python312Packages.mcp
          pkgs.python312Packages.prompt-toolkit
        ];
        nativeBuildInputs = with pkgs.python312Packages; [
          setuptools
          wheel
          pip
        ];
        postInstall = ''
          mkdir -p $out/bin
          cp $src/bin/superassistant-proxy $out/bin/superassistant-proxy
          chmod +x $out/bin/superassistant-proxy
          cp $src/bin/config.json $out/bin/config.json
        '';
        meta = with pkgs.lib; {
          description = "FastMCP-based persistent project shell and API server (mcp-grok-server)";
          homepage = "https://github.com/MBanucu/mcp-grok";
          license = licenses.gpl3Only;
          maintainers = [ ];
          mainProgram = "mcp-grok-server";
        };
      };
      devShells.${system} = {
        default = pkgs.mkShell {
          buildInputs = [
            pkgs.python312
            pkgs.python312Packages.pytest
            pkgs.python312Packages.flake8
            pkgs.pyright
            pkgs.python312Packages.requests
            pkgs.git
            pkgs.gh
            pkgs.jq
            pkgs.unzip
          ];
          inputsFrom = [ self.packages.${system}.default ];
          shellHook = ''
            export PYTHONPATH="$PWD/src:$PWD/tests:$PYTHONPATH"
            export PATH="$PWD/bin:$PATH"
            python -m menu.menu
            exit $?
          '';
        };
        menuSuppressed = pkgs.mkShell {
          buildInputs = [
            pkgs.python312
            pkgs.python312Packages.pytest
            pkgs.python312Packages.flake8
            pkgs.pyright
            pkgs.python312Packages.requests
            pkgs.git
            pkgs.gh
            pkgs.jq
            pkgs.unzip
          ];
          inputsFrom = [ self.packages.${system}.default ];
          shellHook = ''
            export PYTHONPATH="$PWD/src:$PWD/tests:$PYTHONPATH"
            export PATH="$PWD/bin:$PATH"
          '';
        };
      };
    };
}
