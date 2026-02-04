# HTML Translation Tool

A desktop application for translating HTML files using local LLM models via Ollama, with support for glossary management, pattern detection, and multiple translation modes.

## Features

- **PySide6-based GUI**: Modern desktop interface for Windows and macOS
- **Local LLM Translation**: Uses Ollama models (Gemma2, Qwen, etc.) for privacy-focused translation
- **Project Management**: Organize translations by project with separate glossaries
- **Glossary System**:
  - Create and manage custom terminology glossaries
  - Auto-extract terms from source HTML
  - Pattern detection for game terms, names, and special formats
- **Translation Modes**:
  - Standard Translation
  - Glossary Reference (highlights glossary terms)
  - Smart Mode (auto-detects and uses glossary when needed)
- **Multi-threaded Processing**: Configurable worker count for faster batch translation
- **Progress Tracking**: Real-time progress bars and file status
- **Dual Preview**: Side-by-side source and translated HTML preview
- **Search Functionality**: Search and retranslate across original and translated files
- **Flexible Output Structure**: Customize output folder organization

## Prerequisites

- Python 3.8 or higher
- [Ollama](https://ollama.ai/) installed and running
- At least one Ollama model downloaded (e.g., `gemma2:2b`, `qwen2.5:3b`)

## Installation

### Windows

1. Clone the repository:
```bash
git clone https://github.com/yourusername/HTML-Translation.git
cd HTML-Translation
```

2. Run the setup script:
```bash
setup.bat
```

3. Run the application:
```bash
run_app.bat
```

### macOS/Linux

1. Clone the repository:
```bash
git clone https://github.com/yourusername/HTML-Translation.git
cd HTML-Translation
```

2. Create virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

3. Run the application:
```bash
python app/main.py
```

## Quick Start

1. **Create a Project**: Click "New Project" and enter a project name
2. **Select Source Folder**: Choose the folder containing your HTML files
3. **Configure Settings**:
   - Select target language
   - Choose Ollama model
   - Set translation mode
   - Configure output structure
4. **Build Glossary** (Optional):
   - Open Glossary Editor
   - Auto-extract terms or add manually
   - Save glossary
5. **Start Translation**:
   - Click "Translate Rest" for new files
   - Or "Re-translate All" to retranslate everything
6. **Review Results**: Check translated files in the output folder

## Project Structure

```
HTML-Translation/
├── app/
│   ├── core/              # Core translation engine
│   │   ├── config.py      # Configuration management
│   │   ├── translator.py  # Main translation engine
│   │   ├── glossary_utils.py  # Glossary management
│   │   ├── pattern_utils.py   # Pattern detection
│   │   ├── spacy_extractor.py # NLP-based term extraction
│   │   └── ollama_provider.py # Ollama API integration
│   ├── ui/                # User interface
│   │   ├── main_window.py # Main application window
│   │   └── glossary_editor.py  # Glossary editor dialog
│   ├── main.py            # Application entry point
│   └── projects/          # Project data (created on first run)
├── requirements.txt       # Python dependencies
├── setup.bat             # Windows setup script
├── run_app.bat           # Windows run script
└── SETUP_GUIDE.md        # Detailed setup instructions

```

## Configuration

The application stores configuration in `app/config.json` (created automatically):

- **app_dir**: Application directory (auto-computed)
- **projects_dir**: Projects storage location (auto-computed)
- **custom_output_root**: Custom output directory (optional)
- **ollama_url**: Ollama API URL (default: http://localhost:11434)
- **include_lang_code_folder**: Add language folder to output path
- **include_parent_folder**: Include source folder name in output
- **worker_count**: Number of parallel translation workers (1-10)

## Translation Modes

1. **Standard**: Direct translation without glossary reference
2. **Glossary Reference**: Highlights glossary terms in translation, uses them as reference
3. **Smart Mode**: Automatically detects when glossary should be used based on content

## Output Structure Settings

Customize how translated files are organized:

- **Include Language Folder**: Creates `output/[lang-code]/` folder
- **Include Parent Folder**: Preserves source folder structure in output
- **Custom Output Root**: Specify a custom output directory

Example configurations:
- Both enabled: `output/zh-TW/html/file.html`
- Parent folder disabled: `output/zh-TW/file.html`
- Custom root: `D:/translations/zh-TW/html/file.html`

## Keyboard Shortcuts

- **Ctrl+S**: Save translated file (when modified)
- **Ctrl+R**: Refresh translated tree
- **Ctrl+F**: Focus search box

## Troubleshooting

### Ollama Connection Issues
- Ensure Ollama is running: `ollama serve`
- Check if model is installed: `ollama list`
- Verify Ollama URL in settings

### Translation Errors
- Check Ollama model has enough context length for your HTML
- Try reducing worker count if getting timeout errors
- Ensure source files are valid HTML

### macOS Path Issues
- Projects are stored relative to app location
- Custom output paths should use absolute paths
- Config is cross-platform compatible

## Dependencies

- PySide6: GUI framework
- beautifulsoup4: HTML parsing
- spacy: NLP for term extraction
- requests: Ollama API communication

See `requirements.txt` for complete list.

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Uses [Ollama](https://ollama.ai/) for local LLM inference
- Built with [PySide6](https://doc.qt.io/qtforpython/) (Qt for Python)
- HTML parsing by [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
