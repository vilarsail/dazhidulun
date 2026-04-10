import os
def check_trans():
    total_missing = 0
    for i in range(1, 41):
        with open(f"split/{i}.md", "r") as f:
            c = f.read()
            missing = c.count("此段需要翻译")
            total_missing += missing

    print(f"Total placeholders inserted: {total_missing}")

check_trans()
