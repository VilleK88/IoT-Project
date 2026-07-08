import os

class FileManager:
    # Initializes the file manager and file numbering counters.
    def __init__(self, storage_config):
        self._storage_config = storage_config
        self._vid_count = 0
        self._img_count = 0
        self._pre_buf_count = 0

    # Creates all required project directories on the SD card.
    def prepare_directories(self):
        # Create directories if they don't already exist
        self.create_directory(self._storage_config.vid_dir())
        self.create_directory(self._storage_config.img_dir())
        self.create_directory(self._storage_config.temp_dir())
        self.create_directory(self._storage_config.pre_buf_dir())

    # Loads the next available file numbers from the existing files
    # on the SD card.
    def load_file_counters(self):
        # Continue numbering from the highest existing file number
        self._vid_count = self.get_next_file_num(
            self._storage_config.vid_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix()
        )

        self._img_count = self.get_next_file_num(
            self._storage_config.img_dir(),
            self._storage_config.img_prefix(),
            self._storage_config.img_suffix()
        )

        self._pre_buf_count = self.get_next_file_num(
            self._storage_config.pre_buf_dir(),
            self._storage_config.vid_prefix(),
            self._storage_config.vid_suffix()
        )

    # Creates a directory if it does not already exist.
    def create_directory(self, path):
        try:
            os.mkdir(path)
            print("Directory created:", path)
        except OSError:
            print("Directory already exists:", path)

    # Returns the next available file number for the specified
    # filename pattern.
    def get_next_file_num(self, directory, prefix, suffix):
        highest = self._storage_config.init_file_num()
        # Search for the highest existing file number.
        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith(suffix):
                number_part = filename[len(prefix):-len(suffix)]
                number = int(number_part)
                if number > highest:
                    highest = number
        # Continue numbering after the highest existing file.
        return highest + 1

    # Builds a unique filename using the configured directory,
    # filename prefix, suffix and file number.
    def build_filename(self, directory, prefix, suffix, count):
        # Build a unique filename using the configured folder, prefix and suffix
        filename = "%s/%s%05d%s" % (
            directory,
            prefix,
            count,
            suffix
        )
        return filename

    # Writes a 32-bit unsigned integer in little-endian format.
    def write_u32_le(self, file, value):
        file.write(bytes([
            value & 0xFF,
            value >> 8 & 0xFF,
            value >> 16 & 0xFF,
            value >> 24 & 0xFF
        ]))

    # Writes a 32-bit value to a specific position in a file.
    def patch_u32(self, file, offset, value):
        file.seek(offset)
        self.write_u32_le(file, value)

    # Updates the MJPEG header so the recorded video plays back
    # with the correct duration and frame rate.
    def patch_mjpeg_timing(self, filename, frames, duration_ms):
        # Skip patching if the recording contains no valid frames.
        if frames > 0 and duration_ms > 0:
            # Timescale used by the AVI timing fields (milliseconds).
            time_scale = 1000
            # Calculate the average time between frames.
            us_avg = (duration_ms * 1000) // frames
            # Calculate the playback rate and playback duration
            # stored in the MJPEG header.
            rate = (1000000 * time_scale) // us_avg
            length = (frames * time_scale) // rate
            # Byte offsets of the timing fields in the OpenMV MJPEG header.
            #
            # Each header field is 4 bytes (32 bits), so the offsets are calculated
            # by multiplying the field index by 4.
            #
            # The MJPEG container stores timing information in both the AVI header
            # and the stream header. Both locations must be updated so media players
            # report the correct duration and frame rate.
            micros_offs = 8 * 4  # Average time between frames in microseconds.
            frames_offs = 12 * 4  # Total number of recorded frames.
            # AVI main header timing fields.
            rate_0_offs = 19 * 4  # Playback rate (timescale units per second).
            len_0_offs = 21 * 4  # Stream duration in playback units.
            # AVI stream header timing fields.
            # These values must match the AVI main header timing fields.
            rate_1_offs = 33 * 4 # Playback rate (timescale units per second).
            len_1_offs = 35 * 4 # Stream duration in playback units.
            # Update all timing fields so media players report the correct
            # recording duration and frame rate.
            with open(filename, "r+b") as file:
                self.patch_u32(file, micros_offs, us_avg)
                self.patch_u32(file, frames_offs, frames)
                self.patch_u32(file, rate_0_offs, rate)
                self.patch_u32(file, len_0_offs, length)
                self.patch_u32(file, rate_1_offs, rate)
                self.patch_u32(file, len_1_offs, length)
            print("Patched MJPEG timing")
            print("Frames:", frames)
            print("Duration ms:", duration_ms)
            print("FPS:", (frames * 1000) // duration_ms)

    # Returns the next available video number.
    def get_video_count(self):
        return self._vid_count

    # Advances the video file counter.
    def increase_video_count(self):
        self._vid_count += 1

    # Returns the next available image number.
    def get_img_count(self):
        return self._img_count

    # Advances the image file counter.
    def increase_img_count(self):
        self._img_count += 1

    # Returns the next available pre-buffer video number.
    def get_pre_buf_count(self):
        return self._pre_buf_count

    # Advances the pre-buffer video counter.
    def increase_pre_buf_count(self):
        self._pre_buf_count += 1

    # Reads a 32-bit unsigned integer in little-endian format.
    def read_u32_le(self, file):
        data = file.read(4)
        # Combine the four bytes into a single 32-bit unsigned integer.
        return data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)

    # Appends a missing AVI idx1 index to an OpenMV MJPEG file.
    def patch_mjpeg_index(self, filename):
        # Byte offset of the RIFF file size field.
        # This value must be updated after the idx1 chunk has been appended.
        riff_size_offset = 4

        # In OpenMV's MJPEG header, the "movi" FOURCC starts at byte 220.
        # The first video frame chunk starts directly after it at byte 224.
        movi_base = 220
        frame_pos = 224

        # Stores the offset and size of every video frame.
        # These values are later written to the AVI idx1 chunk.
        index_entries = []

        with open(filename, "r+b") as file:
            # Determine the total file size so we know when to stop scanning.
            file.seek(0, 2)
            file_size = file.tell()

            # Jump to the first MJPEG frame.
            file.seek(frame_pos)

            # Scan every video frame stored in the AVI "movi" section.
            while file.tell() + 8 <= file_size:
                # Remember where the current frame chunk begins.
                chunk_pos = file.tell()
                # Every MJPEG video frame should begin with the "00dc" FOURCC.
                chunk_id = file.read(4)
                # Stop scanning if another chunk type is encountered.
                if chunk_id != b"00dc":
                    break
                # Read the size of the JPEG frame.
                chunk_size = self.read_u32_le(file)

                # AVI idx1 stores frame offsets relative to the start of
                # the "movi" list instead of the beginning of the file.
                chunk_offset = chunk_pos - movi_base
                index_entries.append((chunk_offset, chunk_size))

                # Skip over the JPEG image data to reach the next frame.
                file.seek(chunk_size, 1)
            # Abort if no video frames were found.
            if len(index_entries) == 0:
                print("No MJPEG frames found for AVI index")
                return

            # Append the AVI idx1 chunk to the end of the file.
            file.seek(0, 2)
            file.write(b"idx1")
            # Each idx1 entry occupies 16 bytes.
            self.write_u32_le(file, len(index_entries) * 16)
            # Write one index entry for every recorded frame.
            for chunk_offset, chunk_size in index_entries:
                file.write(b"00dc")  # Frame chunk identifier.
                self.write_u32_le(file, 0x10)  # AVIIF_KEYFRAME flag.
                self.write_u32_le(file, chunk_offset)  # Offset within the movi list.
                self.write_u32_le(file, chunk_size)  # Size of the JPEG frame.

            # The file has grown after appending the idx1 chunk.
            # Update the RIFF file size so the AVI container remains valid.
            final_size = file.tell()
            self.patch_u32(file, riff_size_offset, final_size - 8)

        print("Patched AVI index")
        print("Indexed frames:", len(index_entries))