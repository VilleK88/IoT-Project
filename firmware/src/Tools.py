import gc

class Tools:
    # Prints the current heap memory usage.
    def print_memory_status(self, label):
        print(
            "[MEM]", label, "free:", gc.mem_free(),
            "alloc:", gc.mem_alloc(), "threshold:", gc.threshold()
        )

    # Runs the MicroPython garbage collector.
    def cleanup_memory(self):
        gc.collect()