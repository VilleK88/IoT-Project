from src.StorageConfig import StorageConfig
from src.TimeManager import TimeManager
import os

class LogManager:
    def __init__(self, file_manager):
        self._storage_config = StorageConfig()
        self._file_manager = file_manager
        self._time_manager = TimeManager()

        self._log_count = 0
        self._current_log = None

        self._log_file_prefix = "log_"
        self._log_file_suffix = ".txt"

    def initialize(self):
        self._log_count = self._find_next_log_number()
        self._open_new_log()

    def _find_next_log_number(self):
        highest = -1
        for filename in os.listdir(self._storage_config.logs_dir()):
            if filename.startswith(self._log_file_prefix) and filename.endswith(self._log_file_suffix):
                try:
                    number = int(filename[len(self._log_file_prefix):-len(self._log_file_suffix)])
                    if number > highest:
                        highest = number
                except ValueError as err:
                    print("Error:", err)
                    pass
        return highest + 1

    def _open_new_log(self):
        self._current_log = (
                self._storage_config.logs_dir()
                + "/"
                + self._log_file_prefix
                + "%05d" % self._log_count
                + self._log_file_suffix
        )
        self._log_count += 1

    def _write_log(self, lvl, msg):
        try:
            entry = "{} [{}] {}\n".format(self._time_manager.timestamp(), lvl, msg)
            self._ensure_log_space(len(entry))
            with open(self._current_log, "a") as file:
                file.write(entry)
            if os.stat(self._current_log)[6] >= self._storage_config.max_log_file_size():
                self._open_new_log()
        except Exception as err:
            print("Log write error:", err)
            raise

    def _ensure_log_space(self, incoming_bytes):
        quota = self._file_manager.log_quota_bytes()
        while True:
            used = self._file_manager.directory_size(self._storage_config.logs_dir())
            if used + incoming_bytes <= quota:
                return
            if not self._delete_oldest_log():
                return

    def _delete_oldest_log(self):
        oldest_file = None
        oldest_mtime = None
        for filename in os.listdir(self._storage_config.logs_dir()):
            path = self._storage_config.logs_dir() + "/" + filename
            # Never delete the log that is currently being written.
            if path != self._current_log:
                try:
                    stats = os.stat(path)
                    mtime = stats[8]
                    if oldest_mtime is None or mtime < oldest_mtime:
                        oldest_mtime = mtime
                        oldest_file = path
                except OSError:
                    pass
        if oldest_file:
            os.remove(oldest_file)
            print("Deleted oldest log:", oldest_file)
            return True
        return False

    def info(self, msg):
        self._write_log("INFO", msg)

    def warning(self, msg):
        self._write_log("WARNING", msg)

    def error(self, msg):
        self._write_log("ERROR", msg)