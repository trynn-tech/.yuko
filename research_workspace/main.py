class TerminalEmulator:
    def __init__(self):
        self.screen = [[' ' for _ in range(80)] for _ in range(24)]

    def display(self):
        for row in self.screen:
            print(''.join(row))

    def write(self, text, x, y):
        for i, char in enumerate(text):
            self.screen[y][x + i] = char

    def emulate_unimatrix(self):
        for y in range(24):
            for x in range(80):
                self.screen[y][x] = 'm' if (x + y) % 2 == 0 else 'o'

# Create a terminal emulator and display it
my_terminal = TerminalEmulator()
my_terminal.emulate_unimatrix()
my_terminal.display()
