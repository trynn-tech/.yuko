import time
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_unimatrix():
    cat_art = [
        " /\_/\  ",
        "( o.o ) ",
        " > ^ <
    ]
    for _ in range(10):
        clear_screen()
        for line in cat_art:
            print(line.center(20))
        time.sleep(0.5)

if __name__ == "__main__":
    print_unimatrix()