"""
Ollama Translation Provider
Handles translation requests using local Ollama models
"""

import requests
import json
from typing import Dict, Any


class OllamaProvider:
    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', 11434)
        self.model = config.get('model', 'gemma3:4b')
        self.timeout = config.get('timeout', 60)
        self.temperature = config.get('temperature', 0.1)  # Low temperature for consistent results
        self.base_url = f'http://{self.host}:{self.port}'

    def translate(self, text: str, source_lang: str, target_lang: str, glossary_hint: str = "") -> str:
        """Translate text from source language to target language"""
        prompt = self.build_prompt(text, source_lang, target_lang, glossary_hint)

        try:
            response = self.call_ollama(prompt)
            return self.extract_translation(response, text)
        except Exception as error:
            print(f'[Ollama] Translation error: {error}')
            raise

    def translate_html_direct(self, html: str, source_lang: str, target_lang: str, glossary_hint: str = "", project_name: str = "Project") -> str:
        """Translate entire HTML directly with glossary in prompt"""
        prompt = self.build_html_direct_prompt(html, source_lang, target_lang, glossary_hint, project_name)

        print(f'\n[Ollama] Direct mode prompt (first 500 chars):\n{prompt[:500]}...\n')

        try:
            response = self.call_ollama(prompt)
            print(f'\n[Ollama] AI response (first 500 chars):\n{response[:500]}...\n')

            translated = self.extract_html_translation(response, html)

            if translated == html:
                print(f'[Ollama] WARNING: Translation returned same as original - AI may not be translating!')

            return translated
        except Exception as error:
            print(f'[Ollama] HTML translation error: {error}')
            raise

    def build_prompt(self, text: str, source_lang: str, target_lang: str, glossary_hint: str = "") -> str:
        """Build translation prompt"""
        lang_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ja': 'Japanese',
            'zh-TW': 'Traditional Chinese (繁體中文)',
            'zh-CN': 'Simplified Chinese',
            'ko': 'Korean'
        }

        source = lang_names.get(source_lang, source_lang)
        target = lang_names.get(target_lang, target_lang)

        # Check if text contains placeholders (placeholder mode)
        if "__GLOSS_" in text:
            # Placeholder mode: simple prompt with placeholder preservation
            prompt = f"""Translate to {target}. Output only the translation. Keep __GLOSS_0__, __GLOSS_1__ etc unchanged.

{text}"""
        elif glossary_hint:
            # Direct mode: include glossary terms in prompt
            prompt = f"""Translate to {target}. Glossary terms below are for reference - use them when appropriate. Translate consistently. Output only the translation.

{glossary_hint}

{text}"""
        else:
            # No glossary mode: simple translation
            prompt = f"""Translate to {target}. Output only the translation.

{text}"""

        return prompt

    def build_html_direct_prompt(self, html: str, source_lang: str, target_lang: str, glossary_hint: str = "", project_name: str = "Project") -> str:
        """Build prompt for direct HTML translation"""
        lang_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ja': 'Japanese',
            'zh-TW': 'Traditional Chinese (繁體中文)',
            'zh-CN': 'Simplified Chinese',
            'ko': 'Korean'
        }

        source = lang_names.get(source_lang, source_lang)
        target = lang_names.get(target_lang, target_lang)

        # Build glossary section with project name
        glossary_section = ""
        if glossary_hint:
            # Replace "Glossary:" with "{project_name} Glossary terms:"
            glossary_section = f"\n\n{project_name} {glossary_hint.replace('Glossary:', 'Glossary terms:')}"

        # Use user's exact format with clarification
        prompt = f"""Translate following HTML/HTM {source} contents to {target}, you must:
- Translate all English text to {target}, including text content and attribute values (value="...", title="...", alt="...", placeholder="...")
- Base on {project_name} glossary terms
- Consistent translate
- Keep HTML tags/structure unchanged, only translate English text
- Return complete translated HTML starting with <html>{glossary_section}

{html}"""

        return prompt

    def call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        url = f'{self.base_url}/api/generate'

        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': self.temperature
            }
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()

            if 'error' in data:
                raise Exception(data['error'])

            return data.get('response', '')

        except requests.exceptions.RequestException as e:
            raise Exception(f'Ollama request failed: {e}')

    def extract_translation(self, response: str, original_text: str = "") -> str:
        """Extract clean translation from response"""
        # Remove common prefixes that models might add
        translation = response.strip()

        # Remove "Translation:" prefix if present
        if translation.lower().startswith('translation:'):
            translation = translation[12:].strip()

        # Remove quotes if the entire response is quoted
        if (translation.startswith('"') and translation.endswith('"')) or \
           (translation.startswith("'") and translation.endswith("'")):
            translation = translation[1:-1]

        translation = translation.strip()

        # Hallucination detection: if translation has way more sentences than original
        if original_text:
            orig_sentences = original_text.count('.') + original_text.count('!') + original_text.count('?')
            trans_sentences = translation.count('。') + translation.count('！') + translation.count('？') + \
                             translation.count('.') + translation.count('!') + translation.count('?')
            # If translation has 2+ more sentence endings than original, likely hallucination
            if trans_sentences > orig_sentences + 1 and len(original_text) < 100:
                print(f'[Ollama] WARNING: Possible hallucination detected. Original sentences: {orig_sentences}, Translation sentences: {trans_sentences}')
                # Try to extract just the first sentence
                for sep in ['。', '！', '？', '.', '!', '?']:
                    if sep in translation:
                        first_part = translation.split(sep)[0] + (sep if sep in '。！？' else '')
                        if len(first_part) > 3:
                            print(f'[Ollama] Truncating to first sentence: {first_part}')
                            return first_part.strip()

        return translation

    def extract_html_translation(self, response: str, original_html: str = "") -> str:
        """Extract HTML translation from response"""
        # The response should contain the full HTML
        translation = response.strip()

        # Remove markdown code blocks if present
        if translation.startswith('```html'):
            translation = translation[7:].strip()
        elif translation.startswith('```'):
            translation = translation[3:].strip()

        if translation.endswith('```'):
            translation = translation[:-3].strip()

        # Ensure it starts with <html> or <!DOCTYPE>
        if not translation.lower().startswith('<html') and not translation.lower().startswith('<!doctype'):
            print(f'[Ollama] WARNING: Response does not start with HTML tag')
            # Try to find the HTML content in the response
            html_start = translation.lower().find('<html')
            if html_start > 0:
                translation = translation[html_start:]
            else:
                # If still no HTML found, return original
                print(f'[Ollama] ERROR: Could not find HTML in response, returning original')
                return original_html

        return translation

    def check_connection(self) -> bool:
        """Check if Ollama is running"""
        try:
            url = f'{self.base_url}/api/version'
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            print(f'[Ollama] Connected to {self.host}:{self.port} using model {self.model}')
            return True
        except Exception as error:
            print(f'[Ollama] Connection failed: {error}')
            return False

    def get_available_models(self) -> list:
        """Get list of available models from Ollama"""
        try:
            url = f'{self.base_url}/api/tags'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            models = []
            for model in data.get('models', []):
                name = model.get('name', '')
                size = model.get('details', {}).get('parameter_size', '')
                family = model.get('details', {}).get('family', '')
                models.append({
                    'name': name,
                    'size': size,
                    'family': family
                })
            return models
        except Exception as error:
            print(f'[Ollama] Failed to get models: {error}')
            return []

    def set_model(self, model_name: str):
        """Change the model being used"""
        self.model = model_name
        print(f'[Ollama] Switched to model: {model_name}')

    def set_temperature(self, temperature: float):
        """Set the temperature for generation"""
        self.temperature = temperature
        print(f'[Ollama] Temperature set to: {temperature}')
