# Raspberry Pi Class Image

Store the class Raspberry Pi image and metadata in this directory.

Current image baseline:

- Includes `xacro` and the ROMI ROS 2 runtime dependencies used by this repo.
- Default SSH username: `student`
- Default SSH password: `romi32u4`

Recommended contents:

- `ClassPiImage-ubuntu22.04.img.xz` (or your official class image filename)
- `ClassPiImage-ubuntu22.04.sha256`
- `RELEASE_NOTES.md` (what changed between image versions)

Suggested release workflow:

1. Compress the image (`.img.xz`) before sharing.
2. Publish a SHA256 checksum for integrity verification.
3. Include a short changelog for students and TAs.

Flashing summary (Raspberry Pi Imager):

1. Device: Raspberry Pi 4.
2. OS: Use Custom (select the class image).
3. Storage: target microSD card.
4. Flash and eject safely.
