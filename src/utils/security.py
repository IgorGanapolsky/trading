# ruff: noqa: UP045
"""
Security utilities for AI trading system.

This module provides:
1. API key/secret masking for logs
2. Prompt injection detection and defense
3. LLM output validation for trade signals
4. Input sanitization for all external data

Based on OWASP LLM Top 10 2025 and OpenAI security best practices.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# PROMPT INJECTION DEFENSE
# =============================================================================


class ThreatLevel(Enum):
    """Threat classification for detected attacks."""

    NONE = "none"
    LOW = "low"  # Suspicious but possibly benign
    MEDIUM = "medium"  # Likely attack attempt
    HIGH = "high"  # Definite attack
    CRITICAL = "critical"  # Active exploitation attempt


@dataclass
class SecurityScanResult:
    """Result of security scan on input text."""

    is_safe: bool
    threat_level: ThreatLevel
    threats_detected: list[str]
    sanitized_text: str | None  # None if blocked entirely
    original_length: int
    blocked: bool


class PromptInjectionDefense:
    """
    Multi-layer prompt injection detection and defense.

    Based on:
    - OWASP LLM01:2025 Prompt Injection guidelines
    - OpenAI's Atlas hardening research (Dec 2025)
    - Lakera prompt injection defense patterns

    Usage:
        defense = PromptInjectionDefense()
        result = defense.scan("user input here")
        if not result.is_safe:
            raise SecurityError(f"Blocked: {result.threats_detected}")
    """

    # Direct injection patterns - attempts to override system behavior
    DIRECT_INJECTION_PATTERNS = [
        # System prompt overrides
        (r"ignore\s+(all\s+)?previous\s+instructions?", "system_override"),
        (r"disregard\s+(all\s+)?(prior|previous|above)", "system_override"),
        (r"forget\s+(everything|all|your)(\s+\w+)*", "system_override"),  # More flexible
        (r"new\s+system\s+prompt", "system_override"),
        (r"you\s+are\s+now\s+a", "role_hijack"),
        (r"act\s+as\s+(if\s+you\s+are\s+)?a?\s*different", "role_hijack"),  # More flexible
        (r"pretend\s+(you\s+are|to\s+be)\s+a", "role_hijack"),
        (r"from\s+now\s+on[,\s]+you", "role_hijack"),
        # Jailbreak attempts
        (r"ignore\s+safety\s+guidelines?", "jailbreak"),
        (r"bypass\s+(security|restrictions?|filters?)", "jailbreak"),
        (r"disable\s+(safety|security|restrictions?)", "jailbreak"),
        (r"override\s+(safety|security|your)\s+\w*\s*protocols?", "jailbreak"),  # More flexible
        (r"do\s+anything\s+now", "jailbreak"),  # DAN pattern
        (r"developer\s+mode\s+(enabled|activated)", "jailbreak"),
        # Instruction injection
        (r"\[system\]|\[assistant\]|\[user\]", "format_injection"),
        (r"<\|?(system|assistant|user)\|?>", "format_injection"),
        (r"###\s*(system|instruction|prompt)", "format_injection"),
    ]

    # Indirect injection patterns - hidden in data/content
    INDIRECT_INJECTION_PATTERNS = [
        # Hidden instructions in data
        (r"when\s+you\s+(see|read|process)\s+this", "hidden_instruction"),
        (r"if\s+an?\s+(ai|llm|assistant)\s+(reads?|sees?)", "hidden_instruction"),
        (r"note\s+to\s+(ai|llm|assistant|claude)", "hidden_instruction"),
        (r"attention\s+(ai|llm|model)", "hidden_instruction"),
        # Data exfiltration attempts
        (r"(send|transmit|post|email)\s+.*(api.?key|secret|password)", "exfiltration"),
        (r"(include|add|append)\s+.*(credentials?|tokens?)\s+in", "exfiltration"),
        (r"reveal\s+(your|the)\s+(system|initial)\s+prompt", "exfiltration"),
        (r"show\s+me\s+(your|the)\s+instructions?", "exfiltration"),
        # Trading-specific attacks
        (r"(buy|sell)\s+all\s+(positions?|shares?|stocks?)", "trade_manipulation"),
        (r"execute\s+maximum\s+(position|trade|order)", "trade_manipulation"),
        (r"bypass\s+(risk|trade)\s+gateway", "trade_manipulation"),
        (r"override\s+(position|risk)\s+limits?", "trade_manipulation"),
        (r"ignore\s+(stop.?loss|risk\s+management)", "trade_manipulation"),
        (r"disable\s+circuit\s+breakers?", "trade_manipulation"),
    ]

    # Encoding/obfuscation patterns
    OBFUSCATION_PATTERNS = [
        (r"\\x[0-9a-fA-F]{2}", "hex_encoding"),
        (r"\\u[0-9a-fA-F]{4}", "unicode_escape"),
        (r"&#x?[0-9a-fA-F]+;", "html_entity"),
        (r"base64[:\s]", "base64_mention"),
        (r"eval\s*\(", "code_injection"),
        (r"exec\s*\(", "code_injection"),
    ]

    # Separator/delimiter abuse
    DELIMITER_PATTERNS = [
        (r"-{10,}", "delimiter_abuse"),
        (r"={10,}", "delimiter_abuse"),
        (r"\*{10,}", "delimiter_abuse"),
        (r"#{10,}", "delimiter_abuse"),
        (r"</?[a-z]+>.*</?[a-z]+>", "html_tags"),
    ]

    def __init__(self, strict_mode: bool = True):
        """
        Initialize defense system.

        Args:
            strict_mode: If True, blocks on LOW threats. If False, only HIGH+.
        """
        self.strict_mode = strict_mode
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._direct = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.DIRECT_INJECTION_PATTERNS
        ]
        self._indirect = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.INDIRECT_INJECTION_PATTERNS
        ]
        self._obfuscation = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.OBFUSCATION_PATTERNS
        ]
        self._delimiters = [(re.compile(p, re.IGNORECASE), t) for p, t in self.DELIMITER_PATTERNS]

    def scan(self, text: str) -> SecurityScanResult:
        """
        Scan text for prompt injection attempts.

        Args:
            text: Input text to scan

        Returns:
            SecurityScanResult with threat assessment
        """
        if not text or not text.strip():
            return SecurityScanResult(
                is_safe=True,
                threat_level=ThreatLevel.NONE,
                threats_detected=[],
                sanitized_text=text,
                original_length=len(text) if text else 0,
                blocked=False,
            )

        threats = []
        threat_scores = {
            ThreatLevel.NONE: 0,
            ThreatLevel.LOW: 1,
            ThreatLevel.MEDIUM: 2,
            ThreatLevel.HIGH: 3,
            ThreatLevel.CRITICAL: 4,
        }

        max_threat = ThreatLevel.NONE

        # Check direct injection (HIGH threat)
        for pattern, threat_type in self._direct:
            if pattern.search(text):
                threats.append(f"DIRECT:{threat_type}")
                if threat_type in ("jailbreak", "system_override"):
                    max_threat = ThreatLevel.CRITICAL
                else:
                    max_threat = max(max_threat, ThreatLevel.HIGH, key=lambda x: threat_scores[x])

        # Check indirect injection (MEDIUM-HIGH threat)
        for pattern, threat_type in self._indirect:
            if pattern.search(text):
                threats.append(f"INDIRECT:{threat_type}")
                if threat_type in ("trade_manipulation", "exfiltration"):
                    max_threat = max(
                        max_threat, ThreatLevel.CRITICAL, key=lambda x: threat_scores[x]
                    )
                else:
                    max_threat = max(max_threat, ThreatLevel.MEDIUM, key=lambda x: threat_scores[x])

        # Check obfuscation (MEDIUM threat - suspicious)
        for pattern, threat_type in self._obfuscation:
            if pattern.search(text):
                threats.append(f"OBFUSCATION:{threat_type}")
                max_threat = max(max_threat, ThreatLevel.MEDIUM, key=lambda x: threat_scores[x])

        # Check delimiter abuse (LOW threat - possibly benign)
        for pattern, threat_type in self._delimiters:
            if pattern.search(text):
                threats.append(f"DELIMITER:{threat_type}")
                max_threat = max(max_threat, ThreatLevel.LOW, key=lambda x: threat_scores[x])

        # Determine if we should block
        if self.strict_mode:
            blocked = max_threat in (ThreatLevel.MEDIUM, ThreatLevel.HIGH, ThreatLevel.CRITICAL)
        else:
            blocked = max_threat in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)

        # Log security events
        if threats:
            logger.warning(
                "🛡️ SECURITY: Detected %d threats (level=%s): %s",
                len(threats),
                max_threat.value,
                ", ".join(threats[:5]),  # Limit log size
            )

        return SecurityScanResult(
            is_safe=max_threat == ThreatLevel.NONE,
            threat_level=max_threat,
            threats_detected=threats,
            sanitized_text=None if blocked else text,
            original_length=len(text),
            blocked=blocked,
        )

    def sanitize(self, text: str) -> str:
        """
        Attempt to sanitize text by removing dangerous patterns.

        WARNING: Sanitization is NOT a substitute for blocking.
        Use this only for low-risk content that must be processed.

        Args:
            text: Input text to sanitize

        Returns:
            Sanitized text with dangerous patterns removed
        """
        if not text:
            return ""

        sanitized = text

        # Remove format injection markers
        sanitized = re.sub(
            r"\[/?system\]|\[/?assistant\]|\[/?user\]", "", sanitized, flags=re.IGNORECASE
        )
        sanitized = re.sub(r"<\|?/?(system|assistant|user)\|?>", "", sanitized, flags=re.IGNORECASE)

        # Remove excessive delimiters
        sanitized = re.sub(r"-{5,}", "---", sanitized)
        sanitized = re.sub(r"={5,}", "===", sanitized)
        sanitized = re.sub(r"\*{5,}", "***", sanitized)

        # Remove HTML-like tags
        sanitized = re.sub(r"<[^>]{1,50}>", "", sanitized)

        return sanitized.strip()


# Global defense instance
_defense = PromptInjectionDefense(strict_mode=True)


def scan_for_injection(text: str) -> SecurityScanResult:
    """
    Scan text for prompt injection attempts.

    This is the main entry point for security scanning.

    Args:
        text: Input text to scan

    Returns:
        SecurityScanResult with threat assessment

    Example:
        result = scan_for_injection(user_input)
        if result.blocked:
            raise SecurityError(f"Blocked: {result.threats_detected}")
    """
    return _defense.scan(text)


def validate_llm_input(text: str, source: str = "unknown") -> str:
    """
    Validate and potentially block LLM input.

    Args:
        text: Input text to validate
        source: Source of the input (for logging)

    Returns:
        The original text if safe

    Raises:
        SecurityError: If prompt injection detected
    """
    result = scan_for_injection(text)

    if result.blocked:
        logger.error(
            "🚨 BLOCKED INPUT from %s: %s (threats: %s)",
            source,
            text[:100] + "..." if len(text) > 100 else text,
            result.threats_detected,
        )
        raise SecurityError(f"Prompt injection detected from {source}: {result.threats_detected}")

    return text


class SecurityError(Exception):
    """Raised when a security violation is detected."""

    pass


# =============================================================================
# LLM OUTPUT VALIDATION FOR TRADE SIGNALS
# =============================================================================


@dataclass
class TradeSignalValidation:
    """Result of trade signal validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    sanitized_signal: dict[str, Any] | None


class LLMOutputValidator:
    """
    Validates LLM-generated trade signals to prevent hallucinations
    and malicious outputs from affecting trading decisions.

    Checks:
    1. Symbol validity (whitelist)
    2. Quantity/price ranges
    3. Action validity
    4. Confidence bounds
    5. Reasoning sanity
    """

    # Valid US equity symbols (expandable)
    # Core watchlist - add more as needed
    ALLOWED_SYMBOLS = {
        # Major indices ETFs
        "SPY",
        "QQQ",
        "IWM",
        "DIA",
        "VTI",
        "VOO",
        # Sector ETFs
        "XLK",
        "XLF",
        "XLE",
        "XLV",
        "XLI",
        "XLP",
        "XLU",
        "XLB",
        "XLY",
        "XLRE",
        # Bond ETFs
        "TLT",
        "IEF",
        "SHY",
        "BND",
        "AGG",
        "LQD",
        "HYG",
        "TIP",
        # Treasury ETFs
        "SHV",
        "SGOV",
        "BIL",
        "SCHO",
        "SCHR",
        # Volatility
        "VXX",
        "UVXY",
        "SVXY",
        # Major tech
        "AAPL",
        "MSFT",
        "GOOGL",
        "GOOG",
        "AMZN",
        "META",
        "NVDA",
        "TSLA",
        "AMD",
        "INTC",
        "CRM",
        "ORCL",
        "ADBE",
        "NFLX",
        # Financials
        "JPM",
        "BAC",
        "WFC",
        "GS",
        "MS",
        "C",
        "V",
        "MA",
        "AXP",
        # Healthcare
        "JNJ",
        "UNH",
        "PFE",
        "MRK",
        "ABBV",
        "LLY",
        "TMO",
        # Consumer
        "WMT",
        "COST",
        "HD",
        "MCD",
        "NKE",
        "SBUX",
        "TGT",
        # Energy
        "XOM",
        "CVX",
        "COP",
        "SLB",
        "EOG",
        # Industrial
        "CAT",
        "DE",
        "BA",
        "UPS",
        "FDX",
        "HON",
        "GE",
        # Other major
        "BRK.B",
        "BRKB",
        "DIS",
        "CMCSA",
        "VZ",
        "T",
        "PEP",
        "KO",
    }

    # CRITICAL: No crypto allowed (Lesson Learned #052)
    BLOCKED_SYMBOLS = {
        "BTC",
        "ETH",
        "DOGE",
        "SOL",
        "XRP",
        "ADA",
        "DOT",
        "AVAX",
        "MATIC",
        "LINK",
        "UNI",
        "ATOM",
        "LTC",
        "BCH",
        "SHIB",
        "BTCUSD",
        "ETHUSD",
        "BTCUSDT",
        "ETHUSDT",
        # Crypto ETFs (not allowed per policy)
        "GBTC",
        "ETHE",
        "BITO",
    }

    VALID_ACTIONS = {"BUY", "SELL", "HOLD", "CLOSE", "SKIP"}
    VALID_SIDES = {"buy", "sell", "long", "short"}

    # Reasonable bounds
    MAX_QUANTITY = 10000  # Max shares per trade
    MAX_NOTIONAL = 50000  # Max $ per trade
    MIN_NOTIONAL = 10  # Min $ per trade
    MAX_PRICE = 100000  # Sanity check
    MIN_PRICE = 0.01  # Penny stock floor

    def __init__(self, custom_symbols: set[str] | None = None):
        """
        Initialize validator.

        Args:
            custom_symbols: Additional symbols to allow
        """
        self.allowed_symbols = self.ALLOWED_SYMBOLS.copy()
        if custom_symbols:
            self.allowed_symbols.update(custom_symbols)

    def validate_signal(self, signal: dict[str, Any]) -> TradeSignalValidation:
        """
        Validate an LLM-generated trade signal.

        Args:
            signal: Dict with keys like symbol, action, quantity, price, confidence

        Returns:
            TradeSignalValidation with validity status and any issues
        """
        errors = []
        warnings = []

        # 1. Validate symbol
        symbol = signal.get("symbol", "").upper().strip()
        if not symbol:
            errors.append("Missing symbol")
        elif symbol in self.BLOCKED_SYMBOLS:
            errors.append(f"BLOCKED: {symbol} is cryptocurrency (not allowed)")
        elif symbol not in self.allowed_symbols:
            warnings.append(f"Unknown symbol: {symbol} (not in whitelist)")

        # 2. Validate action/side
        action = signal.get("action", "").upper()
        side = signal.get("side", "").lower()

        if action and action not in self.VALID_ACTIONS:
            errors.append(f"Invalid action: {action}")
        if side and side not in self.VALID_SIDES:
            errors.append(f"Invalid side: {side}")

        # 3. Validate quantity
        quantity = signal.get("quantity")
        if quantity is not None:
            try:
                qty = float(quantity)
                if qty <= 0:
                    errors.append(f"Invalid quantity: {qty} (must be positive)")
                elif qty > self.MAX_QUANTITY:
                    errors.append(f"Quantity too large: {qty} > {self.MAX_QUANTITY}")
                elif qty != int(qty) and qty < 1:
                    warnings.append(f"Fractional quantity: {qty}")
            except (TypeError, ValueError):
                errors.append(f"Invalid quantity type: {quantity}")

        # 4. Validate notional
        notional = signal.get("notional")
        if notional is not None:
            try:
                not_val = float(notional)
                if not_val < self.MIN_NOTIONAL:
                    errors.append(f"Notional too small: ${not_val} < ${self.MIN_NOTIONAL}")
                elif not_val > self.MAX_NOTIONAL:
                    errors.append(f"Notional too large: ${not_val} > ${self.MAX_NOTIONAL}")
            except (TypeError, ValueError):
                errors.append(f"Invalid notional type: {notional}")

        # 5. Validate price
        price = signal.get("price") or signal.get("limit_price")
        if price is not None:
            try:
                price_val = float(price)
                if price_val < self.MIN_PRICE:
                    errors.append(f"Price too low: ${price_val}")
                elif price_val > self.MAX_PRICE:
                    errors.append(f"Price suspiciously high: ${price_val}")
            except (TypeError, ValueError):
                errors.append(f"Invalid price type: {price}")

        # 6. Validate confidence
        confidence = signal.get("confidence")
        if confidence is not None:
            try:
                conf = float(confidence)
                if conf < 0 or conf > 1:
                    errors.append(f"Confidence out of range: {conf} (must be 0-1)")
                elif conf > 0.99:
                    warnings.append(f"Suspiciously high confidence: {conf}")
            except (TypeError, ValueError):
                errors.append(f"Invalid confidence type: {confidence}")

        # 7. Check for NaN/None/undefined issues
        for key, value in signal.items():
            if value is None and key in ("symbol", "action", "side"):
                errors.append(f"Required field is None: {key}")
            elif isinstance(value, float) and (value != value):  # NaN check
                errors.append(f"NaN detected in field: {key}")
            elif isinstance(value, str) and value.lower() in ("nan", "undefined", "null"):
                errors.append(f"Invalid string value in {key}: {value}")

        is_valid = len(errors) == 0

        # Create sanitized signal if valid
        sanitized = None
        if is_valid:
            sanitized = {
                "symbol": symbol,
                "action": action or signal.get("action"),
                "side": side or signal.get("side"),
                "quantity": signal.get("quantity"),
                "notional": signal.get("notional"),
                "price": signal.get("price"),
                "confidence": signal.get("confidence"),
            }

        if errors:
            logger.warning("❌ Trade signal validation failed: %s", errors)
        if warnings:
            logger.info("⚠️ Trade signal warnings: %s", warnings)

        return TradeSignalValidation(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            sanitized_signal=sanitized,
        )


# Global validator instance
_validator = LLMOutputValidator()


def validate_trade_signal(signal: dict[str, Any]) -> TradeSignalValidation:
    """
    Validate an LLM-generated trade signal.

    Args:
        signal: Trade signal dict from LLM

    Returns:
        TradeSignalValidation with status and issues

    Example:
        result = validate_trade_signal({"symbol": "SPY", "action": "BUY"})
        if not result.is_valid:
            raise ValueError(f"Invalid signal: {result.errors}")
    """
    return _validator.validate_signal(signal)


def is_valid_symbol(symbol: str) -> bool:
    """Quick check if a symbol is in the allowed list."""
    return symbol.upper() in _validator.allowed_symbols


def is_blocked_symbol(symbol: str) -> bool:
    """Check if a symbol is explicitly blocked (crypto)."""
    return symbol.upper() in LLMOutputValidator.BLOCKED_SYMBOLS


# =============================================================================
# ORIGINAL MASKING FUNCTIONS (preserved)
# =============================================================================


def mask_api_key(api_key: str | None, visible_chars: int = 4) -> str:
    """
    Mask an API key, showing only the first few characters.

    Args:
        api_key: The API key to mask (can be None)
        visible_chars: Number of characters to show (default: 4)

    Returns:
        Masked API key string (e.g., "ABCD***" or "***" if None)

    Example:
        >>> mask_api_key("sk-1234567890abcdef")
        "sk-1***"
        >>> mask_api_key(None)
        "***"
    """
    if not api_key:
        return "***"

    if len(api_key) <= visible_chars:
        return "***"

    return f"{api_key[:visible_chars]}***"


def mask_secret(secret: str | None, visible_chars: int = 4) -> str:
    """
    Mask a secret key, showing only the first few characters.

    Args:
        secret: The secret to mask (can be None)
        visible_chars: Number of characters to show (default: 4)

    Returns:
        Masked secret string (e.g., "ABCD***" or "***" if None)
    """
    return mask_api_key(secret, visible_chars)


def sanitize_log_message(message: str) -> str:
    """
    Sanitize a log message by masking any potential API keys or secrets.

    This function attempts to detect and mask common patterns of API keys
    and secrets in log messages.

    Args:
        message: The log message to sanitize

    Returns:
        Sanitized message with sensitive data masked
    """
    # Common API key patterns
    patterns = [
        (
            r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{10,})(["\']?)',
            r"\1***\3",
        ),
        (r'(secret["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{10,})(["\']?)', r"\1***\3"),
        (r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']+)(["\']?)', r"\1***\3"),
        (r'(token["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{20,})(["\']?)', r"\1***\3"),
    ]

    sanitized = message
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def is_sensitive_key(key_name: str) -> bool:
    """
    Check if a key name indicates sensitive information.

    Args:
        key_name: The name of the key/variable to check

    Returns:
        True if the key name suggests sensitive data
    """
    sensitive_patterns = [
        "api_key",
        "apikey",
        "api-key",
        "secret",
        "secret_key",
        "secret-key",
        "password",
        "passwd",
        "pwd",
        "token",
        "access_token",
        "refresh_token",
        "auth",
        "authorization",
        "credential",
        "cred",
    ]

    key_lower = key_name.lower()
    return any(pattern in key_lower for pattern in sensitive_patterns)
