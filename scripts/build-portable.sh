#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
case "$(uname -m)" in
 x86_64) rbm_target=x86_64-unknown-linux-musl ;;
 aarch64) rbm_target=aarch64-unknown-linux-musl ;;
 *) echo 'Build natively or select a supported musl target manually.' >&2; exit 1 ;;
esac
rustup target list --installed | grep -qx "$rbm_target" || {
    echo "First install the target: rustup target add $rbm_target" >&2
    exit 1
}
RBM_TARGET="$rbm_target" scripts/build-deb.sh
