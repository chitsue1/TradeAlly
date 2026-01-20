{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.pandas
    pkgs.python311Packages.ta
    pkgs.python311Packages.requests
  ];
}