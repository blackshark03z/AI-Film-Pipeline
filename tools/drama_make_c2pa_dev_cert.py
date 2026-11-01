"""Generate a LOCAL development ES256 certificate chain for C2PA signing.

Writes root_ca.pem, signer_cert.pem (end-entity + root chain) and
signer_key.pem to --out (default %LOCALAPPDATA%/film_pipeline/c2pa_dev/,
outside the repo). The chain is self-issued: validators report the signer as
untrusted, the manifest still binds the content hash. Never commit the keys.
    uv run python tools/drama_make_c2pa_dev_cert.py [--out DIR] [--force]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from film_pipeline.drama.disclosure import default_dev_cert_dir  # noqa: E402


def _name(cn: str):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    return x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AI Film Pipeline (dev)"),
        x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def generate(out: Path, force: bool = False) -> dict[str, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID

    paths = {k: out / f"{k}.pem" for k in
             ("root_ca", "signer_cert", "signer_key")}
    if all(p.exists() for p in paths.values()) and not force:
        return paths
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    root_key = ec.generate_private_key(ec.SECP256R1())
    root_name = _name("AFP Dev Test Root CA")
    root = (x509.CertificateBuilder()
            .subject_name(root_name).issuer_name(root_name)
            .public_key(root_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                root_key.public_key()), False)
            .sign(root_key, hashes.SHA256()))
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (x509.CertificateBuilder()
            .subject_name(_name("AFP Dev Test Signer")).issuer_name(root_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + dt.timedelta(days=825))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                           True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False), True)
            .add_extension(x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.EMAIL_PROTECTION]), False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                key.public_key()), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                root_key.public_key()), False)
            .sign(root_key, hashes.SHA256()))
    pem = serialization.Encoding.PEM
    paths["root_ca"].write_bytes(root.public_bytes(pem))
    paths["signer_cert"].write_bytes(leaf.public_bytes(pem) +
                                     root.public_bytes(pem))
    paths["signer_key"].write_bytes(key.private_bytes(
        pem, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    try:
        os.chmod(paths["signer_key"], 0o600)
    except OSError:
        pass
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=default_dev_cert_dir())
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    for k, p in generate(args.out, args.force).items():
        print(k, p)


if __name__ == "__main__":
    main()
