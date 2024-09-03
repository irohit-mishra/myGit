import sys
import os
import zlib
import hashlib

def create_blob_entry(path, write=True):
    with open(path,"rb") as f:
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
        key=lambda x:x if os.path.isfile(os.path.join(path,x)) else f"{x}/",
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

            # Read the content of the file
            with open(file_path, "rb") as f:
                content = f.read()

            # Create the git object
            header = f"blob {len(content)}\0".encode()
            store = header + content

            # Compute the SHA-1 hash
            sha1 = hashlib.sha1(store).hexdigest()

            # Write the object to the .git/objects directory
            obj_dir = f".git/objects/{sha1[:2]}"
            obj_file = f"{sha1[2:]}"

            if not os.path.exists(obj_dir):
                os.makedirs(obj_dir)

            with open(os.path.join(obj_dir, obj_file), "wb") as f:
                f.write(zlib.compress(store))

            # Print the SHA-1 hash
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


    elif command =="write-tree":
        print(write_tree("./"))

    else:
        raise RuntimeError(f"Unknown command #{command}")

def commit_tree(tree_sha, parent_sha, message):
    author = "Rohit Mishra <mail.irohitmishra@gmail.com>"
    timestamp = int(time.time())
    timezone = "-0000"

    # Format the commit object
    commit_content = f"tree {tree_sha}\n"
    if parent_sha:
        commit_content += f"parent {parent_sha}\n"
    commit_content += f"author {author} {timestamp} {timezone}\n"
    commit_content += f"committer {author} {timestamp} {timezone}\n\n"
    commit_content += f"{message}\n"

    # Add the header and calculate the hash
    commit_object = f"commit {len(commit_content)}\0".encode() + commit_content.encode()
    commit_sha = hashlib.sha1(commit_object).hexdigest()

    # Write the commit object to the .git/objects directory
    obj_dir = f".git/objects/{commit_sha[:2]}"
    obj_file = f"{commit_sha[2:]}"
    
    if not os.path.exists(obj_dir):
        os.makedirs(obj_dir)

    with open(os.path.join(obj_dir, obj_file), "wb") as f:
        f.write(zlib.compress(commit_object))

    # Print the commit SHA
    print(commit_sha)

def main():
    if len(sys.argv) < 5 or sys.argv[3] != "-m":
        print("Usage: ./your_program.sh commit-tree <tree_sha> -p <commit_sha> -m <message>")
        sys.exit(1)
    
    tree_sha = sys.argv[2]
    parent_sha = sys.argv[4] if sys.argv[1] == "-p" else None
    message_index = sys.argv.index("-m") + 1
    message = sys.argv[message_index]

    commit_tree(tree_sha, parent_sha, message)
if __name__ == "__main__":
    main()
