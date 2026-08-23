import time
import random

class AsciiArt:
    def __init__(self):
        self.ascii_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=[]{}|;:,.<>?/`~"

    def print_ascii_art(self):
        while True:
            for char in self.ascii_chars:
                print(char, end='', flush=True)
                time.sleep(0.1)
            print()

if __name__ == "__main__":
    art = AsciiArt()
    art.print_ascii_art()
