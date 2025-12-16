# Meme Renamer

AI-powered image renaming tool that analyzes images and renames files based on their content, including any visible text.

## Features

- 🤖 **Multiple AI Providers** - Choose from OpenAI, Claude, or Gemini
- 📄 **PDF Support** - Rename PDFs with Claude or Gemini
- 🔍 **Smart Detection** - Detects non-descriptive filenames automatically
- 📁 **Extension Fixing** - Auto-detects and fixes missing/doubled extensions
- 🔒 **Safe by Default** - Dry-run mode prevents accidental changes
- 🏃 **Batch Processing** - Process entire folders efficiently

## Requirements

### Python Version
- **Python 3.8+** (tested with Python 3.10)

### Python Packages

**Quick install (all packages):**
```bash
pip install -r requirements.txt
```

**Or install individually:**
```bash
# Core packages (required)
pip install pillow python-dotenv

# AI Providers (install at least one)
pip install openai          # For GPT-4o (default, images only)
pip install anthropic       # For Claude (images + PDFs)
pip install google-generativeai  # For Gemini (images + PDFs)

# Optional: Better filename detection
pip install nltk
python -c "import nltk; nltk.download('words')"
```

| Package | Purpose |
|---------|---------|
| `pillow` | Image processing (PIL) |
| `python-dotenv` | Load API keys from `.env` file |
| `openai` | OpenAI API client (GPT-4o) |
| `anthropic` | Anthropic API client (Claude) |
| `google-generativeai` | Google API client (Gemini) |
| `nltk` | (Optional) English dictionary for smarter filename detection |

## AI Providers

| Provider | Model | PDF Support | Notes |
|----------|-------|-------------|-------|
| **OpenAI** | GPT-4o | ❌ No | Default. Fast, reliable. |
| **Claude** | Claude Sonnet | ✅ Yes | Excellent quality. Best for PDFs. |
| **Gemini** | Gemini 1.5 Flash | ✅ Yes | Fast. Has free tier. |

### API Key Setup

#### Option 1: Using a `.env` file (Recommended)

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API key(s):
   ```
   OPENAI_API_KEY=sk-your-key-here
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   GOOGLE_API_KEY=your-key-here
   ```

The `.env` file is gitignored and will never be uploaded to GitHub.

#### Option 2: Environment variable
```bash
export OPENAI_API_KEY="sk-your-key-here"
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export GOOGLE_API_KEY="your-key-here"
```

#### Option 3: Pass directly to script
```bash
python image_renamer.py /path/to/images --api-key sk-your-key-here
```

## Usage

### Basic Commands

```bash
# Dry run - see what would be renamed (no changes made)
python image_renamer.py /path/to/images

# Actually rename files
python image_renamer.py /path/to/images --execute

# Quick count - no API calls, just show what would be processed
python image_renamer.py /path/to/images --count-only

# Test connection and measure latency
python image_renamer.py /path/to/images --test-connection
```

### Choosing a Provider

```bash
# Use OpenAI (default) - images only
python image_renamer.py /path/to/images --execute

# Use Claude - supports PDFs
python image_renamer.py /path/to/images --provider claude --execute

# Use Gemini - supports PDFs, has free tier
python image_renamer.py /path/to/images --provider gemini --execute
```

### Processing PDFs

OpenAI's vision API doesn't support PDFs. Use Claude or Gemini:

```bash
# Process PDFs with Claude
python image_renamer.py /path/to/pdfs --provider claude --execute

# Process PDFs with Gemini
python image_renamer.py /path/to/pdfs --provider gemini --execute
```

### Limiting Processing

```bash
# Process only first 10 files (good for testing)
python image_renamer.py /path/to/images --limit 10 --execute
```

### Fixing Extensions Only (No AI)

```bash
# Dry run - see what would be fixed
python image_renamer.py /path/to/images --fix-extensions

# Actually fix extensions
python image_renamer.py /path/to/images --fix-extensions --execute
```

## Features Detail

### Auto-detect Missing File Extensions (ON by default)

Many images downloaded from the web or messaging apps have no file extension. This tool:

1. Detects images without extensions by reading file header bytes
2. Identifies the correct format (PNG, JPG, GIF, WEBP, BMP, TIFF, PDF)
3. Adds the correct extension when renaming

**Example:**
```
CURRENT:  downloaded_image
DETECTED: .png (was missing extension)
RENAMED:  cat_meme_funny.png
```

To disable this feature, use `--no-add-extension`.

### Fix Doubled Extensions

Fixes files with doubled extensions like `photo.jpg.jpg`:
```bash
python image_renamer.py /path/to/images --fix-extensions --execute
```

## Cost Estimate

Using GPT-4o with low-detail images:
- **~$0.00004 per image**
- **~$0.15-0.20 for 4,000 images**

Claude and Gemini have similar pricing. Gemini has a free tier.

## Supported Formats

### Images
- `.jpg` / `.jpeg`
- `.png`
- `.gif`
- `.webp`
- `.bmp`
- `.tiff`

### Documents
- `.pdf` (requires Claude or Gemini)

## Platform Compatibility

Works on **Windows**, **macOS**, and **Linux** with no additional configuration needed.

| Platform | Requirements | Notes |
|----------|--------------|-------|
| **Windows** | Python 3.8+, pip packages | Use `python` instead of `python3` |
| **macOS** | Python 3.8+, pip packages | Works out of the box |
| **Linux** | Python 3.8+, pip packages | Works out of the box |

### Windows-specific notes:
```cmd
# Install packages
pip install pillow python-dotenv openai anthropic google-generativeai

# Run the script
python image_renamer.py C:\Users\YourName\Pictures --execute
```

### macOS/Linux:
```bash
# Install packages
pip3 install pillow python-dotenv openai anthropic google-generativeai

# Run the script
python3 image_renamer.py /path/to/images --execute
```

## What Gets Renamed

Files with non-descriptive names like:
- Facebook/Instagram IDs (`598247563_940449168402670_n.jpg`)
- Screenshots (`Screenshot 2025-12-15 at 3.42.42 PM.png`)
- Auto-generated names (`IMG_1234.jpg`, `DSC_5678.jpg`)
- UUIDs and hex strings
- Generic names (`image1.jpg`, `download.png`)

Files with meaningful names are skipped.
