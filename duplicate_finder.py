#!/usr/bin/env python3
"""
Duplicate Image Finder Module
Detects duplicate and similar images using multiple methods:
- Exact duplicates (file hash)
- Visual similarity (perceptual hashing)
- Filename similarity (Levenshtein distance)
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False


# Supported image extensions
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'}


@dataclass
class FileInfo:
    """Information about a single file."""
    path: str
    filename: str
    size: int
    hash: Optional[str] = None
    perceptual_hash: Optional[str] = None
    dimensions: Optional[Tuple[int, int]] = None
    thumbnail: Optional[object] = None  # PIL.Image object
    

@dataclass
class DuplicatePair:
    """Represents a pair of duplicate/similar files."""
    file1: FileInfo
    file2: FileInfo
    similarity_score: float  # 0-100
    match_type: str  # 'exact', 'similar_name', 'visual'
    hash_difference: int = 0


class DuplicateFinder:
    """Main class for finding duplicate images."""
    
    def __init__(self, similarity_threshold: int = 85):
        """
        Initialize the duplicate finder.
        
        Args:
            similarity_threshold: Threshold for considering images similar (0-100)
        """
        if not PILLOW_AVAILABLE:
            raise ImportError("PIL/Pillow is required for duplicate detection")
        
        if not IMAGEHASH_AVAILABLE:
            raise ImportError("imagehash is required for duplicate detection. Install with: pip install imagehash")
        
        self.similarity_threshold = similarity_threshold
        self.cache: Dict[str, FileInfo] = {}
        
    def calculate_file_hash(self, file_path: str, algorithm: str = 'md5') -> str:
        """
        Calculate file content hash.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm ('md5' or 'sha256')
            
        Returns:
            Hexadecimal hash string
        """
        hash_func = hashlib.md5() if algorithm == 'md5' else hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    def calculate_perceptual_hash(self, image_path: str, method: str = 'average') -> str:
        """
        Calculate perceptual hash of an image.
        
        Args:
            image_path: Path to the image
            method: Hashing method ('average', 'perceptual', 'difference', 'wavelet')
            
        Returns:
            Hexadecimal hash string
        """
        try:
            img = Image.open(image_path)
            
            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Calculate hash based on method
            if method == 'average':
                hash_obj = imagehash.average_hash(img)
            elif method == 'perceptual':
                hash_obj = imagehash.phash(img)
            elif method == 'difference':
                hash_obj = imagehash.dhash(img)
            elif method == 'wavelet':
                hash_obj = imagehash.whash(img)
            else:
                hash_obj = imagehash.average_hash(img)
            
            return str(hash_obj)
        except Exception as e:
            print(f"Error calculating perceptual hash for {image_path}: {e}")
            return None
    
    def generate_thumbnail(self, image_path: str, size: Tuple[int, int] = (200, 200)) -> Optional[object]:
        """
        Generate a thumbnail for display.
        
        Args:
            image_path: Path to the image
            size: Thumbnail size (width, height)
            
        Returns:
            PIL Image object or None
        """
        try:
            img = Image.open(image_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            print(f"Error generating thumbnail for {image_path}: {e}")
            return None
    
    def get_image_dimensions(self, image_path: str) -> Optional[Tuple[int, int]]:
        """
        Get image dimensions without loading the full image.
        
        Args:
            image_path: Path to the image
            
        Returns:
            Tuple of (width, height) or None
        """
        try:
            with Image.open(image_path) as img:
                return img.size
        except Exception as e:
            print(f"Error getting dimensions for {image_path}: {e}")
            return None
    
    def scan_file(self, file_path: str, generate_thumbnail: bool = False) -> Optional[FileInfo]:
        """
        Scan a single file and gather its information.
        
        Args:
            file_path: Path to the file
            generate_thumbnail: Whether to generate a thumbnail
            
        Returns:
            FileInfo object or None if file cannot be processed
        """
        path = Path(file_path)
        
        # Check if file exists and has supported extension
        if not path.exists() or not path.is_file():
            return None
        
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            return None
        
        # Check cache
        if file_path in self.cache:
            return self.cache[file_path]
        
        try:
            # Get basic file info
            file_info = FileInfo(
                path=str(path.absolute()),
                filename=path.name,
                size=path.stat().st_size,
                dimensions=self.get_image_dimensions(file_path)
            )
            
            # Calculate hashes
            file_info.hash = self.calculate_file_hash(file_path)
            file_info.perceptual_hash = self.calculate_perceptual_hash(file_path, method='average')
            
            # Generate thumbnail if requested
            if generate_thumbnail:
                file_info.thumbnail = self.generate_thumbnail(file_path)
            
            # Cache the result
            self.cache[file_path] = file_info
            
            return file_info
        except Exception as e:
            print(f"Error scanning file {file_path}: {e}")
            return None
    
    def calculate_hash_similarity(self, hash1: str, hash2: str) -> int:
        """
        Calculate similarity between two perceptual hashes.
        
        Args:
            hash1: First hash string
            hash2: Second hash string
            
        Returns:
            Hamming distance (number of differing bits)
        """
        if not hash1 or not hash2:
            return 100  # Maximum difference
        
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            return h1 - h2  # Hamming distance
        except Exception:
            return 100
    
    def compare_images(self, file1: FileInfo, file2: FileInfo, method: str = 'all') -> Optional[DuplicatePair]:
        """
        Compare two images and determine if they are duplicates.
        
        Args:
            file1: First file info
            file2: Second file info
            method: Comparison method ('exact', 'visual', 'all')
            
        Returns:
            DuplicatePair if files are similar enough, None otherwise
        """
        # Exact duplicate check
        if method in ('exact', 'all'):
            if file1.size == file2.size and file1.hash == file2.hash:
                return DuplicatePair(
                    file1=file1,
                    file2=file2,
                    similarity_score=100.0,
                    match_type='exact',
                    hash_difference=0
                )
        
        # Visual similarity check
        if method in ('visual', 'all'):
            if file1.perceptual_hash and file2.perceptual_hash:
                hash_diff = self.calculate_hash_similarity(
                    file1.perceptual_hash, 
                    file2.perceptual_hash
                )
                
                # Calculate similarity score (0-100)
                # Hash difference of 0 = 100% similar
                # Hash difference of 10 = ~50% similar (for 64-bit hash)
                # We'll use a threshold-based approach
                if hash_diff == 0:
                    similarity_score = 100.0
                elif hash_diff <= 5:
                    similarity_score = 95.0 - (hash_diff * 2)
                elif hash_diff <= 10:
                    similarity_score = 85.0 - ((hash_diff - 5) * 3)
                else:
                    similarity_score = max(0, 70.0 - ((hash_diff - 10) * 5))
                
                # Check if similarity meets threshold
                if similarity_score >= self.similarity_threshold:
                    return DuplicatePair(
                        file1=file1,
                        file2=file2,
                        similarity_score=similarity_score,
                        match_type='visual',
                        hash_difference=hash_diff
                    )
        
        return None
    
    def calculate_levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance
        """
        if len(s1) < len(s2):
            return self.calculate_levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def find_duplicates_between_dirs(
        self, 
        dir1: str, 
        dir2: str, 
        method: str = 'all',
        progress_callback: Optional[callable] = None
    ) -> List[DuplicatePair]:
        """
        Find duplicates between two directories.
        
        Args:
            dir1: First directory path
            dir2: Second directory path
            method: Detection method ('exact', 'visual', 'all')
            progress_callback: Optional callback function for progress updates
            
        Returns:
            List of duplicate pairs
        """
        duplicates = []
        
        # Scan both directories
        files1 = []
        files2 = []
        
        dir1_path = Path(dir1)
        dir2_path = Path(dir2)
        
        if not dir1_path.exists() or not dir2_path.exists():
            print(f"Error: One or both directories do not exist")
            return duplicates
        
        # Scan directory 1
        print(f"Scanning directory 1: {dir1}")
        for file_path in dir1_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                file_info = self.scan_file(str(file_path))
                if file_info:
                    files1.append(file_info)
                    if progress_callback:
                        progress_callback(f"Scanning {file_path.name}...")
        
        # Scan directory 2
        print(f"Scanning directory 2: {dir2}")
        for file_path in dir2_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                file_info = self.scan_file(str(file_path))
                if file_info:
                    files2.append(file_info)
                    if progress_callback:
                        progress_callback(f"Scanning {file_path.name}...")
        
        print(f"Found {len(files1)} files in directory 1 and {len(files2)} files in directory 2")
        
        # Compare files from dir1 with files from dir2
        total_comparisons = len(files1) * len(files2)
        comparison_count = 0
        
        for file1 in files1:
            for file2 in files2:
                comparison_count += 1
                if progress_callback:
                    progress_callback(f"Comparing: {comparison_count}/{total_comparisons}")
                
                duplicate = self.compare_images(file1, file2, method)
                if duplicate:
                    duplicates.append(duplicate)
        
        print(f"Found {len(duplicates)} duplicate pairs")
        return duplicates
    
    def find_duplicates_in_dir(
        self, 
        directory: str, 
        method: str = 'all',
        progress_callback: Optional[callable] = None
    ) -> List[DuplicatePair]:
        """
        Find duplicates within a single directory.
        
        Args:
            directory: Directory path to scan
            method: Detection method ('exact', 'visual', 'all')
            progress_callback: Optional callback function for progress updates
            
        Returns:
            List of duplicate pairs
        """
        duplicates = []
        files = []
        
        dir_path = Path(directory)
        
        if not dir_path.exists():
            print(f"Error: Directory {directory} does not exist")
            return duplicates
        
        # Scan directory
        print(f"Scanning directory: {directory}")
        for file_path in dir_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                file_info = self.scan_file(str(file_path))
                if file_info:
                    files.append(file_info)
                    if progress_callback:
                        progress_callback(f"Scanning {file_path.name}...")
        
        print(f"Found {len(files)} files")
        
        # Compare all pairs (avoiding duplicate comparisons)
        total_comparisons = len(files) * (len(files) - 1) // 2
        comparison_count = 0
        
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                comparison_count += 1
                if progress_callback:
                    progress_callback(f"Comparing: {comparison_count}/{total_comparisons}")
                
                duplicate = self.compare_images(files[i], files[j], method)
                if duplicate:
                    duplicates.append(duplicate)
        
        print(f"Found {len(duplicates)} duplicate pairs")
        return duplicates


def export_duplicates_csv(duplicates: List[DuplicatePair], output_file: str):
    """
    Export duplicate results to CSV file.
    
    Args:
        duplicates: List of duplicate pairs
        output_file: Output CSV file path
    """
    import csv
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'File1_Path', 'File1_Name', 'File1_Size',
            'File2_Path', 'File2_Name', 'File2_Size',
            'Similarity_Score', 'Match_Type', 'Hash_Difference'
        ])
        
        for dup in duplicates:
            writer.writerow([
                dup.file1.path, dup.file1.filename, dup.file1.size,
                dup.file2.path, dup.file2.filename, dup.file2.size,
                f"{dup.similarity_score:.1f}%", dup.match_type, dup.hash_difference
            ])
    
    print(f"Exported {len(duplicates)} duplicate pairs to {output_file}")


def print_duplicate_summary(duplicates: List[DuplicatePair]):
    """
    Print a summary of duplicates to console.
    
    Args:
        duplicates: List of duplicate pairs
    """
    if not duplicates:
        print("\n✅ No duplicates found!")
        return
    
    print(f"\n🔍 Found {len(duplicates)} duplicate pair(s):")
    print("=" * 80)
    
    # Group by match type
    exact_matches = [d for d in duplicates if d.match_type == 'exact']
    visual_matches = [d for d in duplicates if d.match_type == 'visual']
    
    if exact_matches:
        print(f"\n📋 Exact Matches: {len(exact_matches)}")
        for i, dup in enumerate(exact_matches[:10], 1):  # Show first 10
            print(f"  {i}. {dup.file1.filename} ↔ {dup.file2.filename}")
            print(f"     Size: {dup.file1.size} bytes | 100% match")
        if len(exact_matches) > 10:
            print(f"     ... and {len(exact_matches) - 10} more")
    
    if visual_matches:
        print(f"\n🖼️  Visual Matches: {len(visual_matches)}")
        for i, dup in enumerate(visual_matches[:10], 1):  # Show first 10
            print(f"  {i}. {dup.file1.filename} ↔ {dup.file2.filename}")
            print(f"     Similarity: {dup.similarity_score:.1f}% | Hash diff: {dup.hash_difference}")
        if len(visual_matches) > 10:
            print(f"     ... and {len(visual_matches) - 10} more")
    
    print("\n" + "=" * 80)
