"""
Pattern Detection Utilities
Identifies game-specific patterns that should not be translated
"""

import re
from typing import List, Tuple


class PatternDetector:
    def __init__(self):
        # Game-specific patterns that should NEVER be translated
        self.exclusion_patterns = [
            # Game string references (e.g., &$379;, &$2306;, &$%region_name%;)
            r'&\$\d+;',
            r'&\$%[^;]+;',  # Variable placeholders like &$%region_name%;

            # Template variables (e.g., %fav_list%, %player_name%)
            r'%[a-zA-Z_][a-zA-Z0-9_]*%',

            # Action commands (e.g., bypass _bbsgetfav, link itemName)
            r'bypass\s+[a-zA-Z_][a-zA-Z0-9_]*',
            r'link\s+[a-zA-Z_][a-zA-Z0-9_]*',

            # HTML entities that aren't text (e.g., &nbsp;, &gt;)
            r'&[a-z]+;',

            # Variable placeholders with various formats
            r'\$\{[^}]+\}',  # ${variable}
            r'\$[a-zA-Z_][a-zA-Z0-9_]*',  # $variable

            # Server commands/scripts
            r'npc_[a-zA-Z0-9_]+',
            r'quest_[a-zA-Z0-9_]+',
        ]

        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.exclusion_patterns
        ]

    def should_skip_translation(self, text: str) -> bool:
        """
        Check if text should be skipped (not translated)
        Returns True if text contains only game patterns
        """
        if not text or not text.strip():
            return True

        # If text is ONLY a pattern (like "&$379;"), skip it
        text_stripped = text.strip()
        for pattern in self.compiled_patterns:
            if pattern.fullmatch(text_stripped):
                return True

        # If text is very short and contains symbols, likely a pattern
        if len(text_stripped) <= 3 and not text_stripped[0].isalpha():
            return True

        return False

    def has_game_patterns(self, text: str) -> bool:
        """
        Check if text contains any game patterns
        Returns True if patterns are found
        """
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True
        return False

    def extract_text_parts(self, text: str) -> List[Tuple[str, bool]]:
        """
        Split text into translatable and non-translatable parts
        Returns: List of (text_part, should_translate) tuples

        Example:
        "Bookmark list &$379;" -> [("Bookmark list ", True), ("&$379;", False)]
        """
        parts = []
        last_end = 0

        # Find all pattern matches
        matches = []
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), match.group()))

        # Sort by start position
        matches.sort(key=lambda x: x[0])

        # Extract parts
        for start, end, matched_text in matches:
            # Add text before pattern (translatable)
            if start > last_end:
                before_text = text[last_end:start]
                if before_text.strip():
                    parts.append((before_text, True))

            # Add pattern itself (non-translatable)
            parts.append((matched_text, False))
            last_end = end

        # Add remaining text
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining.strip():
                parts.append((remaining, True))

        return parts

    def clean_for_translation(self, text: str) -> str:
        """
        Remove game patterns to get clean text for translation
        Example: "Bookmark list &$379;" -> "Bookmark list"
        """
        cleaned = text
        for pattern in self.compiled_patterns:
            cleaned = pattern.sub('', cleaned)

        return cleaned.strip()

    def get_stats(self) -> dict:
        """Get statistics about pattern detection"""
        return {
            'total_patterns': len(self.exclusion_patterns),
            'patterns': self.exclusion_patterns
        }
