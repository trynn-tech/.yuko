class UnimatrixEmulator:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.screen = [[' ' for _ in range(width)] for _ in range(height)]

    def set_pixel(self, x, y, char):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.screen[y][x] = char

    def display(self):
        for row in self.screen:
            print(''.join(row))

import random
import time

def main():
    width, height = 80, 24
    emulator = UnimatrixEmulator(width, height)

    while True:
        for y in range(height):
            for x in range(width):
                emulator.set_pixel(x, y, random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+{}|:"<>?'))
        emulator.display()
        time.sleep(0.1)

if __name__ == "__main__":
    main()
