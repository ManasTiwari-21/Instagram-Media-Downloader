import tkinter as tk

from src.gui.main_window import MainWindow


def main():
    root = tk.Tk()

    MainWindow(root)

    root.mainloop()


if __name__ == "__main__":
    main()