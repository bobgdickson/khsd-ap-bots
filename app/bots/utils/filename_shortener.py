import os
import hashlib
from pathlib import Path

# ---- CONFIG ----
TARGET_DIR = r"C:\Users\Bob_Dickson\OneDrive - Kern High School District\Documents - Fiscal\Accounts Payable\Vestis"
MAX_LENGTH = 60  # Safe for PeopleSoft 64-char limits
DRY_RUN = False   # Set to False to actually rename
# -----------------

def shorten_filename(filename, max_length):
    name, ext = os.path.splitext(filename)

    if len(filename) <= max_length:
        return filename  # no change needed

    # Create short hash for uniqueness
    hash_suffix = hashlib.md5(filename.encode()).hexdigest()[:6]

    # Extract numbers (often invoice/account numbers)
    numbers = "_".join(filter(str.isdigit, name.split("_")))
    
    base = f"{numbers}_{hash_suffix}" if numbers else hash_suffix

    # Truncate safely
    allowed_length = max_length - len(ext)
    shortened = base[:allowed_length]

    return shortened + ext


def process_directory(directory):
    for file in os.listdir(directory):
        old_path = os.path.join(directory, file)

        if not os.path.isfile(old_path):
            continue

        new_name = shorten_filename(file, MAX_LENGTH)

        if new_name != file:
            new_path = os.path.join(directory, new_name)

            print(f"Rename:\n  {file}\n  → {new_name}\n")

            if not DRY_RUN:
                os.rename(old_path, new_path)


if __name__ == "__main__":
    process_directory(TARGET_DIR)
