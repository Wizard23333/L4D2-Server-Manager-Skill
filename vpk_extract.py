from pathlib import Path
import struct
import sys

def read_null_terminated_string(f):
    chars = []
    while True:
        c = f.read(1)
        if not c or c == b'\x00':
            break
        chars.append(c.decode('ascii', errors='ignore'))
    return "".join(chars)

def extract_vpk(vpk_path, output_dir):
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    with open(vpk_path, 'rb') as f:
        # Read Header
        signature, version = struct.unpack('<II', f.read(8))
        if signature != 0x55aa1234:
            print("Not a valid VPK file.")
            return

        tree_size = struct.unpack('<I', f.read(4))[0]
        
        if version == 2:
            # Skip V2 specific header parts (file_data_section_size, archive_md5_section_size, etc.)
            f.read(16)

        # The tree starts after the header
        header_size = 12 if version == 1 else 28
        f.seek(header_size)

        while True:
            extension = read_null_terminated_string(f)
            if not extension:
                break
            
            while True:
                path = read_null_terminated_string(f)
                if not path:
                    break
                
                while True:
                    filename = read_null_terminated_string(f)
                    if not filename:
                        break
                    
                    # Read directory entry
                    # CRC (4), Preload Bytes (2), Archive Index (2), Entry Offset (4), Entry Size (4), Terminator (2)
                    entry_data = f.read(18)
                    if len(entry_data) < 18:
                        break
                    crc, preload_bytes, archive_index, entry_offset, entry_size, terminator = struct.unpack('<IHHIIH', entry_data)
                    
                    path_name = "" if path in (" ", ".") else path
                    entry_path = Path(path_name) / f"{filename}.{extension}"
                    full_path = (output_root / entry_path).resolve()
                    if output_root != full_path and output_root not in full_path.parents:
                        raise ValueError(f"Refusing to extract outside output directory: {entry_path}")
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    preload_data = f.read(preload_bytes)
                    if len(preload_data) != preload_bytes:
                        raise EOFError(f"Unexpected EOF while reading preload data for {entry_path}")

                    # Store current position after preload data to come back to the tree.
                    current_pos = f.tell()
                    
                    # Seek to the actual data
                    data_start = header_size + tree_size
                    f.seek(data_start + entry_offset)
                    
                    with open(full_path, 'wb') as out_f:
                        out_f.write(preload_data)

                        # Write data in chunks to avoid MemoryError
                        remaining = entry_size
                        while remaining > 0:
                            chunk_size = min(remaining, 1024 * 1024) # 1MB chunks
                            data = f.read(chunk_size)
                            if not data:
                                break
                            out_f.write(data)
                            remaining -= len(data)
                    
                    print(f"Extracted: {entry_path}")
                    f.seek(current_pos)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python vpk_extract.py <vpk_path> <output_dir>")
    else:
        extract_vpk(sys.argv[1], sys.argv[2])
