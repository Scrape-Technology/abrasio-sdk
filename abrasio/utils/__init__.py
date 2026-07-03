"""Utility functions for Abrasio SDK."""

from .human import (
    human_move_to,
    human_click,
    human_type,
    human_scroll,
    random_delay,
    human_wait,
    simulate_reading,
)

# Region validation utilities (always available)
from .fingerprint import (
    validate_region_consistency,
    auto_configure_region,
    get_region_config,
    list_supported_regions,
    get_realistic_screen,
    get_realistic_locale,
    REGION_CONFIG,
)

# IP-based geolocation (for local mode auto-configuration)
from .geolocation import (
    detect_geolocation,
    get_locale_timezone_from_ip,
    clear_geolocation_cache,
    GeoLocation,
)

# Client certificates (TLS Client Authentication)
from .certificates import build_client_certificate, route_with_client_certificate

__all__ = [
    # Human behavior
    "human_move_to",
    "human_click",
    "human_type",
    "human_scroll",
    "random_delay",
    "human_wait",
    "simulate_reading",
    # Region utilities (always available)
    "validate_region_consistency",
    "auto_configure_region",
    "get_region_config",
    "list_supported_regions",
    "get_realistic_screen",
    "get_realistic_locale",
    "REGION_CONFIG",
    # IP-based geolocation
    "detect_geolocation",
    "get_locale_timezone_from_ip",
    "clear_geolocation_cache",
    "GeoLocation",
    # Client certificates
    "build_client_certificate",
    "route_with_client_certificate",
]

# Optional fingerprint utilities (requires browserforge)
try:
    from .fingerprint import (
        generate_fingerprint,
        validate_fingerprint_consistency,
    )
    __all__.extend([
        "generate_fingerprint",
        "validate_fingerprint_consistency",
    ])
except ImportError:
    # browserforge not installed
    pass
