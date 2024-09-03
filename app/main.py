import sys
import os
import zlib
import hashlib
import requests
from pathlib import Path
import requests

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

    obj_dir = directory / f".git/objects/{sha[:2]}"
    obj_file = obj_dir / sha[2:]

    if not obj_dir.exists():
        obj_dir.mkdir(parents=True)

    with open(obj_file, "wb") as f:
        f.write(zlib.compress(store))

    return sha

def clone_repo(repo_url, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    os.chdir(target_dir)
    os.makedirs(".git/objects", exist_ok=True)
    os.makedirs(".git/refs", exist_ok=True)

    # Set up HEAD to point to main branch
    with open(".git/HEAD", "w") as f:
        f.write("ref: refs/heads/main\n")

    repo_parts = repo_url.rstrip('/').split('/')
    repo_owner = repo_parts[-2]
    repo_name = repo_parts[-1]

    info_refs_url = f"https://github.com/{repo_owner}/{repo_name}.git/info/refs?service=git-upload-pack"
    response = requests.get(info_refs_url)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch info/refs: {response.status_code}")

    refs = parse_refs(response.content)
    for ref_name, ref_sha in refs.items():
        save_ref(ref_name, ref_sha)

    upload_pack_url = f"https://github.com/{repo_owner}/{repo_name}.git/git-upload-pack"
    upload_pack_data = build_upload_pack_request(refs)
    response = requests.post(upload_pack_url, data=upload_pack_data, headers={"Content-Type": "application/x-git-upload-pack-request"})
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch pack data: {response.status_code}")

    process_packfile(response.content)

def parse_refs(data):
    refs = {}
    lines = data.decode().split('\n')
    for line in lines:
        if line.startswith('00'):
            break
        parts = line.split()
        if len(parts) >= 2:
            ref_sha, ref_name = parts[0], parts[1]
            refs[ref_name] = ref_sha
    return refs

def save_ref(ref_name, ref_sha):
    ref_dir = os.path.dirname(f".git/{ref_name}")
    os.makedirs(ref_dir, exist_ok=True)
    with open(f".git/{ref_name}", "w") as f:
        f.write(ref_sha + "\n")

def build_upload_pack_request(refs):
    request = "0067want " + refs["HEAD"] + " multi_ack_detailed\n00000009done\n"
    return request.encode()

def process_packfile(data):
    unpacked = zlib.decompress(data)
    # Further process the unpacked data to store the objects
    # Here you'd parse the packfile format and store blobs, trees, and commits accordingly

def main():
    if len(sys.argv) != 4 or sys.argv[1] != "clone":
        print("Usage: your_program.sh clone <repository_url> <target_directory>")
        return

    repo_url = sys.argv[2]
    target_dir = sys.argv[3]
    clone_repo(repo_url, target_dir)

if __name__ == "__main__":
    main()
