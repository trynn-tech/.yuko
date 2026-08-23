import time
import random

class AsciiArt:
    def __init__(self):
        self.ascii_chars = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"

    def print_ascii(self):
        while True:
            for char in self.ascii_chars:
                print(char, end='', flush=True)
                time.sleep(0.05)
            print()

if __name__ == "__main__":
    ascii_art = AsciiArt()
    ascii_art.print_ascii()
