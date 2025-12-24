{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "act-shell";
  buildInputs = [
    pkgs.docker
    pkgs.git
    pkgs.act
  ];
  shellHook = ''
    echo "✅ Docker is available in this nix-shell."
    echo "➡ Make sure the Docker daemon is running on your system before using act."
    echo "---"
    echo "Running your workflow locally using act (from pkgs.act package, ubuntu-22.04 image mapping):"
    echo "act -P ubuntu-latest=catthehacker/ubuntu:act-22.04 -W .github/workflows/python-package.yml"
    docker pull catthehacker/ubuntu:act-22.04 || true
    act -P ubuntu-latest=catthehacker/ubuntu:act-22.04 --container-options "" -W .github/workflows/python-package.yml
    exit $?
  '';
}
