import time
import os

# ASCII art of a cat
cat_art = """
 /\_/\  
( o.o ) 
 > ^ <
"""

print(cat_art)

class Cat:
    def meow(self):
        os.system("echo 'Meow~' | lolcat")

    def dancing_meows(self):
        for _ in range(5):
            self.meow()
            time.sleep(0.5)

if __name__ == "__main__":
    cat = Cat()
    cat.dancing_meows()
