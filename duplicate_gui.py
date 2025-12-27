#!/usr/bin/env python3
"""
Duplicate Image Finder GUI
Two-pane interface for reviewing and managing duplicate images.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Frame, Label, Button, Checkbutton, IntVar
from pathlib import Path
from typing import List, Optional, Callable
import shutil

try:
    from PIL import Image, ImageTk
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import send2trash
    SEND2TRASH_AVAILABLE = True
except ImportError:
    SEND2TRASH_AVAILABLE = False

from duplicate_finder import DuplicatePair, FileInfo


class DuplicateFinderGUI:
    """Main GUI class for duplicate image review."""
    
    def __init__(self, duplicates: List[DuplicatePair], on_close: Optional[Callable] = None):
        """
        Initialize the GUI.
        
        Args:
            duplicates: List of duplicate pairs to review
            on_close: Optional callback when window closes
        """
        if not PILLOW_AVAILABLE:
            raise ImportError("PIL/Pillow is required for GUI")
        
        self.duplicates = duplicates
        self.current_index = 0
        self.on_close = on_close
        self.deleted_files = set()
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("Duplicate Image Finder")
        self.root.geometry("1000x700")
        
        # Selection variables
        self.select_left = IntVar(value=0)
        self.select_right = IntVar(value=0)
        
        # Image references (to prevent garbage collection)
        self.left_image_ref = None
        self.right_image_ref = None
        
        self._create_widgets()
        self._setup_keyboard_shortcuts()
        
        if duplicates:
            self.display_duplicate_pair(0)
        else:
            messagebox.showinfo("No Duplicates", "No duplicate images found!")
            self.root.destroy()
    
    def _create_widgets(self):
        """Create all GUI widgets."""
        # Header frame
        header_frame = Frame(self.root, bg='#f0f0f0', height=50)
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        header_frame.pack_propagate(False)
        
        # Status label
        self.status_label = Label(
            header_frame, 
            text=f"Showing duplicate 1 of {len(self.duplicates)}",
            font=('Arial', 12, 'bold'),
            bg='#f0f0f0'
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Navigation buttons
        nav_frame = Frame(header_frame, bg='#f0f0f0')
        nav_frame.pack(side=tk.RIGHT, padx=10)
        
        self.prev_button = Button(
            nav_frame,
            text="< Previous",
            command=self.previous_pair,
            width=10
        )
        self.prev_button.pack(side=tk.LEFT, padx=5)
        
        self.next_button = Button(
            nav_frame,
            text="Next >",
            command=self.next_pair,
            width=10
        )
        self.next_button.pack(side=tk.LEFT, padx=5)
        
        # Main content frame (two panes)
        content_frame = Frame(self.root)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left pane
        left_frame = Frame(content_frame, bd=2, relief=tk.GROOVE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        Label(left_frame, text="File 1", font=('Arial', 11, 'bold')).pack(pady=5)
        
        # Left thumbnail
        self.left_thumbnail_label = Label(left_frame, bg='gray', width=300, height=300)
        self.left_thumbnail_label.pack(pady=10)
        
        # Left checkbox
        self.left_checkbox = Checkbutton(
            left_frame,
            text="Select for action",
            variable=self.select_left,
            font=('Arial', 10)
        )
        self.left_checkbox.pack(pady=5)
        
        # Left file info
        self.left_info_frame = Frame(left_frame)
        self.left_info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.left_filename_label = Label(self.left_info_frame, text="", anchor='w', justify=tk.LEFT)
        self.left_filename_label.pack(fill=tk.X)
        
        self.left_size_label = Label(self.left_info_frame, text="", anchor='w', justify=tk.LEFT)
        self.left_size_label.pack(fill=tk.X)
        
        self.left_dimensions_label = Label(self.left_info_frame, text="", anchor='w', justify=tk.LEFT)
        self.left_dimensions_label.pack(fill=tk.X)
        
        self.left_path_label = Label(
            self.left_info_frame, 
            text="", 
            anchor='w', 
            justify=tk.LEFT,
            wraplength=400,
            fg='gray'
        )
        self.left_path_label.pack(fill=tk.X)
        
        # Right pane
        right_frame = Frame(content_frame, bd=2, relief=tk.GROOVE)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        Label(right_frame, text="File 2", font=('Arial', 11, 'bold')).pack(pady=5)
        
        # Right thumbnail
        self.right_thumbnail_label = Label(right_frame, bg='gray', width=300, height=300)
        self.right_thumbnail_label.pack(pady=10)
        
        # Right checkbox
        self.right_checkbox = Checkbutton(
            right_frame,
            text="Select for action",
            variable=self.select_right,
            font=('Arial', 10)
        )
        self.right_checkbox.pack(pady=5)
        
        # Right file info
        self.right_info_frame = Frame(right_frame)
        self.right_info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.right_filename_label = Label(self.right_info_frame, text="", anchor='w', justify=tk.LEFT)
        self.right_filename_label.pack(fill=tk.X)
        
        self.right_size_label = Label(self.right_info_frame, text="", anchor='w', justify=tk.LEFT)
        self.right_size_label.pack(fill=tk.X)
        
        self.right_dimensions_label = Label(self.right_info_frame, text="", anchor='w', justify=tk.LEFT)
        self.right_dimensions_label.pack(fill=tk.X)
        
        self.right_path_label = Label(
            self.right_info_frame, 
            text="", 
            anchor='w', 
            justify=tk.LEFT,
            wraplength=400,
            fg='gray'
        )
        self.right_path_label.pack(fill=tk.X)
        
        # Similarity indicator (below both panes)
        similarity_frame = Frame(self.root, bg='#f0f0f0', height=40)
        similarity_frame.pack(fill=tk.X, padx=5, pady=5)
        similarity_frame.pack_propagate(False)
        
        Label(similarity_frame, text="Similarity:", font=('Arial', 10), bg='#f0f0f0').pack(side=tk.LEFT, padx=10)
        
        self.similarity_bar = tk.Canvas(similarity_frame, width=200, height=20, bg='white')
        self.similarity_bar.pack(side=tk.LEFT, padx=5)
        
        self.similarity_label = Label(similarity_frame, text="", font=('Arial', 10, 'bold'), bg='#f0f0f0')
        self.similarity_label.pack(side=tk.LEFT, padx=10)
        
        # Action buttons frame
        action_frame = Frame(self.root, bg='#f0f0f0', height=60)
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        action_frame.pack_propagate(False)
        
        Label(action_frame, text="Actions:", font=('Arial', 10, 'bold'), bg='#f0f0f0').pack(side=tk.LEFT, padx=10)
        
        Button(
            action_frame,
            text="Delete Selected",
            command=self.delete_selected,
            bg='#ff6b6b',
            fg='white',
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        Button(
            action_frame,
            text="Move Selected",
            command=self.move_selected,
            bg='#4ecdc4',
            fg='white',
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        Button(
            action_frame,
            text="Copy Selected",
            command=self.copy_selected,
            bg='#95e1d3',
            fg='black',
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        Button(
            action_frame,
            text="Skip This Pair",
            command=self.next_pair,
            bg='#ffd93d',
            fg='black',
            width=15
        ).pack(side=tk.LEFT, padx=5)
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts."""
        self.root.bind('<Left>', lambda e: self.previous_pair())
        self.root.bind('<Right>', lambda e: self.next_pair())
        self.root.bind('<space>', lambda e: self.toggle_left_selection())
        self.root.bind('<Delete>', lambda e: self.delete_selected())
        self.root.bind('<Return>', lambda e: self.next_pair())
        self.root.bind('<Escape>', lambda e: self.root.destroy())
    
    def toggle_left_selection(self):
        """Toggle left checkbox selection."""
        self.select_left.set(1 - self.select_left.get())
    
    def format_file_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def update_thumbnail(self, image_label: Label, file_info: FileInfo) -> bool:
        """
        Update thumbnail in the specified label.
        
        Args:
            image_label: Label widget to update
            file_info: File information containing thumbnail
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if file was deleted
            if file_info.path in self.deleted_files or not Path(file_info.path).exists():
                # Show "deleted" placeholder
                img = Image.new('RGB', (200, 200), color='#cccccc')
                photo = ImageTk.PhotoImage(img)
                image_label.config(image=photo, text="[DELETED]", compound=tk.CENTER)
                # Store reference
                if image_label == self.left_thumbnail_label:
                    self.left_image_ref = photo
                else:
                    self.right_image_ref = photo
                return False
            
            # Load and display thumbnail
            if file_info.thumbnail is None:
                # Generate thumbnail if not already available
                try:
                    img = Image.open(file_info.path)
                    img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    file_info.thumbnail = img
                except Exception as e:
                    print(f"Error loading thumbnail: {e}")
                    return False
            
            photo = ImageTk.PhotoImage(file_info.thumbnail)
            image_label.config(image=photo, text="")
            
            # Store reference to prevent garbage collection
            if image_label == self.left_thumbnail_label:
                self.left_image_ref = photo
            else:
                self.right_image_ref = photo
            
            return True
        except Exception as e:
            print(f"Error updating thumbnail: {e}")
            return False
    
    def get_similarity_color(self, score: float) -> str:
        """Get color for similarity score."""
        if score >= 99:
            return '#2ecc71'  # Green - exact match
        elif score >= 85:
            return '#f1c40f'  # Yellow - very similar
        elif score >= 70:
            return '#e67e22'  # Orange - somewhat similar
        else:
            return '#e74c3c'  # Red - barely similar
    
    def display_duplicate_pair(self, index: int):
        """
        Display a duplicate pair at the given index.
        
        Args:
            index: Index of duplicate pair to display
        """
        if index < 0 or index >= len(self.duplicates):
            return
        
        self.current_index = index
        pair = self.duplicates[index]
        
        # Update status
        self.status_label.config(text=f"Showing duplicate {index + 1} of {len(self.duplicates)}")
        
        # Update navigation buttons
        self.prev_button.config(state=tk.NORMAL if index > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if index < len(self.duplicates) - 1 else tk.DISABLED)
        
        # Reset selections
        self.select_left.set(0)
        self.select_right.set(0)
        
        # Update left pane
        self.update_thumbnail(self.left_thumbnail_label, pair.file1)
        self.left_filename_label.config(text=f"File: {pair.file1.filename}")
        self.left_size_label.config(text=f"Size: {self.format_file_size(pair.file1.size)}")
        if pair.file1.dimensions:
            self.left_dimensions_label.config(
                text=f"Dimensions: {pair.file1.dimensions[0]}x{pair.file1.dimensions[1]}"
            )
        else:
            self.left_dimensions_label.config(text="Dimensions: Unknown")
        self.left_path_label.config(text=f"Path: {pair.file1.path}")
        
        # Update right pane
        self.update_thumbnail(self.right_thumbnail_label, pair.file2)
        self.right_filename_label.config(text=f"File: {pair.file2.filename}")
        self.right_size_label.config(text=f"Size: {self.format_file_size(pair.file2.size)}")
        if pair.file2.dimensions:
            self.right_dimensions_label.config(
                text=f"Dimensions: {pair.file2.dimensions[0]}x{pair.file2.dimensions[1]}"
            )
        else:
            self.right_dimensions_label.config(text="Dimensions: Unknown")
        self.right_path_label.config(text=f"Path: {pair.file2.path}")
        
        # Update similarity indicator
        similarity = pair.similarity_score
        color = self.get_similarity_color(similarity)
        
        # Draw similarity bar
        self.similarity_bar.delete("all")
        bar_width = int(200 * similarity / 100)
        self.similarity_bar.create_rectangle(0, 0, bar_width, 20, fill=color, outline="")
        self.similarity_bar.create_rectangle(0, 0, 200, 20, outline="black")
        
        self.similarity_label.config(
            text=f"{similarity:.0f}% ({pair.match_type})",
            fg=color
        )
    
    def previous_pair(self):
        """Navigate to previous duplicate pair."""
        if self.current_index > 0:
            self.display_duplicate_pair(self.current_index - 1)
    
    def next_pair(self):
        """Navigate to next duplicate pair."""
        if self.current_index < len(self.duplicates) - 1:
            self.display_duplicate_pair(self.current_index + 1)
    
    def get_selected_files(self) -> List[str]:
        """Get list of selected file paths."""
        selected = []
        pair = self.duplicates[self.current_index]
        
        if self.select_left.get():
            selected.append(pair.file1.path)
        if self.select_right.get():
            selected.append(pair.file2.path)
        
        return selected
    
    def delete_selected(self):
        """Delete selected files."""
        selected = self.get_selected_files()
        
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one file to delete.")
            return
        
        # Confirm deletion
        file_list = '\n'.join([Path(f).name for f in selected])
        response = messagebox.askyesno(
            "Confirm Deletion",
            f"Delete {len(selected)} file(s)?\n\n{file_list}\n\n"
            f"{'Files will be moved to trash.' if SEND2TRASH_AVAILABLE else 'Files will be permanently deleted!'}"
        )
        
        if not response:
            return
        
        # Delete files
        deleted_count = 0
        for file_path in selected:
            try:
                if SEND2TRASH_AVAILABLE:
                    send2trash.send2trash(file_path)
                else:
                    os.remove(file_path)
                self.deleted_files.add(file_path)
                deleted_count += 1
                print(f"Deleted: {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete {Path(file_path).name}:\n{str(e)}")
        
        if deleted_count > 0:
            messagebox.showinfo("Success", f"Deleted {deleted_count} file(s)")
            # Refresh display
            self.display_duplicate_pair(self.current_index)
    
    def move_selected(self):
        """Move selected files to another directory."""
        selected = self.get_selected_files()
        
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one file to move.")
            return
        
        # Ask for destination directory
        dest_dir = filedialog.askdirectory(title="Select destination directory")
        if not dest_dir:
            return
        
        # Move files
        moved_count = 0
        for file_path in selected:
            try:
                filename = Path(file_path).name
                dest_path = Path(dest_dir) / filename
                
                # Handle name collision
                counter = 1
                while dest_path.exists():
                    stem = Path(filename).stem
                    ext = Path(filename).suffix
                    dest_path = Path(dest_dir) / f"{stem}_{counter}{ext}"
                    counter += 1
                
                shutil.move(file_path, str(dest_path))
                self.deleted_files.add(file_path)
                moved_count += 1
                print(f"Moved: {file_path} -> {dest_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to move {Path(file_path).name}:\n{str(e)}")
        
        if moved_count > 0:
            messagebox.showinfo("Success", f"Moved {moved_count} file(s) to {dest_dir}")
            # Refresh display
            self.display_duplicate_pair(self.current_index)
    
    def copy_selected(self):
        """Copy selected files to another directory."""
        selected = self.get_selected_files()
        
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one file to copy.")
            return
        
        # Ask for destination directory
        dest_dir = filedialog.askdirectory(title="Select destination directory")
        if not dest_dir:
            return
        
        # Copy files
        copied_count = 0
        for file_path in selected:
            try:
                filename = Path(file_path).name
                dest_path = Path(dest_dir) / filename
                
                # Handle name collision
                counter = 1
                while dest_path.exists():
                    stem = Path(filename).stem
                    ext = Path(filename).suffix
                    dest_path = Path(dest_dir) / f"{stem}_{counter}{ext}"
                    counter += 1
                
                shutil.copy2(file_path, str(dest_path))
                copied_count += 1
                print(f"Copied: {file_path} -> {dest_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy {Path(file_path).name}:\n{str(e)}")
        
        if copied_count > 0:
            messagebox.showinfo("Success", f"Copied {copied_count} file(s) to {dest_dir}")
    
    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()
        
        if self.on_close:
            self.on_close()
