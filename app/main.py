import sys
import os
import zlib


def main():
    # You can use print statements as follows for debugging, they'll be visible when running tests.
    #print("Logs from your program will appear here!")

    # Uncomment this block to pass the first stage
    #
    command = sys.argv[1]
    if command == "init":
         os.mkdir(".git")
         os.mkdir(".git/objects")
         os.mkdir(".git/refs")
         with open(".git/HEAD", "w") as f:
             f.write("ref: refs/heads/main\n")
         print("Initialized git directory")
    elif command =="cat-file":
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

    else:
         raise RuntimeError(f"Unknown command #{command}")

if __name__ == "__main__":
    main()
