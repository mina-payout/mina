with import <nixpkgs> {};
mkShell {
  nativeBuildInputs = 
    [ opam pkgconfig
      m4 openssl gmp jemalloc libffi
      libsodium postgresql
      rustup # ships both cargo and rustc
      zlib bzip2
      capnproto go_1_16
    ];
  shellHook = ''
    eval $(opam env 2>/dev/null)
    '';
}
