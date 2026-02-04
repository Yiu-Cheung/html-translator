# HTML Translator - User Manual

Welcome to the HTML Translator User Manual! This guide will help you get started with translating HTML files using local AI models.

## Table of Contents

1. [Getting Started](#getting-started)
2. [First Time Setup](#first-time-setup)
3. [Basic Workflow](#basic-workflow)
4. [Understanding the Interface](#understanding-the-interface)
5. [Working with Projects](#working-with-projects)
6. [Using the Glossary](#using-the-glossary)
7. [Translation Modes](#translation-modes)
8. [Batch Translation](#batch-translation)
9. [Search and Retranslate](#search-and-retranslate)
10. [Settings and Configuration](#settings-and-configuration)
11. [Tips and Best Practices](#tips-and-best-practices)
12. [Troubleshooting](#troubleshooting)

---

## Getting Started

### What You Need

Before using HTML Translator, make sure you have:

1. **Ollama** installed and running on your computer
   - Download from: https://ollama.ai/
   - Install at least one model (e.g., `ollama pull gemma2:2b`)

2. **Python 3.8+** (if running from source)

3. **HTML files** you want to translate

### Quick Start (3 Steps)

1. **Create a Project**: Click "New Project" and give it a name
2. **Select Source Folder**: Choose the folder with your HTML files
3. **Click "Translate Rest"**: Watch as your files get translated!

---

## First Time Setup

### Step 1: Install Ollama

1. Download Ollama from https://ollama.ai/
2. Install it on your computer
3. Open terminal/command prompt and run:
   ```bash
   ollama pull gemma2:2b
   ```
   (This downloads a small, fast translation model)

### Step 2: Run HTML Translator

**Windows:**
- Double-click `run_app.bat`

**macOS/Linux:**
```bash
python app/main.py
```

### Step 3: Create Your First Project

1. Click **"New Project"** button (or File → New Project)
2. Enter a project name (e.g., "My Website Translation")
3. Click OK

🎉 You're ready to translate!

---

## Basic Workflow

### Translating Your First HTML File

1. **Select Project** (if not already selected)
2. **Select Source Folder**
   - Click "Select Folder" button
   - Choose the folder containing your HTML files
   - Files will appear in the left "Source Files" tree

3. **Choose Settings**
   - Target Language: Select your target language (e.g., zh-TW for Traditional Chinese)
   - Model: Choose an Ollama model (gemma2:2b is a good start)
   - Mode: Start with "Standard" mode

4. **Start Translation**
   - Click **"Translate Rest"** to translate all untranslated files
   - OR right-click a specific file → "Re-translate" for one file

5. **Review Results**
   - Click on files in the "Translated Files" tree (right side)
   - Original and translated HTML appear in the preview panes
   - Make manual edits if needed (they're saved automatically!)

---

## Understanding the Interface

### Main Window Layout

```
┌─────────────────────────────────────────────────────────────┐
│  File  Project  Tools  Help                                  │
├─────────────────────────────────────────────────────────────┤
│  [Project] [Source Folder] Language: [▼] Model: [▼] Mode:[▼]│
│  [Translate Rest] [Re-translate All] [Stop]                  │
├──────────────────┬──────────────────────────────────────────┤
│ Source Files  │  │  Translated Files  │                      │
│ □ html/       │  │  ✓ html/          │                      │
│   • file1.html│  │    • file1.html   │                      │
│   • file2.html│  │    • file2.html   │                      │
├──────────────────┴──────────────────────────────────────────┤
│ Original HTML            │  Translated HTML                  │
│ <html>...</html>         │  <html>...</html>                │
├──────────────────────────┴───────────────────────────────────┤
│ Status: Ready | Progress: [████████░░] 80%                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Elements

**Top Toolbar:**
- **Project dropdown**: Switch between projects
- **Select Folder**: Choose source HTML folder
- **Language**: Target translation language
- **Model**: Ollama AI model to use
- **Mode**: Translation mode (Standard/Glossary Reference/Smart)

**Action Buttons:**
- **Translate Rest**: Translate only files that haven't been translated yet
- **Re-translate All**: Retranslate everything (careful! overwrites existing)
- **Stop**: Stop the translation process
- **Refresh**: Refresh the translated files tree

**Left Panel - Source Files:**
- Tree view of your source HTML files
- ✓ = Already translated
- Right-click for options (Re-translate, Open in Explorer)

**Right Panel - Translated Files:**
- Tree view of translated HTML files
- Mirrors your source structure
- Right-click to open in Explorer

**Bottom Panels - Preview:**
- Left: Original HTML content
- Right: Translated HTML content
- Edit translated content directly (saves automatically on Ctrl+S)

**Status Bar:**
- Current operation status
- Progress bar for batch translations
- File counts and statistics

---

## Working with Projects

### What is a Project?

A project is a workspace that stores:
- Glossary (custom terminology)
- Translation cache (for consistency)
- Project-specific settings

**Why use projects?** Different content needs different terminology. Game translations need game terms, technical docs need technical terms!

### Creating a New Project

1. Click **"New Project"** or go to File → New Project
2. Enter a descriptive name (e.g., "Game UI", "User Manual", "Marketing Site")
3. Click OK

### Switching Between Projects

Use the **Project dropdown** at the top-left to switch between projects.

Each project remembers:
- Its glossary
- Translation cache
- Last used source folder

### Project Organization Tips

✅ **Good Project Structure:**
- One project per website/application
- One project per content type (UI, docs, marketing)
- Share glossaries for related projects

❌ **Avoid:**
- Single project for everything (glossary gets messy)
- Too many small projects (hard to manage)

---

## Using the Glossary

### What is a Glossary?

A glossary is your custom dictionary of terms and their translations. It ensures consistent translation of:
- Product names (should not be translated)
- Technical terms
- Character names (in games)
- Brand names
- Specialized vocabulary

### Opening the Glossary Editor

Click **"Glossary Editor"** button or go to Tools → Glossary Editor

### Building a Glossary

#### Method 1: Auto-Extract Terms (Recommended for First Time)

1. Open Glossary Editor
2. Click **"Auto Extract from Source"**
3. The app scans your HTML and finds:
   - Proper nouns
   - Capitalized terms
   - Repeated technical words
4. Review the extracted terms
5. Add manual translations for important terms
6. Click **"Save"**

#### Method 2: Manual Entry

1. Open Glossary Editor
2. Click **"Add Entry"**
3. Enter:
   - **Source term**: The original word/phrase (e.g., "Health Potion")
   - **Target term**: Your preferred translation (e.g., "生命藥水")
   - **Category**: Optional grouping (e.g., "Items", "Skills")
   - **Notes**: Context or usage notes
4. Click OK
5. Click **"Save"** when done

### Glossary Best Practices

✅ **Do:**
- Add product/brand names (often kept in English)
- Add character names with consistent translations
- Add technical terms specific to your domain
- Use categories to organize (UI, Items, Skills, etc.)

❌ **Don't:**
- Add every single word (just important terms)
- Add common words (the AI handles those)
- Forget to save!

### Example Glossary for Game Translation

| Source Term | Target Term | Category | Notes |
|-------------|-------------|----------|-------|
| Health Potion | 生命藥水 | Items | Red potion icon |
| Quest | 任務 | UI | Not "quest" (keep consistent) |
| Guild | 公會 | System | Player organization |
| Level Up | 升級 | UI | Keep caps consistent |

---

## Translation Modes

The app offers three translation modes to suit different needs:

### 1. Standard Mode

**When to use:** Quick translations without glossary

**How it works:**
- Translates directly without glossary reference
- Fastest mode
- Good for general content

**Best for:**
- First pass translations
- Content without specialized terms
- Testing/experimentation

### 2. Glossary Reference Mode

**When to use:** Content with specialized terminology

**How it works:**
- Shows glossary terms to the AI
- AI uses them as reference (but not forced)
- Highlights glossary terms in translation
- Ensures consistency with your terminology

**Best for:**
- Game translations (items, skills, characters)
- Technical documentation
- Content with brand names
- Anything requiring consistent terminology

### 3. Smart Mode (Recommended)

**When to use:** General use, mixed content

**How it works:**
- Automatically detects if content needs glossary
- Uses glossary only when relevant terms are found
- Balances speed and accuracy

**Best for:**
- Mixed content (some pages need glossary, some don't)
- General website translation
- When unsure which mode to use

### Choosing the Right Mode

```
Is this your first translation? → Start with Standard
├─ Do you have a glossary? → No → Standard Mode
│                          → Yes → Continue
├─ Does every file need glossary terms? → Yes → Glossary Reference
│                                       → No → Smart Mode
└─ Not sure? → Smart Mode (it decides for you!)
```

---

## Batch Translation

### Translating Multiple Files

#### Option 1: Translate Rest (Recommended)

1. Select source folder
2. Click **"Translate Rest"**
3. Only untranslated files will be processed
4. Safe to run multiple times!

**Use when:**
- Adding new files to existing project
- Resuming after stopping
- First time translating a folder

#### Option 2: Re-translate All

1. Click **"Re-translate All"**
2. Choose "Yes" to clear existing translations (or "No" to overwrite)
3. ALL files will be retranslated

⚠️ **Warning:** This overwrites existing translations!

**Use when:**
- Changed glossary and want to reapply
- Changed model/mode and want consistency
- Previous translations had issues

### Right-Click Retranslate

For more control:

**Single File:**
1. Right-click file in Source tree
2. Select "Re-translate"
3. Only that file gets retranslated

**Multiple Files:**
1. Hold Ctrl/Cmd and click multiple files
2. Right-click selection
3. Select "Re-translate All (X items)"

**Entire Folder:**
1. Right-click a folder
2. Select "Re-translate All in Folder"
3. All files in that folder get retranslated

### Progress Tracking

During batch translation, you'll see:
- **Progress bar**: Visual progress indicator
- **Status text**: Current file being translated
- **File count**: "Translating: file.html (15/42)"
- **Stop button**: Click to stop (current file finishes first)

### Performance Tips

**Speed up translations:**
1. Increase worker count in Settings (File → Settings → Worker Count)
   - 1 worker = Slowest, most stable
   - 3 workers = Balanced (default)
   - 6+ workers = Fastest, but heavy on system

2. Use smaller models for faster speed:
   - `gemma2:2b` - Very fast, good quality
   - `qwen2.5:3b` - Balanced
   - `qwen2.5:7b` - Slower, better quality

3. Use Standard mode for first pass (fastest)

---

## Search and Retranslate

### Why Search?

Find specific terms or phrases across all files:
- Check if glossary terms are used correctly
- Find files containing specific text
- Locate errors or inconsistencies

### How to Search

1. **Enter search term** in search box (top-right)
2. **Select search scope:**
   - ☑ Original Files: Search source HTML
   - ☑ Translated Files: Search translated HTML
3. **Click "Search"** or press Enter
4. Results appear in the Search Results panel

### Search Results Panel

Each result shows:
- **File name**: Which file contains the match
- **Context**: Text around the match
- **Location**: Original or Translated

### Retranslate from Search Results

1. Select one or more search results (Ctrl+Click for multiple)
2. Right-click selection
3. Choose "Retranslate" or "Retranslate (X files)"
4. Selected files will be retranslated

**Use case example:**
- You updated glossary term "Health Potion" → "生命藥水"
- Search for "Health Potion" in Original Files
- Select all results
- Retranslate to apply new glossary term

---

## Settings and Configuration

### Accessing Settings

Go to **File → Settings**

### Important Settings

#### General Settings

**Target Language:**
- Choose your translation target language
- Common: `zh-TW` (Traditional Chinese), `ja` (Japanese), `ko` (Korean)

**Ollama Model:**
- Select which AI model to use
- Must be installed in Ollama first
- Recommendations:
  - `gemma2:2b` - Fast, good for testing
  - `qwen2.5:3b` - Balanced, good all-rounder
  - `qwen2.5:7b` - Best quality, slower

**Worker Count:**
- How many files to translate simultaneously
- Range: 1-10
- Recommended: 3 (good balance)
- Higher = faster but uses more resources

#### Output Settings

**Custom Output Root:**
- By default, outputs to `app/output/`
- Specify custom path if desired (e.g., `D:/Translations/`)

**Include Language Code Folder:**
- ☑ Enabled: `output/zh-TW/file.html`
- ☐ Disabled: `output/file.html`
- Recommended: Enabled (keeps languages separate)

**Include Parent Folder:**
- ☑ Enabled: `output/zh-TW/html/file.html` (preserves structure)
- ☐ Disabled: `output/zh-TW/file.html` (flat structure)
- Recommended: Enabled (maintains organization)

#### Preview Settings

**Auto-refresh on Translation Complete:**
- ☑ Enabled: Preview updates automatically when file finishes
- ☐ Disabled: Manual selection needed
- Recommended: Enabled for visual feedback

### Advanced Settings

**Ollama URL:**
- Default: `http://localhost:11434`
- Change if Ollama runs on different port or remote server

---

## Tips and Best Practices

### 🎯 Translation Quality Tips

1. **Build glossary first**
   - Run "Auto Extract from Source" before first translation
   - Review and add manual translations for key terms
   - Update glossary as you find inconsistencies

2. **Use appropriate models**
   - Small files: Use fast models (`gemma2:2b`)
   - Important content: Use larger models (`qwen2.5:7b`)
   - Test with small batches first

3. **Review and edit**
   - Always review critical content
   - Edit translated HTML directly in preview
   - Press Ctrl+S to save edits

4. **Consistent terminology**
   - Use Glossary Reference mode for important content
   - Search and fix inconsistencies
   - Keep glossary updated

### 🚀 Workflow Efficiency Tips

1. **Organize by project**
   - One project per website/application
   - Reuse glossaries across similar projects

2. **Batch translation strategy**
   - First pass: Standard mode for speed
   - Second pass: Retranslate important files with Glossary Reference
   - Final: Manual review and edits

3. **Use search for quality control**
   - Search for common errors
   - Find all uses of key terms
   - Retranslate problem files

4. **Leverage multi-threading**
   - Increase worker count for large batches
   - Lower it if system becomes slow

### 💾 File Management Tips

1. **Backup source files**
   - App only modifies output folder
   - But backup source files before starting!

2. **Version control**
   - Use git for source files
   - Track translated outputs if needed

3. **Output structure**
   - Keep "Include Parent Folder" enabled
   - Maintains source structure in output
   - Easier to find translated files

### 🎮 Game Translation Specific Tips

1. **Categorize glossary**
   - Items, Skills, Characters, UI, System
   - Makes finding and updating easier

2. **Test in-game**
   - Check if translations fit UI space
   - Verify special characters display correctly

3. **Handle placeholders**
   - Glossary entries like `{0}`, `%s`, `$1` should not be translated
   - Add to glossary as "do not translate"

---

## Troubleshooting

### Ollama Connection Issues

**Problem:** "Failed to connect to Ollama"

**Solutions:**
1. Check Ollama is running:
   ```bash
   ollama list
   ```
2. Start Ollama:
   ```bash
   ollama serve
   ```
3. Verify model is installed:
   ```bash
   ollama pull gemma2:2b
   ```
4. Check Ollama URL in Settings (should be `http://localhost:11434`)

### Translation Errors

**Problem:** "Translation failed" or timeout errors

**Solutions:**
1. **File too large:**
   - Use smaller model with larger context
   - Split large HTML files

2. **Model overloaded:**
   - Reduce worker count
   - Close other Ollama applications

3. **Invalid HTML:**
   - Check source HTML is valid
   - Fix HTML syntax errors

### No Files Showing

**Problem:** Source tree is empty after selecting folder

**Solutions:**
1. Check folder contains `.html` or `.htm` files
2. Try selecting parent folder
3. Verify file permissions (read access)

### Glossary Not Working

**Problem:** Glossary terms not appearing in translation

**Solutions:**
1. **Check translation mode:**
   - Standard mode doesn't use glossary
   - Switch to Glossary Reference or Smart mode

2. **Verify glossary is saved:**
   - Open Glossary Editor
   - Check terms are present
   - Click Save

3. **Re-translate:**
   - Glossary only applies to new translations
   - Right-click → Re-translate to apply glossary

### Slow Translation

**Problem:** Translation is very slow

**Solutions:**
1. **Use smaller model:**
   - `gemma2:2b` is much faster than `qwen2.5:7b`
   - Switch in Settings → Ollama Model

2. **Increase workers:**
   - Settings → Worker Count → Increase to 5-6
   - (If system has enough RAM)

3. **Close other apps:**
   - Free up system resources
   - Ollama needs CPU/RAM

### Preview Not Updating

**Problem:** Preview shows old content

**Solutions:**
1. **Enable auto-refresh:**
   - Settings → Auto-refresh on translation complete

2. **Click Refresh:**
   - Click "Refresh" button in toolbar

3. **Reselect file:**
   - Click another file, then click back

### Cross-Platform Issues (macOS)

**Problem:** "Project path not found" on macOS

**Solution:**
- Projects are stored relative to app location
- Don't move app folder after creating projects
- If moved, recreate projects

### Edited Translations Not Saving

**Problem:** Manual edits to translated HTML are lost

**Solutions:**
1. **Press Ctrl+S to save:**
   - Edits are not auto-saved
   - Must save manually or on window close

2. **Don't retranslate:**
   - Re-translating overwrites manual edits
   - Use "Translate Rest" instead of "Re-translate All"

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save translated file (when edited) |
| Ctrl+R | Refresh translated tree |
| Ctrl+F | Focus search box |
| Ctrl+N | New project |
| Ctrl+O | Open source folder |
| F5 | Refresh translated tree |

---

## Need More Help?

### Resources

- **GitHub Repository:** https://github.com/Yiu-Cheung/html-translator
- **Report Issues:** https://github.com/Yiu-Cheung/html-translator/issues
- **Email Support:** yiumail@gmail.com

### Before Asking for Help

Please provide:
1. Operating system (Windows/macOS/Linux)
2. Ollama version (`ollama --version`)
3. Model being used
4. Error message (if any)
5. Steps to reproduce the issue

---

## About the Author

**HTML Translator** is developed by **YiuCheung**

- Email: yiumail@gmail.com
- GitHub: https://github.com/Yiu-Cheung

### Contributing

Contributions are welcome! Please submit pull requests or issues on GitHub.

### License

This project is licensed under the MIT License. See LICENSE file for details.

---

**Happy Translating! 🌐✨**
