"""
Translation Engine
Wraps the translation logic for use with the desktop UI
"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
import re

# Import from app/core modules
from .glossary_utils import GlossaryManager
from .pattern_utils import PatternDetector
from .ollama_provider import OllamaProvider


@dataclass
class TranslationStats:
    """Statistics for a translation operation"""
    total_chunks: int = 0
    cached_chunks: int = 0
    new_chunks: int = 0
    skipped_patterns: int = 0
    glossary_hints: int = 0
    processing_time: float = 0.0
    errors: int = 0


@dataclass
class TranslationResult:
    """Result of translating a single file"""
    input_path: str
    output_path: str
    success: bool
    stats: TranslationStats
    error_message: str = ''
    original_html: str = ''
    translated_html: str = ''


class TranslationEngine:
    """
    Main translation engine for the desktop app.
    Wraps POC modules with progress callbacks for UI integration.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the translation engine.

        Args:
            config: Dictionary with:
                - cache_path: Path to translation cache directory
                - glossary_path: Path to glossary.json
                - ollama_host: Ollama server host
                - ollama_port: Ollama server port
                - ollama_model: Model name to use
        """
        self.config = config

        # Initialize components
        self.glossary = GlossaryManager(config.get('glossary_path', 'glossary.json'))
        self.pattern_detector = PatternDetector()
        self.provider = OllamaProvider({
            'host': config.get('ollama_host', 'localhost'),
            'port': config.get('ollama_port', 11434),
            'model': config.get('ollama_model', 'gemma3:4b'),
            'timeout': config.get('timeout', 60)
        })

        self.source_lang = config.get('source_lang', 'en')
        self.project_name = config.get('project_name', 'Project')
        self._stop_requested = False
        self._case_sensitive_glossary = config.get('case_sensitive_glossary', True)

        # Translation mode: 'glossary_reference' (default), 'glossary_placeholder', or 'full_context'
        self._translation_mode = config.get('translation_mode', 'glossary_reference')
        # Backward compatibility
        if config.get('direct_translate_mode', False) and self._translation_mode == 'glossary_placeholder':
            self._translation_mode = 'full_context'

        # Progress callbacks
        self._on_chunk_translated: Optional[Callable] = None
        self._on_file_progress: Optional[Callable] = None

    def set_callbacks(self,
                      on_chunk_translated: Optional[Callable] = None,
                      on_file_progress: Optional[Callable] = None):
        """Set progress callbacks for UI integration"""
        self._on_chunk_translated = on_chunk_translated
        self._on_file_progress = on_file_progress

    def check_connection(self) -> bool:
        """Check if Ollama is connected and model is available"""
        return self.provider.check_connection()

    def stop(self):
        """Request translation to stop"""
        self._stop_requested = True

    def reset_stop(self):
        """Reset stop flag"""
        self._stop_requested = False

    def set_case_sensitive_glossary(self, case_sensitive: bool):
        """Set case sensitivity for glossary matching"""
        self._case_sensitive_glossary = case_sensitive

    def set_translation_mode(self, mode: str):
        """Set translation mode: 'glossary_reference', 'glossary_placeholder', or 'full_context'"""
        if mode not in ['glossary_reference', 'glossary_placeholder', 'full_context']:
            raise ValueError(f"Invalid translation mode: {mode}. Must be 'glossary_reference', 'glossary_placeholder', or 'full_context'")
        self._translation_mode = mode

    def set_direct_translate_mode(self, direct_mode: bool):
        """Set direct translation mode (backward compatibility)"""
        self._translation_mode = 'full_context' if direct_mode else 'glossary_placeholder'

    def translate_file(self, input_path: str, target_lang: str,
                       output_path: Optional[str] = None) -> TranslationResult:
        """
        Translate a single HTML file.

        Args:
            input_path: Path to input HTML file
            target_lang: Target language code
            output_path: Path to output file (optional)

        Returns:
            TranslationResult with stats and translated content
        """
        import time
        start_time = time.time()

        stats = TranslationStats()
        result = TranslationResult(
            input_path=input_path,
            output_path=output_path or '',
            success=False,
            stats=stats
        )

        try:
            # Read input file
            with open(input_path, 'r', encoding='utf-8') as f:
                original_html = f.read()
            result.original_html = original_html

            # Choose translation method based on mode
            mode_display = {'glossary_reference': 'Glossary Reference', 'glossary_placeholder': 'Glossary Placeholder', 'full_context': 'Full Context Reference'}
            print(f'[Translator] Using mode: {mode_display.get(self._translation_mode, self._translation_mode)}')
            if self._translation_mode == 'full_context':
                # Full Context Reference: send entire HTML to AI with glossary in prompt
                translated_html = self._translate_html_direct(original_html, target_lang, stats)
            elif self._translation_mode == 'glossary_reference':
                # Glossary Reference: provide glossary reference before each translation
                translated_html = self._translate_html_preserve_structure(original_html, target_lang, stats)
            else:
                # Glossary Placeholder: replace glossary terms with placeholders
                translated_html = self._translate_html_preserve_structure(original_html, target_lang, stats)

            result.translated_html = translated_html

            # Write output if path specified
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(translated_html)

            result.success = True

        except Exception as e:
            result.error_message = str(e)
            stats.errors += 1

        stats.processing_time = time.time() - start_time
        return result

    def translate_text(self, text: str, target_lang: str) -> str:
        """Translate a single text chunk (for preview)"""
        stats = TranslationStats()
        return self._translate_text(text, target_lang, stats)

    def _translate_text(self, text: str, target_lang: str, stats: TranslationStats, skip_cache: bool = False) -> str:
        """Internal translation with stats tracking"""
        if self._stop_requested:
            return text

        # Translate with AI
        try:
            # Debug logging for attribute values
            if len(text) < 50:
                print(f'[AI] Sending to AI: "{text}"')

            translated = self.provider.translate(
                text,
                self.source_lang,
                target_lang,
                ""  # No glossary hint - use placeholders instead
            )

            # Debug logging for attribute values
            if len(text) < 50:
                print(f'[AI] Received from AI: "{translated}"')

            stats.new_chunks += 1

            # Callback
            if self._on_chunk_translated:
                self._on_chunk_translated(text, translated)

            return translated

        except Exception as e:
            stats.errors += 1
            return text  # Return original on error

    def _translate_text_direct(self, text: str, target_lang: str, stats: TranslationStats, skip_cache: bool = False) -> str:
        """Direct translation with glossary included in prompt (no placeholders)"""
        if self._stop_requested:
            return text

        # Get relevant glossary terms for this text
        glossary_hint = self._build_glossary_hint(text, target_lang)

        # Translate with AI (glossary included in prompt)
        try:
            translated = self.provider.translate(
                text,
                self.source_lang,
                target_lang,
                glossary_hint  # Pass glossary directly
            )
            stats.new_chunks += 1

            # Callback
            if self._on_chunk_translated:
                self._on_chunk_translated(text, translated)

            return translated

        except Exception as e:
            stats.errors += 1
            return text  # Return original on error

    def _translate_text_context_window(self, text: str, target_lang: str, stats: TranslationStats, skip_cache: bool = False) -> str:
        """Context Window mode: Provide glossary reference before translation (POC-proven best method)"""
        if self._stop_requested:
            return text

        # Find glossary terms in this text
        matches = self.glossary.find_matches(text, target_lang) if self.glossary else []

        # Build context window
        context = ""
        if matches:
            context = "[Glossary Terms - Use these exact translations]\n"
            # Deduplicate by term (in case of case variations)
            seen_terms = set()
            for term, translation in matches:
                term_lower = term.lower()
                if term_lower not in seen_terms:
                    context += f"{term} = {translation}\n"
                    seen_terms.add(term_lower)
            context += f"\n[Translate the following text to {self._get_language_name(target_lang)}]\n"

        # Translate with AI
        try:
            # Pass context as part of the glossary hint
            translated = self.provider.translate(
                text,
                self.source_lang,
                target_lang,
                context  # Context window with glossary
            )
            stats.new_chunks += 1

            # Callback
            if self._on_chunk_translated:
                self._on_chunk_translated(text, translated)

            return translated

        except Exception as e:
            stats.errors += 1
            return text  # Return original on error

    def _get_language_name(self, lang_code: str) -> str:
        """Convert language code to full name for prompts"""
        lang_names = {
            'zh-TW': 'Traditional Chinese (Taiwan)',
            'zh-CN': 'Simplified Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'en': 'English',
        }
        return lang_names.get(lang_code, lang_code)

    def _build_glossary_hint(self, text: str, target_lang: str) -> str:
        """Build glossary hint string for direct translation mode"""
        if not self.glossary or not self.glossary.terms:
            return ""

        # Find relevant glossary terms that appear in the text
        # Use dict to ensure no duplicate English terms
        relevant_terms_dict = {}
        text_lower = text.lower()

        for term, translation in self.glossary.terms.items():
            # Skip if already added (deduplication based on English term)
            if term in relevant_terms_dict:
                continue

            if self._case_sensitive_glossary:
                if term in text:
                    relevant_terms_dict[term] = translation
            else:
                if term.lower() in text_lower:
                    relevant_terms_dict[term] = translation

        if not relevant_terms_dict:
            return ""

        # Build hint string
        relevant_terms = [f"{term} = {translation}" for term, translation in relevant_terms_dict.items()]
        return "Glossary:\n" + "\n".join(relevant_terms)

    def _translate_html_direct(self, html: str, target_lang: str, stats: TranslationStats) -> str:
        """Direct translation mode: send entire HTML to AI with glossary"""
        if self._stop_requested:
            return html

        # Build glossary hint - only include terms that appear in the HTML
        # Use dict to ensure no duplicate English terms
        glossary_hint = ""
        if self.glossary and self.glossary.terms:
            relevant_terms_dict = {}  # key: English term, value: translation
            html_lower = html.lower()

            for term, translation in self.glossary.terms.items():
                # Skip if already added (deduplication based on English term)
                if term in relevant_terms_dict:
                    continue

                if self._case_sensitive_glossary:
                    if term in html:
                        relevant_terms_dict[term] = translation
                else:
                    if term.lower() in html_lower:
                        relevant_terms_dict[term] = translation

            if relevant_terms_dict:
                relevant_terms = [f"{term} = {translation}" for term, translation in relevant_terms_dict.items()]
                glossary_hint = "Glossary:\n" + "\n".join(relevant_terms)
                print(f'[Translator] Direct mode: Found {len(relevant_terms)} unique relevant glossary terms out of {len(self.glossary.terms)} total')
                print(f'[Translator] Sample terms: {relevant_terms[:5]}')
            else:
                print(f'[Translator] Direct mode: No glossary terms found in HTML')

        # Translate entire HTML with AI
        try:
            translated = self.provider.translate_html_direct(
                html,
                self.source_lang,
                target_lang,
                glossary_hint,
                self.project_name
            )
            stats.new_chunks += 1
            stats.total_chunks += 1

            # Callback
            if self._on_chunk_translated:
                self._on_chunk_translated(html, translated)

            return translated

        except Exception as e:
            stats.errors += 1
            print(f"[Translator] Direct HTML translation error: {e}")
            return html  # Return original on error

    def _is_already_target_language(self, text: str, target_lang: str) -> bool:
        """Check if text is already in target language (to skip unnecessary translation)"""
        # For Chinese languages, check if text is mostly CJK characters
        if target_lang in ['zh', 'zh-TW', 'zh-CN']:
            # Count CJK characters
            cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
            cjk_chars = len(cjk_pattern.findall(text))
            total_chars = len([c for c in text if c.isalpha()])

            # If more than 50% is CJK, consider it already Chinese
            if total_chars > 0 and cjk_chars / total_chars > 0.5:
                return True

        # For Japanese
        elif target_lang == 'ja':
            # Check for Hiragana, Katakana, or Kanji
            jp_pattern = re.compile(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]')
            jp_chars = len(jp_pattern.findall(text))
            total_chars = len([c for c in text if c.isalpha()])

            if total_chars > 0 and jp_chars / total_chars > 0.5:
                return True

        # For Korean
        elif target_lang == 'ko':
            # Check for Hangul
            kr_pattern = re.compile(r'[\uac00-\ud7af]')
            kr_chars = len(kr_pattern.findall(text))
            total_chars = len([c for c in text if c.isalpha()])

            if total_chars > 0 and kr_chars / total_chars > 0.5:
                return True

        return False

    def _translate_html_preserve_structure(self, html: str, target_lang: str, stats: TranslationStats) -> str:
        """Translate HTML while preserving exact structure using regex"""
        if self._stop_requested:
            return html

        # Pattern to find text between > and < (text content)
        text_pattern = re.compile(r'(>)([^<]+)(<)')

        # Pattern to find translatable HTML attributes
        # Matches: value="text", title="text", alt="text", placeholder="text"
        attr_pattern = re.compile(r'\b(value|title|alt|placeholder)="([^"]+)"', re.IGNORECASE)

        # Collect all text segments with their positions
        segments = []
        for match in text_pattern.finditer(html):
            text = match.group(2)
            if text.strip():
                # Skip game patterns
                if self.pattern_detector.should_skip_translation(text.strip()):
                    stats.skipped_patterns += 1
                    continue
                # Skip if already in target language
                if self._is_already_target_language(text.strip(), target_lang):
                    stats.skipped_patterns += 1
                    continue
                segments.append({
                    'type': 'text',
                    'start': match.start(2),
                    'end': match.end(2),
                    'original': text,
                    'stripped': text.strip()
                })

        # Collect all attribute values with their positions
        for match in attr_pattern.finditer(html):
            attr_name = match.group(1)
            attr_value = match.group(2)
            if attr_value.strip():
                # Skip game patterns
                if self.pattern_detector.should_skip_translation(attr_value.strip()):
                    stats.skipped_patterns += 1
                    continue
                # Skip if already in target language
                if self._is_already_target_language(attr_value.strip(), target_lang):
                    stats.skipped_patterns += 1
                    continue
                segments.append({
                    'type': 'attribute',
                    'attr_name': attr_name,
                    'start': match.start(2),
                    'end': match.end(2),
                    'original': attr_value,
                    'stripped': attr_value.strip()
                })

        # Translate unique texts
        unique_texts = {}
        for seg in segments:
            stripped = seg['stripped']
            if stripped and stripped not in unique_texts:
                stats.total_chunks += 1

                # First, protect game patterns from translation
                text_protected, pattern_map = self._protect_game_patterns(stripped)

                if self._translation_mode == 'full_context':
                    # Full Context Reference: pass text directly, glossary in prompt
                    translated = self._translate_text_direct(text_protected, target_lang, stats, skip_cache=True)
                elif self._translation_mode == 'glossary_reference':
                    # Glossary Reference: provide glossary reference
                    translated = self._translate_text_context_window(text_protected, target_lang, stats, skip_cache=True)
                else:
                    # Glossary Placeholder: replace glossary terms with placeholders
                    text_with_placeholders, placeholder_map = self._apply_glossary_placeholders(text_protected, target_lang)

                    # Check if the text is already fully translated
                    if not placeholder_map and self._is_already_target_language(text_with_placeholders, target_lang):
                        # Already translated by glossary, skip AI
                        translated = text_with_placeholders
                        if len(stripped) < 50:
                            print(f'[Glossary] Text fully covered by glossary, skipping AI: "{translated}"')
                    else:
                        # Translate
                        translated = self._translate_text(text_with_placeholders, target_lang, stats, skip_cache=True)
                        # Post-replace placeholders with glossary translations
                        translated = self._restore_glossary_placeholders(translated, placeholder_map)

                # Finally, restore game patterns
                translated = self._restore_game_patterns(translated, pattern_map)

                if translated != stripped:
                    unique_texts[stripped] = translated

        # Replace in HTML from end to start (to preserve positions)
        result = html
        for seg in reversed(segments):
            stripped = seg['stripped']
            if stripped in unique_texts:
                original = seg['original']
                translated = unique_texts[stripped]
                # Preserve leading/trailing whitespace from original
                leading_ws = original[:len(original) - len(original.lstrip())]
                trailing_ws = original[len(original.rstrip()):]
                new_text = leading_ws + translated + trailing_ws
                result = result[:seg['start']] + new_text + result[seg['end']:]

        return result

    def _protect_game_patterns(self, text: str):
        """Replace game patterns with placeholders to protect them from translation.

        Returns: (text_with_placeholders, pattern_map)
        Example: "Click &$%region_name%;" -> "Click __PATTERN_0__", {"__PATTERN_0__": "&$%region_name%;"}
        """
        placeholder_map = {}
        result = text
        placeholder_count = 0

        # Find all game patterns using PatternDetector
        matches = []
        for pattern in self.pattern_detector.compiled_patterns:
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), match.group()))

        # Sort by start position (replace from end to start to preserve positions)
        matches.sort(key=lambda x: x[0], reverse=True)

        # Replace each pattern with a placeholder
        for start, end, matched_text in matches:
            placeholder = f"__PATTERN_{placeholder_count}__"
            result = result[:start] + placeholder + result[end:]
            placeholder_map[placeholder] = matched_text
            placeholder_count += 1

        return result, placeholder_map

    def _restore_game_patterns(self, text: str, pattern_map: dict) -> str:
        """Restore game patterns from placeholders"""
        result = text
        for placeholder, original_pattern in pattern_map.items():
            result = result.replace(placeholder, original_pattern)
        return result

    def _apply_glossary_placeholders(self, text: str, target_lang: str):
        """Replace glossary terms with placeholders before AI translation.

        Uses smart matching with spaCy if available (extracts nouns/entities first),
        otherwise falls back to brute-force matching through all glossary terms.
        """
        placeholder_map = {}
        result = text
        placeholder_count = 0

        # Use smart matching if available (spaCy extracts candidates first)
        # This is much faster: O(candidates) instead of O(all_glossary_terms)
        if hasattr(self.glossary, 'find_matches_smart'):
            matches = self.glossary.find_matches_smart(text, target_lang)
        else:
            # Fallback to brute-force matching
            matches = self.glossary.find_matches(text, target_lang)

        # Debug logging for attribute values (short text)
        if len(text) < 50 and matches:
            print(f'[Glossary] Text: "{text}" - Found {len(matches)} matches: {[(t, tr) for t, tr in matches[:3]]}')

        # Sort by length (longest first) to avoid partial replacements
        matches = sorted(matches, key=lambda x: len(x[0]), reverse=True)

        for term, translation in matches:
            # Always use case-insensitive search to FIND the term first
            # (glossary may have different case than text)
            # Use word boundaries for all alphabetic terms to prevent partial matches
            # e.g., "erest" should not match inside "interested"
            if term.isalpha():
                find_pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            else:
                find_pattern = re.compile(re.escape(term), re.IGNORECASE)

            match = find_pattern.search(result)
            if match:
                matched_text = match.group()

                # If case-sensitive mode, verify exact case match
                if self._case_sensitive_glossary:
                    # Check if the matched text has same case as glossary term
                    # or if text matches any case (for terms like adena/Adena)
                    if matched_text != term and matched_text.lower() != term.lower():
                        continue

                placeholder = f"__GLOSS_{placeholder_count}__"
                # Replace using case-insensitive pattern to handle case differences
                result = find_pattern.sub(placeholder, result, count=1)
                placeholder_map[placeholder] = translation

                # Debug logging for attribute values
                if len(text) < 50:
                    print(f'[Glossary] Replaced "{matched_text}" → {placeholder} (will restore to "{translation}")')

                placeholder_count += 1

        # For very short texts with placeholders, just return the translation directly
        # No need for AI to translate if glossary covers the whole text
        if placeholder_count > 0:
            # Check if text is almost entirely placeholders
            remaining_text = result
            for ph in placeholder_map.keys():
                remaining_text = remaining_text.replace(ph, '')
            remaining_alpha = sum(1 for c in remaining_text if c.isalpha())

            # If less than 3 letters remain, let AI translate what's left
            # but still use placeholders for glossary terms
            if remaining_alpha < 3 and len(text) < 20:
                # For very short texts, directly replace with glossary
                final_result = result
                for ph, trans in placeholder_map.items():
                    final_result = final_result.replace(ph, trans)
                # Remove spaces between CJK characters
                cjk_pattern = re.compile(r'([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]) +([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff])')
                while cjk_pattern.search(final_result):
                    final_result = cjk_pattern.sub(r'\1\2', final_result)
                return final_result, {}  # Return translated, no placeholders needed

        return result, placeholder_map

    def _restore_glossary_placeholders(self, text: str, placeholder_map: dict) -> str:
        """Restore glossary translations from placeholders"""
        result = text

        # Debug logging
        if len(text) < 50 and placeholder_map:
            print(f'[Glossary] Restoring placeholders in: "{text}"')

        for placeholder, translation in placeholder_map.items():
            if placeholder in result:
                result = result.replace(placeholder, translation)
                # Debug logging
                if len(text) < 50:
                    print(f'[Glossary] Restored {placeholder} → "{translation}"')
            elif len(text) < 50:
                print(f'[Glossary] WARNING: {placeholder} not found in AI response!')

        if len(text) < 50 and placeholder_map:
            print(f'[Glossary] Final result: "{result}"')

        # Remove spaces between CJK characters (Chinese/Japanese/Korean)
        # This fixes issues like "商人 雷克斯" -> "商人雷克斯"
        cjk_pattern = re.compile(r'([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]) +([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff])')
        while cjk_pattern.search(result):
            result = cjk_pattern.sub(r'\1\2', result)

        return result

    def get_glossary_stats(self) -> Dict[str, int]:
        """Get glossary statistics"""
        return {
            'total_terms': len(self.glossary.terms)
        }

    def reload_glossary(self, glossary_path: str = None):
        """Reload glossary from file after editing"""
        if glossary_path:
            self.config['glossary_path'] = glossary_path
        path = self.config.get('glossary_path', 'glossary.json')
        self.glossary = GlossaryManager(path)
