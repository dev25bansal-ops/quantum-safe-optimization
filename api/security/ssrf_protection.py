"""
SSRF (Server-Side Request Forgery) Protection.

Validates URLs to prevent requests to internal networks and sensitive endpoints.
"""

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Blocked IP ranges - private networks, localhost, etc.
BLOCKED_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),  # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),  # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),  # Private Class C
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("0.0.0.0/8"),  # "This" network
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped addresses
]

# Blocked hostnames
BLOCKED_HOSTNAMES = [
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",  # GCP metadata
    "metadata.azure.com",  # Azure metadata
    "169.254.169.254",  # Cloud metadata IP
]

# Blocked URL schemes
ALLOWED_SCHEMES = ["http", "https"]

# Blocked ports
BLOCKED_PORTS = [
    22,  # SSH
    23,  # Telnet
    25,  # SMTP
    53,  # DNS
    445,  # SMB
    1433,  # MSSQL
    1521,  # Oracle
    3306,  # MySQL
    5432,  # PostgreSQL
    6379,  # Redis
    27017,  # MongoDB
]


def is_ip_private(ip_str: str) -> bool:
    """Check if an IP address is in a private/blocked range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in BLOCKED_PRIVATE_NETWORKS:
            if ip in network:
                return True
        return False
    except ValueError:
        return False


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname to IP addresses."""
    try:
        # Get all IP addresses for the hostname
        results = socket.getaddrinfo(hostname, None)
        ips = []
        for result in results:
            ip = result[4][0]
            if ip not in ips:
                ips.append(ip)
        return ips
    except socket.gaierror:
        return []
    except Exception:
        return []


def is_hostname_blocked(hostname: str) -> bool:
    """Check if hostname is in blocked list."""
    hostname_lower = hostname.lower()
    for blocked in BLOCKED_HOSTNAMES:
        if hostname_lower == blocked.lower() or hostname_lower.endswith(f".{blocked.lower()}"):
            return True

    # Check for IP address patterns in hostname
    ip_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
    if re.match(ip_pattern, hostname):
        return is_ip_private(hostname)

    return False


def validate_url(url: str, allow_localhost: bool = False) -> tuple[bool, str]:
    """
    Validate a URL for SSRF protection.

    Args:
        url: The URL to validate
        allow_localhost: Whether to allow localhost (for development)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL is required"

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"

    # Check scheme
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"URL scheme '{parsed.scheme}' not allowed. Use http or https."

    # Check port
    if parsed.port and parsed.port in BLOCKED_PORTS:
        return False, f"Port {parsed.port} is blocked for security reasons."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must have a hostname"

    # Check blocked hostnames
    if not allow_localhost and is_hostname_blocked(hostname):
        return False, f"Hostname '{hostname}' is blocked (private/internal network)."

    # Resolve hostname and check IPs
    if not allow_localhost:
        ips = resolve_hostname(hostname)
        if not ips:
            # If we can't resolve, we'll allow it but log a warning
            logger.warning(f"Could not resolve hostname: {hostname}")
        else:
            for ip in ips:
                if is_ip_private(ip):
                    return False, f"Hostname '{hostname}' resolves to private IP '{ip}'"

    return True, ""


def validate_webhook_url(url: str) -> tuple[bool, str]:
    """Validate a webhook callback URL."""
    return validate_url(url, allow_localhost=False)


def validate_callback_url(url: str) -> tuple[bool, str]:
    """Validate a job callback URL."""
    return validate_url(url, allow_localhost=False)


# Pre-configured allowed webhook domains (optional allowlist)
ALLOWED_WEBHOOK_DOMAINS = None  # Set via environment variable if needed


def is_domain_allowed(hostname: str) -> bool:
    """Check if domain is in allowed list (if configured)."""
    if ALLOWED_WEBHOOK_DOMAINS is None:
        return True  # No allowlist configured, use blocklist instead

    hostname_lower = hostname.lower()
    for allowed in ALLOWED_WEBHOOK_DOMAINS:
        if hostname_lower == allowed.lower() or hostname_lower.endswith(f".{allowed.lower()}"):
            return True
    return False
