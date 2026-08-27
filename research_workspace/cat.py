import random

def generate_cat():
    cats = [
        " /\_/\  ",
        "( o.o ) ",
        " > ^ <
    ]
    return random.choice(cats)

def create_unimatrix(num_cats):
    unimatrix = []
    for _ in range(num_cats):
        unimatrix.append(generate_cat())
    return unimatrix

def main():
    num_cats = 10  # You can change this number to generate more or fewer cats
    unimatrix = create_unimatrix(num_cats)
    for cat in unimatrix:
        print(cat)

if __name__ == "__main__":
    main()