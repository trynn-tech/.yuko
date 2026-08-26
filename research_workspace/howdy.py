class Unimatrix:
    def __init__(self):
        self.screen_height = 24
        self.screen_width = 80

    def display_matrix(self):
        for i in range(self.screen_height):
            for j in range(self.screen_width):
                if (i + j) % 2 == 0:
                    print("m", end="")
                else:
                    print(" ", end="")
            print()

unimatrix = Unimatrix()
unimatrix.display_matrix()
