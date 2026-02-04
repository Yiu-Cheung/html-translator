"""
Glossary/Terminology Management
Handles user-provided manual translations for special terms
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


class GlossaryManager:
    def __init__(self, glossary_path: str = 'data/lineage2/glossary.json', use_spacy: bool = True):
        self.glossary_path = Path(glossary_path)
        self.terms = {}
        self.terms_lower = {}  # Lowercase index: {term.lower(): (original_term, translation)}
        self.spacy_extractor = None
        self._use_spacy = use_spacy
        self.load_glossary()
        self._init_spacy()

    def load_glossary(self):
        """Load glossary from JSON file"""
        # Check if path is valid and is a file
        if self.glossary_path and str(self.glossary_path).strip() and self.glossary_path.exists() and self.glossary_path.is_file():
            try:
                with open(self.glossary_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Support both old format (with "terms" wrapper) and new format (direct mapping)
                    if isinstance(data, dict):
                        if 'terms' in data:
                            # Old format: {"terms": {"term": {"zh": "..."}}}
                            # Convert to new format
                            old_terms = data['terms']
                            self.terms = {}
                            for term, translations in old_terms.items():
                                if isinstance(translations, dict):
                                    # Get zh, zh-TW, or first available translation
                                    translation = translations.get('zh') or translations.get('zh-TW') or list(translations.values())[0]
                                    self.terms[term] = translation
                                else:
                                    self.terms[term] = translations
                        else:
                            # New format: {"term": "translation"}
                            self.terms = data
                # Build lowercase index for fast lookup
                self._build_lowercase_index()
                print(f'[Glossary] Loaded {len(self.terms)} terms from {self.glossary_path}')
            except Exception as e:
                print(f'[Glossary] Failed to load glossary: {e}')
                self.terms = {}
                self.terms_lower = {}
        else:
            # Empty path or file doesn't exist - start with empty glossary
            self.terms = {}
            self.terms_lower = {}

    def _build_lowercase_index(self):
        """Build lowercase index for O(1) lookup"""
        self.terms_lower = {
            term.lower(): (term, translation)
            for term, translation in self.terms.items()
        }

    def _init_spacy(self):
        """Initialize spaCy extractor if available"""
        if not self._use_spacy:
            print('[Glossary] spaCy disabled by configuration')
            return

        try:
            from .spacy_extractor import SpacyExtractor
            self.spacy_extractor = SpacyExtractor()
            if self.spacy_extractor.is_available:
                print('[Glossary] spaCy smart matching enabled')
            else:
                self.spacy_extractor = None
                print('[Glossary] spaCy not available, using brute-force matching')
        except ImportError:
            print('[Glossary] spaCy module not found, using brute-force matching')

    def save_glossary(self):
        """Save glossary to JSON file"""
        try:
            with open(self.glossary_path, 'w', encoding='utf-8') as f:
                # Save in new simplified format: {"term": "translation"}
                json.dump(self.terms, f, ensure_ascii=False, indent=2)
            print(f'[Glossary] Saved {len(self.terms)} terms to {self.glossary_path}')
        except Exception as e:
            print(f'[Glossary] Failed to save glossary: {e}')

    def add_term(self, term: str, translation: str):
        """Add a term with its translation"""
        self.terms[term] = translation
        self.terms_lower[term.lower()] = (term, translation)
        self.save_glossary()

    def find_matches(self, text: str, target_lang: str = None) -> List[Tuple[str, str]]:
        """
        Find glossary terms in text and return matching translations (brute-force)
        Returns: List of (source_term, target_translation) tuples
        Note: target_lang parameter is kept for compatibility but not used in new format
        """
        import re
        matches = []

        for term, translation in self.terms.items():
            # Use word boundary matching to avoid partial matches (e.g., "Er" inside "Ever")
            if term.isalpha():
                # Alphabetic terms: use word boundaries
                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            else:
                # Non-alphabetic terms (numbers, special chars): exact match
                pattern = re.compile(re.escape(term), re.IGNORECASE)

            if pattern.search(text):
                matches.append((term, translation))

        return matches

    def find_matches_smart(self, text: str, target_lang: str = None) -> List[Tuple[str, str]]:
        """
        Smart glossary matching using spaCy extraction.

        Instead of iterating through all 41,592 glossary terms,
        we extract nouns/entities from the text and only look those up.

        Performance: O(n*k) instead of O(n*m) where k << m
        - k = ~10-20 extracted candidates per text
        - m = 41,592 glossary terms

        Falls back to brute-force if spaCy is not available.

        Returns: List of (source_term, translation) tuples
        """
        if not self.spacy_extractor or not self.spacy_extractor.is_available:
            return self.find_matches(text, target_lang)

        matches = []
        seen = set()  # Avoid duplicates

        # Extract candidate terms using spaCy
        candidates = self.spacy_extractor.extract_glossary_candidates(text)

        # Look up each candidate in the lowercase index
        for candidate in candidates:
            key = candidate.lower()
            if key in self.terms_lower and key not in seen:
                original_term, translation = self.terms_lower[key]
                matches.append((original_term, translation))
                seen.add(key)

        # Also check for multi-word glossary terms that might span candidates
        # This handles cases like "Proof of Blood" where individual words might not match
        text_lower = text.lower()
        for candidate in candidates:
            # Check if this candidate is part of a longer glossary term
            for term_lower, (original_term, translation) in self.terms_lower.items():
                if (candidate.lower() in term_lower and
                    term_lower in text_lower and
                    term_lower not in seen):
                    matches.append((original_term, translation))
                    seen.add(term_lower)

        return matches

    def build_glossary_hint(self, text: str, target_lang: str) -> str:
        """
        Build glossary hint for AI prompt
        Returns: String to include in prompt, or empty if no matches
        """
        matches = self.find_matches(text, target_lang)

        if not matches:
            return ""

        hint = "\n\nIMPORTANT - Use these exact translations for the following terms:\n"
        for source, target in matches:
            hint += f'- "{source}" = "{target}"\n'

        return hint

    def get_stats(self) -> Dict[str, Any]:
        """Get glossary statistics"""
        return {
            'totalTerms': len(self.terms),
            'terms': list(self.terms.keys())
        }
