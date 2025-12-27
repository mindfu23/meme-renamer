#!/usr/bin/env python3
"""
Image Renamer Script
Scans a directory for images, identifies files with non-descriptive names,
analyzes them using vision AI, and renames them based on content.

Supports multiple AI providers:
- OpenAI (GPT-4o) - default, images only (no PDF)
- Claude (Anthropic) - images and PDFs
- Gemini (Google) - images and PDFs
"""

import os
import re
import sys
import base64
import hashlib
from pathlib import Path
from datetime import datetime

# Load .env file if it exists (for local API key storage)
try:
    from dotenv import load_dotenv
    # Load from .env in the same directory as this script
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass  # dotenv not installed, rely on environment variables

# Core dependencies
# pip install openai pillow python-dotenv
# Optional: pip install anthropic google-generativeai

# Try importing AI provider libraries
OPENAI_AVAILABLE = False
ANTHROPIC_AVAILABLE = False
GOOGLE_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    pass

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    pass

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    pass

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# Check if at least one provider and pillow are available
DEPENDENCIES_AVAILABLE = PILLOW_AVAILABLE and (OPENAI_AVAILABLE or ANTHROPIC_AVAILABLE or GOOGLE_AVAILABLE)
if not DEPENDENCIES_AVAILABLE:
    if not PILLOW_AVAILABLE:
        MISSING_DEP = "No module named 'PIL' (pillow)"
    else:
        MISSING_DEP = "No AI provider available. Install at least one: openai, anthropic, or google-generativeai"
else:
    MISSING_DEP = None

# Supported AI providers
AI_PROVIDERS = {
    'openai': {'available': OPENAI_AVAILABLE, 'supports_pdf': False, 'env_key': 'OPENAI_API_KEY'},
    'claude': {'available': ANTHROPIC_AVAILABLE, 'supports_pdf': True, 'env_key': 'ANTHROPIC_API_KEY'},
    'gemini': {'available': GOOGLE_AVAILABLE, 'supports_pdf': True, 'env_key': 'GOOGLE_API_KEY'},
}


def print_dependency_error():
    """Print helpful error message when dependencies are missing."""
    print(f"\n❌ Error: Missing dependencies.")
    print(f"   {MISSING_DEP}")
    print("\n" + "=" * 60)
    print("SOLUTION:")
    print("=" * 60)
    print("\n1. Install required packages:")
    print("   pip install pillow python-dotenv")
    print("\n2. Install at least one AI provider:")
    print("   pip install openai          # For GPT-4o (images only)")
    print("   pip install anthropic       # For Claude (images + PDFs)")
    print("   pip install google-generativeai  # For Gemini (images + PDFs)")
    print("\n3. If you already installed but still see this error,")
    print("   you may have multiple Python versions installed.")
    print("   Try installing with the specific Python this script uses:")
    print(f"\n   {sys.executable} -m pip install pillow openai anthropic google-generativeai python-dotenv")
    print("\n4. Or run the script explicitly with that Python:")
    print(f"   {sys.executable} image_renamer.py <directory>")
    print("\n" + "=" * 60)

# Configuration
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.pdf'}
# Extensions that OpenAI vision API supports (no PDF)
OPENAI_SUPPORTED = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILENAME_LENGTH = 100

# Common non-descriptive patterns
NON_DESCRIPTIVE_PATTERNS = [
    r'^[a-f0-9]{8,}$',  # Hex strings (like UUIDs without dashes)
    r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',  # Full UUIDs
    r'^\d+$',  # Just numbers
    r'^IMG_?\d+$',  # IMG_12345
    r'^DSC_?\d+$',  # DSC_12345
    r'^DCIM_?\d+$',  # DCIM_12345
    r'^Screenshot.*\d{4}.*$',  # Screenshot with timestamp
    r'^Screen Shot.*$',  # Mac screenshots
    r'^image\s*\d*$',  # image, image1, image 2
    r'^photo\s*\d*$',  # photo, photo1
    r'^pic\s*\d*$',  # pic, pic1
    r'^download\s*\d*$',  # download, download(1)
    r'^\d{4}-\d{2}-\d{2}.*$',  # Date-based names
    r'^[A-Za-z]{1,3}\d{5,}$',  # Short prefix + long number
    r'^temp.*$',  # temp files
    r'^untitled.*$',  # untitled
    r'^\(\d+\)$',  # Just (1), (2), etc.
    r'^copy.*$',  # copy of...
    r'^[a-zA-Z0-9]{32,}$',  # Long random alphanumeric strings (NO hyphens/underscores - those are likely word separators)
    r'^[a-zA-Z0-9]{4,7}$',  # Short random alphanumeric (4-7 chars like "2M3cw", "2WekD", "qHqjdg6")
    r'^[a-zA-Z]\d[a-zA-Z0-9]+$',  # Starts with letter, then digit, then more (like "d6ha3sn")
    r'^\d[a-zA-Z]\d*[a-zA-Z0-9]*$',  # Starts with digit, then letter pattern (like "2M3cw")
]

# Try to load English dictionary for word validation
# Falls back to a basic indicator list if not available
ENGLISH_WORDS = None
DICTIONARY_AVAILABLE = False

try:
    from nltk.corpus import words
    # Load English words into a set for O(1) lookup
    ENGLISH_WORDS = set(w.lower() for w in words.words())
    DICTIONARY_AVAILABLE = True
except (ImportError, LookupError):
    # NLTK not installed or words corpus not downloaded
    # User can install with: pip install nltk && python -c "import nltk; nltk.download('words')"
    pass

# Fallback indicator words (used if dictionary not available, or as supplements)
MEANINGFUL_INDICATORS = [
    'cat', 'dog', 'car', 'house', 'person', 'landscape', 'portrait',
    'family', 'wedding', 'birthday', 'vacation', 'beach', 'mountain',
    'city', 'food', 'sunset', 'sunrise', 'nature', 'animal', 'flower',
    'tree', 'building', 'art', 'painting', 'drawing', 'logo', 'icon',
    'banner', 'header', 'background', 'texture', 'pattern', 'design',
    'chart', 'graph', 'diagram', 'map', 'screenshot', 'mockup',
    # Brand/product words (not in dictionary but common in filenames)
    'fender', 'guitar', 'amp', 'schedule', 'indeed', 'poster', 'flyer',
    'comic', 'meme', 'tweet', 'post', 'article', 'news', 'video',
    'imgur', 'reddit', 'tumblr', 'instagram', 'facebook', 'twitter',
]

# Common abbreviations and acronyms (not in standard dictionaries)
COMMON_ABBREVIATIONS = {
    # Medical/psychological conditions
    'adhd', 'add', 'ocd', 'ptsd', 'asd', 'bpd', 'gad', 'mdd',
    # Technology
    'ai', 'ml', 'api', 'cpu', 'gpu', 'ram', 'ssd', 'hdd', 'usb', 'hdmi',
    'nft', 'vr', 'ar', 'iot', 'ui', 'ux', 'os', 'pc', 'mac', 'ios',
    'html', 'css', 'js', 'sql', 'php', 'xml', 'json', 'yaml',
    # File formats (without dots)
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'mp3', 'mp4', 'avi', 'mov',
    # General/business
    'diy', 'fyi', 'asap', 'faq', 'tbd', 'tba', 'rsvp', 'eta', 'ceo', 'cto',
    'hr', 'pr', 'qa', 'roi', 'kpi', 'b2b', 'b2c', 'saas', 'crm', 'erp',
    # Countries/regions
    'usa', 'uk', 'eu', 'uae', 'nyc', 'la', 'sf', 'dc',
    # Internet/social
    'lol', 'omg', 'wtf', 'btw', 'imo', 'imho', 'afk', 'brb', 'tldr',
    'dm', 'pm', 'op', 'oc', 'ama', 'eli5', 'til', 'tfw', 'mfw',
    # Misc
    'vs', 'aka', 'etc', 'misc', 'info', 'intro', 'outro', 'demo', 'beta',
}


def is_ordinal_number(text: str) -> bool:
    """
    Check if text is an ordinal number (1st, 2nd, 3rd, 4th, 21st, 22nd, 23rd, etc.)
    
    Args:
        text: The text to check (case-insensitive)
    
    Returns:
        True if text is a valid ordinal number
    """
    return bool(re.match(r'^\d+(st|nd|rd|th)$', text.lower()))


def is_english_word(word: str, min_length: int = 3) -> bool:
    """
    Check if a word is a valid English word, abbreviation, or ordinal.
    Uses NLTK dictionary if available, plus abbreviations and ordinals.
    
    Args:
        word: The word to check (will be lowercased)
        min_length: Minimum length to consider (default 3)
    
    Returns:
        True if word appears to be a valid English word, abbreviation, or ordinal
    """
    word = word.lower()
    
    # Check ordinals first (1st, 2nd, 3rd, etc.) - these can be any length
    if is_ordinal_number(word):
        return True
    
    # Check common abbreviations (allow shorter min_length for abbreviations)
    if word in COMMON_ABBREVIATIONS:
        return True
    
    if len(word) < min_length:
        return False
    
    # Check dictionary if available
    if DICTIONARY_AVAILABLE and ENGLISH_WORDS:
        if word in ENGLISH_WORDS:
            return True
    
    # Check fallback indicators (exact match or word contains indicator)
    for indicator in MEANINGFUL_INDICATORS:
        if word == indicator or indicator in word:
            return True
    
    return False


def extract_fb_img_suffix(filename: str) -> tuple[bool, str]:
    """
    Check if filename is FB_IMG format and extract any text suffix.
    
    Returns:
        (is_fb_img, suffix_text)
        - is_fb_img: True if this is an FB_IMG file
        - suffix_text: Any text after the numbers (e.g., '-some-text-here' from 'FB_IMG_123456-some-text-here.jpg')
    """
    name = Path(filename).stem
    
    # Match FB_IMG_ followed by numbers, then optionally more content
    fb_match = re.match(r'^FB_IMG_\d+(.*)$', name, re.IGNORECASE)
    if fb_match:
        suffix = fb_match.group(1)
        # Clean up the suffix (remove leading hyphens/underscores)
        suffix = re.sub(r'^[-_]+', '', suffix)
        return (True, suffix)
    
    return (False, '')


def _count_gibberish_segments(name_parts: list, original_name: str) -> int:
    """
    Count how many segments look like random gibberish (base64, URL-encoded, etc.)
    
    Gibberish indicators:
    - Mixed case with numbers (WBCVJe8p9Yg2)
    - Very few vowels relative to consonants
    - Unusual letter-number-letter patterns
    - Random lowercase with interspersed numbers (uyvyw1)
    
    Valid patterns that are NOT gibberish:
    - Resolution patterns (4096x1024)
    - Year patterns (1970s, 2016)
    - Year + word (2016SFWCSchedule)
    - Word + number suffix (world1, version2) where word is valid English
    """
    gibberish_segments = 0
    
    for part in name_parts:
        if len(part) >= 5:
            # Skip parts that look like valid patterns
            # - Resolution patterns (NxN)
            if re.match(r'^\d+x\d+$', part):
                continue
            # - Year patterns (1970s, 80s)
            if re.match(r'^(19|20)?\d{2}s?$', part):
                continue
            # - Parts that start with a year then have words (2016sfwcschedule)
            if re.match(r'^(19|20)?\d{2,4}[a-z]{4,}', part):
                word_part = re.sub(r'^\d+', '', part)
                if len(word_part) >= 4:
                    continue  # Year + real word, not gibberish
            
            # - Word + number suffix (world1, version2, meme3)
            # If the letters form a real English word, it's not gibberish
            letters_only = re.sub(r'[^a-zA-Z]', '', part)
            if len(letters_only) >= 3 and is_english_word(letters_only):
                continue  # Real word with number suffix, not gibberish
            
            # Check for mixed alphanumeric that looks random
            has_letters = bool(re.search(r'[a-zA-Z]', part))
            has_numbers = bool(re.search(r'\d', part))
            
            # Check original case (before lowercasing) for mixed case detection
            orig_part = None
            for op in re.split(r'[-_\s]+', original_name):
                if op.lower() == part:
                    orig_part = op
                    break
            if orig_part is None:
                orig_part = part
            
            has_mixed_case = bool(re.search(r'[a-z]', orig_part) and re.search(r'[A-Z]', orig_part))
            has_letter_number_mix = bool(re.search(r'[a-zA-Z]\d|\d[a-zA-Z]', orig_part))
            
            # Calculate vowel ratio
            vowels = len(re.findall(r'[aeiouAEIOU]', orig_part))
            letters_only = re.sub(r'[^a-zA-Z]', '', orig_part)
            
            is_gibberish = False
            
            if has_letters and has_numbers:
                # Mixed case with letter-number mixing (WBCVJe8p9Yg2)
                if has_mixed_case and has_letter_number_mix:
                    is_gibberish = True
                # Mostly consonants with random numbers
                elif len(letters_only) >= 4 and vowels == 0:
                    is_gibberish = True
                # Unusual vowel ratio (normal English ~40% vowels)
                elif len(letters_only) >= 5 and vowels / len(letters_only) < 0.15:
                    is_gibberish = True
                # Letter-number mixing with low vowel ratio (uyvyw1, 5augd8h)
                elif has_letter_number_mix and len(letters_only) >= 4 and vowels / len(letters_only) < 0.25:
                    is_gibberish = True
                # Digits embedded within letters (letter-digit-letter pattern like "a1b", "5augd8h")
                # This is very unusual in real words - usually digits are at start/end
                elif re.search(r'[a-zA-Z]\d+[a-zA-Z]', orig_part):
                    is_gibberish = True
            
            # Pure letter gibberish (no numbers) - very low vowel ratio
            if not has_numbers and len(letters_only) >= 5:
                if vowels / len(letters_only) < 0.1:
                    is_gibberish = True
            
            if is_gibberish:
                gibberish_segments += 1
    
    return gibberish_segments


def is_non_descriptive_filename(filename: str) -> bool:
    """
    Check if a filename is non-descriptive (random, auto-generated, etc.)
    
    Improved logic:
    - FB_IMG files with only numbers are non-descriptive
    - FB_IMG files with text suffix are non-descriptive (but suffix is preserved)
    - Files with 3+ word-like segments (3+ chars each) are considered descriptive
    - Files with 2+ meaningful segments are usually descriptive
    - Recognizes resolution patterns (4096x1024), year patterns (1970s, 2016), dates
    - Checks against common non-descriptive patterns
    """
    # Remove extension and clean up
    name = Path(filename).stem.lower().strip()
    original_name = Path(filename).stem  # Keep original case for FB_IMG check
    
    # Special handling for FB_IMG files
    is_fb_img, suffix = extract_fb_img_suffix(original_name)
    if is_fb_img:
        # FB_IMG with only numbers = non-descriptive
        # FB_IMG with text suffix = still non-descriptive (we'll preserve the suffix when renaming)
        return True
    
    # Split into word-like segments FIRST - check for descriptive names before pattern matching
    name_parts = re.split(r'[-_\s]+', name)
    
    # Filter to meaningful parts (3+ alpha chars, not pure numbers)
    meaningful_parts = [
        part for part in name_parts 
        if len(part) >= 3 and re.search(r'[a-zA-Z]{2,}', part)
    ]
    
    # Also count short meaningful words (2-char words that are real words)
    short_meaningful_words = {'ad', 'tv', 'uk', 'us', 'pc', 'ai', 'vs', 'dj', 'cd', 'hi', 'no', 'ok', 'up'}
    for part in name_parts:
        if part.lower() in short_meaningful_words:
            meaningful_parts.append(part)
    
    # EARLY CHECK: Look for gibberish patterns BEFORE other checks
    # This prevents random strings like "3ULlgPB5MU-WBCVJe8p9Yg2" from being considered descriptive
    gibberish_segments = _count_gibberish_segments(name_parts, original_name)
    
    # Count how many parts have real English words, abbreviations, or ordinals
    real_word_parts = 0
    for part in name_parts:
        part_lower = part.lower()
        if is_ordinal_number(part_lower):
            real_word_parts += 1
        elif part_lower in COMMON_ABBREVIATIONS:
            real_word_parts += 1
        else:
            clean = re.sub(r'\d+', '', part_lower)
            if len(clean) >= 3 and is_english_word(clean):
                real_word_parts += 1
    
    # If ALL long parts are gibberish AND no real words found, definitely non-descriptive
    long_parts = len([p for p in name_parts if len(p) >= 5])
    if gibberish_segments > 0 and gibberish_segments >= long_parts and real_word_parts == 0:
        return True
    
    # If we have 3+ meaningful word-like segments AND not too much gibberish, consider it descriptive
    # This catches things like "you-had-me-at-fuck-the-system-anarchy-love"
    if len(meaningful_parts) >= 3 and gibberish_segments < 2:
        return False
    
    # If we have 2+ real words (dictionary/abbreviation/ordinal), it's descriptive
    if real_word_parts >= 2:
        return False
    
    # If we have 2+ meaningful segments AND no gibberish, check if they're real words (not codes)
    if len(meaningful_parts) >= 2 and gibberish_segments == 0:
        # Check if at least one is a real English word, ordinal, or abbreviation
        real_word_count = 0
        for part in meaningful_parts:
            part_lower = part.lower()
            # Check ordinals first (1st, 2nd, 3rd, etc.) - BEFORE stripping digits
            if is_ordinal_number(part_lower):
                real_word_count += 1
                continue
            # Check if the part itself (with numbers) is an abbreviation
            if part_lower in COMMON_ABBREVIATIONS:
                real_word_count += 1
                continue
            # Now strip numbers and check the remaining text
            clean_part = re.sub(r'\d+', '', part_lower)
            if len(clean_part) >= 3:
                # Use dictionary check if available
                if is_english_word(clean_part):
                    real_word_count += 1
                # Also check vowel ratio as fallback (real words have ~30-50% vowels)
                elif len(clean_part) >= 4:
                    vowels = len(re.findall(r'[aeiou]', clean_part))
                    vowel_ratio = vowels / len(clean_part) if clean_part else 0
                    if vowel_ratio >= 0.25:  # Slightly higher threshold without dictionary
                        real_word_count += 1
        if real_word_count >= 1:
            return False
    
    # Check if it contains any meaningful English words, ordinals, or abbreviations
    for part in name_parts:
        part_lower = part.lower()
        # Check ordinals first
        if is_ordinal_number(part_lower):
            return False
        # Check abbreviations
        if part_lower in COMMON_ABBREVIATIONS:
            return False
        if len(part) >= 3:
            # Remove numbers to get the word part
            clean_part = re.sub(r'\d+', '', part_lower)
            if len(clean_part) >= 3 and is_english_word(clean_part):
                return False  # Has a meaningful word
    
    # Check for common metadata patterns that indicate a real filename
    # Resolution patterns like 4096x1024, 1920x1080
    if re.search(r'\d{3,4}x\d{3,4}', name):
        # Has resolution - check if there's also a descriptive word
        for part in name_parts:
            clean_part = re.sub(r'[\dx]+', '', part)  # Remove numbers and x
            if len(clean_part) >= 3:
                return False  # Has resolution AND a word
    
    # Year patterns like 1970s, 2016, 80s - if combined with other words, likely descriptive
    has_year_pattern = bool(re.search(r'(^|[_-])(\d{2,4}s?|19\d{2}|20\d{2})([_-]|$)', name))
    if has_year_pattern:
        # Check if there's a meaningful word alongside the year
        for part in name_parts:
            clean_part = re.sub(r'\d+s?', '', part)  # Remove year-like patterns
            if len(clean_part) >= 3 and re.search(r'[a-z]{3,}', clean_part):
                return False  # Has year AND a real word
    
    # NOW check against non-descriptive patterns (after ruling out descriptive names)
    for pattern in NON_DESCRIPTIVE_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return True
    
    # If most segments look like gibberish, it's non-descriptive
    # (gibberish_segments was already calculated at the start)
    if gibberish_segments > 0 and gibberish_segments >= len(meaningful_parts):
        return True
    
    # Check if name is too short or mostly numbers
    alpha_chars = sum(1 for c in name if c.isalpha())
    if alpha_chars < 3:
        return True
    
    # If name is very short with no clear meaning
    if len(name) <= 4 and not any(ind in name.lower() for ind in MEANINGFUL_INDICATORS):
        return True
    
    return False


def encode_image_to_base64(image_path: str) -> str:
    """Convert image to base64 for API submission."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_image_mime_type(image_path: str) -> str:
    """Get the MIME type based on file extension."""
    ext = Path(image_path).suffix.lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
    }
    return mime_types.get(ext, 'image/jpeg')


def detect_image_format(file_path: str) -> str:
    """
    Detect image format by reading file header bytes.
    Returns the appropriate file extension (with dot) or empty string if unknown.
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(32)
        
        # Check magic bytes for common image formats
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return '.png'
        elif header[:3] == b'\xff\xd8\xff':
            return '.jpg'
        elif header[:6] in (b'GIF87a', b'GIF89a'):
            return '.gif'
        elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return '.webp'
        elif header[:2] == b'BM':
            return '.bmp'
        elif header[:4] in (b'II*\x00', b'MM\x00*'):  # TIFF
            return '.tiff'
        elif header[:4] == b'\x00\x00\x01\x00':  # ICO
            return '.ico'
        elif header[:5] == b'%PDF-':  # PDF
            return '.pdf'
        else:
            return ''
    except Exception:
        return ''


def has_image_extension(filename: str) -> bool:
    """Check if filename already ends with a supported image/PDF extension."""
    lower_name = filename.lower()
    return any(lower_name.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def strip_duplicate_extension(filename: str) -> str:
    """
    Remove duplicate extensions like .jpg.jpg or .png.png.
    Returns the corrected filename.
    """
    for ext in SUPPORTED_EXTENSIONS:
        doubled = ext + ext  # e.g., '.jpg.jpg'
        if filename.lower().endswith(doubled):
            # Remove the duplicate extension
            return filename[:-len(ext)]
    return filename


def get_file_extension(file_path: Path, add_missing_extension: bool = True) -> str:
    """
    Get the file extension, detecting from content if missing.
    
    Args:
        file_path: Path to the file
        add_missing_extension: If True, detect extension from file content when missing
    
    Returns:
        File extension with dot (e.g., '.jpg')
    """
    ext = file_path.suffix.lower()
    
    # If file has a valid image extension, use it
    if ext in SUPPORTED_EXTENSIONS:
        return ext
    
    # If no extension or unknown extension, try to detect from content
    if add_missing_extension:
        detected = detect_image_format(str(file_path))
        if detected:
            return detected
    
    # Fallback to original extension or .jpg
    return ext if ext else '.jpg'


def analyze_image_with_vision(client, image_path: str, provider: str = 'openai') -> str:
    """
    Use AI vision model to analyze the image and generate a descriptive name.
    
    Args:
        client: AI client instance (OpenAI, Anthropic, or Gemini)
        image_path: Path to the image file
        provider: Which AI provider to use ('openai', 'claude', 'gemini')
    """
    if provider == 'openai':
        return _analyze_with_openai(client, image_path)
    elif provider == 'claude':
        return _analyze_with_claude(client, image_path)
    elif provider == 'gemini':
        return _analyze_with_gemini(client, image_path)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _get_analysis_prompt() -> str:
    """Return the common prompt used for all providers."""
    return """Analyze this image and provide a short, descriptive filename (without extension).

Rules:
1. Be concise: 2-5 words maximum
2. Use lowercase with underscores between words
3. Include any visible text/logos if prominent
4. Describe the main subject or content
5. No special characters except underscores
6. No file extension in your response

Examples of good responses:
- golden_retriever_playing_fetch
- company_logo_blue
- sunset_over_mountains
- receipt_walmart_dec2024
- hand_drawn_cat_sketch

Just respond with the filename, nothing else."""


def _analyze_with_openai(client, image_path: str) -> str:
    """Analyze image using OpenAI GPT-4o."""
    base64_image = encode_image_to_base64(image_path)
    mime_type = get_image_mime_type(image_path)
    
    # Check if it's a PDF (OpenAI doesn't support PDFs)
    if mime_type == 'application/pdf':
        raise ValueError("OpenAI does not support PDF analysis. Use --provider claude or --provider gemini")
    
    response = client.chat.completions.create(
        model="gpt-4o",  # or "gpt-4o-mini" for lower cost
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": _get_analysis_prompt()
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                            "detail": "low"  # Use "high" for more detail but higher cost
                        }
                    }
                ]
            }
        ],
        max_tokens=50
    )
    
    suggested_name = response.choices[0].message.content.strip()
    return _clean_suggested_name(suggested_name)


def _analyze_with_claude(client, image_path: str) -> str:
    """Analyze image using Anthropic Claude."""
    base64_image = encode_image_to_base64(image_path)
    mime_type = get_image_mime_type(image_path)
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",  # Best balance of speed/quality for vision
        max_tokens=50,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64_image
                        }
                    },
                    {
                        "type": "text",
                        "text": _get_analysis_prompt()
                    }
                ]
            }
        ]
    )
    
    suggested_name = response.content[0].text.strip()
    return _clean_suggested_name(suggested_name)


def _analyze_with_gemini(client, image_path: str) -> str:
    """Analyze image using Google Gemini."""
    import google.generativeai as genai
    
    mime_type = get_image_mime_type(image_path)
    
    # Read the file directly for Gemini
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Use the client (which is actually the model for Gemini)
    response = client.generate_content([
        _get_analysis_prompt(),
        {"mime_type": mime_type, "data": image_data}
    ])
    
    suggested_name = response.text.strip()
    return _clean_suggested_name(suggested_name)


def _clean_suggested_name(suggested_name: str) -> str:
    """Clean up the AI-suggested filename."""
    # Clean up the suggested name
    suggested_name = re.sub(r'[^\w\s-]', '', suggested_name)
    suggested_name = re.sub(r'[-\s]+', '_', suggested_name)
    suggested_name = suggested_name.lower().strip('_')
    
    return suggested_name[:MAX_FILENAME_LENGTH]


def sanitize_filename(name: str) -> str:
    """
    Ensure the filename is valid for the filesystem.
    Also strips any file extension that might have been included (we add it separately).
    """
    # Remove or replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_.')
    
    # Strip any file extension the AI might have included
    # This prevents doubled extensions like .jpg.jpg
    for ext in SUPPORTED_EXTENSIONS:
        if name.lower().endswith(ext):
            name = name[:-len(ext)].rstrip('_.')
            break
    
    return name[:MAX_FILENAME_LENGTH]


def get_unique_filename(directory: Path, base_name: str, extension: str) -> str:
    """Generate a unique filename if one already exists. Uses _v2, _v3, etc. for collisions."""
    new_name = f"{base_name}{extension}"
    new_path = directory / new_name
    
    counter = 2  # Start at 2 for _v2, _v3, etc.
    while new_path.exists():
        new_name = f"{base_name}_v{counter}{extension}"
        new_path = directory / new_name
        counter += 1
    
    return new_name


def test_openai_connection(api_key: str = None):
    """
    Test connection to OpenAI and measure latency.
    Makes a simple API call to measure response time.
    """
    test_connection(provider='openai', api_key=api_key)


def test_connection(provider: str = 'openai', api_key: str = None):
    """
    Test connection to AI provider and measure latency.
    Makes a simple API call to measure response time.
    
    Args:
        provider: Which AI provider to test ('openai', 'claude', 'gemini')
        api_key: API key for the provider
    """
    import time
    
    if not DEPENDENCIES_AVAILABLE:
        print_dependency_error()
        return
    
    provider_info = AI_PROVIDERS.get(provider)
    if not provider_info:
        print(f"❌ Unknown provider: {provider}")
        print(f"   Available providers: {', '.join(AI_PROVIDERS.keys())}")
        return
    
    if not provider_info['available']:
        pkg_name = {'openai': 'openai', 'claude': 'anthropic', 'gemini': 'google-generativeai'}[provider]
        print(f"❌ Provider '{provider}' not available. Install with:")
        print(f"   pip install {pkg_name}")
        return
    
    print(f"\n🔌 Testing {provider.upper()} Connection...")
    print("=" * 60)
    
    try:
        client = _create_client(provider, api_key)
        
        if provider == 'openai':
            _test_openai(client)
        elif provider == 'claude':
            _test_claude(client)
        elif provider == 'gemini':
            _test_gemini(client)
            
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        env_key = provider_info['env_key']
        if "api_key" in str(e).lower() or "auth" in str(e).lower() or "key" in str(e).lower():
            print(f"   Check your {env_key} environment variable or use --api-key")


def _create_client(provider: str, api_key: str = None):
    """Create and return the appropriate client for the provider."""
    if provider == 'openai':
        if api_key:
            return OpenAI(api_key=api_key)
        return OpenAI()
    
    elif provider == 'claude':
        if api_key:
            return anthropic.Anthropic(api_key=api_key)
        return anthropic.Anthropic()
    
    elif provider == 'gemini':
        key = api_key or os.environ.get('GOOGLE_API_KEY')
        if not key:
            raise ValueError("No GOOGLE_API_KEY found. Set it as environment variable or use --api-key")
        genai.configure(api_key=key)
        return genai.GenerativeModel('gemini-1.5-flash')
    
    raise ValueError(f"Unknown provider: {provider}")


def _test_openai(client):
    """Test OpenAI connection."""
    import time
    
    # Test 1: Simple text completion (fast)
    print("\n1️⃣  Testing basic API connection...")
    start = time.time()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'ok'"}],
        max_tokens=5
    )
    text_latency = time.time() - start
    print(f"   ✅ Text API: {text_latency:.2f}s")
    
    # Test 2: Vision API with tiny image (more realistic)
    print("\n2️⃣  Testing Vision API (simulates image analysis)...")
    # Create a tiny 1x1 pixel PNG as base64
    tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    start = time.time()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "What color is this? One word."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{tiny_png}", "detail": "low"}}
            ]
        }],
        max_tokens=10
    )
    vision_latency = time.time() - start
    print(f"   ✅ Vision API: {vision_latency:.2f}s")
    
    _print_test_results(text_latency, vision_latency, supports_pdf=False)


def _test_claude(client):
    """Test Claude connection."""
    import time
    
    # Test 1: Simple text completion
    print("\n1️⃣  Testing basic API connection...")
    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=5,
        messages=[{"role": "user", "content": "Say 'ok'"}]
    )
    text_latency = time.time() - start
    print(f"   ✅ Text API: {text_latency:.2f}s")
    
    # Test 2: Vision API with tiny image
    print("\n2️⃣  Testing Vision API (simulates image analysis)...")
    tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": tiny_png}},
                {"type": "text", "text": "What color is this? One word."}
            ]
        }]
    )
    vision_latency = time.time() - start
    print(f"   ✅ Vision API: {vision_latency:.2f}s")
    
    _print_test_results(text_latency, vision_latency, supports_pdf=True)


def _test_gemini(client):
    """Test Gemini connection."""
    import time
    
    # Test 1: Simple text completion
    print("\n1️⃣  Testing basic API connection...")
    start = time.time()
    response = client.generate_content("Say 'ok'")
    text_latency = time.time() - start
    print(f"   ✅ Text API: {text_latency:.2f}s")
    
    # Test 2: Vision API with tiny image
    print("\n2️⃣  Testing Vision API (simulates image analysis)...")
    tiny_png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    
    start = time.time()
    response = client.generate_content([
        "What color is this? One word.",
        {"mime_type": "image/png", "data": tiny_png_bytes}
    ])
    vision_latency = time.time() - start
    print(f"   ✅ Vision API: {vision_latency:.2f}s")
    
    _print_test_results(text_latency, vision_latency, supports_pdf=True)


def _print_test_results(text_latency: float, vision_latency: float, supports_pdf: bool):
    """Print test results summary."""
    print("\n" + "=" * 60)
    print("📊 RESULTS")
    print("=" * 60)
    print(f"Text API latency:   {text_latency:.2f}s")
    print(f"Vision API latency: {vision_latency:.2f}s")
    print(f"PDF support:        {'✅ Yes' if supports_pdf else '❌ No'}")
    print(f"\n⏱️  Estimated time per image: {vision_latency:.1f}-{vision_latency + 1:.1f}s")
    print(f"   For 100 images: ~{int(vision_latency * 100 / 60)}-{int((vision_latency + 1) * 100 / 60)} minutes")
    print(f"   For 1000 images: ~{int(vision_latency * 1000 / 60)}-{int((vision_latency + 1) * 1000 / 60)} minutes")
    print("\n✅ Connection test successful!")


def fix_extensions_only(directory: str, dry_run: bool = True):
    """
    Fix file extension issues in a directory:
    1. Add missing extensions to image/PDF files (detected from content)
    2. Remove doubled extensions like .jpg.jpg or .png.png
    
    This does NOT use AI - it just detects format from file contents.
    
    Args:
        directory: Path to the directory containing files
        dry_run: If True, only show what would be changed without actually renaming
    """
    directory_path = Path(directory)
    if not directory_path.exists():
        print(f"Error: Directory '{directory}' does not exist.")
        return
    
    if not directory_path.is_dir():
        print(f"Error: '{directory}' is not a directory.")
        return
    
    print(f"\n🔧 {'[DRY RUN] ' if dry_run else ''}Fixing file extensions...")
    print("=" * 60)
    
    files_fixed = 0
    doubled_fixed = 0
    files_skipped = 0
    
    for f in sorted(directory_path.iterdir()):
        if not f.is_file():
            continue
            
        # Check for doubled extensions first (e.g., .jpg.jpg)
        corrected_name = strip_duplicate_extension(f.name)
        if corrected_name != f.name:
            new_path = f.parent / corrected_name
            
            # Check for collision
            if new_path.exists():
                base, ext = os.path.splitext(corrected_name)
                corrected_name = get_unique_filename(f.parent, base, ext)
                new_path = f.parent / corrected_name
            
            if dry_run:
                print(f"🔄 {f.name} → {corrected_name} (removed duplicate extension)")
            else:
                f.rename(new_path)
                print(f"✅ {f.name} → {corrected_name} (removed duplicate extension)")
            doubled_fixed += 1
            continue
        
        # Check for missing extensions
        if not f.suffix:
            detected_ext = detect_image_format(str(f))
            if detected_ext:
                new_name = f.name + detected_ext
                new_path = f.parent / new_name
                
                # Check for collision
                if new_path.exists():
                    new_name = get_unique_filename(f.parent, f.name, detected_ext)
                    new_path = f.parent / new_name
                
                if dry_run:
                    print(f"📁 {f.name} → {new_name}")
                else:
                    f.rename(new_path)
                    print(f"✅ {f.name} → {new_name}")
                files_fixed += 1
            else:
                files_skipped += 1
    
    print("=" * 60)
    total_fixed = files_fixed + doubled_fixed
    if dry_run:
        print(f"Would fix: {total_fixed} files")
        if files_fixed:
            print(f"  - Missing extensions: {files_fixed}")
        if doubled_fixed:
            print(f"  - Doubled extensions: {doubled_fixed}")
    else:
        print(f"Fixed: {total_fixed} files")
        if files_fixed:
            print(f"  - Missing extensions: {files_fixed}")
        if doubled_fixed:
            print(f"  - Doubled extensions: {doubled_fixed}")
    
    if files_skipped:
        print(f"Skipped (not images/PDFs): {files_skipped} files")
    
    if dry_run and total_fixed > 0:
        print(f"\nTo apply changes, run with --execute")


def count_only_scan(directory: str, add_missing_extensions: bool = True):
    """
    Quick scan to count how many files would be processed, without making any API calls.
    
    Args:
        directory: Path to the directory containing images
        add_missing_extensions: If True, include files without extensions in the count
    """
    directory_path = Path(directory)
    if not directory_path.exists():
        print(f"Error: Directory '{directory}' does not exist.")
        return
    
    if not directory_path.is_dir():
        print(f"Error: '{directory}' is not a directory.")
        return
    
    # Find all image files
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(directory_path.glob(f'*{ext}'))
        image_files.extend(directory_path.glob(f'*{ext.upper()}'))
    
    if add_missing_extensions:
        for f in directory_path.iterdir():
            if f.is_file() and not f.suffix:
                if detect_image_format(str(f)):
                    image_files.append(f)
    
    image_files = list(set(image_files))
    
    print(f"\n📊 SCAN RESULTS (no API calls made)")
    print("=" * 60)
    print(f"Total images found: {len(image_files)}")
    print("-" * 60)
    
    non_descriptive_files = []
    descriptive_count = 0
    fb_img_count = 0
    
    for image_path in sorted(image_files):
        filename = image_path.name
        is_fb_img, suffix = extract_fb_img_suffix(filename)
        
        if is_non_descriptive_filename(filename):
            non_descriptive_files.append(filename)
            if is_fb_img:
                fb_img_count += 1
        else:
            descriptive_count += 1
    
    print(f"✓ Already descriptive: {descriptive_count}")
    print(f"📷 Non-descriptive (will be renamed): {len(non_descriptive_files)}")
    if fb_img_count > 0:
        print(f"   └─ FB_IMG files: {fb_img_count}")
    
    print("\n" + "=" * 60)
    
    if len(non_descriptive_files) > 0:
        print(f"\n📝 Sample of files that would be renamed (first 20):")
        print("-" * 60)
        for filename in non_descriptive_files[:20]:
            is_fb_img, suffix = extract_fb_img_suffix(filename)
            if is_fb_img and suffix:
                print(f"  • {filename}  [FB_IMG, will preserve: '{suffix}']")
            elif is_fb_img:
                print(f"  • {filename}  [FB_IMG]")
            else:
                print(f"  • {filename}")
        
        if len(non_descriptive_files) > 20:
            print(f"  ... and {len(non_descriptive_files) - 20} more")
    
    print("\n" + "=" * 60)
    print("To proceed with renaming, run without --count-only")
    print("  Dry run:  python image_renamer.py <directory>")
    print("  Execute:  python image_renamer.py <directory> --execute")
    
    return len(non_descriptive_files)


def process_directory(directory: str, dry_run: bool = True, api_key: str = None, add_missing_extensions: bool = True, limit: int = None, provider: str = 'openai'):
    """
    Process all images in the directory.
    
    Args:
        directory: Path to the directory containing images
        dry_run: If True, only show what would be renamed without actually renaming
        api_key: API key for the AI provider (or set environment variable)
        add_missing_extensions: If True, detect and add file extensions to files missing them
        limit: Maximum number of files to process (None = no limit)
        provider: Which AI provider to use ('openai', 'claude', 'gemini')
    """
    if not DEPENDENCIES_AVAILABLE:
        print_dependency_error()
        return
    
    # Validate provider
    provider_info = AI_PROVIDERS.get(provider)
    if not provider_info:
        print(f"❌ Unknown provider: {provider}")
        print(f"   Available providers: {', '.join(AI_PROVIDERS.keys())}")
        return
    
    if not provider_info['available']:
        pkg_name = {'openai': 'openai', 'claude': 'anthropic', 'gemini': 'google-generativeai'}[provider]
        print(f"❌ Provider '{provider}' not available. Install with:")
        print(f"   pip install {pkg_name}")
        return
    
    # Initialize AI client
    try:
        client = _create_client(provider, api_key)
    except Exception as e:
        print(f"❌ Failed to initialize {provider}: {str(e)}")
        return
    
    print(f"\n🤖 Using AI provider: {provider.upper()}")
    if provider_info['supports_pdf']:
        print("   ✅ PDF support enabled")
    else:
        print("   ⚠️  No PDF support (PDFs will be skipped)")
    
    directory_path = Path(directory)
    if not directory_path.exists():
        print(f"Error: Directory '{directory}' does not exist.")
        return
    
    if not directory_path.is_dir():
        print(f"Error: '{directory}' is not a directory.")
        return
    
    # Find all image files (including those without extensions)
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(directory_path.glob(f'*{ext}'))
        image_files.extend(directory_path.glob(f'*{ext.upper()}'))
    
    # Also check files without extensions
    if add_missing_extensions:
        for f in directory_path.iterdir():
            if f.is_file() and not f.suffix:
                if detect_image_format(str(f)):
                    image_files.append(f)
    
    image_files = list(set(image_files))  # Remove duplicates
    
    print(f"\nFound {len(image_files)} image(s) in '{directory}'")
    if limit:
        print(f"⚠️  Limit set: will process at most {limit} non-descriptive file(s)")
    print("-" * 60)
    
    non_descriptive_count = 0
    renamed_count = 0
    skipped_pdfs = 0
    errors = []
    
    for image_path in sorted(image_files):
        filename = image_path.name
        
        if is_non_descriptive_filename(filename):
            non_descriptive_count += 1
            
            # Check if we've hit the limit
            if limit and renamed_count >= limit:
                print(f"\n⚠️  Reached limit of {limit} files. Stopping.")
                break
            
            # Check if it's a PDF and provider doesn't support it
            is_pdf = image_path.suffix.lower() == '.pdf' or get_image_mime_type(str(image_path)) == 'application/pdf'
            if is_pdf and not provider_info['supports_pdf']:
                print(f"\n📄 Skipping PDF (use --provider claude or --provider gemini): {filename}")
                skipped_pdfs += 1
                continue
            
            print(f"\n📷 Non-descriptive: {filename}")
            
            try:
                # Check for FB_IMG suffix to preserve
                is_fb_img, fb_suffix = extract_fb_img_suffix(filename)
                
                # Analyze the image
                print("   🔍 Analyzing image...")
                suggested_name = analyze_image_with_vision(client, str(image_path), provider)
                suggested_name = sanitize_filename(suggested_name)
                
                if not suggested_name:
                    print("   ⚠️  Could not generate a descriptive name, skipping.")
                    continue
                
                # If FB_IMG had a text suffix, append it to the new name
                if is_fb_img and fb_suffix:
                    # Clean and append the suffix
                    clean_suffix = sanitize_filename(fb_suffix)
                    if clean_suffix:
                        suggested_name = f"{suggested_name}_{clean_suffix}"
                        print(f"   📎 Preserved FB_IMG suffix: {clean_suffix}")
                
                # Get extension (detect from content if missing)
                extension = get_file_extension(image_path, add_missing_extensions)
                had_extension = bool(image_path.suffix)
                
                new_filename = get_unique_filename(directory_path, suggested_name, extension)
                new_path = directory_path / new_filename
                
                if not had_extension and extension:
                    print(f"   📎 Detected format: {extension} (was missing extension)")
                print(f"   📝 Suggested name: {new_filename}")
                
                if not dry_run:
                    image_path.rename(new_path)
                    print(f"   ✅ Renamed to: {new_filename}")
                    renamed_count += 1
                else:
                    print(f"   🔄 Would rename to: {new_filename}")
                    
            except Exception as e:
                error_msg = f"Error processing {filename}: {str(e)}"
                errors.append(error_msg)
                print(f"   ❌ {error_msg}")
        else:
            print(f"✓ Descriptive: {filename}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"AI Provider: {provider.upper()}")
    print(f"Total images scanned: {len(image_files)}")
    print(f"Non-descriptive names found: {non_descriptive_count}")
    
    if skipped_pdfs > 0:
        print(f"PDFs skipped (no PDF support): {skipped_pdfs}")
        print(f"  💡 Use --provider claude or --provider gemini for PDF support")
    
    if dry_run:
        print(f"Would rename: {non_descriptive_count - skipped_pdfs} file(s)")
        print("\n⚠️  This was a DRY RUN. No files were actually renamed.")
        print("   Run with --execute to perform the actual renaming.")
    else:
        print(f"Successfully renamed: {renamed_count} file(s)")
    
    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for error in errors:
            print(f"  - {error}")


def run_duplicate_finder(args):
    """
    Run the duplicate finder with the provided arguments.
    
    Args:
        args: Parsed command-line arguments
    """
    try:
        from duplicate_finder import DuplicateFinder, export_duplicates_csv, print_duplicate_summary
    except ImportError as e:
        print(f"❌ Error: Missing dependencies for duplicate detection: {e}")
        print("\n   Install with: pip install imagehash send2trash")
        return
    
    # Only import GUI if needed
    if not args.no_gui:
        try:
            from duplicate_gui import DuplicateFinderGUI
        except ImportError as e:
            print(f"⚠️  Warning: GUI not available: {e}")
            print("   Falling back to console output mode")
            args.no_gui = True
    
    # Validate arguments
    if args.dir1 and args.dir2:
        # Two-directory mode
        dir1 = os.path.expanduser(args.dir1)
        dir2 = os.path.expanduser(args.dir2)
        
        if not os.path.exists(dir1):
            print(f"❌ Error: Directory '{dir1}' does not exist")
            return
        if not os.path.exists(dir2):
            print(f"❌ Error: Directory '{dir2}' does not exist")
            return
        
        print(f"\n🔍 Finding duplicates between two directories:")
        print(f"   Directory 1: {dir1}")
        print(f"   Directory 2: {dir2}")
    elif args.dir1:
        # Single directory mode (using --dir1)
        dir1 = os.path.expanduser(args.dir1)
        dir2 = None
        
        if not os.path.exists(dir1):
            print(f"❌ Error: Directory '{dir1}' does not exist")
            return
        
        print(f"\n🔍 Finding duplicates in directory: {dir1}")
    elif args.directory:
        # Single directory mode (using positional argument)
        dir1 = os.path.expanduser(args.directory)
        dir2 = None
        
        if not os.path.exists(dir1):
            print(f"❌ Error: Directory '{dir1}' does not exist")
            return
        
        print(f"\n🔍 Finding duplicates in directory: {dir1}")
    else:
        print("❌ Error: Please provide a directory to scan")
        print("   Use: --dir1 /path/to/dir (single directory)")
        print("   Or:  --dir1 /path/to/dir1 --dir2 /path/to/dir2 (two directories)")
        print("   Or:  /path/to/dir --find-duplicates (single directory)")
        return
    
    print(f"   Similarity threshold: {args.similarity_threshold}%")
    print(f"   Detection method: {args.method}")
    print("=" * 80)
    
    # Create duplicate finder
    finder = DuplicateFinder(similarity_threshold=args.similarity_threshold)
    
    # Map method argument to internal method
    method_map = {
        'exact': 'exact',
        'visual': 'visual',
        'similar': 'visual',  # Treat 'similar' as 'visual'
        'all': 'all'
    }
    method = method_map.get(args.method, 'all')
    
    # Find duplicates
    try:
        if dir2:
            duplicates = finder.find_duplicates_between_dirs(dir1, dir2, method=method)
        else:
            duplicates = finder.find_duplicates_in_dir(dir1, method=method)
    except Exception as e:
        print(f"\n❌ Error during duplicate detection: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Handle results
    if not duplicates:
        print("\n✅ No duplicates found!")
        return
    
    print(f"\n✅ Found {len(duplicates)} duplicate pair(s)")
    
    # Export to CSV if requested
    if args.output:
        try:
            export_duplicates_csv(duplicates, args.output)
        except Exception as e:
            print(f"❌ Error exporting to CSV: {e}")
    
    # Show GUI or print summary
    if args.no_gui:
        print_duplicate_summary(duplicates)
    else:
        print("\n🖼️  Launching GUI for review...")
        try:
            from duplicate_gui import DuplicateFinderGUI
            gui = DuplicateFinderGUI(duplicates)
            gui.run()
        except Exception as e:
            print(f"❌ Error launching GUI: {e}")
            print("\nFalling back to console output:")
            print_duplicate_summary(duplicates)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Rename images based on their content using AI vision analysis, or find duplicate images.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test connection to default provider (OpenAI)
  python image_renamer.py /path/to/images --test-connection

  # Test Claude connection
  python image_renamer.py /path/to/images --test-connection --provider claude

  # Quick count - see how many files match (no API calls)
  python image_renamer.py /path/to/images --count-only

  # Process only first 10 files (for testing)
  python image_renamer.py /path/to/images --limit 10 --execute

  # Dry run (see what would be renamed without changing anything)
  python image_renamer.py /path/to/images

  # Actually rename the files
  python image_renamer.py /path/to/images --execute

  # Use Claude for PDF support
  python image_renamer.py /path/to/images --provider claude --execute

  # Use Gemini for PDF support
  python image_renamer.py /path/to/images --provider gemini --execute

  # Use a specific API key
  python image_renamer.py /path/to/images --api-key sk-xxx... --execute

  # Find duplicates in a single directory (with GUI)
  python image_renamer.py /path/to/images --find-duplicates

  # Find duplicates between two directories
  python image_renamer.py --find-duplicates --dir1 /path/to/dir1 --dir2 /path/to/dir2

  # Find duplicates and export to CSV (no GUI)
  python image_renamer.py /path/to/images --find-duplicates --no-gui --output duplicates.csv

  # Adjust similarity threshold (default: 85)
  python image_renamer.py /path/to/images --find-duplicates --similarity-threshold 95

AI Providers:
  openai  - GPT-4o (default). Fast, good quality. NO PDF support.
  claude  - Claude Sonnet. Excellent quality. PDF support.
  gemini  - Gemini 1.5 Flash. Fast, free tier. PDF support.

Environment Variables:
  OPENAI_API_KEY    - For OpenAI/GPT-4o
  ANTHROPIC_API_KEY - For Claude
  GOOGLE_API_KEY    - For Gemini
        """
    )
    
    parser.add_argument(
        'directory',
        nargs='?',  # Make optional to support --dir1/--dir2 mode
        help='Directory containing images to process'
    )
    
    # Duplicate finder arguments
    parser.add_argument(
        '--find-duplicates',
        action='store_true',
        help='Enable duplicate detection mode'
    )
    
    parser.add_argument(
        '--dir1',
        help='First directory to scan (for duplicate detection)'
    )
    
    parser.add_argument(
        '--dir2',
        help='Second directory to compare against (optional, for two-directory mode)'
    )
    
    parser.add_argument(
        '--similarity-threshold',
        type=int,
        default=85,
        help='Threshold for considering images similar (0-100, default: 85)'
    )
    
    parser.add_argument(
        '--method',
        choices=['exact', 'similar', 'visual', 'all'],
        default='all',
        help='Detection method: exact (file hash), visual (perceptual hash), all (default: all)'
    )
    
    parser.add_argument(
        '--no-gui',
        action='store_true',
        help='Skip GUI and output results to console/CSV'
    )
    
    parser.add_argument(
        '--output',
        help='Save duplicate report to CSV file'
    )
    
    # Existing arguments
    
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually rename files (default is dry-run mode)'
    )
    
    parser.add_argument(
        '--provider',
        choices=['openai', 'claude', 'gemini'],
        default='openai',
        help='AI provider to use (default: openai). Use claude or gemini for PDF support.'
    )
    
    parser.add_argument(
        '--api-key',
        help='API key for the selected provider (or set environment variable)'
    )
    
    parser.add_argument(
        '--no-add-extension',
        action='store_true',
        help='Do not add file extensions to files missing them (by default, extensions are detected and added)'
    )
    
    parser.add_argument(
        '--fix-extensions',
        action='store_true',
        help='Only add missing file extensions (no AI renaming). Does not require API key.'
    )
    
    parser.add_argument(
        '--count-only',
        action='store_true',
        help='Only count how many files would be renamed, without making any API calls'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit the number of files to process (useful for testing)'
    )
    
    parser.add_argument(
        '--test-connection',
        action='store_true',
        help='Test API connection and measure latency for the selected provider'
    )
    
    args = parser.parse_args()
    
    # Handle duplicate finding mode
    if args.find_duplicates:
        return run_duplicate_finder(args)
    
    # Expand user home directory if needed
    directory = os.path.expanduser(args.directory) if args.directory else None
    
    if not directory:
        parser.error("directory is required when not using --find-duplicates with --dir1/--dir2")
    
    # If fix-extensions mode, just add extensions and exit (no API needed)
    if args.fix_extensions:
        fix_extensions_only(directory=directory, dry_run=not args.execute)
        return
    
    # If test-connection mode, test and exit
    if args.test_connection:
        test_connection(provider=args.provider, api_key=args.api_key)
        return
    
    # If count-only mode, just scan and report
    if args.count_only:
        count_only_scan(
            directory=directory,
            add_missing_extensions=not args.no_add_extension
        )
        return
    
    process_directory(
        directory=directory,
        dry_run=not args.execute,
        api_key=args.api_key,
        add_missing_extensions=not args.no_add_extension,
        limit=args.limit,
        provider=args.provider
    )


if __name__ == '__main__':
    main()
