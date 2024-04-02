{ pkgs, ... }:

{
  languages.python = {
    enable = true;
    package = pkgs.python312;
    poetry.enable = true;
    # libraries = [
    #   pkgs.libgcc
    # ];
    # manylinux.enable = true;
  };
  env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
    pkgs.gcc-unwrapped
  ];
}
