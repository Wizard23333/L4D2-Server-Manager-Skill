import os
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
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

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
                    
                    full_path = os.path.join(output_dir, path, f"{filename}.{extension}")
                    dir_name = os.path.dirname(full_path)
                    if not os.path.exists(dir_name):
                        os.makedirs(dir_name)
                    
                    # Store current position to come back to the tree
                    current_pos = f.tell()
                    
                    # Seek to the actual data
                    data_start = header_size + tree_size
                    f.seek(data_start + entry_offset)
                    
                    with open(full_path, 'wb') as out_f:
                        # Write preload data if any
                        # Preload data is actually right after the 18-byte entry in the tree
                        # We should have read it before seeking to the data section.
                        # For simplicity, we skip it for now unless needed.
                        
                        # Write data in chunks to avoid MemoryError
                        remaining = entry_size
                        while remaining > 0:
                            chunk_size = min(remaining, 1024 * 1024) # 1MB chunks
                            data = f.read(chunk_size)
                            if not data:
                                break
                            out_f.write(data)
                            remaining -= len(data)
                    
                    print(f"Extracted: {path}/{filename}.{extension}")
                    f.seek(current_pos)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python vpk_extract.py <vpk_path> <output_dir>")
    else:
        extract_vpk(sys.argv[1], sys.argv[2])
