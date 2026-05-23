import socket
import unittest
from unittest.mock import patch

from cryptography import x509

from backend import generate_cert


def _stringify_names(names):
    result = []
    for name in names:
        if isinstance(name, x509.DNSName):
            result.append(("dns", name.value))
        elif isinstance(name, x509.IPAddress):
            result.append(("ip", str(name.value)))
    return result


class GenerateCertTests(unittest.TestCase):
    @patch.object(generate_cert, "discover_ipv4_addresses", return_value={"192.168.1.23", "10.0.0.7", "127.0.0.1"})
    @patch.object(socket, "gethostname", return_value="myknowledge-dev")
    def test_collect_subject_alt_names_includes_local_ips_and_defaults(self, _hostname, _discover):
        names = generate_cert.collect_subject_alt_names()
        stringified = _stringify_names(names)

        self.assertIn(("dns", "localhost"), stringified)
        self.assertIn(("dns", "myknowledge-dev"), stringified)
        self.assertIn(("ip", "127.0.0.1"), stringified)
        self.assertIn(("ip", "192.168.1.23"), stringified)
        self.assertIn(("ip", "10.0.0.7"), stringified)

    @patch.object(generate_cert, "discover_ipv4_addresses", return_value={"127.0.0.1"})
    @patch.object(socket, "gethostname", return_value="localhost")
    def test_collect_subject_alt_names_deduplicates_entries(self, _hostname, _discover):
        names = generate_cert.collect_subject_alt_names()
        stringified = _stringify_names(names)

        self.assertEqual(stringified.count(("dns", "localhost")), 1)
        self.assertEqual(stringified.count(("ip", "127.0.0.1")), 1)


if __name__ == "__main__":
    unittest.main()
