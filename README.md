# Meme Renamer

AI-powered image renaming tool that analyzes images and renames files based on their content, including any visible text. Also includes a powerful duplicate image finder with visual comparison GUI.

## Features

### Image Renaming
- 🤖 **Multiple AI Providers** - Choose from OpenAI, Claude, or Gemini
- 📄 **PDF Support** - Rename PDFs with Claude or Gemini
- 🔍 **Smart Detection** - Detects non-descriptive filenames automatically
- 📁 **Extension Fixing** - Auto-detects and fixes missing/doubled extensions
- 🔒 **Safe by Default** - Dry-run mode prevents accidental changes
- 🏃 **Batch Processing** - Process entire folders efficiently

### Duplicate Image Finder (NEW!)
- 🔎 **Multiple Detection Methods** - Exact duplicates, visual similarity, and filename matching
- 🖼️ **Interactive GUI** - Two-pane interface for side-by-side comparison
- 📊 **Similarity Scoring** - Color-coded similarity indicators (85-100%)
- 🗂️ **File Operations** - Delete, move, or copy duplicates with confirmation
- 🗑️ **Safe Deletion** - Send files to trash/recycle bin (if available)
- 📈 **CSV Export** - Export duplicate reports for analysis
- ⚡ **Fast Scanning** - Perceptual hashing with caching for performance

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

# AI Providers (install at least one for renaming feature)
pip install openai          # For GPT-4o (default, images only)
pip install anthropic       # For Claude (images + PDFs)
pip install google-generativeai  # For Gemini (images + PDFs)

# Duplicate detection (required for --find-duplicates)
pip install imagehash send2trash

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
| `imagehash` | Perceptual hashing for duplicate detection |
| `send2trash` | Safe file deletion (trash/recycle bin) |
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

---

## Duplicate Image Finder

The duplicate finder helps you identify and manage duplicate or visually similar images across your collection.

### Detection Methods

The tool uses multiple methods to find duplicates:

1. **Exact Duplicates** - Same file size and identical content (MD5 hash)
2. **Visual Similarity** - Perceptual hashing (aHash, pHash, dHash, wHash)
3. **Filename Similarity** - Levenshtein distance for similar names

### Usage

#### Find duplicates in a single directory (with GUI)
```bash
python image_renamer.py /path/to/images --find-duplicates
```

#### Find duplicates between two directories
```bash
python image_renamer.py --find-duplicates --dir1 /path/to/dir1 --dir2 /path/to/dir2
```

#### Export results to CSV (no GUI)
```bash
python image_renamer.py /path/to/images --find-duplicates --no-gui --output duplicates.csv
```

#### Adjust similarity threshold (default: 85%)
```bash
# More strict (only very similar images)
python image_renamer.py /path/to/images --find-duplicates --similarity-threshold 95

# More lenient (catch more potential duplicates)
python image_renamer.py /path/to/images --find-duplicates --similarity-threshold 70
```

#### Choose detection method
```bash
# Only exact duplicates (fastest)
python image_renamer.py /path/to/images --find-duplicates --method exact

# Only visual similarity
python image_renamer.py /path/to/images --find-duplicates --method visual

# All methods (default)
python image_renamer.py /path/to/images --find-duplicates --method all
```

### GUI Features

The interactive GUI provides:

- **Side-by-side comparison** - View both images with thumbnails
- **File information** - Filename, size, dimensions, path
- **Similarity indicator** - Color-coded similarity score
  - 🟢 Green: 99-100% (Exact match)
  - 🟡 Yellow: 85-99% (Very similar)
  - 🟠 Orange: 70-84% (Somewhat similar)
- **Navigation** - Previous/Next buttons to review all pairs
- **Selection** - Checkboxes to mark files for action
- **File operations**:
  - Delete selected files (to trash if available)
  - Move selected files to another directory
  - Copy selected files to another directory

### Keyboard Shortcuts

- `←` / `→` - Navigate between duplicate pairs
- `Space` - Toggle left file selection
- `Delete` - Delete selected files (with confirmation)
- `Enter` - Skip to next pair
- `Escape` - Close window

### Similarity Thresholds

- **Exact match (100%)** - Identical files (same hash)
- **Very similar (85-99%)** - Likely duplicates or near-duplicates
- **Somewhat similar (70-84%)** - Possibly related images
- **Below 70%** - Probably different images

### CSV Export Format

The exported CSV includes:
- File paths and names for both files
- File sizes
- Similarity score (%)
- Match type (exact, visual, similar_name)
- Hash difference (for visual matches)

Example:
```csv
File1_Path,File1_Name,File1_Size,File2_Path,File2_Name,File2_Size,Similarity_Score,Match_Type,Hash_Difference
/path/to/image1.jpg,image1.jpg,12345,/path/to/image1_copy.jpg,image1_copy.jpg,12345,100.0%,exact,0
```

### Performance Tips

- **Cache is used** - Files are scanned once and cached for the session
- **Exact matches exit early** - If exact hash matches, perceptual hash is skipped
- **Adjust threshold** - Higher threshold = faster scanning (fewer matches)
- **Use --method exact** - For fastest scan if you only need exact duplicates

### Troubleshooting

#### No GUI available
If you see "GUI not available", the tool will automatically fall back to console output. This happens when:
- `tkinter` is not installed (usually included with Python)
- Running in a headless environment
- Using `--no-gui` flag

Solution: Use `--no-gui` flag and `--output` to export to CSV

#### All images show 100% similarity
This can happen with:
- Solid color images (all have similar perceptual hashes)
- Very small images (not enough detail)

Solution: Use `--method exact` to only find true duplicates

#### Files not found
Make sure:
- Directory paths are correct
- Images have supported extensions (.jpg, .jpeg, .png, .gif, .webp, .bmp, .tiff)
- You have read permissions for the directories

### Supported Image Formats

- `.jpg` / `.jpeg`
- `.png`
- `.gif`
- `.webp`
- `.bmp`
- `.tiff`

PDFs are not supported for duplicate detection (use for renaming only).
