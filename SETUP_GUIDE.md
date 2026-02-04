# Setup Guide - HTML Translation POC

## Prerequisites

1. **Python 3.8+** - Download from [python.org](https://www.python.org/)
2. **Ollama** - Install from [ollama.ai](https://ollama.ai/)
3. **Git** (optional) - For cloning the repository

## Quick Setup (Windows)

### Method 1: Automatic Setup (Recommended)

1. **Run the setup script:**
   ```batch
   setup.bat
   ```

   This will:
   - Check Python installation
   - Create virtual environment in `venv/`
   - Install all dependencies from `requirements.txt`

2. **Download Ollama model:**
   ```batch
   ollama pull gemma3:4b
   ```

3. **Start translating:**
   ```batch
   cd poc
   run_demo.bat
   ```

### Method 2: Manual Setup

1. **Create virtual environment:**
   ```batch
   python -m venv venv
   ```

2. **Activate virtual environment:**
   ```batch
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```batch
   pip install -r requirements.txt
   ```

4. **Download Ollama model:**
   ```batch
   ollama pull gemma3:4b
   ```

5. **Navigate to POC folder:**
   ```batch
   cd poc
   ```

6. **Run demo:**
   ```batch
   run_demo.bat
   ```

## Folder Structure

```
HTML-Translation/
├── venv/                           ← Virtual environment (auto-created)
├── poc/                            ← Main working directory
│   ├── input/                      ← Place HTML files here
│   ├── output/                     ← Translated files (auto-created)
│   ├── data/
│   │   ├── lineage2/
│   │   │   ├── glossary.json      ← Main glossary (3,116 terms)
│   │   │   └── npc-name/          ← NPC game data
│   │   └── translations/           ← Translation cache (auto-created)
│   ├── translate_poc_v2.py         ← Main translator
│   ├── run_demo.bat                ← Batch translate all files
│   ├── retranslate_term.bat        ← Re-translate specific term
│   └── rebuild_npc_glossary.bat    ← Rebuild NPC glossary
├── requirements.txt                ← Python dependencies
└── setup.bat                       ← Automatic setup script
```

## Running on Different PCs

All batch scripts now automatically activate the virtual environment from the root directory. You don't need to manually activate venv before running scripts.

### What Works Automatically

✅ `run_demo.bat` - Activates venv, then translates all files
✅ `retranslate_term.bat` - Activates venv, then re-translates specific files
✅ `rebuild_npc_glossary.bat` - Activates venv, then rebuilds glossary

### First Time on New PC

1. Clone or copy the project folder
2. Run `setup.bat` from root directory
3. Run `ollama pull gemma3:4b`
4. Done! All batch scripts will work

## Troubleshooting

### "Python not found"
- Install Python 3.8+ from python.org
- Make sure "Add Python to PATH" is checked during installation

### "Virtual environment not found"
- Run `setup.bat` from the root directory
- Or manually create: `python -m venv venv`

### "Ollama connection failed"
- Make sure Ollama is running: `ollama serve`
- Check model is downloaded: `ollama list`
- Download if needed: `ollama pull gemma3:4b`

### "Module not found" errors
- Activate venv: `venv\Scripts\activate`
- Reinstall dependencies: `pip install -r requirements.txt`

## Dependencies

- **beautifulsoup4** - HTML parsing
- **requests** - HTTP requests to Ollama API

All dependencies are listed in `requirements.txt` and installed automatically by `setup.bat`.

## Updating the Project

1. Pull latest changes (if using git)
2. Activate venv: `venv\Scripts\activate`
3. Update dependencies: `pip install -r requirements.txt --upgrade`
4. Deactivate: `deactivate`

## Notes

- Virtual environment is in the **root directory** (`venv/`)
- All batch scripts in `poc/` folder automatically activate venv
- No need to manually activate venv before running batch scripts
- Cache and translations are stored in `poc/data/`
