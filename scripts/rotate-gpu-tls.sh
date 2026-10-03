#!/usr/bin/env bash
# Issue a new GPU gateway server certificate (90 days) signed by the environment's private CA and add it as a new
# version of trend-<env>-gpu-tls. With --new-ca, first create a new CA (365 days): its key goes to
# trend-<env>-gpu-ca-key, which no runtime identity can read, and its certificate to trend-<env>-gpu-ca, which the
# API trusts. Key material exists only in a temporary directory that is removed on exit. Prints version numbers.
#
# Afterwards pin the printed versions: gpu.tls_secret_version for the VM (read at boot by the installer) and, after
# a CA change, services.gpu.ca_secret_version for the API. A new CA and its first server certificate roll together.
set -euo pipefail

environment=${1:?staging or production}
new_ca=${2:-}
project=${PROJECT_ID:-stunning-crane-508614-c1}
case "$environment" in
  staging) address=10.40.1.4 ;;
  production) address=10.41.1.4 ;;
  *) echo "environment must be staging or production" >&2; exit 1 ;;
esac
openssl_image=alpine:3.22@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8
prefix=trend-$environment-gpu
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

gc() { gcloud --project "$project" --quiet "$@"; }
ensure_secret() {
  gc secrets describe "$1" >/dev/null 2>&1 ||
    gc secrets create "$1" --replication-policy user-managed --locations asia-northeast1 \
      --labels "app=trend,environment=$environment" >/dev/null
}
add_version() {
  gc secrets versions add "$1" --data-file "$2" --format 'value(name)' | sed 's#.*/##'
}
openssl_run() {
  docker run --rm -v "$work:/w" -w /w --entrypoint sh "$openssl_image" -ec "apk add -q openssl >/dev/null; $1"
}

if [ "$new_ca" = --new-ca ]; then
  openssl_run "
    openssl ecparam -name prime256v1 -genkey -noout -out ca.key
    openssl req -x509 -new -key ca.key -sha256 -days 365 -subj '/CN=Trend $environment GPU gateway CA' \
      -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' -addext 'keyUsage=critical,keyCertSign,cRLSign' -out ca.pem
    chmod 644 ca.key ca.pem"
  ensure_secret "$prefix-ca-key"
  ensure_secret "$prefix-ca"
  echo "ca_key_version=$(add_version "$prefix-ca-key" "$work/ca.key")"
  echo "ca_version=$(add_version "$prefix-ca" "$work/ca.pem")"
else
  gc secrets versions access latest --secret "$prefix-ca-key" >"$work/ca.key"
  gc secrets versions access latest --secret "$prefix-ca" >"$work/ca.pem"
fi

openssl_run "
  openssl ecparam -name prime256v1 -genkey -noout -out server.key
  openssl req -new -key server.key -subj '/CN=$address' -out server.csr
  printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:$address\n' >ext.cnf
  openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 90 -sha256 -extfile ext.cnf -out server.pem 2>/dev/null
  openssl verify -CAfile ca.pem server.pem >/dev/null
  openssl x509 -in server.pem -noout -enddate >expiry.txt
  chmod 644 server.key server.pem expiry.txt"
python3 -c 'import json,sys;print(json.dumps({"cert_pem":open(sys.argv[1]).read(),"key_pem":open(sys.argv[2]).read()}))' \
  "$work/server.pem" "$work/server.key" >"$work/tls.json"
ensure_secret "$prefix-tls"
echo "tls_version=$(add_version "$prefix-tls" "$work/tls.json")"
echo "server_$(cat "$work/expiry.txt")"
