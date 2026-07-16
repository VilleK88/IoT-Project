import gc

class Tools:
    # Prints the current heap memory usage.
    def print_memory_status(self, label):
        self.cleanup_memory()
        print(label)
        print("Free:", gc.mem_free(), ", Allocated:", gc.mem_alloc())

    # Runs the MicroPython garbage collector.
    def cleanup_memory(self):
        gc.collect()