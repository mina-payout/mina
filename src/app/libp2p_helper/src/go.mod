module codanet

go 1.13

require (
	capnproto.org/go/capnp/v3 v3.0.0-alpha.1
	github.com/AndreasBriese/bbloom v0.0.0-20190825152654-46b345b51c96 // indirect
	github.com/campoy/jsonenums v0.0.0-20180221195324-eec6d38da64e
	github.com/dgraph-io/ristretto v0.0.3 // indirect
	github.com/dgryski/go-farm v0.0.0-20200201041132-a6ae2369ad13 // indirect
	github.com/georgeee/go-bs-lmdb v1.0.6-0.20210916154400-0f7f708a2364
	github.com/go-errors/errors v1.0.1
	github.com/golang/snappy v0.0.1 // indirect
	github.com/ipfs/go-bitswap v0.4.0
	github.com/ipfs/go-ds-badger v0.2.4
	github.com/ipfs/go-log v1.0.5
	github.com/ipfs/go-log/v2 v2.1.3
	github.com/libp2p/go-libp2p v0.14.3
	github.com/libp2p/go-libp2p-connmgr v0.2.4
	github.com/libp2p/go-libp2p-core v0.8.5
	github.com/libp2p/go-libp2p-discovery v0.5.0
	github.com/libp2p/go-libp2p-kad-dht v0.10.0
	github.com/libp2p/go-libp2p-mplex v0.4.1
	github.com/libp2p/go-libp2p-peerstore v0.2.7
	github.com/libp2p/go-libp2p-pubsub v0.3.4
	github.com/libp2p/go-libp2p-record v0.1.3
	github.com/libp2p/go-mplex v0.3.0
	github.com/multiformats/go-multiaddr v0.3.3
	github.com/prometheus/client_golang v1.10.0
	github.com/stretchr/testify v1.7.0
	golang.org/x/crypto v0.0.0-20210322153248-0c34fe9e7dc2
	golang.org/x/lint v0.0.0-20201208152925-83fdc39ff7b5 // indirect
	golang.org/x/mod v0.4.0 // indirect
	google.golang.org/grpc v1.34.0 // indirect
	honnef.co/go/tools v0.0.1-2020.1.4 // indirect
	libp2p_ipc v0.0.0
)

replace libp2p_ipc => ../../../libp2p_ipc
