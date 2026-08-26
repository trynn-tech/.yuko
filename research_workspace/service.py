import time
import os
import random

class CatUnimatrixEmulator:
    def __init__(self, width=80, height=24):
        self.width = width
        self.height = height
        self.screen = [[' ' for _ in range(width)] for _ in range(height)]

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def update_screen(self):
        self.clear_screen()
        for row in self.screen:
            print(''.join(row))

    def simulate_unimatrix(self, duration=5):
        for _ in range(duration):
            for y in range(self.height):
                for x in range(self.width):
                    self.screen[y][x] = '🐱' if random.choice([True, False]) else ' '
            self.update_screen()
            time.sleep(0.1)

if __name__ == "__main__":
    emulator = CatUnimatrixEmulator()
    emulator.simulate_unimatrix()
