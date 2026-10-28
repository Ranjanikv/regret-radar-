import os
import subprocess
import sys


def build_and_upload_slc(bucketfs_path: str = "/buckets/bfsdefault/default/slc/"):
    """Build the Script Language Container (SLC) Docker image and upload it to BucketFS."""
    image_tag = "regret_radar_nlp_slc:latest"
    print("Building SLC Docker image...")
    subprocess.check_call(["docker", "build", "-t", image_tag, "."], cwd=os.path.abspath("slc"))

    tar_path = os.path.abspath("slc/regret_radar_nlp_slc.tar")
    print(f"Exporting image to {tar_path}...")
    subprocess.check_call(["docker", "save", "-o", tar_path, image_tag])

    print(f"Uploading tar to BucketFS path {bucketfs_path}...")
    subprocess.check_call(["exasol", "bucketfs", "upload", tar_path, bucketfs_path])
    print("Upload complete.")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    build_and_upload_slc(path or "/buckets/bfsdefault/default/slc/")
