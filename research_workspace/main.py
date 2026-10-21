import time
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_plant():
    plant = [
        r"   /\   ",
        r"  /  \  ",
        r" /    \ ",
        r" \    / ",
        r"  \  /  ",
        r"   \/   "
    ]
    for _ in range(10):
        clear_screen()
        for line in plant:
            print(line.center(20))
        time.sleep(0.5)

if __name__ == "__main__":
    print_plant()
