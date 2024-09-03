import sys
import os
import zlib
import hashlib
from pathlib import Path
import struct
import urllib.request

def create_blob_entry(path, write=True):
    with open(path, "rb") as f:
        data = f.read()
    header = f"blob {len(data)}\0".encode("utf-8")
    store = header + data
    sha = hashlib.sha1(store).hexdigest()
    if write:
        os.makedirs(f".git/objects/{sha[:2]}", exist_ok=True)
        with open(f".git/objects/{sha[:2]}/{sha[2:]}", "wb") as f:
            f.write(zlib.compress(store))
    return sha

def write_tree(path: str):
    if os.path.isfile(path):
        return create_blob_entry(path)
    contents = sorted(
        os.listdir(path),
        key=lambda x: x if os.path.isfile(os.path.join(path, x)) else f"{x}/",
    )
    s = b""
    for item in contents:
        if item == ".git":
            continue
        full = os.path.join(path, item)
        if os.path.isfile(full):
            s += f"100644 {item}\0".encode()
        else:
            s += f"40000 {item}\0".encode()
        sha1 = int.to_bytes(int(write_tree(full), base=16), length=20, byteorder="big")
        s += sha1
    s = f"tree {len(s)}\0".encode() + s
    sha1 = hashlib.sha1(s).hexdigest()
    os.makedirs(f".git/objects/{sha1[:2]}", exist_ok=True)
    with open(f".git/objects/{sha1[:2]}/{sha1[2:]}", "wb") as f:
        f.write(zlib.compress(s))
    return sha1

def write_object(directory, obj_type, contents):
    header = f"{obj_type} {len(contents)}\0".encode()
    store = header + contents
    sha = hashlib.sha1(store).hexdigest()

    # Write the object to .git/objects
    obj_dir = directory / f".git/objects/{sha[:2]}"
    obj_file = obj_dir / sha[2:]

    if not obj_dir.exists():
        obj_dir.mkdir(parents=True)

    with open(obj_file, "wb") as f:
        f.write(zlib.compress(store))

    return sha

def main():
    command = sys.argv[1]

    if command == "init":
        os.mkdir(".git")
        os.mkdir(".git/objects")
        os.mkdir(".git/refs")
        with open(".git/HEAD", "w") as f:
            f.write("ref: refs/heads/main\n")
        print("Initialized git directory")

    elif command == "cat-file":
        if sys.argv[2] == "-p":
            blob_sha = sys.argv[3]
            with open(f".git/objects/{blob_sha[:2]}/{blob_sha[2:]}", "rb") as f:
                raw = zlib.decompress(f.read())
                header, content = raw.split(b"\0", maxsplit=1)
                print(content.decode("utf-8"), end="")

    elif command == "hash-object":
        if sys.argv[2] == "-w":
            file_path = sys.argv[3]
            with open(file_path, "rb") as f:
                content = f.read()
            header = f"blob {len(content)}\0".encode()
            store = header + content
            sha1 = hashlib.sha1(store).hexdigest()
            obj_dir = f".git/objects/{sha1[:2]}"
            obj_file = f"{sha1[2:]}"
            if not os.path.exists(obj_dir):
                os.makedirs(obj_dir)
            with open(os.path.join(obj_dir, obj_file), "wb") as f:
                f.write(zlib.compress(store))
            print(sha1)

    elif command == "ls-tree":
        param, hash = sys.argv[2], sys.argv[3]
        if param == "--name-only":
            with open(f".git/objects/{hash[:2]}/{hash[2:]}", "rb") as f:
                data = zlib.decompress(f.read())
                _, binary_data = data.split(b"\x00", maxsplit=1)
            while binary_data:
                mode_name, binary_data = binary_data.split(b"\0", maxsplit=1)
                mode, name = mode_name.split(b" ", maxsplit=1)
                binary_data = binary_data[20:]
                print(name.decode("utf-8"))

    elif command == "write-tree":
        print(write_tree("./"))

    elif command == "commit-tree":
        tree_sha = sys.argv[2]
        parent_sha = sys.argv[4]
        message = sys.argv[6]
        contents = b"".join(
            [
                b"tree %b\n" % tree_sha.encode(),
                b"parent %b\n" % parent_sha.encode(),
                b"author irohit-mishra <mail.irohitmishra@users.noreply.github.com> -0000\n",
                b"committer irohit-mishra <mail.irohitmishra@users.noreply.github.com> -0000\n\n",
                message.encode(),
                b"\n",
            ]
        )
        hash = write_object(Path("."), "commit", contents)
        print(hash)

    # Fetch refs
    refs = fetch_refs(url)
    for name, sha in refs.items():
        Path(parent / ".git" / name).write_text(sha + "\n")

    # Fetch and unpack objects
    pack_file = fetch_pack(url, refs)
    unpack_objects(parent, pack_file)

    # Render the working directory
    render_tree(parent, parent, refs["HEAD"])

def fetch_refs(url):
    req = urllib.request.Request(f"{url}/info/refs?service=git-upload-pack")
    with urllib.request.urlopen(req) as f:
        refs = {
            bs[1].decode(): bs[0].decode()
            for bs0 in cast(bytes, f.read()).split(b"\n")
            if (bs1 := bs0[4:])
            and not bs1.startswith(b"#")
            and (bs2 := bs1.split(b"\0")[0])
            and (bs := (bs2[4:] if bs2.endswith(b"HEAD") else bs2).split(b" "))
        }
    return refs

def fetch_pack(url, refs):
    body = (
        b"0011command=fetch0001000fno-progress"
        + b"".join(b"0032want " + ref.encode() + b"\n" for ref in refs.values())
        + b"0009done\n0000"
    )
    req = urllib.request.Request(
        f"{url}/git-upload-pack",
        data=body,
        headers={"Git-Protocol": "version=2"},
    )
    with urllib.request.urlopen(req) as f:
        return f.read()

def unpack_objects(parent, pack_file):
    def next_size_type(bs: bytes):
        ty = (bs[0] & 0b_0111_0000) >> 4
        size = bs[0] & 0b_0000_1111
        i = 1
        off = 4
        while bs[i - 1] & 0b_1000_0000:
            size += (bs[i] & 0b_0111_1111) << off
            off += 7
            i += 1
        return ty, size, bs[i:]

    # Strip header and version
    pack_file = pack_file[8:]
    n_objs, *_ = struct.unpack("!I", pack_file[:4])
    pack_file = pack_file[4:]

    for _ in range(n_objs):
        ty, _, pack_file = next_size_type(pack_file)
        if ty in [1, 2, 3, 4]:  # commit, tree, blob, tag
            dec = zlib.decompressobj()
            content = dec.decompress(pack_file)
            pack_file = dec.unused_data
            write_object(parent, ty, content)
        else:
            raise RuntimeError(f"Not implemented for type {ty}")

if __name__ == "__main__":
    main()
