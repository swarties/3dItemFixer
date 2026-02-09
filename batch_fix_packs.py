import os
import zipfile
import json
import shutil
from pathlib import Path
import sys
import time
from collections import deque
from ctypes import windll

# Detect emoji support
USE_EMOJIS = True
try:
    # Test if terminal supports emojis by checking encoding
    if sys.stdout.encoding.lower() not in ['utf-8', 'utf8']:
        USE_EMOJIS = False
except:
    USE_EMOJIS = False

# Emoji fallbacks for compatibility
ICONS = {
    'search': '🔍' if USE_EMOJIS else '[?]',
    'wrench': '🔧' if USE_EMOJIS else '[*]',
    'disk': '💾' if USE_EMOJIS else '[B]',
    'package': '📦' if USE_EMOJIS else '[P]',
    'check': '✅' if USE_EMOJIS else '[+]',
    'cross': '❌' if USE_EMOJIS else '[X]',
    'skip': '⏭️' if USE_EMOJIS else '[>]',
    'tick': '✓' if USE_EMOJIS else 'OK',
    'circle': '○' if USE_EMOJIS else 'o',
    'warning': '⚠️' if USE_EMOJIS else '[!]',
    'sparkle': '✨' if USE_EMOJIS else '*',
}

# Enable ANSI escape sequences on Windows (built-in, no external library needed!)
ANSI_ENABLED = False
if os.name == 'nt':
    try:
        kernel32 = windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        ANSI_ENABLED = True
    except:
        # Fallback if ctypes fails (non-standard environment)
        ANSI_ENABLED = False
else:
    # Linux/Mac have native ANSI support
    ANSI_ENABLED = True

def clear_screen_ansi():
    """Clear screen using ANSI codes - no flicker!"""
    if ANSI_ENABLED:
        sys.stdout.write("\033[H\033[2J")  # Move to top + clear screen
        sys.stdout.flush()
    else:
        os.system('cls' if os.name == 'nt' else 'clear')

def move_cursor_home():
    """Move cursor to top without clearing"""
    if ANSI_ENABLED:
        sys.stdout.write("\033[H")
        sys.stdout.flush()

def hide_cursor():
    """Hide the blinking cursor"""
    if ANSI_ENABLED:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

def show_cursor():
    """Show the cursor again"""
    if ANSI_ENABLED:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

def check_if_has_models(zip_path):
    """
    Check if zip contains model JSON files without extracting
    Returns True if models/item/*.json files are found
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_path in zip_ref.namelist():
                if 'models/item/' in file_path and file_path.endswith('.json'):
                    return True
        return False
    except Exception:
        return False

def fix_missing_textures_in_memory(zip_path):
    """
    Fix #missing textures by processing ZIP in memory
    Returns (modified, count_fixed, buffer)
    """
    modified = False
    count_fixed = 0
    temp_buffer = {}

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('.json') and 'models/item/' in file_info.filename:
                    try:
                        content = zip_ref.read(file_info.filename).decode('utf-8')
                        if '#missing' in content:
                            new_content = content.replace('#missing', '#0')
                            temp_buffer[file_info.filename] = (new_content.encode('utf-8'), file_info)
                            count_fixed += 1
                            modified = True
                        else:
                            temp_buffer[file_info.filename] = (content.encode('utf-8'), file_info)
                    except:
                        temp_buffer[file_info.filename] = (zip_ref.read(file_info.filename), file_info)
                else:
                    temp_buffer[file_info.filename] = (zip_ref.read(file_info.filename), file_info)

        return modified, count_fixed, temp_buffer
    except Exception:
        return False, 0, None

def truncate_filename(filename, max_length=50):
    """Truncate long filenames with ellipsis"""
    if len(filename) <= max_length:
        return filename
    return filename[:max_length-3] + "..."

def print_progress_bar(iteration, total, length=40, fill='█'):
    """Print a progress bar"""
    # Use ASCII fallback for progress bar if no emoji support
    fill_char = fill if USE_EMOJIS else '#'

    if total == 0:
        return "|" + "-"*length + "| 0.0%"
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill_char * filled_length + '-' * (length - filled_length)
    return f"|{bar}| {percent}%"

def draw_frame(idx, total, zip_filename, history, status_lines):
    """Build entire TUI frame as one string - properly clears old content!"""
    frame = []

    frame.append("="*70)
    frame.append("  TEXTURE PACK BATCH FIXER [FLICKER-FREE MODE]")
    frame.append("="*70)
    frame.append("")

    # Recent history
    frame.append("Recent completions:")
    frame.append("-"*70)
    if history:
        for item in history:
            frame.append(item)
    else:
        frame.append("(none yet)")
    frame.append("-"*70)

    # Current pack
    frame.append("")
    frame.append(f"[{idx}/{total}] Processing: {truncate_filename(zip_filename, 50)}")
    frame.append("="*70)
    frame.append(f"Overall: {print_progress_bar(idx, total, 40)}")
    frame.append("-"*70)
    frame.append("")

    # Status lines
    for line in status_lines:
        frame.append(line)

    # Add blank lines to clear old content (ensures clean slate)
    for _ in range(10):
        frame.append("")

    return "\n".join(frame)

def process_zip_files(directory=".", create_backups=True):
    """Find all zip files, check for models, and fix #missing textures"""
    zip_files = [f for f in os.listdir(directory) 
                 if f.endswith('.zip') and not f.startswith('backup_')]

    if not zip_files:
        print(f"{ICONS['cross']} No zip files found in current directory!")
        return

    total_fixed = 0
    successful_packs = []
    failed_packs = []
    skipped_packs = []
    history = deque(maxlen=10)

    hide_cursor()  # Hide blinking cursor

    try:
        for idx, zip_filename in enumerate(zip_files, 1):
            zip_path = os.path.join(directory, zip_filename)
            status_lines = []

            # Draw initial frame - use clear on first draw
            if ANSI_ENABLED:
                sys.stdout.write("\033[H\033[2J")  # Clear screen + move to home
            else:
                clear_screen_ansi()
            sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
            sys.stdout.flush()

            # Step 1: Check for models
            status_lines = [f"{ICONS['search']} Checking for models..."]
            if ANSI_ENABLED:
                sys.stdout.write("\033[H\033[2J")
            else:
                clear_screen_ansi()
            sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
            sys.stdout.flush()

            if not check_if_has_models(zip_path):
                status_lines = [f"{ICONS['search']} Checking for models... {ICONS['skip']} Skipped"]
                if ANSI_ENABLED:
                    sys.stdout.write("\033[H\033[2J")
                else:
                    clear_screen_ansi()
                sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                sys.stdout.flush()
                skipped_packs.append(zip_filename)
                history.append(f"[{idx}/{len(zip_files)}] {truncate_filename(zip_filename, 40)} | Skipped")
                time.sleep(0.3)
                continue

            status_lines = [f"{ICONS['search']} Checking for models... {ICONS['tick']}"]
            if ANSI_ENABLED:
                sys.stdout.write("\033[H\033[2J")
            else:
                clear_screen_ansi()
            sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
            sys.stdout.flush()

            try:
                # Step 2: Process in memory
                status_lines.append(f"{ICONS['wrench']} Scanning & fixing...")
                if ANSI_ENABLED:
                    sys.stdout.write("\033[H\033[2J")
                else:
                    clear_screen_ansi()
                sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                sys.stdout.flush()

                modified, fixed_count, buffer = fix_missing_textures_in_memory(zip_path)

                if not modified:
                    status_lines[-1] = f"{ICONS['wrench']} Scanning & fixing... No issues"
                    if ANSI_ENABLED:
                        sys.stdout.write("\033[H\033[2J")
                    else:
                        clear_screen_ansi()
                    sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                    sys.stdout.flush()
                    successful_packs.append((zip_filename, 0))
                    history.append(f"[{idx}/{len(zip_files)}] {truncate_filename(zip_filename, 40)} | Clean")
                    time.sleep(0.3)
                    continue

                status_lines[-1] = f"{ICONS['wrench']} Scanning & fixing... Found {fixed_count} file(s)"
                if ANSI_ENABLED:
                    sys.stdout.write("\033[H\033[2J")
                else:
                    clear_screen_ansi()
                sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                sys.stdout.flush()
                total_fixed += fixed_count

                # Step 3: Backup
                if create_backups:
                    backup_name = f"backup_{zip_filename}"
                    backup_path = os.path.join(directory, backup_name)

                    if not os.path.exists(backup_path):
                        status_lines.append(f"{ICONS['disk']} Creating backup...")
                        if ANSI_ENABLED:
                            sys.stdout.write("\033[H\033[2J")
                        else:
                            clear_screen_ansi()
                        sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                        sys.stdout.flush()
                        shutil.copy2(zip_path, backup_path)
                        status_lines[-1] = f"{ICONS['disk']} Creating backup... {ICONS['tick']}"
                        if ANSI_ENABLED:
                            sys.stdout.write("\033[H\033[2J")
                        else:
                            clear_screen_ansi()
                        sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                        sys.stdout.flush()

                # Step 4: Write fixed version
                status_lines.append(f"{ICONS['package']} Writing fixed ZIP...")
                if ANSI_ENABLED:
                    sys.stdout.write("\033[H\033[2J")
                else:
                    clear_screen_ansi()
                sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                sys.stdout.flush()

                temp_zip = zip_path + '.tmp'

                with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for filename, (content, file_info) in buffer.items():
                        zipf.writestr(file_info, content)

                os.remove(zip_path)
                os.rename(temp_zip, zip_path)

                status_lines[-1] = f"{ICONS['package']} Writing fixed ZIP... {ICONS['tick']}"
                status_lines.append(f"{ICONS['check']} Fixed!")
                if ANSI_ENABLED:
                    sys.stdout.write("\033[H\033[2J")
                else:
                    clear_screen_ansi()
                sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                sys.stdout.flush()

                successful_packs.append((zip_filename, fixed_count))
                history.append(f"[{idx}/{len(zip_files)}] {truncate_filename(zip_filename, 40)} | Fixed {fixed_count}")
                time.sleep(0.3)

            except Exception as e:
                error_msg = str(e)[:45]
                status_lines.append(f"{ICONS['cross']} Error: {error_msg}")
                if ANSI_ENABLED:
                    sys.stdout.write("\033[H\033[2J")
                else:
                    clear_screen_ansi()
                sys.stdout.write(draw_frame(idx, len(zip_files), zip_filename, history, status_lines))
                sys.stdout.flush()
                failed_packs.append((zip_filename, str(e)))
                history.append(f"[{idx}/{len(zip_files)}] {truncate_filename(zip_filename, 40)} | Failed")

                temp_zip = zip_path + '.tmp'
                if os.path.exists(temp_zip):
                    try:
                        os.remove(temp_zip)
                    except:
                        pass
                time.sleep(0.3)

    finally:
        show_cursor()  # Always restore cursor

    # Final summary
    time.sleep(0.3)
    clear_screen_ansi()
    print("="*70)
    print("  FINAL SUMMARY")
    print("="*70)
    print(f"\nTotal packs scanned: {len(zip_files)}")
    print(f"{ICONS['check']} Processed: {len(successful_packs)}")
    print(f"{ICONS['skip']} Skipped (no models): {len(skipped_packs)}")
    print(f"{ICONS['cross']} Failed: {len(failed_packs)}")
    print(f"{ICONS['wrench']} Total files fixed: {total_fixed}")

    if successful_packs:
        print("\n" + "-"*70)
        print(f"{ICONS['check']} SUCCESSFULLY PROCESSED:")
        for pack, count in successful_packs:
            display_name = truncate_filename(pack, 50)
            if count > 0:
                print(f"   {ICONS['tick']} {display_name} ({count} file(s))")
            else:
                print(f"   {ICONS['circle']} {display_name} (clean)")

    if skipped_packs:
        print("\n" + "-"*70)
        print(f"{ICONS['skip']} SKIPPED (NO MODEL FILES):")
        for pack in skipped_packs:
            print(f"   - {truncate_filename(pack, 55)}")

    if failed_packs:
        print("\n" + "-"*70)
        print(f"{ICONS['cross']} FAILED:")
        for pack, error in failed_packs:
            print(f"   x {truncate_filename(pack, 55)}")
            print(f"     {error[:60]}")

    if total_fixed > 0:
        print("\n" + "-"*70)
        if create_backups:
            print(f"{ICONS['disk']} Backups saved with 'backup_' prefix")
        else:
            print(f"{ICONS['warning']} No backups created")

    print("\n" + "="*70)

if __name__ == "__main__":
    clear_screen_ansi()
    print("="*70)
    print("  TEXTURE PACK BATCH FIXER")
    print("  Replaces #missing with #0 in model JSON files")
    print("="*70)
    print(f"\nWorking directory: {os.getcwd()}")

    # Show mode info
    mode_info = []
    if ANSI_ENABLED:
        mode_info.append("ANSI codes enabled")
    if USE_EMOJIS:
        mode_info.append("Emoji support detected")
    if mode_info:
        print(f"Mode: {', '.join(mode_info)}")

    while True:
        response = input("\nCreate backups of original files? (Y/n): ").strip().lower()
        if response in ['y', 'yes', '']:
            create_backups = True
            print(f"{ICONS['check']} Backups will be created")
            break
        elif response in ['n', 'no']:
            create_backups = False
            print(f"\n{ICONS['warning']} WARNING: Original files will be PERMANENTLY overwritten!")
            print(f"{ICONS['warning']} This action CANNOT be undone!")
            confirm = input("\nAre you absolutely sure? Type 'yes' to confirm: ").strip().lower()
            if confirm == 'yes':
                print(f"{ICONS['warning']} Backups disabled - proceeding without backups")
                break
            else:
                print(f"\n{ICONS['check']} Cancelled. Let's try again.")
        else:
            print("Invalid input. Please enter 'y' or 'n'.")

    input("\nPress Enter to start processing...")

    process_zip_files(create_backups=create_backups)

    print(f"\n{ICONS['sparkle']} All done!")
    input("\nPress Enter to exit...")

