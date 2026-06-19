from src.StorageConfig import StorageConfig
import os

class VideoFileManager:
    def __init__(self, storage_config):
        self._storage_config = storage_config

    def create_directory(self, path):
        try:
            os.mkdir(path)
            print("Directory created:", path)
        except OSError:
            print("Directory already exists:", path)

    def get_next_file_num(self, directory, prefix, suffix):
        highest = self._storage_config.init_file_num()

        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith(suffix):
                number_part = filename[len(prefix):-len(suffix)]
                number = int(number_part)
                if number > highest:
                    highest = number

        return highest + 1

    def build_filename(self, directory, prefix, suffix, count):
        # Build a unique filename using the configured folder, prefix and suffix
        filename = "%s/%s%05d%s" % (
            directory,
            prefix,
            count,
            suffix
        )
        return filename

    def write_u32_le(self, file, value):
        file.write(bytes([
            value & 0xFF,
            value >> 8 & 0xFF,
            value >> 16 & 0xFF,
            value >> 24 & 0xFF
        ]))

    def patch_u32(self, file, offset, value):
        file.seek(offset)
        self.write_u32_le(file, value)

    def patch_mjpeg_timing(self, filename, frames, duration_ms):
        if frames <= 0 or duration_ms <= 0:
            return

        time_scale = 1000

        us_avg = (duration_ms * 1000) // frames
        rate = (1000000 * time_scale) // us_avg
        length = (frames * time_scale) // rate

        micros_offs = 8 * 4
        frames_offs = 12 * 4
        rate_0_offs = 19 * 4
        len_0_offs = 21 * 4
        rate_1_offs = 33 * 4
        len_1_offs = 35 * 4

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