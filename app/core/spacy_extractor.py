"""
spaCy-based Term Extractor for Smart Glossary Matching
Extracts named entities and nouns from text for targeted glossary lookup
"""

import spacy
from typing import Set, Optional


class SpacyExtractor:
    """
    Extract glossary candidates from text using spaCy NLP.

    Instead of checking all 41,592 glossary terms against every text chunk,
    we extract only the nouns/entities from the text and look those up.
    This reduces O(n*m) to O(n*k) where k << m.
    """

    _instance: Optional['SpacyExtractor'] = None
    _nlp = None

    def __new__(cls, model_name: str = "en_core_web_sm"):
        """Singleton pattern - only load spaCy model once"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "en_core_web_sm"):
        """Initialize spaCy with specified model"""
        if self._initialized:
            return

        try:
            print(f'[spaCy] Loading model: {model_name}')
            self._nlp = spacy.load(model_name)

            # Disable unnecessary components for speed
            # Keep parser for noun_chunks, disable lemmatizer
            disable_pipes = []
            for pipe in ['lemmatizer', 'attribute_ruler']:
                if pipe in self._nlp.pipe_names:
                    disable_pipes.append(pipe)

            if disable_pipes:
                self._nlp.disable_pipes(*disable_pipes)
                print(f'[spaCy] Disabled pipes for speed: {disable_pipes}')

            print(f'[spaCy] Model loaded successfully. Active pipes: {self._nlp.pipe_names}')
            self._initialized = True

        except OSError as e:
            print(f'[spaCy] Failed to load model "{model_name}": {e}')
            print(f'[spaCy] Please install with: python -m spacy download {model_name}')
            self._nlp = None
            self._initialized = True  # Mark as initialized to avoid retry

    @property
    def is_available(self) -> bool:
        """Check if spaCy is available and model is loaded"""
        return self._nlp is not None

    def extract_glossary_candidates(self, text: str) -> Set[str]:
        """
        Extract terms that should be checked against glossary.

        Extracts:
        1. Named Entities (PERSON, GPE, LOC, ORG, PRODUCT, EVENT)
        2. Proper Nouns (PROPN) - catches names not recognized as entities
        3. Noun phrases - for multi-word terms like "Proof of Blood"
        4. Individual nouns (NOUN) - catches item names

        Returns:
            Set of candidate terms (original case preserved)
        """
        if not self._nlp:
            return set()

        doc = self._nlp(text)
        candidates = set()

        # Relevant entity types for game glossaries
        relevant_ent_types = {
            "PERSON",   # Character names
            "GPE",      # Geopolitical entities (cities, countries)
            "LOC",      # Locations (mountains, caves, etc.)
            "ORG",      # Organizations (guilds, factions)
            "PRODUCT",  # Items, weapons
            "EVENT",    # Quest names, events
            "FAC",      # Facilities, buildings
            "WORK_OF_ART",  # Titles
        }

        # 1. Named Entities
        for ent in doc.ents:
            if ent.label_ in relevant_ent_types:
                candidates.add(ent.text)
                # Also add individual words for multi-word entities
                for word in ent.text.split():
                    if len(word) > 2:  # Skip very short words
                        candidates.add(word)

        # 2. Proper Nouns (PROPN) - catches names not recognized as entities
        for token in doc:
            if token.pos_ == "PROPN" and len(token.text) > 1:
                candidates.add(token.text)

        # 3. Noun phrases (for multi-word terms)
        for chunk in doc.noun_chunks:
            candidates.add(chunk.text)
            # Also add the root noun
            if chunk.root.pos_ in ("NOUN", "PROPN"):
                candidates.add(chunk.root.text)

        # 4. Individual nouns (NOUN)
        for token in doc:
            if token.pos_ == "NOUN" and len(token.text) > 2:
                candidates.add(token.text)

        # 5. Also include capitalized words (often proper nouns/names)
        words = text.split()
        for word in words:
            # Remove trailing punctuation
            clean_word = word.rstrip('.,;:!?')
            if clean_word and clean_word[0].isupper() and len(clean_word) > 2:
                candidates.add(clean_word)

        # 6. Include all alphabetic words >= 4 chars (catches game terms like "adena")
        # Game glossaries often have lowercase terms that spaCy doesn't recognize
        for word in words:
            clean_word = word.strip('.,;:!?()-')
            if clean_word.isalpha() and len(clean_word) >= 4:
                candidates.add(clean_word)

        return candidates

    def extract_with_context(self, text: str) -> dict:
        """
        Extract candidates with additional context information.
        Useful for debugging and understanding what spaCy detected.

        Returns:
            Dictionary with entities, proper_nouns, nouns, noun_chunks
        """
        if not self._nlp:
            return {'entities': [], 'proper_nouns': [], 'nouns': [], 'noun_chunks': []}

        doc = self._nlp(text)

        return {
            'entities': [(ent.text, ent.label_) for ent in doc.ents],
            'proper_nouns': [token.text for token in doc if token.pos_ == "PROPN"],
            'nouns': [token.text for token in doc if token.pos_ == "NOUN"],
            'noun_chunks': [chunk.text for chunk in doc.noun_chunks],
        }


# Module-level convenience function
_extractor: Optional[SpacyExtractor] = None

def get_extractor(model_name: str = "en_core_web_sm") -> SpacyExtractor:
    """Get or create the singleton SpacyExtractor instance"""
    global _extractor
    if _extractor is None:
        _extractor = SpacyExtractor(model_name)
    return _extractor


def extract_candidates(text: str) -> Set[str]:
    """Convenience function to extract glossary candidates"""
    return get_extractor().extract_glossary_candidates(text)
