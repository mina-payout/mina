[%%import "/src/config.mlh"]

open Core_kernel

(* TODO: temporary hack *)
[%%ifdef consensus_mechanism]

[%%versioned
module Stable = struct
  module V1 = struct
    type t =
      | Proof of Pickles.Side_loaded.Proof.Stable.V1.t
      | Signature of Signature.Stable.V1.t
      | None_given
    [@@deriving sexp, equal, yojson, hash, compare]

    let to_latest = Fn.id
  end
end]

let gen : t Quickcheck.Generator.t =
  let open Quickcheck.Let_syntax in
  (* dummy proof and signature *)
  match%bind Int.gen_uniform_incl 0 2 with
  | 0 ->
      let n2 = Pickles_types.Nat.N2.n in
      let proof = Pickles.Proof.dummy n2 n2 n2 in
      return (Proof proof)
  | 1 ->
      return (Signature Signature.dummy)
  | 2 ->
      return None_given
  | n ->
      failwithf "Control.gen: unexpected index %d" n ()

[%%else]

[%%versioned
module Stable = struct
  module V1 = struct
    type t = Proof of unit | Signature of Signature.Stable.V1.t | None_given
    [@@deriving sexp, equal, yojson, hash, compare]

    let to_latest = Fn.id
  end
end]

[%%endif]

module Tag = struct
  type t = Proof | Signature | None_given [@@deriving equal, compare, sexp]
end

let tag : t -> Tag.t = function
  | Proof _ ->
      Proof
  | Signature _ ->
      Signature
  | None_given ->
      None_given
