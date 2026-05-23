# -*- coding: utf-8 -*-
"""生成包含当前局域网 IPv4 的自签名 SSL 证书。"""
import datetime
import ipaddress
import os
import socket

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def discover_ipv4_addresses():
    """收集本机当前可用的 IPv4 地址。"""
    addresses = {"127.0.0.1"}
    hostname = socket.gethostname()

    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            if family == socket.AF_INET and sockaddr:
                addresses.add(sockaddr[0])
    except OSError:
        pass

    # 通过 UDP 套接字获取当前默认出站地址，不会实际发送流量。
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass

    extra_ips = os.environ.get("MYKNOWLEDGE_EXTRA_CERT_IPS", "")
    for ip in extra_ips.split(","):
        ip = ip.strip()
        if ip:
            addresses.add(ip)

    valid_addresses = set()
    for ip in addresses:
        try:
            valid_addresses.add(str(ipaddress.IPv4Address(ip)))
        except ipaddress.AddressValueError:
            continue
    return valid_addresses


def collect_subject_alt_names():
    """构造证书 SAN，包含 localhost、主机名和当前 IPv4。"""
    entries = []
    seen = set()

    def add_dns(name):
        if not name:
            return
        key = ("dns", name)
        if key not in seen:
            seen.add(key)
            entries.append(x509.DNSName(name))

    def add_ip(ip):
        try:
            normalized = str(ipaddress.IPv4Address(ip))
        except ipaddress.AddressValueError:
            return
        key = ("ip", normalized)
        if key not in seen:
            seen.add(key)
            entries.append(x509.IPAddress(ipaddress.IPv4Address(normalized)))

    add_dns("localhost")
    add_dns(socket.gethostname())

    for ip in sorted(discover_ipv4_addresses()):
        add_ip(ip)

    return entries


def build_certificate():
    """生成私钥和证书对象。"""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    ips = sorted(discover_ipv4_addresses())
    common_name = next((ip for ip in ips if ip != "127.0.0.1"), socket.gethostname() or "localhost")
    san_entries = collect_subject_alt_names()

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MyKnowledge"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    now_utc = datetime.datetime.now(datetime.UTC)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now_utc)
        .not_valid_after(now_utc + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .sign(key, hashes.SHA256(), default_backend())
    )

    return key, cert


def write_certificate_files(script_dir=None):
    """写入 cert.pem 和 key.pem。"""
    if script_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    key, cert = build_certificate()
    cert_path = os.path.join(script_dir, "cert.pem")
    key_path = os.path.join(script_dir, "key.pem")

    with open(cert_path, "wb") as cert_file:
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as key_file:
        key_file.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    return cert_path, key_path


def main():
    cert_path, key_path = write_certificate_files()
    print("证书生成成功!")
    print(f"证书路径: {cert_path}")
    print(f"密钥路径: {key_path}")
    print(f"当前 SAN IP: {', '.join(sorted(discover_ipv4_addresses()))}")


if __name__ == "__main__":
    main()
