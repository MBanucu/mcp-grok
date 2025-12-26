{
  description = "MCP-Grok: Persistent project shell and API server";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in {
      packages.${system}.default = pkgs.python312Packages.buildPythonApplication {
        pname = "mcp-grok";
        version = "0.1.0";
        src = ./.;
        format = "pyproject";
        propagatedBuildInputs = [
          pkgs.python312Packages.mcp
          pkgs.python312Packages.prompt-toolkit
        ];
        nativeBuildInputs = with pkgs.python312Packages; [ setuptools wheel pip ];
        installPhase = ''
          runHook preInstall
          ${pkgs.python312Packages.pip}/bin/pip install . --prefix=$out --no-build-isolation --no-deps
          mkdir -p $out/bin
          cp ./bin/superassistant-proxy $out/bin/superassistant-proxy
          chmod +x $out/bin/superassistant-proxy
          cp ./bin/config.json $out/bin/config.json
          runHook postInstall
        '';
        meta = with pkgs.lib; {
          description = "FastMCP-based persistent project shell and API server (mcp-grok-server)";
          homepage = "https://github.com/MBanucu/mcp-grok";
          license = licenses.gpl3Only;
          maintainers = [];
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
          ];
          inputsFrom = [ self.packages.${system}.default ];
          shellHook = ''
            export PYTHONPATH="$PWD/src:$PWD/tests:$PYTHONPATH"
            export PATH="$PWD/bin:$PATH"
            echo "[devShell] PYTHONPATH set to $PYTHONPATH"
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
          ];
          inputsFrom = [ self.packages.${system}.default ];
          shellHook = ''
            export PYTHONPATH="$PWD/src:$PWD/tests:$PYTHONPATH"
            export PATH="$PWD/bin:$PATH"
            echo "[devShell(menuSuppressed)] PYTHONPATH set to $PYTHONPATH (menu suppressed)"
          '';
        };
      };




    };
}
